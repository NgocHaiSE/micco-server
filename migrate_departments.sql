-- ═══════════════════════════════════════════════════════════════
-- Migration: Add departments, department access control,
--            and document_chunks table for embeddings
-- ═══════════════════════════════════════════════════════════════

-- ─── Enable pgvector ─────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "vector";

-- ─── Create departments table ────────────────────────────────
CREATE TABLE IF NOT EXISTS departments (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100)  NOT NULL UNIQUE,
    description     TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_departments_name ON departments (name);

-- ─── Add department_id to users ──────────────────────────────
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_users_department ON users (department_id);

-- ─── Add department_id to documents ──────────────────────────
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL;
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS category VARCHAR(50) NOT NULL DEFAULT 'Tài liệu';
CREATE INDEX IF NOT EXISTS idx_documents_department ON documents (department_id);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents (category);

-- ─── Create document_chunks table ────────────────────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER       NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER       NOT NULL,
    content         TEXT          NOT NULL,
    embedding       vector(1536),
    token_count     INTEGER       DEFAULT 0,
    metadata        JSONB         DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks (document_id);

-- ─── Seed departments ────────────────────────────────────────
INSERT INTO departments (name, description) VALUES
    ('Kế toán',     'Phòng Kế toán - Tài chính'),
    ('Nhân sự',     'Phòng Nhân sự'),
    ('Kỹ thuật',    'Phòng Kỹ thuật - Công nghệ'),
    ('Kinh doanh',  'Phòng Kinh doanh - Marketing'),
    ('Pháp chế',    'Phòng Pháp chế - Hợp đồng'),
    ('Ban Giám đốc','Ban lãnh đạo công ty')
ON CONFLICT (name) DO NOTHING;

DO $$ BEGIN RAISE NOTICE '✅ Migration complete: departments, document_chunks, access control columns added'; END $$;
