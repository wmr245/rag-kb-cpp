from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI

from app.core.config import REDIS_URL
from app.db.postgres import ensure_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_schema()
        print("[startup] postgres schema ensured")
    except Exception as e:
        print(f"[startup] postgres schema ensure failed: {e}")
        raise

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
