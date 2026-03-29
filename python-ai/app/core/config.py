import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUERY_CACHE_TTL_SEC = int(os.getenv("QUERY_CACHE_TTL_SEC", "300"))
QUERY_CACHE_PREFIX = os.getenv("QUERY_CACHE_PREFIX", "rag:query:v1")
CACHE_SCHEMA_VERSION = "v1"
KB_VERSION_KEY = "rag:kb:version"

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "ragkb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/workspace/uploads")
GAME_DATA_DIR = os.getenv("GAME_DATA_DIR", "/workspace/game-data")
GAME_TESTING_API_ENABLED = os.getenv("GAME_TESTING_API_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv(
    "EMBEDDING_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
).rstrip("/")

LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
).rstrip("/")

RERANK_ENABLED = os.getenv("RERANK_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
RERANK_PROVIDER = os.getenv("RERANK_PROVIDER", "").strip()
RERANK_BASE_URL = os.getenv("RERANK_BASE_URL", "").strip().rstrip("/")
RERANK_API_KEY = os.getenv("RERANK_API_KEY", "").strip()
RERANK_MODEL = os.getenv("RERANK_MODEL", "").strip()
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "20"))
RERANK_TIMEOUT_SEC = float(os.getenv("RERANK_TIMEOUT_SEC", "30"))
RERANK_SCORE_WEIGHT = float(os.getenv("RERANK_SCORE_WEIGHT", "0.65"))
LOCAL_RERANK_SCORE_WEIGHT = float(os.getenv("LOCAL_RERANK_SCORE_WEIGHT", "0.35"))
RERANK_INSTRUCT = os.getenv(
    "RERANK_INSTRUCT",
    "Given a web search query, retrieve relevant passages that answer the query.",
).strip()

PG_DSN = (
    f"host={POSTGRES_HOST} "
    f"port={POSTGRES_PORT} "
    f"dbname={POSTGRES_DB} "
    f"user={POSTGRES_USER} "
    f"password={POSTGRES_PASSWORD}"
)
