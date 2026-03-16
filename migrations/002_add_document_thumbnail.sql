-- Add thumbnail column to documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS thumbnail VARCHAR(500);
