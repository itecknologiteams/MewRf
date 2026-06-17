-- ============================================================================
-- add_tid_column.sql
-- Adds the chip `tid` column to the `tags` table.
--
-- tid  = the RFID chip's permanent TID read by the reader
--        (e.g. E28011052000704A8F9F0AE3). 24 chars, globally unique.
--        Nullable: existing rows stay NULL until re-registered.
--
-- This is the standalone equivalent of Django migration
-- apps/vehicles/migrations/0006_tag_tid.py — use it to apply the change to a
-- database that does not have the column yet (e.g. the master server).
--
-- Safe to run multiple times (idempotent).
-- Usage:  psql -U postgres -h <host> -d <dbname> -f add_tid_column.sql
-- ============================================================================

BEGIN;

-- 1. Add the column (no-op if it already exists).
ALTER TABLE tags ADD COLUMN IF NOT EXISTS tid character varying(24);

-- 2. Enforce uniqueness. PostgreSQL allows multiple NULLs under a UNIQUE
--    constraint, so existing NULL rows are fine. Guarded so re-runs don't error.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'tags_tid_key'
    ) THEN
        ALTER TABLE tags ADD CONSTRAINT tags_tid_key UNIQUE (tid);
    END IF;
END$$;

COMMIT;

-- Verify:
--   \d tags
-- Expect:  tid | character varying(24) | nullable, unique constraint tags_tid_key
