import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from app.core.logging_config import logger
from app.db.postgres import get_conn
from app.services.cache_service import bump_kb_version_sync
from app.services.document_service import insert_chunks
from app.services.embedding_service import embed_texts
from app.services.file_service import read_chunks_with_meta


@dataclass
class DocRow:
    doc_id: int
    title: str
    source_path: str
    status: str
    chunk_count: int
    metadata_chunk_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill chunk metadata for existing docs")
    parser.add_argument("--doc-ids", nargs="*", type=int, default=[], help="specific doc ids to reingest")
    parser.add_argument("--limit", type=int, default=0, help="max number of docs to process")
    parser.add_argument(
        "--all-ready",
        action="store_true",
        help="process all ready docs, not only those with missing metadata",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="only print target docs without reingesting",
    )
    return parser.parse_args()


def load_target_docs(doc_ids: Sequence[int], all_ready: bool) -> List[DocRow]:
    sql = """
        SELECT
            d.id,
            d.title,
            d.source_path,
            d.status,
            COUNT(c.id) AS chunk_count,
            COUNT(c.id) FILTER (
                WHERE c.heading IS NOT NULL
                   OR c.section_path IS NOT NULL
                   OR c.chunk_type IS NOT NULL
                   OR c.source_type IS NOT NULL
            ) AS metadata_chunk_count
        FROM docs d
        LEFT JOIN chunks c ON c.doc_id = d.id
        WHERE d.status = 'ready'
        GROUP BY d.id, d.title, d.source_path, d.status
        ORDER BY d.id
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    docs = [
        DocRow(
            doc_id=int(row[0]),
            title=row[1],
            source_path=row[2],
            status=row[3],
            chunk_count=int(row[4] or 0),
            metadata_chunk_count=int(row[5] or 0),
        )
        for row in rows
    ]

    if doc_ids:
        wanted = set(doc_ids)
        docs = [doc for doc in docs if doc.doc_id in wanted]
    elif not all_ready:
        docs = [doc for doc in docs if doc.chunk_count > 0 and doc.metadata_chunk_count < doc.chunk_count]
    else:
        docs = [doc for doc in docs if doc.chunk_count > 0]

    return docs


def iter_target_docs(docs: Sequence[DocRow], limit: int) -> Iterable[DocRow]:
    if limit and limit > 0:
        yield from docs[:limit]
        return
    yield from docs


def reingest_doc(doc: DocRow) -> tuple[int, int]:
    source_path = Path(doc.source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"source file not found: {doc.source_path}")

    chunks = read_chunks_with_meta(str(source_path), chunk_size=700, overlap=100)
    if not chunks:
        raise ValueError(f"no chunks parsed for doc_id={doc.doc_id}")

    texts = [item["text"] for item in chunks]
    embeddings = embed_texts(texts)
    insert_chunks(doc.doc_id, chunks, embeddings)
    metadata_count = len(
        [
            c
            for c in chunks
            if c.get("heading") or c.get("section_path") or c.get("chunk_type") or c.get("source_type")
        ]
    )
    return len(chunks), metadata_count


def main() -> int:
    args = parse_args()
    docs = load_target_docs(args.doc_ids, args.all_ready)

    if not docs:
        print("[backfill] no target docs")
        return 0

    selected = list(iter_target_docs(docs, args.limit))
    print(f"[backfill] target_docs={len(selected)}")
    for doc in selected:
        print(
            f"[backfill] target doc_id={doc.doc_id} title={doc.title!r} chunk_count={doc.chunk_count} metadata_chunk_count={doc.metadata_chunk_count}"
        )

    if args.dry_run:
        return 0

    success_count = 0
    failure_count = 0

    for doc in selected:
        try:
            chunk_count, metadata_count = reingest_doc(doc)
            success_count += 1
            print(
                f"[backfill] success doc_id={doc.doc_id} chunk_count={chunk_count} metadata_chunk_count={metadata_count}"
            )
        except Exception as exc:
            failure_count += 1
            logger.exception("backfill failed doc_id=%s error=%s", doc.doc_id, str(exc))
            print(f"[backfill] failed doc_id={doc.doc_id} error={exc}")

    if success_count > 0:
        bump_kb_version_sync(trace_id="backfill-chunk-metadata", task_id="backfill-chunk-metadata")

    print(f"[backfill] done success={success_count} failure={failure_count}")
    return 1 if failure_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
