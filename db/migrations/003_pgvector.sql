-- Migration 003: pgvector — semantic job similarity
-- Requires: postgres image pgvector/pgvector:pg15 (or pg16)
-- Run after: 001_initial.sql, 002_*.sql

-- ── Extension ────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Column ───────────────────────────────────────────────────
-- 1024 dims = jina-embeddings-v3 default
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- ── Index ────────────────────────────────────────────────────
-- IVFFlat: fast ANN search. lists=10 OK up to ~10k rows.
-- Rebuild with higher lists when jobs > 10k: REINDEX INDEX idx_jobs_embedding
CREATE INDEX IF NOT EXISTS idx_jobs_embedding
  ON jobs USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 10);

-- ── Similarity search function ────────────────────────────────
-- Usage: SELECT * FROM find_similar_jobs('[0.1,0.2,...]'::vector);
CREATE OR REPLACE FUNCTION find_similar_jobs(
  query_embedding vector(1024),
  similarity_threshold float DEFAULT 0.88,
  max_results int DEFAULT 5
)
RETURNS TABLE(
  job_id        uuid,
  job_title     text,
  company_name  text,
  similarity    float
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    j.id                                          AS job_id,
    j.job_title,
    c.name                                        AS company_name,
    (1 - (j.embedding <=> query_embedding))::float AS similarity
  FROM jobs j
  LEFT JOIN companies c ON c.company_id = j.company_id
  WHERE j.embedding IS NOT NULL
    AND (1 - (j.embedding <=> query_embedding)) > similarity_threshold
  ORDER BY j.embedding <=> query_embedding
  LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- ── Dedup helper ──────────────────────────────────────────────
-- Returns existing job_id if a near-duplicate exists (>= 0.92 similarity)
-- Used in Flow 3 before INSERT to avoid double-storing same vacancy
CREATE OR REPLACE FUNCTION find_duplicate_job(
  query_embedding vector(1024),
  dedup_threshold float DEFAULT 0.92
)
RETURNS uuid AS $$
  SELECT j.id
  FROM jobs j
  WHERE j.embedding IS NOT NULL
    AND (1 - (j.embedding <=> query_embedding)) >= dedup_threshold
  ORDER BY j.embedding <=> query_embedding
  LIMIT 1;
$$ LANGUAGE sql;
