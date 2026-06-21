# Design: Topup Receipt Printing (POS / ESC-POS)

Date: 2026-06-18
Status: Approach decided — **Option B** (MewRf prints directly via CUPS `lp`)

## Problem

When a cash topup succeeds (from the QTag Topup handheld app → MewRf backend),
the backend should trigger a **receipt print** on the **same POS thermal printer**
already used by the toll system, producing a topup receipt.

## Existing printer working (quick-toll-system)

`quick-toll-system/src/app/api/printer/print-receipt/route.ts`:

- Builds **ESC/POS** byte stream for an **80mm** thermal printer (48 chars/line):
  init → center → header image (`public/receipt.png`, raster `GS v 0`) → title
  "Shahrah-e-Bhutto" → rows (`label … value`) → footer "Project by Malir
  Expressway Limited / Powered by iTecknologi Group" → full cut (`GS V 65 3`).
- Prints by writing the bytes to a temp file and running, on Linux/CUPS:
  ```
  lp -d POS80 -o raw "<tmpfile>"
  ```
  i.e. the printer is a CUPS printer named **`POS80`**. (There is no printer
  URL/API in `.env`; printing is the `lp` command + CUPS queue.)
- Exposed as a Next.js route `POST /api/printer/print-receipt` with payload
  types `receipt` (toll exit) and `entry_ticket`.

So "the same printer" = the CUPS `POS80` queue on the gate PC; "the same API" =
quick-toll-system's `print-receipt` endpoint.

## Goal

After a successful cash topup, print a **TOPUP RECEIPT** on `POS80`.

> **Only the print mechanism is reused** — i.e. the **same POS80 printer** + the
> ESC/POS-over-`lp` technique from quick-toll-system. The receipt **layout is
> topup-specific** (below); it is NOT the toll EXIT/ENTRY receipt (no toll fee,
> no change-due, no entry/exit plaza, no toll header/QR).

## Approaches

**Option A — Reuse quick-toll-system's print service (recommended — matches
"same API").**
- MewRf backend, after topup, makes an HTTP `POST` to quick-toll-system's
  printer endpoint (configurable: `PRINTER_API_URL`, e.g.
  `http://localhost:3000/api/printer/print-receipt`).
- Add a `topup` payload type to that route's ESC/POS builder (small cross-repo
  change in quick-toll-system) so the layout matches a topup receipt.
- Pros: one printer codebase (ESC/POS, header image, cut, CUPS). DRY.
- Cons: quick-toll-system must be running on the gate PC; change spans two repos.

**Option B — MewRf prints directly via CUPS `lp`. ✅ CHOSEN**
- Django builds the ESC/POS bytes itself and runs `lp -d POS80 -o raw <tmpfile>`
  via `subprocess` (replicating quick-toll-system's proven ESC/POS layout).
- Pros: self-contained — no dependency on quick-toll-system running.
- Cons: duplicates the ESC/POS logic in Python (one small module).

> Targets the **same physical printer** (`POS80`). No HTTP call to
> quick-toll-system; the MewRf backend must run on the gate PC where the `POS80`
> CUPS queue exists.

## Flow

```
QTag Topup app → POST /accounts/topup/cash/  (MewRf backend)
   ↓ (balance credited, TOPUP_CASH transaction created — already built)
   ↓ on success, fire receipt print (best-effort):
       Option A → POST PRINTER_API_URL { type:'topup', data:{…} }
       Option B → build ESC/POS → lp -d POS80 -o raw
   ↓
   response includes  printed: true|false  (so the app can show
   "Receipt printed" or offer "Reprint")
```

**Important:** printing is **best-effort and non-blocking** — the topup is
already committed (cash taken, balance added). A print failure MUST NOT fail the
topup or roll it back; it returns `printed: false` (+ logs) and the receipt can
be reprinted.

## Receipt content (topup — its own layout)

A dedicated topup receipt (80mm / 48 cols), distinct from the toll receipt:

```
          [ LOGO ]            <- ME / Malir Expressway logo (raster image)
        TOPUP RECEIPT
================================
Receipt #:        TX-7A4C9F
Date / Time: 18/06/2026 14:30:21
--------------------------------
Consumer:        Kashif Mughal
Vehicle Reg:           BP-3641
TID:    E2801105200070D4FB330A36
--------------------------------
Amount Added:        Rs.  500.00
Previous Balance:    Rs. 5000.00
New Balance:         Rs. 5500.00
Payment:                    CASH
Operator:                    ali
================================
       Thank you
 Malir Expressway Limited
 Powered by iTecknologi Group
          [cut]
```

Notes:
- Header is the **logo image** (ME / Malir Expressway) printed as an ESC/POS
  raster (`GS v 0`), centered — then **TOPUP RECEIPT**. (Not the toll
  "Shahrah-e-Bhutto / EXIT" text, no toll QR.)
- Shows **Amount Added + Previous + New balance** (topup-specific), `Payment: CASH`.
- `Receipt #` derived from the topup `Transaction.id`.
- Footer/branding adjustable.
- Data the backend passes to the printer: consumer name, vehicle reg, tid,
  amount, balance_before, balance_after, payment ('CASH'), operator name,
  receipt no., datetime.

### Logo → ESC/POS raster
- Provide a **monochrome / high-contrast PNG** of the logo at a configured path
  (e.g. `RECEIPT_LOGO_PATH`, default `apps/accounts/receipt_logo.png`).
- Backend converts it to a 1-bit raster (luminance threshold → bits → `GS v 0`),
  scaled to ~360–400 dots wide for 80mm — same technique as quick-toll-system's
  `portraitEscPos()`, implemented in Python with **Pillow (PIL)**.
- Thermal printers are 1-bit B/W: the **black "ME"** prints crisply; the
  **orange road** will threshold to black/white (may look faint). For best
  results supply a **black-on-white** version of the logo for the receipt.
- Cache the rasterized bytes after first build (logo rarely changes).

## Backend changes (MewRf)

- `CashTopupView` (`apps/accounts/views.py`): after the successful topup (both
  existing-topup and register+topup paths), call a `print_topup_receipt(...)`
  helper with the receipt data; wrap in try/except so failure only sets
  `printed=False`. Add `printed` to the response.
- New helper module `apps/accounts/printing.py` (Option B):
  - `print_topup_receipt(data)` → build ESC/POS bytes (logo raster + text rows +
    cut) → write temp file → `subprocess.run(['lp','-d', POS_PRINTER_NAME,'-o','raw', path])`.
  - `_logo_escpos()` → load `RECEIPT_LOGO_PATH` via Pillow, threshold to 1-bit,
    emit `GS v 0` raster; cache bytes.
- `requirements.txt`: add **Pillow** (logo rasterization).
- Settings/env:
  - `TOPUP_RECEIPT_PRINT_ENABLED` (bool, default False — dev/Windows without a
    printer won't error).
  - `POS_PRINTER_NAME` (default `POS80`).
  - `RECEIPT_LOGO_PATH` (default `apps/accounts/receipt_logo.png`).
- A receipt number: reuse the topup `Transaction.id` (short derived form, e.g.
  `TX-<first 6 of id>`).

## Optional: reprint

A `POST /accounts/topup/reprint/` (or a button in the app) to reprint the last
topup receipt for a TID — mirrors quick-toll-system's `receipts/reprint`. Phase 2.

## Out of scope

- Receipt image/branding redesign (reuse existing `receipt.png` + footer).
- Non-cash (JazzCash) topup receipts (separate; JazzCash spec is its own doc).
- Windows printing (gate PCs are Linux/CUPS; dev laptop won't print — gated by
  `TOPUP_RECEIPT_PRINT_ENABLED`).

## Decisions / open questions

1. ~~Option A or B?~~ → **Option B** (MewRf prints directly via `lp -d POS80`).
   The MewRf backend therefore runs on the gate PC that has the `POS80` CUPS
   printer (same machine as quick-toll-system's printer).
2. **Exact receipt fields/wording** — confirm the layout above (include CNIC?
   phone? plaza/booth id?). *(default: as shown — no CNIC/phone on the receipt.)*
3. **Reprint** needed in v1 or phase 2? *(default: phase 2.)*
```
