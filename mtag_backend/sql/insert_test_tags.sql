-- ============================================================================
-- insert_test_tags.sql
-- Dummy test data: vehicle + account + tag, all bound to owner user id = 5
-- (ali / 03102020202).
--
-- Each tag: tag_serial = TID, tid = TID, epc = EPC.
--   (Gate now matches on `tid`. We keep tag_serial = TID too, so tags are
--    recognised even on machines still running the older tag_serial lookup.)
--
-- This script is self-healing and safe to re-run:
--   * ensures the `tid` column exists (idempotent),
--   * each tag block is guarded with  tid = X OR tag_serial = X  so a TID that
--     already exists in EITHER column is skipped (no duplicate, no error),
--   * a final backfill sets  tid = tag_serial  for any of these TIDs that were
--     already registered the old way (tag_serial holds the TID, tid is NULL),
--     so those existing tags become recognisable under the new tid lookup.
--
-- TIDs from the scanned images (6 unique; one duplicate of
-- E2801105200070D4FB330A36 was dropped). All share EPC 300833B2DDD9014000000000.
--
-- Usage:  psql -U postgres -h <host> -d tag_db -f insert_test_tags.sql
-- ============================================================================

-- ─── Ensure tid column exists (idempotent) ─────────────────────────────────
ALTER TABLE tags ADD COLUMN IF NOT EXISTS tid character varying(24);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tags_tid_key') THEN
        ALTER TABLE tags ADD CONSTRAINT tags_tid_key UNIQUE (tid);
    END IF;
END$$;

-- ─── Owner user (id=5, ali) ─────────────────────────────────────────────────
-- Create user 5 from the provided row if missing. Guarded for re-runs.
INSERT INTO users (id, password, last_login, is_superuser, uuid, full_name,
                   cnic, phone, user_role, status, is_staff,
                   created_at, updated_at, last_login_at, created_by_id)
VALUES (5,
        'pbkdf2_sha256$1200000$RBiRO8k3SMxMiFFuoY7fIG$u62nNTKw9+cjz6eQ3nRxIDmAU1DmZLLvUcrIkMY4Ku4=',
        NULL, false, '4f754655-5b4a-4f32-a7d2-0d508533822a', 'ali',
        '3630215620121', '03102020202', 'user', 'active', false,
        '2026-04-29 11:44:36.421987+05', '2026-04-29 11:44:36.422001+05', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- Keep the id sequence ahead of the explicit id so future user inserts don't collide.
SELECT setval(pg_get_serial_sequence('users', 'id'),
              GREATEST((SELECT MAX(id) FROM users), 1));

-- ─── Tag #1 ─────────────────────────────────────────────────────────────────
WITH v AS (
    INSERT INTO vehicles (id, plate_number, vehicle_type, status, registered_at, updated_at, owner_id)
    SELECT gen_random_uuid(), 'TST-0001', 'car', 'active', now(), now(), 5
    WHERE NOT EXISTS (SELECT 1 FROM tags WHERE tid = 'E28011052000704A8F9F0AE3' OR tag_serial = 'E28011052000704A8F9F0AE3')
    RETURNING id
), acc AS (
    INSERT INTO accounts (id, balance, balance_updated_at, created_at, user_id, vehicle_id)
    SELECT gen_random_uuid(), 5000.00, now(), now(), 5, id FROM v
)
INSERT INTO tags (id, tag_serial, tid, epc, issued_at, expiry_date, status, vehicle_id, updated_at)
SELECT gen_random_uuid(), 'E28011052000704A8F9F0AE3', 'E28011052000704A8F9F0AE3', '300833B2DDD9014000000000', now(), '2099-12-31', 'active', id, now() FROM v;

-- ─── Tag #2 ─────────────────────────────────────────────────────────────────
WITH v AS (
    INSERT INTO vehicles (id, plate_number, vehicle_type, status, registered_at, updated_at, owner_id)
    SELECT gen_random_uuid(), 'TST-0002', 'car', 'active', now(), now(), 5
    WHERE NOT EXISTS (SELECT 1 FROM tags WHERE tid = 'E28011052000704C8F9F0AE3' OR tag_serial = 'E28011052000704C8F9F0AE3')
    RETURNING id
), acc AS (
    INSERT INTO accounts (id, balance, balance_updated_at, created_at, user_id, vehicle_id)
    SELECT gen_random_uuid(), 5000.00, now(), now(), 5, id FROM v
)
INSERT INTO tags (id, tag_serial, tid, epc, issued_at, expiry_date, status, vehicle_id, updated_at)
SELECT gen_random_uuid(), 'E28011052000704C8F9F0AE3', 'E28011052000704C8F9F0AE3', '300833B2DDD9014000000000', now(), '2099-12-31', 'active', id, now() FROM v;

-- ─── Tag #3 ─────────────────────────────────────────────────────────────────
WITH v AS (
    INSERT INTO vehicles (id, plate_number, vehicle_type, status, registered_at, updated_at, owner_id)
    SELECT gen_random_uuid(), 'TST-0003', 'car', 'active', now(), now(), 5
    WHERE NOT EXISTS (SELECT 1 FROM tags WHERE tid = 'E2801105200070DCFB330A36' OR tag_serial = 'E2801105200070DCFB330A36')
    RETURNING id
), acc AS (
    INSERT INTO accounts (id, balance, balance_updated_at, created_at, user_id, vehicle_id)
    SELECT gen_random_uuid(), 5000.00, now(), now(), 5, id FROM v
)
INSERT INTO tags (id, tag_serial, tid, epc, issued_at, expiry_date, status, vehicle_id, updated_at)
SELECT gen_random_uuid(), 'E2801105200070DCFB330A36', 'E2801105200070DCFB330A36', '300833B2DDD9014000000000', now(), '2099-12-31', 'active', id, now() FROM v;

-- ─── Tag #4 ─────────────────────────────────────────────────────────────────
WITH v AS (
    INSERT INTO vehicles (id, plate_number, vehicle_type, status, registered_at, updated_at, owner_id)
    SELECT gen_random_uuid(), 'TST-0004', 'car', 'active', now(), now(), 5
    WHERE NOT EXISTS (SELECT 1 FROM tags WHERE tid = 'E2801105200070D2FB330A36' OR tag_serial = 'E2801105200070D2FB330A36')
    RETURNING id
), acc AS (
    INSERT INTO accounts (id, balance, balance_updated_at, created_at, user_id, vehicle_id)
    SELECT gen_random_uuid(), 5000.00, now(), now(), 5, id FROM v
)
INSERT INTO tags (id, tag_serial, tid, epc, issued_at, expiry_date, status, vehicle_id, updated_at)
SELECT gen_random_uuid(), 'E2801105200070D2FB330A36', 'E2801105200070D2FB330A36', '300833B2DDD9014000000000', now(), '2099-12-31', 'active', id, now() FROM v;

-- ─── Tag #5 ─────────────────────────────────────────────────────────────────
WITH v AS (
    INSERT INTO vehicles (id, plate_number, vehicle_type, status, registered_at, updated_at, owner_id)
    SELECT gen_random_uuid(), 'TST-0005', 'car', 'active', now(), now(), 5
    WHERE NOT EXISTS (SELECT 1 FROM tags WHERE tid = 'E2801105200070D4FB330A36' OR tag_serial = 'E2801105200070D4FB330A36')
    RETURNING id
), acc AS (
    INSERT INTO accounts (id, balance, balance_updated_at, created_at, user_id, vehicle_id)
    SELECT gen_random_uuid(), 5000.00, now(), now(), 5, id FROM v
)
INSERT INTO tags (id, tag_serial, tid, epc, issued_at, expiry_date, status, vehicle_id, updated_at)
SELECT gen_random_uuid(), 'E2801105200070D4FB330A36', 'E2801105200070D4FB330A36', '300833B2DDD9014000000000', now(), '2099-12-31', 'active', id, now() FROM v;

-- ─── Tag #6 ─────────────────────────────────────────────────────────────────
WITH v AS (
    INSERT INTO vehicles (id, plate_number, vehicle_type, status, registered_at, updated_at, owner_id)
    SELECT gen_random_uuid(), 'TST-0006', 'car', 'active', now(), now(), 5
    WHERE NOT EXISTS (SELECT 1 FROM tags WHERE tid = 'E2801105200070D6FB330A36' OR tag_serial = 'E2801105200070D6FB330A36')
    RETURNING id
), acc AS (
    INSERT INTO accounts (id, balance, balance_updated_at, created_at, user_id, vehicle_id)
    SELECT gen_random_uuid(), 5000.00, now(), now(), 5, id FROM v
)
INSERT INTO tags (id, tag_serial, tid, epc, issued_at, expiry_date, status, vehicle_id, updated_at)
SELECT gen_random_uuid(), 'E2801105200070D6FB330A36', 'E2801105200070D6FB330A36', '300833B2DDD9014000000000', now(), '2099-12-31', 'active', id, now() FROM v;

-- ─── Backfill: pre-existing tags where the TID lives in tag_serial ──────────
-- For any of these 6 TIDs already registered the old way (tag_serial = TID,
-- tid = NULL), set tid so the new tid-based gate lookup recognises them.
UPDATE tags
SET tid = tag_serial
WHERE tid IS NULL
  AND tag_serial IN (
      'E28011052000704A8F9F0AE3',
      'E28011052000704C8F9F0AE3',
      'E2801105200070DCFB330A36',
      'E2801105200070D2FB330A36',
      'E2801105200070D4FB330A36',
      'E2801105200070D6FB330A36'
  );
