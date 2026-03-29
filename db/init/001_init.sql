CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS docs (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  source_path TEXT NOT NULL,
  owner TEXT NOT NULL,
  source_type VARCHAR(32),
  content_hash CHAR(64),
  status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
  doc_summary TEXT,
  doc_keywords TEXT,
  route_text TEXT,
  route_embedding VECTOR(1536),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
  id UUID PRIMARY KEY,
  doc_id BIGINT NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
  status VARCHAR(16) NOT NULL,
  progress INT NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
  error TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks (
  id BIGSERIAL PRIMARY KEY,
  doc_id BIGINT NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  text TEXT NOT NULL,
  page INT,
  heading TEXT,
  section_path TEXT,
  chunk_type VARCHAR(32),
  source_type VARCHAR(32),
  context_text TEXT,
  embedding VECTOR(1536),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (doc_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS rag_logs (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  doc_scope TEXT,
  q_hash CHAR(64) NOT NULL,
  topk INT NOT NULL,
  latency_ms INT NOT NULL,
  cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
  token_in INT NOT NULL DEFAULT 0,
  token_out INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS game_memories (
  id TEXT PRIMARY KEY,
  assistant_id TEXT NOT NULL,
  user_scope TEXT NOT NULL,
  worldbook_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  responder_id TEXT NOT NULL,
  character_ids TEXT[] NOT NULL DEFAULT '{}',
  location_id TEXT,
  scene_id TEXT,
  day_index INT NOT NULL,
  memory_type VARCHAR(32) NOT NULL,
  summary TEXT NOT NULL,
  retrieval_text TEXT NOT NULL,
  trigger_hints TEXT[] NOT NULL DEFAULT '{}',
  emotion_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  relation_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  salience DOUBLE PRECISION NOT NULL DEFAULT 0,
  importance DOUBLE PRECISION NOT NULL DEFAULT 0,
  visibility JSONB NOT NULL DEFAULT '{}'::jsonb,
  archived_from_session BOOLEAN NOT NULL DEFAULT TRUE,
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  embedding VECTOR(1536)
);

CREATE TABLE IF NOT EXISTS game_memory_profiles (
  assistant_id TEXT NOT NULL,
  user_scope TEXT NOT NULL,
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
);

CREATE INDEX IF NOT EXISTS idx_docs_owner_created_at
ON docs(owner, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_docs_owner_content_hash
ON docs(owner, content_hash);

CREATE INDEX IF NOT EXISTS idx_docs_source_type
ON docs(source_type);

CREATE INDEX IF NOT EXISTS idx_docs_title_trgm
ON docs USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_docs_doc_summary_trgm
ON docs USING gin (doc_summary gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_docs_doc_keywords_trgm
ON docs USING gin (doc_keywords gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_docs_route_text_trgm
ON docs USING gin (route_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_docs_route_embedding_ivfflat
ON docs
USING ivfflat (route_embedding vector_cosine_ops)
WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id
ON chunks(doc_id);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id_chunk_type
ON chunks(doc_id, chunk_type);

CREATE INDEX IF NOT EXISTS idx_chunks_text_trgm
ON chunks USING gin (text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_chunks_heading_trgm
ON chunks USING gin (heading gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_chunks_section_path_trgm
ON chunks USING gin (section_path gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_chunks_context_text_trgm
ON chunks USING gin (context_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_tasks_status_updated_at
ON tasks(status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_rag_logs_user_created_at
ON rag_logs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivfflat
ON chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_game_memories_worldbook_created_at
ON game_memories(worldbook_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_game_memories_assistant_created_at
ON game_memories(assistant_id, user_scope, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_game_memories_session_created_at
ON game_memories(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_game_memories_responder_created_at
ON game_memories(responder_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_game_memories_summary_trgm
ON game_memories USING gin (summary gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_game_memories_retrieval_text_trgm
ON game_memories USING gin (retrieval_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_game_memories_embedding_ivfflat
ON game_memories
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_game_memory_profiles_worldbook_updated_at
ON game_memory_profiles(worldbook_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_game_memory_profiles_assistant_updated_at
ON game_memory_profiles(assistant_id, user_scope, updated_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_game_memory_profiles_assistant_character_scope
ON game_memory_profiles(assistant_id, character_id, user_scope);
