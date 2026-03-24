-- Add approval workflow columns to documents and knowledge_entries
-- approval_status: 'pending_approval' | 'approved' | 'rejected'

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS approval_status  VARCHAR(20)  NOT NULL DEFAULT 'pending_approval',
    ADD COLUMN IF NOT EXISTS approved_by_id   INTEGER      REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approved_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approval_note    TEXT;

ALTER TABLE knowledge_entries
    ADD COLUMN IF NOT EXISTS approval_status  VARCHAR(20)  NOT NULL DEFAULT 'pending_approval',
    ADD COLUMN IF NOT EXISTS approved_by_id   INTEGER      REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approved_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approval_note    TEXT;

CREATE INDEX IF NOT EXISTS idx_documents_approval_status  ON documents (approval_status);
CREATE INDEX IF NOT EXISTS idx_knowledge_approval_status  ON knowledge_entries (approval_status);

-- Back-fill: existing documents/knowledge are considered already approved
UPDATE documents       SET approval_status = 'approved' WHERE approval_status = 'pending_approval';
UPDATE knowledge_entries SET approval_status = 'approved' WHERE approval_status = 'pending_approval';
