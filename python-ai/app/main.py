from datetime import datetime, timezone
from fastapi import FastAPI

app = FastAPI(title="rag-ai-service", version="0.1.0")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-service",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
