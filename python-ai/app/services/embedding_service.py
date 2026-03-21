import time
from typing import List


import httpx

from app.core.config import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
)
from app.core.logging_config import logger


def _max_embed_batch_size() -> int:
    model = (EMBEDDING_MODEL or "").strip().lower()
    if model in {"text-embedding-v3", "text-embedding-v4"}:
        return 10
    return 25


def _embedding_payload(texts: List[str]) -> dict:
    payload = {
        "model": EMBEDDING_MODEL,
        "input": texts,
    }

    model = (EMBEDDING_MODEL or "").strip().lower()
    if model in {"text-embedding-v3", "text-embedding-v4"}:
        payload["dimensions"] = EMBEDDING_DIM

    return payload


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

    logger.info(
        "embed_texts start url=%s model=%s text_count=%s expected_dim=%s batch_size=%s",
        url,
        EMBEDDING_MODEL,
        len(texts),
        EMBEDDING_DIM,
        _max_embed_batch_size(),
    )

    vectors: List[List[float]] = []

    with httpx.Client(timeout=60.0) as client:
        batch_size = _max_embed_batch_size()
        for batch_index, start in enumerate(range(0, len(texts), batch_size), start=1):
            batch = texts[start : start + batch_size]
            payload = _embedding_payload(batch)

            start_time = time.time()
            resp = client.post(url, headers=headers, json=payload)
            elapsed_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "embed_texts response batch_index=%s batch_count=%s status_code=%s elapsed_ms=%s",
                batch_index,
                len(batch),
                resp.status_code,
                elapsed_ms,
            )

            if resp.status_code != 200:
                logger.error("embed_texts failed batch_index=%s body=%s", batch_index, resp.text)
                raise ValueError(f"embedding request failed: {resp.status_code} {resp.text}")

            body = resp.json()
            data = body.get("data", [])
            if len(data) != len(batch):
                logger.error(
                    "embedding count mismatch batch_index=%s expected=%s actual=%s body=%s",
                    batch_index,
                    len(batch),
                    len(data),
                    body,
                )
                raise ValueError(
                    f"embedding count mismatch: expected {len(batch)}, got {len(data)}"
                )

            for idx, item in enumerate(data):
                embedding = item.get("embedding")
                if not isinstance(embedding, list):
                    logger.error("invalid embedding payload batch_index=%s item_index=%s item=%s", batch_index, idx, item)
                    raise ValueError("invalid embedding payload")
                if len(embedding) != EMBEDDING_DIM:
                    logger.error(
                        "embedding dimension mismatch batch_index=%s item_index=%s expected=%s actual=%s",
                        batch_index,
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


def embed_query(question: str) -> List[float]:
    vectors = embed_texts([question])
    if len(vectors) != 1:
        raise ValueError("query embedding failed")
    return vectors[0]


def vector_to_pg(vector: List[float]) -> str:
    if not vector:
        raise ValueError("vector is empty")
    return "[" + ",".join(f"{x:.10f}" for x in vector) + "]"
