import uuid
from typing import List

from app.core.logging_config import logger
from app.db.postgres import get_conn


def create_doc_and_task(title: str, source_path: str, owner: str) -> tuple[int, str]:
    task_id = str(uuid.uuid4())

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO docs (title, source_path, owner, status)
                VALUES (%s, %s, %s, 'uploaded')
                RETURNING id
                """,
                (title, source_path, owner),
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

    return doc_id, task_id


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
                SET status = %s
                WHERE id = %s
                """,
                (status, doc_id),
            )
        conn.commit()


def insert_chunks(doc_id: int, chunks: List[str], embeddings: List[List[float]]):
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
                cur.execute(
                    """
                    INSERT INTO chunks (doc_id, chunk_index, text, page, embedding)
                    VALUES (%s, %s, %s, %s, %s::vector)
                    """,
                    (doc_id, idx, chunk, 1, embedding),
                )
        conn.commit()

    logger.info("insert_chunks done doc_id=%s chunk_count=%s", doc_id, len(chunks))
