-- ═══════════════════════════════════════════════════════════════
-- Migration: Add category column to documents table
-- Run: sudo docker exec timescaledb psql -U postgres -d docvault -f /tmp/migrate_category.sql
-- ═══════════════════════════════════════════════════════════════

-- Add the column with default value
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS category VARCHAR(50) NOT NULL DEFAULT 'Tài liệu';

-- Add CHECK constraint
ALTER TABLE documents
    DROP CONSTRAINT IF EXISTS documents_category_check;
ALTER TABLE documents
    ADD CONSTRAINT documents_category_check;

-- Add index
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents (category);

DO $$ BEGIN RAISE NOTICE '✅ Migration complete: category column added to documents'; END $$;
