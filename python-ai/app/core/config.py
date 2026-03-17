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

PG_DSN = (
    f"host={POSTGRES_HOST} "
    f"port={POSTGRES_PORT} "
    f"dbname={POSTGRES_DB} "
    f"user={POSTGRES_USER} "
    f"password={POSTGRES_PASSWORD}"
)
