# Online-Only Transaction Flow — Rollout Plan

**Status:** Draft for review
**Related:** [TOLL-BOOTH-DEPLOYMENT-SPEC.md](TOLL-BOOTH-DEPLOYMENT-SPEC.md), `mtag_backend/apps/tolls/services.py`

---

## 1. What changed (recap)

Entry and exit at every booth now require a live connection to the master DB:

- `EntryService.process_entry()` and `ExitService.process_exit()` check master
  connectivity first and reject outright if it's unreachable
  (`"No connection to master DB — cannot process transaction"`).
- Both write locally **and** synchronously push the same row(s) to master
  before returning success. If the master write fails, the local write is
  rolled back (trip deleted on entry; trip reopened + balance restored +
  transaction dropped on exit) and the request is rejected.
- The old 30-second batch push of `toll_trips` / `accounts` / `transactions`
  from local → master has been removed — those tables are now written to
  master in real time, not queued.
- A new setting, `ONLINE_ONLY_MODE`, controls this. It defaults to `True`
  everywhere except `manage.py test` runs (so the test suite doesn't need a
  reachable master).

**Not changed:** the periodic pull (master → local) of fare matrix, plazas,
tags, vehicles, accounts, and active trips — that stays on its existing
30-second cycle. The offline SQLite path (`OfflineExitService`,
`reconciliation_service.py`) was already disconnected from the live gate flow
and remains untouched.

---

## 2. Pre-requisites checklist

### Master server
- [ ] PostgreSQL installed and running, reachable from every booth's network
- [ ] `pg_hba.conf` allows connections from all 10 booth IPs/subnets
- [ ] `postgresql.conf` — `listen_addresses` includes the master's LAN interface
- [ ] Firewall — port 5432 open from booth subnets only (not the public internet)
- [ ] Latest migrations applied (`python manage.py migrate`)
- [ ] Plazas, toll lanes, and toll rates seeded (`Plaza`, `TollLane`, `TollRate`)

### Per booth (×10)
- [ ] Local PostgreSQL installed, running, schema migrated (same migrations as master)
- [ ] Network path to master's port 5432 confirmed (`psql -h <master_ip> -p 5432`)
- [ ] `.env` configured:
  - `DB_HOST=localhost`
  - `MASTER_DB_HOST=<master server IP>`
  - `DJANGO_SETTINGS_MODULE=config.settings.lan` (or `production` if TLS-fronted)
  - `ONLINE_ONLY_MODE` left unset (defaults to `True` outside tests — do not override)
- [ ] RFID reader, barrier serial port, and display configured in `rfid_config.ini`

---

## 3. Rollout sequence

Roll out incrementally, not all 10 booths at once — each step should be
verified before moving to the next.

1. **Master first.** Bring up the master server standalone, confirm migrations
   and seed data, confirm it's reachable from the network segment the booths
   will sit on.

2. **Pilot booth (Booth 1).**
   - Bring up local Postgres + Django, point `.env` at master.
   - Run `python manage.py run_gate` and confirm the log line
     `[sync] Background thread started` appears (sync agent auto-started).
   - Do a single entry scan. Confirm:
     - The trip appears in Booth 1's local `toll_trips`.
     - The same trip appears in master's `toll_trips` **immediately**
       (not after a 30s wait) — this confirms the dual-write path, not the
       batch sync.
   - Do the matching exit scan at Booth 1 (or a second pilot booth — see next
     step). Confirm balance deducted on both local and master, trip marked
     `completed` on both.

3. **Second pilot booth (Booth 2) — cross-plaza test.**
   - Bring up Booth 2 identically.
   - Entry at Booth 1, exit at Booth 2. Confirm the exit succeeds and charges
     the correct entry→exit fare — this is the scenario the whole dual-write
     change exists for.
   - Repeat with the exit fired within a few seconds of the entry (worst-case
     timing) to confirm the `master_pg` fallback lookup in
     `_find_active_trip()` covers it even before the next pull cycle.

4. **Negative-path test (do this before wider rollout).**
   - Temporarily block Booth 1's network path to master (firewall rule, or
     unplug the WAN link).
   - Attempt an entry — confirm it's rejected with
     `"No connection to master DB..."` and the barrier does **not** open.
   - Restore connectivity, confirm entries succeed again.
   - Simulate a master-side failure mid-transaction (e.g., stop Postgres on
     master right as a scan comes in, if a safe way to do this exists in your
     test environment) — confirm the local trip/balance is rolled back, not
     left in a half-committed state.

5. **Remaining booths (3–10).** Roll out in small batches (e.g., 2–3 at a
   time), repeating the single-booth verification from step 2 at each new
   site. Watch master DB connection count and load as booths come online.

6. **Go-live.** All 10 booths on `config.settings.lan`/`production`, sync
   agent confirmed running on each (`ps` / log check), master monitored.

---

## 4. Verification checklist (per booth, before sign-off)

- [ ] Entry scan succeeds, trip visible on master within the same request
- [ ] Exit scan succeeds, fare correctly deducted, trip closed on master
- [ ] Cross-plaza exit (entry at another booth) finds the trip and charges correctly
- [ ] Entry/exit rejected cleanly when master is unreachable (no crash, no
      partial write, barrier stays closed)
- [ ] Rejected transaction leaves no orphaned local trip or double-deducted balance
- [ ] Sync agent thread confirmed running (log line at booth startup)
- [ ] Daily report / `AdminStatsView` numbers match between a booth and master

---

## 5. Open questions / decisions needed

- **Entry-time balance check**: currently reads the account balance from the
  *local* DB, not master directly. Given dual-write keeps local fresh, this
  should be safe in practice, but a balance topped up at another booth/portal
  won't be visible locally until the next pull cycle (≤30s). Decide if this
  gap is acceptable or if the balance check should read from master directly.
- **Manual override on rejection**: the deployment spec mentions "manual
  override (with manager approval)" when master is unreachable — this isn't
  implemented. Decide if/how that should work operationally (e.g., a
  supervisor PIN that logs an override and lets a vehicle through without a
  transaction record, to be reconciled later).
- **`peak_multiplier` on `TollRate`**: still unused (not in any serializer,
  not applied in the fare calculation) — flagged in an earlier review, still
  open.

---

## 6. Rollback plan

If online-only mode causes problems in the field and you need to revert to
the previous (local-write + async batch sync) behavior without a code
rollback:

- Set `ONLINE_ONLY_MODE=False` in that booth's `.env` and restart.
- This skips the connectivity gate and the dual-write/rollback logic
  entirely, reverting to write-local-only behavior.
- Note: the removed periodic push of `toll_trips`/`accounts`/`transactions`
  is **not** restored by this env var — if you rely on the rollback for more
  than a short window, the async push functions would need to be restored in
  `push_service.py` (see git history) to avoid local-only data getting
  stranded.
