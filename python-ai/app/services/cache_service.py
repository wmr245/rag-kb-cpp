import hashlib
import json

import redis as redis_sync

from app.core.config import (
    CACHE_SCHEMA_VERSION,
    KB_VERSION_KEY,
    QUERY_CACHE_PREFIX,
    REDIS_URL,
)
from app.core.logging_config import logger


async def get_kb_cache_version(redis_cli) -> int:
    if redis_cli is None:
        return 0

    try:
        value = await redis_cli.get(KB_VERSION_KEY)
        if value is None:
            await redis_cli.set(KB_VERSION_KEY, "0", nx=True)
            return 0
        return int(value)
    except Exception as e:
        logger.warning("get_kb_cache_version failed error=%s", str(e))
        return 0


def build_query_cache_key(
    question: str,
    doc_scope,
    top_k: int,
    embed_model: str,
    gen_model: str,
    kb_version: int,
) -> str:
    payload = {
        "schema": CACHE_SCHEMA_VERSION,
        "kbVersion": kb_version,
        "question": (question or "").strip(),
        "docScope": sorted(doc_scope or []),
        "topK": top_k,
        "embedModel": embed_model,
        "genModel": gen_model,
        "retrievalVersion": "hybrid-rerank-v2-refusal-v1",
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{QUERY_CACHE_PREFIX}:kbv{kb_version}:{digest}"


def bump_kb_version_sync(
    trace_id: str,
    doc_id: int | None = None,
    task_id: str | None = None,
):
    try:
        redis_sync_client = redis_sync.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
        )
        new_version = redis_sync_client.incr(KB_VERSION_KEY)
        logger.info(
            "kb_version bumped trace_id=%s task_id=%s doc_id=%s kb_version=%s",
            trace_id,
            task_id,
            doc_id,
            new_version,
        )
        return new_version
    except Exception as e:
        logger.warning(
            "kb_version bump failed trace_id=%s task_id=%s doc_id=%s error=%s",
            trace_id,
            task_id,
            doc_id,
            str(e),
        )
        return None
