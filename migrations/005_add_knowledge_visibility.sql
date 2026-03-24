-- Add visibility column to knowledge_entries table
-- 'internal' = only same department can see
-- 'public'   = all users can see

ALTER TABLE knowledge_entries
    ADD COLUMN IF NOT EXISTS visibility VARCHAR(20) NOT NULL DEFAULT 'internal';

CREATE INDEX IF NOT EXISTS idx_knowledge_visibility ON knowledge_entries (visibility);
