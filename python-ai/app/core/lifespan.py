from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI

from app.core.config import REDIS_URL
from app.db.postgres import ensure_schema
from app.services.document_service import backfill_missing_doc_catalog, backfill_missing_chunk_context
from app.services.game_storage_service import ensure_game_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_schema()
        print("[startup] postgres schema ensured")
    except Exception as e:
        print(f"[startup] postgres schema ensure failed: {e}")
        raise

    try:
        ensure_game_storage()
        print("[startup] game storage ensured")
    except Exception as e:
        print(f"[startup] game storage ensure failed: {e}")
        raise

    try:
        backfilled = backfill_missing_doc_catalog()
        print(f"[startup] doc catalog backfilled: {backfilled}")
    except Exception as e:
        print(f"[startup] doc catalog backfill skipped: {e}")

    try:
        chunk_context_backfilled = backfill_missing_chunk_context()
        print(f"[startup] chunk context backfilled: {chunk_context_backfilled}")
    except Exception as e:
        print(f"[startup] chunk context backfill skipped: {e}")

    app.state.redis = None
    try:
        app.state.redis = redis.from_url(
            REDIS_URL,
            decode_responses=True,
        )
        await app.state.redis.ping()
        print(f"[startup] redis connected: {REDIS_URL}")
    except Exception as e:
        print(f"[startup] redis unavailable: {e}")
        app.state.redis = None

    yield

    if app.state.redis is not None:
        await app.state.redis.aclose()
