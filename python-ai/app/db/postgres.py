import psycopg

from app.core.config import EMBEDDING_DIM, PG_DSN


def get_conn():
    return psycopg.connect(PG_DSN)


def ensure_schema() -> None:
    statements = [
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS heading TEXT",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS section_path TEXT",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(32)",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS source_type VARCHAR(32)",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS context_text TEXT",
        "ALTER TABLE docs ADD COLUMN IF NOT EXISTS source_type VARCHAR(32)",
        "ALTER TABLE docs ADD COLUMN IF NOT EXISTS content_hash CHAR(64)",
        "ALTER TABLE docs ADD COLUMN IF NOT EXISTS doc_summary TEXT",
        "ALTER TABLE docs ADD COLUMN IF NOT EXISTS doc_keywords TEXT",
        "ALTER TABLE docs ADD COLUMN IF NOT EXISTS route_text TEXT",
        f"ALTER TABLE docs ADD COLUMN IF NOT EXISTS route_embedding VECTOR({EMBEDDING_DIM})",
        "ALTER TABLE docs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "UPDATE docs SET updated_at = created_at WHERE updated_at IS NULL",
        """
        CREATE INDEX IF NOT EXISTS idx_docs_owner_content_hash
        ON docs(owner, content_hash)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_chunks_doc_id_chunk_type
        ON chunks(doc_id, chunk_type)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_chunks_text_trgm
        ON chunks USING gin (text gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_chunks_heading_trgm
        ON chunks USING gin (heading gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_chunks_section_path_trgm
        ON chunks USING gin (section_path gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_chunks_context_text_trgm
        ON chunks USING gin (context_text gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_docs_title_trgm
        ON docs USING gin (title gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_docs_doc_summary_trgm
        ON docs USING gin (doc_summary gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_docs_doc_keywords_trgm
        ON docs USING gin (doc_keywords gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_docs_route_text_trgm
        ON docs USING gin (route_text gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_docs_source_type
        ON docs(source_type)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_docs_route_embedding_ivfflat
        ON docs
        USING ivfflat (route_embedding vector_cosine_ops)
        WITH (lists = 50)
        """,
    ]

    with get_conn() as conn:
        with conn.cursor() as cur:
            for sql in statements:
                cur.execute(sql)
        conn.commit()
