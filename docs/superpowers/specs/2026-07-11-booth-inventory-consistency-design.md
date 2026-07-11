# Design: Booth/Inventory UI Consistency + Topup-App Logic Parity

**Date:** 2026-07-11
**Status:** Approved (pending spec review)
**Related:** Phase 2 Booth Operations Integration (`docs/PHASE-2-IMPLEMENTATION-PLAN.md`)

---

## Problem

The **Inventory Management** and **Booth Assignment** admin pages (plus `InventoryActivationModal` and `InventoryCheckWarning`) diverge from the rest of the RFID frontend in three ways:

1. **UI** — they use a `min-h-screen bg-gray-50 p-6` wrapper with hardcoded light-mode Tailwind colors (`bg-white`, `text-gray-900`, `bg-blue-600`) and native HTML controls. Every other page (e.g. `TopupPage`) uses a content-width wrapper, CSS-variable design tokens (`var(--bg-surface)`, `var(--accent-*)`, `var(--text-primary)`), `rounded-xl` cards, and works in dark mode. `DashboardLayout` already provides page padding, so these pages double-pad and paint their own full-screen gray background.

2. **Auth/API layer (a real bug)** — these pages call `fetch()` directly with `Authorization: Bearer ${localStorage.getItem('token')}`. The app authenticates via **httpOnly cookies** through a shared `apiFetch` helper (`credentials: 'include'`, auto token-refresh on 401). There is no `token` in localStorage, so these pages send no valid auth and 401.

3. **Logic** — the activation modal uses a bespoke "Quick Create / Link Existing (account search)" flow with a `payment_method` selector and a separate `/vehicles/inventory/activate*` endpoint set. The field-device **topup app** does register-or-topup as one atomic, cash-only, TID-keyed call. The booth/inventory activation should use that same logic.

## Goals

- Booth/Inventory pages visually and behaviorally match the rest of the app (design tokens, layout, dark mode).
- All calls route through the shared `api.ts` service layer (httpOnly-cookie auth).
- Tag registration + topup in the booth/inventory activation uses the **same logic as the topup app**, while **preserving** the Phase-2 booth features (booth-mismatch validation, activation-booth audit, inventory status).

## Non-Goals

- No separate live-scan (RFID reader) uploader on the web; bulk tag seeding stays as the existing CSV upload.
- No change to the Flutter scanner/topup apps.
- No redesign of unrelated pages.

---

## Reference: how the topup app works (source of truth for parity)

Cookie/session auth (no bearer token). Two endpoints, keyed by **chip TID**:

- `POST /accounts/topup/lookup/` — body `{tid}` → `{found, tid, epc, consumer_name, cnic, phone, plate, balance}`.
- `POST /accounts/topup/cash/` — body `{tid, amount, epc, consumer_name, cnic, phone, vehicle_reg}` → `{registered, new_balance}` (+ a `receipt` object). **One call** tops up a registered tag OR registers owner+vehicle+account and activates the tag with `amount` as opening balance.

Field conventions to carry into the web:
- `amount` sent as a **string**.
- `cnic` sent **digits-only** (dashes are UI-only; auto-format `XXXXX-XXXXXXX-X`).
- Lookup returns `plate`; the cash request field is `vehicle_reg`.
- Cash only — no payment-method field.
- Validation: `amount > 0` required; if not found, `consumer_name` + `phone` + `vehicle_reg` required, CNIC optional; if found, consumer fields are read-only echoes.

`CashTopupView` already handles an inventory tag: on register it finds the `Tag` by TID, assigns the new `Vehicle`, sets `status=ACTIVE`, creates `Account` + a `TOPUP`/`TOPUP_CASH` `Transaction`, and returns a receipt. It does **not** currently do booth-mismatch validation, update `UnregisteredInventory`, or write `TagActivation`.

---

## Chosen approach: extend the topup endpoints to be booth-aware (Approach A)

Add an **optional** `activation_booth_id` to the topup endpoints rather than enhancing the parallel `/vehicles/inventory/activate*` endpoints. Rationale: parity is guaranteed because the web uses the *same* endpoint as the topup app; `CashTopupView` already register+activates, so we only bolt on inventory/booth bookkeeping; and we avoid duplicating register+topup logic in two places (the root cause of the drift). The Flutter apps are unaffected — they simply omit `activation_booth_id`, so no booth checks run (identical to today).

Rejected — Approach B (enhance `/vehicles/inventory/activate/` to copy topup logic): keeps two register+topup code paths that will drift again.

---

## Design

### 1. Backend — booth-aware topup (`apps/accounts/views.py`)

**`CashTopupView`** — accept optional `activation_booth_id`:
- In the register/inventory branch, when the TID matches an `UnregisteredInventory` row:
  - If `inv.status == activated` → `400` "Tag already activated."
  - If `inv.booth_assigned_id` is set and `!= activation_booth_id` → `400` "Tag assigned to Booth X, not Booth Y."
  - After the vehicle/account/tag/transaction are created: set `inv.status = activated`, `inv.activated_for_account`, `inv.first_activated_booth_id = activation_booth_id`, `inv.first_activated_at = now`; create a `TagActivation` audit row (`activation_type='auto_created'`, `first_scan_booth_id=activation_booth_id`).
- All of the above only runs when `activation_booth_id` is provided AND an inventory row exists; otherwise behavior is exactly as today (keeps Flutter apps working).
- Whole operation stays inside the existing `db_transaction.atomic()` block.

**`TopupLookupView`** — optionally include the inventory tag's `status` and `booth_assigned_id` in the response so the UI can show a pre-submit warning (`InventoryCheckWarning`) on booth mismatch.

**Endpoints deprecated (left in place, unused by web):** `/vehicles/inventory/activate/`, `/vehicles/inventory/activate-existing/`. Removal is out of scope for this change.

Permissions unchanged: `IsOperator` already admits `admin` and `operator`.

### 2. Frontend service layer (`rfid-frontend/src/services/`)

- In `api.ts`, add topup methods (extend `accountsApi` or add `topupApi`):
  - `topupLookup(tid: string)` → `POST /accounts/topup/lookup/`.
  - `cashTopup(payload)` → `POST /accounts/topup/cash/` with `{tid, amount, epc, consumer_name, cnic, phone, vehicle_reg, activation_booth_id?}`. `epc` is optional on the web (the inventory list items don't carry it); send `''` and the backend keeps the tag's stored `epc`.
- Rewrite `inventoryApi.ts` to use `apiFetch` (httpOnly cookies, auto-refresh, `ApiError`) instead of `fetch` + `localStorage.getItem('token')`. This covers inventory list, CSV upload, assign-booth, and inventory check. Removing the manual Bearer header fixes the 401s.

### 3. Activation modal (`InventoryActivationModal.tsx`) — mirror the topup app

Replace the two-tab (Quick Create / Link Existing) UI with the topup app's single TID-driven flow:
- On open, prefill from the selected inventory tag's TID and call `topupLookup`.
- **Found** → consumer fields (name/phone/CNIC/plate) shown read-only; show current balance; enter amount only. Quick-amount presets (500 / 1000 / 2000 / 5000) as on `TopupPage`.
- **Not found** → editable `consumer_name`, `phone`, `vehicle_reg` (required) and `cnic` (optional, auto-format, digits-only on send); enter amount.
- **Cash only** — remove the CASH/CARD/TRANSFER selector.
- Submit → `cashTopup({... , activation_booth_id})`.
- On success → render a **receipt** card (receipt_no, datetime, consumer, vehicle_reg, tid, amount, balance_before/after, payment=CASH, operator) from the backend `receipt` object, styled like the `TopupPage` success receipt.
- "Link existing" is not lost: the backend reuses an existing owner by phone during registration.

`activation_booth_id` continues to come from the page context/selected booth exactly as in Phase 2.

### 4. UI restyle — `InventoryManagement.tsx`, `BoothAssignmentPage.tsx`, `InventoryActivationModal.tsx`, `InventoryCheckWarning.tsx`

- Remove the `min-h-screen bg-gray-50 p-6` wrapper; use a content-width container consistent with other pages (rely on `DashboardLayout` padding).
- Replace hardcoded colors with design tokens: `var(--bg-surface)`, `var(--bg-elevated)`, `var(--border-custom)`, `var(--text-primary|secondary|tertiary)`, `var(--accent-blue|emerald|amber|rose)`. Result works in light and dark mode.
- Match app patterns: icon + title header, `rounded-xl` cards, `shadow-sm`, token-styled inputs/selects/buttons, status badges via token accent colors, consistent table header/row/pagination styling (mirror `Vehicles.tsx`/`TopupPage.tsx`).

---

## Data flow: activate an inventory tag at a booth

```
Operator selects an unregistered/booth-assigned inventory tag (has tag_serial + tid)
  │
  ├─ Modal opens → topupLookup(tid)
  │     ├─ found=true  → prefill read-only consumer + balance; ask amount
  │     └─ found=false → editable consumer fields + vehicle_reg + cnic; ask amount
  │           (if lookup reports booth mismatch → show InventoryCheckWarning)
  │
  └─ Submit → cashTopup({tid, amount, epc, consumer_name, cnic, phone, vehicle_reg, activation_booth_id})
        ├─ backend: booth-mismatch check (if inventory tag + booth id) → 400 on mismatch
        ├─ register owner+vehicle+account (or topup existing) + TOPUP_CASH txn
        ├─ mark inventory activated + first_activated_booth_id + TagActivation audit
        └─ 200/201 {registered, new_balance, receipt} → modal shows receipt card
```

## Error handling

- All frontend calls surface `ApiError.message` through the existing toast system.
- Backend validation errors (amount ≤ 0, missing consumer fields, duplicate plate 409, booth mismatch 400, already-activated 400) return the standard `{success:false, message, errors}` envelope, rendered by `apiFetch`'s error extraction.
- 401 triggers the existing auto token-refresh; on failure, the app's `auth:expired` flow runs.

## Testing

- **Backend:** extend `apps/vehicles/tests_inventory.py` / accounts tests — booth-mismatch 400; successful booth activation flips inventory status + writes `TagActivation`; register-or-topup unchanged when `activation_booth_id` omitted (Flutter-app regression guard); already-activated rejected.
- **Frontend:** manual/e2e — lookup found vs not-found; register+topup; existing-tag topup; booth-mismatch warning; receipt render; dark-mode visual parity on both pages.

## Rollout / risk

- Additive, backward-compatible backend change (optional field) → no Flutter-app impact.
- Restyle is presentational; auth-layer switch is the highest-value fix (unbreaks the pages).
