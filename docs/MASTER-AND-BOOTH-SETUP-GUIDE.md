# Master & Booth Setup Guide

Current as of the plaza_id / sync-service / fare-matrix work. Supersedes any
earlier copy of this file — the previous version predated the sync split and is
wrong in several places.

---

## 1. Architecture at a glance

**Master** (`192.168.78.200`) is the source of truth. It runs one process.

| Process | Command | Notes |
|---|---|---|
| `mtag-master` | `gunicorn config.wsgi` | API + admin portal. No gate, no sync agent. |

**Each booth** runs three, deliberately separated:

| Process | Command | Talks to | Purpose |
|---|---|---|---|
| `mtag-gate` | `manage.py run_gate` | **local DB only** | RFID reader → barrier. Zero replication logic. |
| `mtag-sync` | `manage.py sync_service` | local DB **+ master** | The *only* process that reaches master. |
| `mtag-web` | `manage.py runserver` | local DB only | Booth-local API. |

The point of the split: if master is unreachable, `mtag-sync` retries and backs
off while `mtag-gate` keeps the lane open off local data. The gate never writes
to master.

### Data flow

```
       Entry booth                  MASTER                   Exit booth
       ───────────                  ──────                   ──────────
 1. trip created locally
 2.        ──push──▶            open trip
 3.                             open trip   ──pull──▶   local copy
 4.                                                     charges the fare,
                                                        closes trip locally
 5.                             ◀──push──                closed trip
 6.        ◀──pull──            closed trip ──pull──▶    every booth learns
                                                         the trip is closed
```

Step 6 matters more than it looks: without it a completed trip stays `active` in
every other booth's DB forever, which blocks that vehicle's **next entry**.

### What each booth mode syncs

`GATE_MODE` in `.env` selects the passes. It is picked up automatically by
`mtag-sync` — there is nothing else to enable, and no setting turns syncing on
or off; the `mtag-sync` process running IS the switch:

| Pass | entry | exit |
|---|---|---|
| reference (plazas, lanes, **vehicle_categories**, **fare_matrix**, tags, **tag_assignments**, users, vehicles, accounts) | ✓ | ✓ |
| closed trips | ✓ | ✓ |
| **open trips** | — | ✓ |
| push (trips, transactions, balances, tags, tag history) | ✓ | ✓ |

An entry booth still pulls reference data — without tags/vehicles/accounts it
cannot validate anyone. Open trips are the only real difference.

---

## 2. Order of operations

**Master must be fully set up before any booth.** A booth's pull selects
`plaza_id`, `vehicle_categories` and `fare_matrix` from master; and once master
migrates, un-updated booths break because `Plaza.code` no longer exists.
Do master and all booths in one maintenance window.

```
master:  deploy → migrate → load_plazas → load_fares → verify
booths:  deploy (one booth first) → verify → remaining booths
then:    rebuild + deploy the frontend
```

---

## 3. Master setup

```bash
# from your dev machine
./deploy_master.sh
```

Set at the top of the script first: `MASTER_IP`, `SSH_USER`, `DB_NAME`
(`master_tag_db`), `DB_PASSWORD`, and `CORS_ORIGINS` if the portal is served
from another origin.

`master_bootstrap.sh` then, on master: installs the venv, generates `.env`
(**preserving an existing `SECRET_KEY`** — rotating it logs every operator out),
creates the DB, runs `migrate`, `collectstatic`, and starts PM2.

It deliberately differs from the booth script in three ways:

- **Never truncates** `plazas`/`lanes`/`rates`/`tags`. The booth script clears
  those so the sync agent can refill them *from* master; doing it here wipes the
  network.
- Sets **`ANPR_GATE_ENABLED=False`** (master has no reader). Note this does NOT
  control syncing — master never syncs simply because it does not run the
  `mtag-sync` process. Syncing is not gated by any setting.
- Warns if Postgres `listen_addresses` is loopback-only — booths push to master's
  Postgres over the LAN, so without this every booth push fails.

### 3a. Load the plazas (master only)

```bash
python manage.py load_plazas                        # dry run
python manage.py load_plazas --apply --drop-legacy --lanes 4
```

| plaza_id | shown as | name |
|---|---|---|
| 1 | 001 | Shahfaisal Main Toll Plaza |
| 2 | 002 | Kathor Main Toll Plaza |
| 101 | 101 | Shafaisal-1 Interchange |
| 102 | 102 | Shafaisal-2 Interchange |
| 103 | 103 | Korangi 1 Interchange |
| 104 | 104 | Korangi 2 Interchange |
| 105 | 105 | Quaidabad Interchange |
| 106 | 106 | Quaidabad Interchange |
| 107 | 107 | Mai Niyari |

`plaza_id` is an **integer** — the leading zeros in `001` are display-only.
Booth config uses the integer (`PLAZA_ID=1`).

`--drop-legacy` removes the old Malir plazas. Migration 0007 renumbers any
pre-existing plaza into a **9000+ legacy range** first, so they can never collide
with `001`/`002`. The command refuses to drop anything a real trip references.

**Never run `load_plazas` on a booth.** Booths receive plazas through the sync
service; loading locally invents rows with different UUIDs and the first pull
collides.

### 3b. Load the fares (master only)

```bash
python manage.py load_fares                     # dry run
python manage.py load_fares --apply             # real tariff
python manage.py load_fares --apply --flat 100  # testing only
```

Fares live in two tables, not in code:

- `vehicle_categories` — `category_index`, `code`, `name`, `description`,
  `is_active`, timestamps
- `fare_matrix` — `from_plaza`, `to_plaza`, `category_index`, `fare`, timestamps

| index | code | class | Fare (PKR) |
|---|---|---|---|
| 1 | `car` | Car / Jeep / Taxi / Pickup | 100 |
| 2 | `wagon` | Wagon / Hiace | 150 |
| 3 | `coach` | Coach / Coaster / Mini Bus | 200 |
| 4 | `large_bus` | Large Bus | 250 |
| 5 | `truck_2axle` | 2 Axle Truck | 350 |
| 6 | `truck_3axle` | 3 Axle Truck | 350 |
| 7 | `truck_4axle` | 4+ Axle Truck | 450 |

**Pricing model: a single tariff.** The fares above are charged for every plaza
pair, in both directions, regardless of distance — 9 x 9 x 7 = **567** rows.

**Same-plaza trips are charged too.** A vehicle entering and exiting at the same
plaza pays the same fare as any other trip, so the matrix includes A->A rows.
Without them the exit is refused with "Toll rate not configured for this route".

If the notification's Column 4 (Full Length Facility) applies to this road, a
trip crossing Quaidabad should cost more and is currently **under-billed**. Fill
in `FULL_LENGTH` and `SEGMENT` in `apps/tolls/fare_registry.py` and `load_fares`
switches to distance-banded pricing automatically — no code change. Filling only
one of the two is rejected, so a half-configured tariff can never go live.

Operators can edit fares afterwards in Django admin → **Fare matrix**; saving
clears the 10-minute fare cache so the change applies to the next vehicle.

### 3c. Verify master

```bash
python manage.py migrate --check          # exits non-zero if anything unapplied
python manage.py showmigrations tolls vehicles | tail
python manage.py shell -c "
from apps.tolls.models import Plaza, FareMatrix
from apps.vehicles.models import VehicleCategory
print('plazas    :', Plaza.objects.count())
print('categories:', VehicleCategory.objects.count())
print('fares     :', FareMatrix.objects.count())"
```

Expect 9 plazas, 7 categories, and 9×9×7 = **567** fare rows once real fares load.

---

## 4. Booth setup

### 4a. Set the per-booth values in `deploy_booth.sh`

| Variable | Notes |
|---|---|
| `BOOTH_IP`, `SSH_USER`, `SSH_PORT` | SSH target |
| `PLAZA_ID` | **integer** from the table above. Wrong value tolls the wrong plaza. |
| `GATE_MODE` | `entry` or `exit`. Not inferrable from the booth number. |
| `LANE_NUMBER` | must exist at that plaza (`load_plazas --lanes N` created 1..N) |
| `READER_IP`, `DISPLAY_IP`, `BARRIER_PORT` | hardware |
| `MASTER_IP`, `MASTER_DB_*`, `DB_*` | database wiring |

### 4b. Deploy

```bash
./deploy_booth.sh
```

`booth_bootstrap.sh` builds the venv, installs the vendored RFID SDK, writes
`.env` and `rfid_config.ini`, creates the local DB, migrates, clears
cloned-image leftovers (only when the booth has no trips), and starts all three
PM2 processes.

### 4c. Mode is declared in two files — keep them in step

| File | Key | Drives |
|---|---|---|
| `rfid_config.ini` | `mode` | what the gate does |
| `.env` | `GATE_MODE` | which sync passes run |

`booth_bootstrap.sh` writes both from one `$GATE_MODE`, so a scripted deploy is
always consistent. A hand-edit to one desyncs them, and the failure is silent:
an exit lane whose sync runs in entry mode never pulls open trips, so **every
exiting vehicle is refused with "No active trip found."** `run_gate` prints a
loud `MODE MISMATCH` error at startup if they disagree.

### 4d. Verify each booth

```bash
pm2 status                            # mtag-web, mtag-gate, mtag-sync all online
pm2 logs mtag-sync --lines 30         # "[sync] Agent started — mode=entry|exit"
pm2 logs mtag-gate  --lines 30        # plaza resolves, reader connects, no MODE MISMATCH

python manage.py sync_service --once  # one verbose cycle; non-zero exit if a push held
python manage.py trip_sync            # DRIFT must be 0
python manage.py migrate --check
```

`sync_service --once` is the important one — it fails loudly if any push held its
watermark, meaning those rows are **not** on master.

---

## 5. Troubleshooting

| Symptom | Cause |
|---|---|
| `Tag not found` on every scan | `tags.tid` is null. The gate matches on `tid` only. Check `SELECT COUNT(*) FROM tags WHERE tid IS NULL OR tid=''`. |
| `Toll rate not configured for this route` | No `fare_matrix` row for that plaza pair + category. Run `load_fares` on master, then re-sync the booth. |
| `No active trip found` at an exit | Exit booth in entry mode (`GATE_MODE`), so open trips are never pulled. |
| `Vehicle already has an active trip` on a valid entry | Closed-trip pull isn't reaching this booth. Run `trip_sync` and check DRIFT. |
| `relation "vehicles" already exists` during migrate | DB was restored from `sql/schema.sql` and has no `django_migrations` rows. Needs `migrate --fake-initial` once. |
| `[push] <table> FAILED, watermark held` | Push failed; rows are **not** on master and will retry. Investigate — this is money. |
| `duplicate key ... plazas_plaza_id_key` on first pull | Booth has pre-seeded plazas with different UUIDs. Bootstrap clears these automatically when the booth has no trips. |

---

## 6. Tag history

`tag_assignments` records which vehicle each tag was fitted to and for how long —
one row per installation period. For any tag you can see the vehicle it is in
now (`removed_at IS NULL`), which vehicle it was in before, when it came off and
why, and where it went next.

Written automatically on registration and on tag reissue, visible in Django
admin under **Tag assignments**, and synced both ways so a swap done at a booth
reaches master.

```sql
SELECT tag_serial, plate_number, assigned_at, removed_at, removed_reason
FROM tag_assignments WHERE tag_serial = 'MTAG000002' ORDER BY assigned_at DESC;
```

---

## 7. Editing fares

Two places, both backed by `fare_matrix` — the same table `ExitService` charges
from, so what you see is what a vehicle pays:

- **Portal** → Plazas & Rates → the fare table (From Plaza / To Plaza / Category
  / Fare). Categories come from `/tolls/vehicle-categories/`.
- **Django admin** → Fare matrix, with inline-editable `fare`.

Either path clears the 10-minute fare cache on save, so a change applies to the
next vehicle rather than up to 10 minutes later.

The legacy `toll_rates` table is retained for history but is **read-only in
admin** and nothing prices from it.

---

## 8. Known gaps

- **Single tariff, no distance banding.** Every plaza pair is charged the same
  fare per category (§3b). If Column 4 of the notification applies, long trips
  are under-billed until `FULL_LENGTH` + `SEGMENT` are filled in.
- **`tags.tid` is nullable** but is the sole gate lookup key. A tag without one
  cannot open a barrier anywhere. Check with:
  `SELECT COUNT(*) FROM tags WHERE tid IS NULL OR tid = '';`
- **Master is a single point of failure for *sync*, not for the lane.** Booths
  keep running during a master outage; replication just backs up.
- **Balance replication is last-writer-wins.** Two booths charging the same
  account inside one sync interval can lose a deduction — `transactions` is the
  durable record, so reconcile balances from it if the two ever disagree.
- **Nothing has been run end-to-end.** Every check in this guide is worth doing
  on the first booth before rolling out the rest.
