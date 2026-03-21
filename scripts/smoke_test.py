#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def build_multipart_body(file_path: Path, title: str, owner: str, boundary: str) -> bytes:
    filename = file_path.name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()

    parts = []

    def add_text_field(name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8")
        )
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")

    add_text_field("title", title)
    add_text_field("owner", owner)

    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(
        (
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts)


def http_json(method: str, url: str, data: bytes | None = None, headers: dict | None = None):
    request = urllib.request.Request(url=url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {payload}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc


def wait_for_task(base_url: str, task_id: str, timeout_sec: int, interval_sec: float) -> dict:
    deadline = time.time() + timeout_sec
    task_url = f"{base_url}/tasks/{task_id}"

    while time.time() < deadline:
        _, payload, _ = http_json("GET", task_url)
        status = payload.get("status")
        progress = payload.get("progress")
        print(f"[task] status={status} progress={progress}")

        if status == "success":
            return payload
        if status == "failed":
            raise RuntimeError(f"ingest failed: {payload.get('error')}")

        time.sleep(interval_sec)

    raise TimeoutError(f"task {task_id} did not finish within {timeout_sec}s")


def ensure_test_file(path: str | None) -> tuple[Path, bool]:
    if path:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"file not found: {file_path}")
        return file_path, False

    temp_dir = Path(tempfile.gettempdir())
    file_path = temp_dir / f"rag_kb_smoke_{uuid.uuid4().hex}.md"
    file_path.write_text(
        """# RAG Smoke Test

这是用于验证知识库链路的一份临时文档。

## 系统目标

系统目标是完成文档上传、异步入库、向量检索和带引用的回答生成。

## 演示重点

演示重点包括 trace id、任务状态、检索命中和引用返回。
""",
        encoding="utf-8",
    )
    return file_path, True


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG gateway smoke test")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--file", help="path to a local .md/.txt/.pdf/.docx file")
    parser.add_argument("--title", default="Smoke Test Document")
    parser.add_argument("--owner", default="smoke-test")
    parser.add_argument("--question", default="这份文档的系统目标是什么？")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    file_path, remove_after = ensure_test_file(args.file)

    try:
        boundary = f"----ragkb{uuid.uuid4().hex}"
        upload_body = build_multipart_body(file_path, args.title, args.owner, boundary)
        upload_headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }

        print(f"[upload] file={file_path}")
        _, upload_payload, _ = http_json(
            "POST",
            f"{base_url}/docs/upload",
            data=upload_body,
            headers=upload_headers,
        )
        print(json.dumps(upload_payload, ensure_ascii=False, indent=2))

        task_id = upload_payload["taskId"]
        wait_for_task(
            base_url=base_url,
            task_id=task_id,
            timeout_sec=args.timeout,
            interval_sec=args.poll_interval,
        )

        query_body = json.dumps(
            {
                "question": args.question,
                "topK": args.top_k,
                "docScope": [],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        query_headers = {"Content-Type": "application/json"}

        _, query_payload, query_response_headers = http_json(
            "POST",
            f"{base_url}/rag/query",
            data=query_body,
            headers=query_headers,
        )

        print("[query] answer:")
        print(query_payload.get("answer", ""))
        print(f"[query] latencyMs={query_payload.get('latencyMs')}")
        print(f"[query] x-cache={query_response_headers.get('x-cache', '')}")
        print(f"[query] x-trace-id={query_response_headers.get('x-trace-id', '')}")

        citations = query_payload.get("citations") or []
        if citations:
            print("[query] citations:")
            for citation in citations:
                print(json.dumps(citation, ensure_ascii=False))

        items = query_payload.get("items") or []
        if items:
            print("[query] top items:")
            for item in items[: min(3, len(items))]:
                summary = {
                    "docId": item.get("docId"),
                    "chunkId": item.get("chunkId"),
                    "chunkIndex": item.get("chunkIndex"),
                    "score": item.get("score"),
                    "heading": item.get("heading"),
                    "sectionPath": item.get("sectionPath"),
                    "chunkType": item.get("chunkType"),
                    "sourceType": item.get("sourceType"),
                }
                print(json.dumps(summary, ensure_ascii=False))

        print("[done] smoke test completed")
        return 0
    finally:
        if remove_after:
            try:
                os.remove(file_path)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
