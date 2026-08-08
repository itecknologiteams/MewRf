-- Verifies the ON CONFLICT ... WHERE guard added to _push_trip_to_master.
-- Uses a TEMP table, so it touches nothing persistent. Run with:
--   sudo -u postgres psql -f verify_exit_guard.sql
\set ON_ERROR_STOP on
CREATE TEMP TABLE toll_trips_check (
    id uuid PRIMARY KEY,
    exit_plaza_id uuid,
    charge_amount numeric(10,2),
    status varchar(20) NOT NULL,
    updated_at timestamptz NOT NULL
);
INSERT INTO toll_trips_check VALUES
  ('11111111-1111-1111-1111-111111111111', NULL, NULL, 'active', now());

\echo '=== 1. First exit, master row active  -> EXPECT "INSERT 0 1" ==='
INSERT INTO toll_trips_check AS t (id, exit_plaza_id, charge_amount, status, updated_at)
VALUES ('11111111-1111-1111-1111-111111111111',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 100.00, 'completed', now())
ON CONFLICT (id) DO UPDATE SET
    exit_plaza_id = EXCLUDED.exit_plaza_id,
    charge_amount = EXCLUDED.charge_amount,
    status = EXCLUDED.status, updated_at = EXCLUDED.updated_at
WHERE t.status = 'active';

\echo '=== 2. Duplicate exit, already completed -> EXPECT "INSERT 0 0" (rowcount 0 => we raise) ==='
INSERT INTO toll_trips_check AS t (id, exit_plaza_id, charge_amount, status, updated_at)
VALUES ('11111111-1111-1111-1111-111111111111',
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 200.00, 'completed', now())
ON CONFLICT (id) DO UPDATE SET
    exit_plaza_id = EXCLUDED.exit_plaza_id,
    charge_amount = EXCLUDED.charge_amount,
    status = EXCLUDED.status, updated_at = EXCLUDED.updated_at
WHERE t.status = 'active';

\echo '=== 3. Master must still hold the FIRST exit: aaaa / 100.00 ==='
SELECT exit_plaza_id, charge_amount, status FROM toll_trips_check;

\echo '=== 4. Fresh entry insert, no conflict -> EXPECT "INSERT 0 1" ==='
INSERT INTO toll_trips_check AS t (id, exit_plaza_id, charge_amount, status, updated_at)
VALUES ('22222222-2222-2222-2222-222222222222', NULL, NULL, 'active', now())
ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status WHERE t.status = 'active';
