import time
from typing import Dict, List, Tuple

import httpx

from app.core.config import (
    LOCAL_RERANK_SCORE_WEIGHT,
    RERANK_API_KEY,
    RERANK_BASE_URL,
    RERANK_ENABLED,
    RERANK_INSTRUCT,
    RERANK_MODEL,
    RERANK_PROVIDER,
    RERANK_SCORE_WEIGHT,
    RERANK_TIMEOUT_SEC,
    RERANK_TOP_N,
)
from app.core.logging_config import logger


class RerankServiceError(RuntimeError):
    pass


def rerank_cache_signature() -> str:
    if not RERANK_ENABLED:
        return "disabled"

    return "|".join(
        [
            RERANK_PROVIDER or "generic",
            RERANK_BASE_URL or "unset",
            RERANK_MODEL or "unset",
            str(max(1, RERANK_TOP_N)),
            f"{max(RERANK_SCORE_WEIGHT, 0.0):.3f}",
            f"{max(LOCAL_RERANK_SCORE_WEIGHT, 0.0):.3f}",
        ]
    )


def _rerank_url() -> str:
    if not RERANK_BASE_URL:
        raise RerankServiceError("RERANK_BASE_URL is not configured")

    if RERANK_BASE_URL.endswith(("/rerank", "/reranks")):
        return RERANK_BASE_URL

    provider = (RERANK_PROVIDER or "").strip().lower()
    if provider == "dashscope":
        return f"{RERANK_BASE_URL}/reranks"

    return f"{RERANK_BASE_URL}/rerank"


def _normalize_score(raw_score: object) -> float:
    try:
        score = float(raw_score)
    except (TypeError, ValueError) as exc:
        raise RerankServiceError(f"invalid rerank score: {raw_score}") from exc

    return round(max(0.0, min(score, 1.0)), 6)


def _extract_results(body: object) -> List[Dict[str, float]]:
    if not isinstance(body, dict):
        raise RerankServiceError("invalid rerank response body")

    results = body.get("results")
    if not isinstance(results, list):
        results = body.get("data")
    if not isinstance(results, list):
        output = body.get("output")
        if isinstance(output, dict):
            results = output.get("results")
    if not isinstance(results, list):
        raise RerankServiceError("rerank response missing results")

    parsed: List[Dict[str, float]] = []
    for item in results:
        if not isinstance(item, dict):
            raise RerankServiceError("invalid rerank result item")

        raw_index = item.get("index")
        raw_score = item.get("relevance_score")
        if raw_score is None:
            raw_score = item.get("score")

        if raw_index is None or raw_score is None:
            raise RerankServiceError(f"rerank result missing index or score: {item}")

        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise RerankServiceError(f"invalid rerank index: {raw_index}") from exc

        parsed.append(
            {
                "index": index,
                "score": _normalize_score(raw_score),
            }
        )

    return parsed


def rerank_candidates(query: str, documents: List[str], top_n: int) -> Tuple[Dict[int, float], int]:
    if not RERANK_ENABLED:
        return {}, 0

    if not RERANK_API_KEY:
        raise RerankServiceError("RERANK_API_KEY is not configured")
    if not RERANK_MODEL:
        raise RerankServiceError("RERANK_MODEL is not configured")

    prepared_documents = [str(document or "").strip() for document in documents]
    if not prepared_documents:
        return {}, 0

    requested_top_n = min(len(prepared_documents), max(1, top_n))
    url = _rerank_url()
    headers = {
        "Authorization": f"Bearer {RERANK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": RERANK_MODEL,
        "query": (query or "").strip(),
        "documents": prepared_documents,
        "top_n": requested_top_n,
    }
    if (RERANK_PROVIDER or "").strip().lower() == "dashscope" and RERANK_INSTRUCT:
        payload["instruct"] = RERANK_INSTRUCT

    logger.info(
        "rerank_candidates start url=%s provider=%s model=%s document_count=%s top_n=%s",
        url,
        RERANK_PROVIDER or "generic",
        RERANK_MODEL,
        len(prepared_documents),
        requested_top_n,
    )

    started_at = time.perf_counter()
    with httpx.Client(timeout=RERANK_TIMEOUT_SEC) as client:
        response = client.post(url, headers=headers, json=payload)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)

    logger.info(
        "rerank_candidates response status_code=%s elapsed_ms=%s",
        response.status_code,
        elapsed_ms,
    )

    if response.status_code != 200:
        logger.error("rerank_candidates failed body=%s", response.text)
        raise RerankServiceError(f"rerank request failed: {response.status_code} {response.text}")

    rows = _extract_results(response.json())
    if len(rows) != requested_top_n:
        raise RerankServiceError(
            f"rerank count mismatch: expected {requested_top_n}, got {len(rows)}"
        )

    scores: Dict[int, float] = {}
    for row in rows:
        index = int(row["index"])
        if index < 0 or index >= requested_top_n:
            raise RerankServiceError(f"rerank index out of range: {index}")
        scores[index] = float(row["score"])

    if len(scores) != requested_top_n:
        raise RerankServiceError(
            f"rerank result coverage mismatch: expected {requested_top_n}, got {len(scores)}"
        )

    return scores, elapsed_ms
