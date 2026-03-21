CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS docs (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  source_path TEXT NOT NULL,
  owner TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

CREATE INDEX IF NOT EXISTS idx_docs_owner_created_at
ON docs(owner, created_at DESC);

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

CREATE INDEX IF NOT EXISTS idx_docs_title_trgm
ON docs USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_tasks_status_updated_at
ON tasks(status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_rag_logs_user_created_at
ON rag_logs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivfflat
ON chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
