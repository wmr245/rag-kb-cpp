import psycopg

from app.core.config import EMBEDDING_DIM, PG_DSN


def get_conn():
    return psycopg.connect(PG_DSN)


def ensure_schema() -> None:
    statements = [
        "CREATE EXTENSION IF NOT EXISTS vector",
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
        f"""
        CREATE TABLE IF NOT EXISTS game_memories (
          id TEXT PRIMARY KEY,
          assistant_id TEXT,
          user_scope TEXT,
          worldbook_id TEXT NOT NULL,
          session_id TEXT NOT NULL,
          responder_id TEXT NOT NULL,
          character_ids TEXT[] NOT NULL DEFAULT '{{}}',
          location_id TEXT,
          scene_id TEXT,
          day_index INT NOT NULL,
          memory_type VARCHAR(32) NOT NULL,
          summary TEXT NOT NULL,
          retrieval_text TEXT NOT NULL,
          trigger_hints TEXT[] NOT NULL DEFAULT '{{}}',
          emotion_payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          relation_payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          salience DOUBLE PRECISION NOT NULL DEFAULT 0,
          importance DOUBLE PRECISION NOT NULL DEFAULT 0,
          visibility JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          archived_from_session BOOLEAN NOT NULL DEFAULT TRUE,
          last_used_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL,
          embedding VECTOR({EMBEDDING_DIM})
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS game_memory_profiles (
          assistant_id TEXT,
          user_scope TEXT,
          worldbook_id TEXT NOT NULL,
          character_id TEXT NOT NULL,
          player_scope TEXT NOT NULL,
          latest_session_id TEXT NOT NULL,
          relationship_stage VARCHAR(32) NOT NULL,
          trust INT NOT NULL,
          affection INT NOT NULL,
          tension INT NOT NULL,
          familiarity INT NOT NULL,
          player_image_summary TEXT NOT NULL,
          relationship_summary TEXT NOT NULL,
          long_term_summary TEXT NOT NULL,
          open_threads TEXT[] NOT NULL DEFAULT '{}',
          important_memory_ids TEXT[] NOT NULL DEFAULT '{}',
          last_interaction_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (worldbook_id, character_id, player_scope)
        )
        """,
        "ALTER TABLE game_memories ADD COLUMN IF NOT EXISTS assistant_id TEXT",
        "ALTER TABLE game_memories ADD COLUMN IF NOT EXISTS user_scope TEXT",
        "UPDATE game_memories SET assistant_id = CONCAT('assistant:', responder_id) WHERE assistant_id IS NULL OR assistant_id = ''",
        "UPDATE game_memories SET user_scope = 'default_player' WHERE user_scope IS NULL OR user_scope = ''",
        "ALTER TABLE game_memory_profiles ADD COLUMN IF NOT EXISTS assistant_id TEXT",
        "ALTER TABLE game_memory_profiles ADD COLUMN IF NOT EXISTS user_scope TEXT",
        "UPDATE game_memory_profiles SET assistant_id = CONCAT('assistant:', character_id) WHERE assistant_id IS NULL OR assistant_id = ''",
        "UPDATE game_memory_profiles SET user_scope = COALESCE(NULLIF(player_scope, ''), 'default_player') WHERE user_scope IS NULL OR user_scope = ''",
        """
        CREATE INDEX IF NOT EXISTS idx_game_memories_worldbook_created_at
        ON game_memories(worldbook_id, created_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_game_memories_assistant_created_at
        ON game_memories(assistant_id, user_scope, created_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_game_memories_session_created_at
        ON game_memories(session_id, created_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_game_memories_responder_created_at
        ON game_memories(responder_id, created_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_game_memories_summary_trgm
        ON game_memories USING gin (summary gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_game_memories_retrieval_text_trgm
        ON game_memories USING gin (retrieval_text gin_trgm_ops)
        """,
        f"""
        CREATE INDEX IF NOT EXISTS idx_game_memories_embedding_ivfflat
        ON game_memories
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 50)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_game_memory_profiles_worldbook_updated_at
        ON game_memory_profiles(worldbook_id, updated_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_game_memory_profiles_assistant_updated_at
        ON game_memory_profiles(assistant_id, user_scope, updated_at DESC)
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_game_memory_profiles_assistant_character_scope
        ON game_memory_profiles(assistant_id, character_id, user_scope)
        """,
    ]

    with get_conn() as conn:
        with conn.cursor() as cur:
            for sql in statements:
                cur.execute(sql)
        conn.commit()
