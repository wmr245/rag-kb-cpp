import hashlib
import math
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, List, Optional

from app.core.logging_config import logger
from app.db.postgres import get_conn


def _detect_source_type(source_path: str) -> str:
    ext = Path(source_path or "").suffix.lower().lstrip(".")
    return ext or "plain"


def _compact_text(text: str, limit: Optional[int] = None) -> str:
    compact = " ".join((text or "").replace("\r", "\n").split())
    if limit is not None and len(compact) > limit:
        return compact[: max(0, limit - 3)].rstrip() + "..."
    return compact


def _strip_chunk_heading(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return ""

    first = lines[0]
    if re.match(r"^\[heading\]\s+", first, flags=re.IGNORECASE):
        lines = lines[1:]
    elif re.match(r"^#{1,6}\s+", first):
        lines = lines[1:]

    return _compact_text("\n".join(lines))


def _unique_preserve(items: Iterable[str]) -> List[str]:
    results: List[str] = []
    seen = set()
    for raw in items:
        item = (raw or "").strip()
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        results.append(item)
    return results


def _heading_candidates(chunks: List[Any], limit: int = 10) -> List[str]:
    values: List[str] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue

        heading = (chunk.get("heading") or "").strip()
        if heading and len(heading) <= 80:
            values.append(heading)

        section_path = (chunk.get("section_path") or "").strip()
        if section_path:
            for part in [part.strip() for part in section_path.split(">")]:
                if part and len(part) <= 80:
                    values.append(part)

        if len(values) >= limit * 3:
            break

    return _unique_preserve(values)[:limit]


def _derive_doc_summary(title: str, chunks: List[Any], max_len: int = 320) -> str:
    parts: List[str] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        body = _strip_chunk_heading(chunk.get("text") or "")
        if not body:
            continue
        parts.append(body)
        if len(" ".join(parts)) >= max_len:
            break

    summary = _compact_text(" ".join(parts), limit=max_len)
    if not summary:
        summary = _compact_text(title, limit=max_len)
    return summary


_ASCII_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "then",
    "than",
    "your",
    "about",
    "what",
    "when",
    "where",
    "which",
    "used",
    "using",
}


def _ascii_terms(text: str) -> List[str]:
    return [term.lower() for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", text or "")]


def _derive_doc_keywords(title: str, chunks: List[Any], summary: str, limit: int = 12) -> str:
    keywords: List[str] = []
    keywords.extend(_heading_candidates(chunks, limit=8))

    title_terms = [term for term in _ascii_terms(title) if term not in _ASCII_STOPWORDS]
    summary_terms = [term for term in _ascii_terms(summary) if term not in _ASCII_STOPWORDS]
    counts = Counter(title_terms + summary_terms)
    for term, _ in counts.most_common(limit):
        keywords.append(term)

    return ", ".join(_unique_preserve(keywords)[:limit])


def _build_route_text(title: str, summary: str, keywords: str, source_type: str, chunks: List[Any]) -> str:
    headings = _heading_candidates(chunks, limit=10)
    parts = [title, source_type, summary, keywords, " ; ".join(headings)]
    return _compact_text("\n".join(part for part in parts if part), limit=1200)


def build_chunk_context_text(title: str, chunk: Any) -> str:
    if isinstance(chunk, dict):
        text = (chunk.get("text") or "").strip()
        heading = (chunk.get("heading") or "").strip()
        section_path = (chunk.get("section_path") or "").strip()
        chunk_type = (chunk.get("chunk_type") or "").strip()
        source_type = (chunk.get("source_type") or "").strip()
    else:
        text = str(chunk or "").strip()
        heading = ""
        section_path = ""
        chunk_type = ""
        source_type = ""

    body = _strip_chunk_heading(text) or _compact_text(text)
    parts = [
        f"Document: {title}" if title else "",
        f"Source type: {source_type}" if source_type else "",
        f"Section path: {section_path}" if section_path else "",
        f"Heading: {heading}" if heading else "",
        f"Chunk type: {chunk_type}" if chunk_type else "",
        f"Content: {body}" if body else "",
    ]
    return _compact_text("\n".join(part for part in parts if part), limit=1800)


def contextualize_chunks(title: str, chunks: List[Any]) -> List[Any]:
    results: List[Any] = []
    for chunk in chunks:
        if isinstance(chunk, dict):
            row = dict(chunk)
        else:
            row = {"text": str(chunk or "")}
        row["context_text"] = build_chunk_context_text(title=title, chunk=row)
        results.append(row)
    return results


def _average_embedding(embeddings: List[List[float]]) -> Optional[List[float]]:
    usable = [embedding for embedding in embeddings if embedding]
    if not usable:
        return None

    dim = len(usable[0])
    totals = [0.0] * dim
    used_count = 0
    for embedding in usable:
        if len(embedding) != dim:
            continue
        for index, value in enumerate(embedding):
            totals[index] += float(value)
        used_count += 1

    if used_count == 0:
        return None

    averaged = [value / used_count for value in totals]
    norm = math.sqrt(sum(value * value for value in averaged))
    if norm > 0:
        averaged = [value / norm for value in averaged]
    return averaged


def _parse_vector_literal(raw: str) -> Optional[List[float]]:
    value = (raw or "").strip().strip("[]")
    if not value:
        return None
    try:
        return [float(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError:
        logger.warning("_parse_vector_literal failed raw_prefix=%s", value[:80])
        return None


def _compute_file_hash(source_path: str) -> str:
    hasher = hashlib.sha256()
    with Path(source_path).open('rb') as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _find_reusable_doc(owner: str, content_hash: str) -> Optional[int]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM docs
                WHERE owner = %s
                  AND content_hash = %s
                  AND status = 'ready'
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (owner, content_hash),
            )
            row = cur.fetchone()
    return int(row[0]) if row else None


def _create_success_task_for_reused_doc(doc_id: int) -> str:
    task_id = str(uuid.uuid4())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (id, doc_id, status, progress, error)
                VALUES (%s, %s, 'success', 100, '')
                """,
                (task_id, doc_id),
            )
        conn.commit()
    return task_id


def _update_doc_catalog_row(
    doc_id: int,
    source_type: str,
    summary: str,
    keywords: str,
    route_text: str,
    route_embedding: Optional[List[float]],
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if route_embedding:
                cur.execute(
                    """
                    UPDATE docs
                    SET source_type = %s,
                        doc_summary = %s,
                        doc_keywords = %s,
                        route_text = %s,
                        route_embedding = %s::vector,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (source_type, summary, keywords, route_text, route_embedding, doc_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE docs
                    SET source_type = %s,
                        doc_summary = %s,
                        doc_keywords = %s,
                        route_text = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (source_type, summary, keywords, route_text, doc_id),
                )
        conn.commit()


def update_doc_catalog(
    doc_id: int,
    title: str,
    source_path: str,
    chunks: List[Any],
    embeddings: Optional[List[List[float]]] = None,
) -> None:
    source_type = ""
    for chunk in chunks:
        if isinstance(chunk, dict) and (chunk.get("source_type") or "").strip():
            source_type = (chunk.get("source_type") or "").strip()
            break
    if not source_type:
        source_type = _detect_source_type(source_path)

    summary = _derive_doc_summary(title=title, chunks=chunks)
    keywords = _derive_doc_keywords(title=title, chunks=chunks, summary=summary)
    route_text = _build_route_text(title=title, summary=summary, keywords=keywords, source_type=source_type, chunks=chunks)
    route_embedding = _average_embedding(embeddings or [])

    _update_doc_catalog_row(
        doc_id=doc_id,
        source_type=source_type,
        summary=summary,
        keywords=keywords,
        route_text=route_text,
        route_embedding=route_embedding,
    )

    logger.info(
        "update_doc_catalog doc_id=%s source_type=%s summary_len=%s keyword_count=%s has_route_embedding=%s",
        doc_id,
        source_type,
        len(summary),
        len([item for item in keywords.split(",") if item.strip()]),
        bool(route_embedding),
    )


def backfill_missing_doc_catalog(batch_size: int = 50, max_docs: int = 500) -> int:
    processed = 0

    while processed < max_docs:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title, source_path
                    FROM docs
                    WHERE status = 'ready'
                      AND (
                        source_type IS NULL
                        OR doc_summary IS NULL OR doc_summary = ''
                        OR doc_keywords IS NULL OR doc_keywords = ''
                        OR route_text IS NULL OR route_text = ''
                        OR route_embedding IS NULL
                      )
                    ORDER BY id ASC
                    LIMIT %s
                    """,
                    (min(batch_size, max_docs - processed),),
                )
                docs = cur.fetchall()

        if not docs:
            break

        for doc_id, title, source_path in docs:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT text, page, heading, section_path, chunk_type, source_type, context_text, embedding::text
                        FROM chunks
                        WHERE doc_id = %s
                        ORDER BY chunk_index ASC
                        """,
                        (doc_id,),
                    )
                    rows = cur.fetchall()

            chunks: List[Any] = []
            embeddings: List[List[float]] = []
            for text, page, heading, section_path, chunk_type, chunk_source_type, context_text, embedding_text in rows:
                chunks.append(
                    {
                        "text": text or "",
                        "page": page,
                        "heading": heading or "",
                        "section_path": section_path or "",
                        "chunk_type": chunk_type or "",
                        "source_type": chunk_source_type or "",
                        "context_text": context_text or "",
                    }
                )
                parsed_embedding = _parse_vector_literal(embedding_text)
                if parsed_embedding:
                    embeddings.append(parsed_embedding)

            if not chunks:
                continue

            update_doc_catalog(
                doc_id=int(doc_id),
                title=str(title or ""),
                source_path=str(source_path or ""),
                chunks=chunks,
                embeddings=embeddings,
            )
            processed += 1

    logger.info("backfill_missing_doc_catalog processed=%s", processed)
    return processed


def create_doc_and_task(title: str, source_path: str, owner: str) -> tuple[int, str, str]:
    task_id = str(uuid.uuid4())
    source_type = _detect_source_type(source_path)
    content_hash = _compute_file_hash(source_path)

    reusable_doc_id = _find_reusable_doc(owner=owner, content_hash=content_hash)
    if reusable_doc_id is not None:
        reused_task_id = _create_success_task_for_reused_doc(reusable_doc_id)
        logger.info(
            "create_doc_and_task duplicate_reused owner=%s doc_id=%s content_hash=%s",
            owner,
            reusable_doc_id,
            content_hash[:12],
        )
        return reusable_doc_id, reused_task_id, "duplicate"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO docs (title, source_path, owner, source_type, content_hash, status)
                VALUES (%s, %s, %s, %s, %s, 'uploaded')
                RETURNING id
                """,
                (title, source_path, owner, source_type, content_hash),
            )
            doc_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO tasks (id, doc_id, status, progress, error)
                VALUES (%s, %s, 'queued', 0, '')
                """,
                (task_id, doc_id),
            )
        conn.commit()

    return doc_id, task_id, "queued"


def load_task(task_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, doc_id, status, progress, error
                FROM tasks
                WHERE id = %s
                """,
                (task_id,),
            )
            return cur.fetchone()


def update_task_status(task_id: str, status: str, progress: int, error: str = ""):
    logger.info(
        "update_task_status task_id=%s status=%s progress=%s error=%s",
        task_id,
        status,
        progress,
        error,
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET status = %s,
                    progress = %s,
                    error = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, progress, error, task_id),
            )
        conn.commit()


def update_doc_status(doc_id: int, status: str):
    logger.info("update_doc_status doc_id=%s status=%s", doc_id, status)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE docs
                SET status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, doc_id),
            )
        conn.commit()


def backfill_missing_chunk_context(batch_size: int = 500, max_chunks: int = 5000) -> int:
    processed = 0

    while processed < max_chunks:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, d.title, c.text, c.heading, c.section_path, c.chunk_type, c.source_type
                    FROM chunks c
                    JOIN docs d ON d.id = c.doc_id
                    WHERE d.status = 'ready'
                      AND (c.context_text IS NULL OR c.context_text = '')
                    ORDER BY c.id ASC
                    LIMIT %s
                    """,
                    (min(batch_size, max_chunks - processed),),
                )
                rows = cur.fetchall()

        if not rows:
            break

        with get_conn() as conn:
            with conn.cursor() as cur:
                for chunk_id, title, text_value, heading, section_path, chunk_type, source_type in rows:
                    context_text = build_chunk_context_text(
                        title=str(title or ""),
                        chunk={
                            "text": text_value or "",
                            "heading": heading or "",
                            "section_path": section_path or "",
                            "chunk_type": chunk_type or "",
                            "source_type": source_type or "",
                        },
                    )
                    cur.execute(
                        """
                        UPDATE chunks
                        SET context_text = %s
                        WHERE id = %s
                        """,
                        (context_text, chunk_id),
                    )
                    processed += 1
            conn.commit()

    logger.info("backfill_missing_chunk_context processed=%s", processed)
    return processed


def insert_chunks(doc_id: int, chunks: List[Any], embeddings: List[List[float]]):
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings length mismatch")

    logger.info(
        "insert_chunks start doc_id=%s chunk_count=%s",
        doc_id,
        len(chunks),
    )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))

            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                if isinstance(chunk, dict):
                    text = (chunk.get("text") or "").strip()
                    page = chunk.get("page") or 1
                    heading = (chunk.get("heading") or "").strip() or None
                    section_path = (chunk.get("section_path") or "").strip() or None
                    chunk_type = (chunk.get("chunk_type") or "").strip() or None
                    source_type = (chunk.get("source_type") or "").strip() or None
                    context_text = (chunk.get("context_text") or "").strip() or None
                else:
                    text = str(chunk).strip()
                    page = 1
                    heading = None
                    section_path = None
                    chunk_type = None
                    source_type = None
                    context_text = None

                if not text:
                    continue

                cur.execute(
                    """
                    INSERT INTO chunks (
                        doc_id,
                        chunk_index,
                        text,
                        page,
                        heading,
                        section_path,
                        chunk_type,
                        source_type,
                        context_text,
                        embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                    """,
                    (
                        doc_id,
                        idx,
                        text,
                        page,
                        heading,
                        section_path,
                        chunk_type,
                        source_type,
                        context_text,
                        embedding,
                    ),
                )
        conn.commit()

    logger.info("insert_chunks done doc_id=%s chunk_count=%s", doc_id, len(chunks))
