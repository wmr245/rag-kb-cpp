import psycopg

from app.core.config import PG_DSN


def get_conn():
    return psycopg.connect(PG_DSN)


def ensure_schema() -> None:
    statements = [
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS heading TEXT",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS section_path TEXT",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(32)",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS source_type VARCHAR(32)",
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
        CREATE INDEX IF NOT EXISTS idx_docs_title_trgm
        ON docs USING gin (title gin_trgm_ops)
        """,
    ]

    with get_conn() as conn:
        with conn.cursor() as cur:
            for sql in statements:
                cur.execute(sql)
        conn.commit()
