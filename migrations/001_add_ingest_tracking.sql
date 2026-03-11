-- Migration 001: Phase 1 EKG ingestion tracking
-- Run once against the MICCO database.
-- Safe to re-run: all statements use IF EXISTS / IF NOT EXISTS guards.

-- 1. Add ingestion tracking columns to documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ingest_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ingest_error TEXT;

-- 2. Drop the IVFFlat index before altering the embedding column type
--    (PostgreSQL requires this; cannot alter a column with a dependent index)
DROP INDEX IF EXISTS idx_chunks_embedding;

-- 3. Change embedding dimension from 1536 (OpenAI ada-002) to 1024 (bge-m3)
--    USING NULL resets existing embeddings to NULL rather than attempting an
--    impossible cast between vector dimensions.
ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1024) USING NULL;

-- 4. Recreate the IVFFlat index with the new dimension
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 5. Drop and recreate the semantic search function with the new vector dimension
DROP FUNCTION IF EXISTS search_chunks_by_embedding(vector, integer, integer);

CREATE OR REPLACE FUNCTION search_chunks_by_embedding(
    p_query_embedding vector(1024),
    p_limit           integer DEFAULT 5,
    p_document_id     integer DEFAULT NULL
)
RETURNS TABLE (
    chunk_id    integer,
    document_id integer,
    chunk_index integer,
    content     text,
    similarity  float
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id            AS chunk_id,
        dc.document_id,
        dc.chunk_index,
        dc.content,
        1 - (dc.embedding <=> p_query_embedding) AS similarity
    FROM document_chunks dc
    WHERE (p_document_id IS NULL OR dc.document_id = p_document_id)
      AND dc.embedding IS NOT NULL
    ORDER BY dc.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$;
