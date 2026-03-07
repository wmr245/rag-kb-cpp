from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from pathlib import Path
from typing import List
import psycopg
import httpx
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("rag-ai")

app = FastAPI()

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "ragkb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/workspace/uploads")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv(
    "EMBEDDING_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1"
).rstrip("/")

PG_DSN = (
    f"host={POSTGRES_HOST} "
    f"port={POSTGRES_PORT} "
    f"dbname={POSTGRES_DB} "
    f"user={POSTGRES_USER} "
    f"password={POSTGRES_PASSWORD}"
)



class IngestRequest(BaseModel):
    taskId: str
    docId: int
    sourcePath: str
    title: str


def get_conn():
    return psycopg.connect(PG_DSN)


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


def read_text_file(source_path: str) -> str:
    path = Path(source_path)
    logger.info("read_text_file source_path=%s", source_path)

    if not path.exists():
        raise FileNotFoundError(f"file not found: {source_path}")

    ext = path.suffix.lower()
    if ext not in [".txt", ".md"]:
        raise ValueError(f"unsupported file type: {ext}")

    text = path.read_text(encoding="utf-8")
    logger.info("read_text_file done source_path=%s text_len=%s", source_path, len(text))
    return text



def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    step = chunk_size - overlap
    if step <= 0:
        raise ValueError("chunk_size must be greater than overlap")

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    logger.info(
        "chunk_text done text_len=%s chunk_size=%s overlap=%s chunk_count=%s",
        len(text),
        chunk_size,
        overlap,
        len(chunks),
    )
    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not EMBEDDING_API_KEY:
        raise ValueError("EMBEDDING_API_KEY is not configured")

    if not texts:
        return []

    url = f"{EMBEDDING_BASE_URL}/embeddings"
    headers = {
        "Authorization": f"Bearer {EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": EMBEDDING_MODEL,
        "input": texts,
    }

    logger.info(
        "embed_texts start url=%s model=%s text_count=%s expected_dim=%s",
        url,
        EMBEDDING_MODEL,
        len(texts),
        EMBEDDING_DIM,
    )

    start_time = time.time()

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=payload)

    elapsed_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "embed_texts response status_code=%s elapsed_ms=%s",
        resp.status_code,
        elapsed_ms,
    )

    if resp.status_code != 200:
        logger.error("embed_texts failed body=%s", resp.text)
        raise ValueError(f"embedding request failed: {resp.status_code} {resp.text}")

    body = resp.json()
    data = body.get("data", [])
    if len(data) != len(texts):
        logger.error(
            "embedding count mismatch expected=%s actual=%s body=%s",
            len(texts),
            len(data),
            body,
        )
        raise ValueError(
            f"embedding count mismatch: expected {len(texts)}, got {len(data)}"
        )

    vectors: List[List[float]] = []
    for idx, item in enumerate(data):
        embedding = item.get("embedding")
        if not isinstance(embedding, list):
            logger.error("invalid embedding payload index=%s item=%s", idx, item)
            raise ValueError("invalid embedding payload")
        if len(embedding) != EMBEDDING_DIM:
            logger.error(
                "embedding dimension mismatch index=%s expected=%s actual=%s",
                idx,
                EMBEDDING_DIM,
                len(embedding),
            )
            raise ValueError(
                f"embedding dimension mismatch: expected {EMBEDDING_DIM}, got {len(embedding)}"
            )
        vectors.append(embedding)

    logger.info(
        "embed_texts success vector_count=%s dim=%s",
        len(vectors),
        len(vectors[0]) if vectors else 0,
    )

    return vectors


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




@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/internal/ingest")
def internal_ingest(req: IngestRequest):
    logger.info(
        "internal_ingest start task_id=%s doc_id=%s source_path=%s title=%s",
        req.taskId,
        req.docId,
        req.sourcePath,
        req.title,
    )

    try:
        update_task_status(req.taskId, "running", 10, "")
        update_doc_status(req.docId, "processing")

        text = read_text_file(req.sourcePath)
        chunks = chunk_text(text, chunk_size=700, overlap=100)

        if not chunks:
            raise ValueError("document is empty after parsing")

        update_task_status(req.taskId, "running", 40, "")
        embeddings = embed_texts(chunks)

        update_task_status(req.taskId, "running", 80, "")
        insert_chunks(req.docId, chunks, embeddings)

        update_task_status(req.taskId, "success", 100, "")
        update_doc_status(req.docId, "ready")

        logger.info(
            "internal_ingest success task_id=%s doc_id=%s chunk_count=%s embedding_dim=%s",
            req.taskId,
            req.docId,
            len(chunks),
            EMBEDDING_DIM,
        )

        return {
            "taskId": req.taskId,
            "docId": req.docId,
            "status": "success",
            "chunkCount": len(chunks),
            "embeddingDim": EMBEDDING_DIM,
        }

    except Exception as e:
        logger.exception(
            "internal_ingest failed task_id=%s doc_id=%s error=%s",
            req.taskId,
            req.docId,
            str(e),
        )
        update_task_status(req.taskId, "failed", 100, str(e))
        update_doc_status(req.docId, "failed")
        raise HTTPException(status_code=500, detail=str(e))
