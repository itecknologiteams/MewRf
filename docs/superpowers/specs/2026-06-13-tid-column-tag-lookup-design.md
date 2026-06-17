# Design: Dedicated `tid` Column + Generated `tag_serial` + Gate Lookup by TID

Date: 2026-06-13
Status: Partially implemented

## Implementation status

- **DONE (2026-06-13):** Added the `tags.tid` column (nullable, unique, indexed)
  via migration `vehicles/0006_tag_tid.py`. `tag_serial` unchanged.
- **DONE (2026-06-14):** Gate lookup switched to `tid`:
  - `services.py` `EntryService`/`ExitService` now `Tag.objects.get(tid=…)`.
  - `run_anpr_gate.py` passes `tag.tid` (with a "no TID registered" guard).
  - Verified: seed tag `MTAG000001` (tid NULL) → "Tag not found"; test TID
    resolves to its vehicle.
- **DONE (2026-06-14):** Frontend single tag-add now captures `tid`:
  - `TagCreateView` accepts `tid` (normalized strip/upper, empty → NULL,
    uniqueness checked).
  - `api.ts addTag` sends `tid`; `Vehicles.tsx` add-tag form has a TID input.
  - Verified end-to-end (tag created via API with normalized tid).
- **DEFERRED (this doc, below):** generated `tag_serial`
  (`DDMMYYHHMM`+`XXXX`+lane); **CSV bulk upload** still maps its `TID` column to
  `tag_serial` (not `tid`); sync column updates; and the offline path (SQLite
  cache: `offline_exit_service.py`, `reconciliation_service.py`,
  `offline_cache.py`) still matches on `tag_serial`.
- **PENDING (external):** JazzCash topup API — user will provide 2 endpoints;
  wire `payments` app (JazzCashService/initiate/callback) to them when received.

## Problem

The RFID reader reads two values per tag: an **EPC** and a chip **TID**
(e.g. `TID: E28011052000704A8F9F0AE3`). Today the system has no `tid` column —
the scanned TID is stored in `tags.tag_serial`, and the gate identifies a tag by
matching the scanned TID against `tag_serial`.

We want:
1. The chip TID stored in its own `tags.tid` column and used as the gate's
   lookup key.
2. `tag_serial` to become a **system-generated issuance code**, not a
   hand-entered or chip-derived value.

## Goal

- Add `tags.tid` (chip TID). Gate (RFID + ANPR) identifies a tag by `tid`.
- Generate `tag_serial` at registration in the format **`DDMMYYHHMMXXXX` + lane**.

## Decisions (confirmed)

1. **Lookup key:** the gate matches a scanned tag on `tid`.
2. **`tag_serial` is system-generated** at registration — the admin no longer
   enters it. The admin provides only the **TID** (required) and **EPC**
   (optional).
3. **`tag_serial` format (left to right):** `DDMMYYHHMM` + `XXXX` + `LaneNumber`
   - `DDMMYYHHMM` — registration timestamp (day, month, 2-digit year, hour,
     minute), 10 chars.
   - `XXXX` — zero-padded sequence of tags issued in that same minute at this
     machine, reset each minute (`0001`, `0002`, …), 4 chars. *(Assumed default
     — confirm.)*
   - `LaneNumber` — the booth/lane number from the **registration machine's
     config** (see Settings). Variable length (typically 1–3 digits).
   - Total length ≈ 15–17 chars; fits `tag_serial varchar(24)`.
4. **Booth/lane source:** fixed per registration machine (config value), NOT
   chosen per request. Each registration machine must have a **distinct** lane
   number to keep serials globally unique across machines.
5. **No backfill of `tid`:** existing rows get `tid = NULL` and will not match at
   the gate until re-registered with their TID. Existing `tag_serial` values are
   left as-is.
6. **transactions.tag_serial:** unchanged. It keeps recording the scanned value
   (the TID). Out of scope to rename/repurpose.

## Data model

`apps/vehicles/models.py` — `Tag`:

```python
tid = models.CharField(max_length=24, null=True, blank=True, unique=True)
# tag_serial: unchanged type (varchar 24, unique, not null) — now populated by
# the generator, not user input.
```

- `tid`: `null=True` (existing rows + not-yet-registered tags), `unique=True`
  (chip TID is globally unique), indexed (looked up on every scan).
- Normalize `tid` on save/registration: strip spaces, uppercase (matches
  `run_gate`'s `tid_raw.replace(' ', '').upper()`).

Migration: add `tid` column + index. **No data backfill.**

## tag_serial generation

A single helper (e.g. `apps/vehicles/serial.py::generate_tag_serial()`):

1. `now = timezone.localtime()`; `prefix = now.strftime('%d%m%y%H%M')`.
2. `lane = settings.REGISTRATION_LANE_NUMBER` (from env/config; error clearly if
   unset).
3. `seq` = next sequence for `(prefix, lane)` — computed as
   `1 + count of tags whose tag_serial starts with <prefix> and ends with <lane>`
   in this minute; zero-pad to 4 (`XXXX`).
4. `tag_serial = f"{prefix}{seq:04d}{lane}"`.
5. Insert inside a transaction; on unique-violation, retry with `seq + 1`
   (handles concurrent issuance). Cap retries (e.g. 20) then error.

**Bulk CSV upload:** all rows share one `prefix`; the sequence increments across
the batch starting from the current max for `(prefix, lane)`.

## Gate lookup changes

- `apps/tolls/services.py`
  - `EntryService.process_entry` / `ExitService.process_exit`: tag fetch changes
    from `Tag.objects.get(tag_serial=…)` to `get(tid=<scanned>)`. The value the
    reader passes is already the normalized TID.
  - "Tag not found" behavior unchanged when no row has that `tid`.
- `apps/tolls/management/commands/run_anpr_gate.py:119`
  - `self._process_tag(tag.tag_serial)` → `self._process_tag(tag.tid)`.
  - If `tag.tid` is empty (not TID-registered), deny with a clear reason
    ("tag has no TID registered").

## Registration / inventory changes

- `apps/vehicles/views.py`
  - `TagCreateView`: accept `tid` (required) + `epc` (optional). Generate
    `tag_serial` via the helper. Validate `tid` uniqueness + normalize. Return
    `tag_serial`, `tid`, `epc`.
  - `TagInventoryUploadView` (CSV): columns are **`TID`** (required) and
    **`EPC`** (optional) — `tag_serial` is generated per row, not supplied.
    Duplicate check is on `tid`.
  - `AvailableTagsView`: include `tid`.
- `apps/vehicles/serializers.py`: add `tid` to the Tag serializer if present.

## Settings / config

- New setting `REGISTRATION_LANE_NUMBER` read from env (e.g.
  `REGISTRATION_LANE_NUMBER` in `.env`), surfaced in `config/settings/base.py`.
  Used as the booth/lane suffix in generated serials. Tag creation errors
  clearly if it is unset.

## Sync (production only — dev sync is disabled)

- `apps/tolls/sync/pull_service.py` `pull_tags` + push counterpart: add `tid` to
  the `SELECT`, `INSERT`, and `ON CONFLICT DO UPDATE` column lists.
- The master PostgreSQL needs the `tid` column (same migration).
- Current local dev (`SYNC_AGENT_ENABLED = False`) needs only the local
  migration.

## Frontend changes

- `rfid-frontend/src/services/api.ts`: create-tag payload sends `tid` (+ `epc`),
  no longer `tag_serial`; types include `tid`; show generated `tag_serial` and
  `tid` in responses.
- Tag add / vehicle registration forms: **TID** input (required), EPC optional;
  remove the manual tag_serial input (now generated/read-only display).
- Tag lists / available tags: display `tid` and the generated `tag_serial`.

## Out of scope

- Storing the scanned **EPC** from a live scan (separate request).
- Renaming/repurposing `transactions.tag_serial`.
- Backfilling existing tags' `tid`.
- RSSI frontend feature (deferred separately).

## Risks / notes

- **Cross-machine serial collision:** uniqueness relies on each registration
  machine having a **distinct** `REGISTRATION_LANE_NUMBER`. If two machines share
  a lane number, identical serials can be generated in the same minute and
  collide on the master after sync. Operations must assign unique lane numbers.
- **Existing tags stop matching** at the gate until re-registered with a TID
  (no-backfill decision). Seed/test tags are affected.
- **CSV format change:** uploads now provide `TID` (+ optional `EPC`); any
  `tag_serial`/serial column is ignored (generated server-side).
- `XXXX` semantics (per-minute sequence) is an assumed default — confirm before
  implementation.
- Repo is not under git, so this spec is saved but not committed.
