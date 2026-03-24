-- Add visibility column to documents table
-- 'internal' = only same department can see
-- 'public'   = all users can see

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS visibility VARCHAR(20) NOT NULL DEFAULT 'internal';

CREATE INDEX IF NOT EXISTS idx_documents_visibility ON documents (visibility);
