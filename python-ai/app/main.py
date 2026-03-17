from fastapi import FastAPI

from app.core.lifespan import lifespan
from app.routers.health import router as health_router
from app.routers.internal import router as internal_router

app = FastAPI(lifespan=lifespan)

app.include_router(health_router)
app.include_router(internal_router)
