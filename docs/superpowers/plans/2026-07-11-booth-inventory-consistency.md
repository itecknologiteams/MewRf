# Booth/Inventory Consistency + Topup-App Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Inventory Management and Booth Assignment pages match the rest of the RFID frontend (design tokens, layout, dark mode), route their calls through the shared cookie-auth `apiFetch`, and make booth/inventory tag activation reuse the topup app's register-or-topup logic while preserving Phase-2 booth features.

**Architecture:** Extend the existing topup endpoints (`/accounts/topup/lookup/`, `/accounts/topup/cash/`) with an optional `activation_booth_id` so `CashTopupView` also does booth-mismatch validation, flips `UnregisteredInventory` status, and writes a `TagActivation` audit — additive and backward-compatible so the Flutter apps are unaffected. Frontend gets typed `accountsApi.topupLookup/cashTopup` methods, `inventoryApi` is rewritten onto `apiFetch`, and the activation modal + both pages are restyled to CSS-variable design tokens.

**Tech Stack:** Django REST Framework (backend), React + TypeScript + Vite + Tailwind (frontend). Backend tests: Django `TestCase` + DRF `APIClient`. Frontend gate: `npm run build` (`tsc -b && vite build`) + `npm run lint` (no unit-test runner in this project).

## Global Constraints

- Backend response envelope is always `{success: bool, message: str, data: any, errors?}` via `utils.response.success_response` / `error_response`. Copy this shape exactly.
- Auth is **httpOnly cookies** — frontend calls use `apiFetch` (`credentials: 'include'`); never add `Authorization: Bearer` headers or read `localStorage.getItem('token')`.
- `VITE_API_URL` already includes the `/api/v1` suffix (`http://localhost:8000/api/v1`). `apiFetch` prepends it; pass endpoints like `/accounts/topup/cash/` (leading slash, no `/api/v1`).
- Money: `amount` is sent/received as a **string**; CNIC is sent **digits-only** (dashes are UI formatting only).
- Design tokens only in restyled UI: `var(--bg-body|surface|elevated)`, `var(--border-custom)`, `var(--text-primary|secondary|tertiary)`, `var(--accent-blue|emerald|amber|rose)`. No hardcoded `bg-gray-*`, `bg-white`, `text-gray-*`, `bg-blue-*`.
- Booth ids are 1–7 (plaza ids). Backend permission `IsOperator` already admits `admin` and `operator`.
- Backend tests run from `mtag_backend/` with: `./venv/Scripts/python.exe manage.py test <path> -v 2` (default settings module `config.settings.local`).
- `print_topup_receipt(receipt)` is best-effort and returns `False` when no printer is present — it never raises and must never fail the topup.

---

## File Structure

**Backend (`mtag_backend/`):**
- Modify: `apps/accounts/views.py` — `CashTopupView` (booth-aware), `TopupLookupView` (echo inventory status).
- Modify (tests): `apps/vehicles/tests_inventory.py` — new `BoothTopupActivationTest` class.

**Frontend (`rfid-frontend/src/`):**
- Modify: `services/api.ts` — export `apiFetch` + `BASE_URL`; add `accountsApi.topupLookup` / `accountsApi.cashTopup` + types.
- Rewrite: `services/inventoryApi.ts` — onto `apiFetch`; `list` / `checkStatus` / `assignBooth` / `upload`; drop `activateQuick` / `activateExisting` / `searchAccounts`.
- Rewrite: `components/InventoryActivationModal.tsx` — topup-app flow + tokens + receipt.
- Restyle: `components/InventoryCheckWarning.tsx` — tokens.
- Restyle + switch to `inventoryApi`: `pages/InventoryManagement.tsx`, `pages/BoothAssignmentPage.tsx`.

---

## Task 1: Backend — make `CashTopupView` booth-aware

**Files:**
- Modify: `mtag_backend/apps/accounts/views.py:57-204` (`CashTopupView.post`)
- Test: `mtag_backend/apps/vehicles/tests_inventory.py` (add `BoothTopupActivationTest`)

**Interfaces:**
- Consumes: existing helpers `_norm_tid`, `_receipt_no`, `print_topup_receipt`; models `Account`, `Transaction`, `TransactionType`, `TransactionStatus`, `TransactionSource` (already imported); `apps.vehicles.models.{Tag, TagStatus, Vehicle, UnregisteredInventory, UnregisteredInventoryStatus, TagActivation}`; `apps.users.models.User`.
- Produces: `POST /accounts/topup/cash/` now accepts optional `activation_booth_id` (int). When present AND the TID matches an `UnregisteredInventory` row, it validates the booth, creates the `Tag` with the inventory's `tag_serial`, marks the inventory `activated`, and writes a `TagActivation`. Response `data` gains a `receipt` object. Behavior is unchanged when `activation_booth_id` is omitted.

- [ ] **Step 1: Write the failing tests**

Add to the end of `mtag_backend/apps/vehicles/tests_inventory.py`. First ensure the import line at top includes `Tag`:

Change the existing import (line 8 area) from:
```python
from .models import UnregisteredInventory, UnregisteredInventoryStatus, TagActivation
```
to:
```python
from .models import UnregisteredInventory, UnregisteredInventoryStatus, TagActivation, Tag
```

Then append this class:
```python
class BoothTopupActivationTest(TestCase):
    """Booth-aware cash topup: register + activate an inventory tag at a booth."""

    def setUp(self):
        self.client = APIClient()
        self.operator = User.objects.create_user(
            phone='03001234567', password='testpass123', full_name='Op',
            user_role=UserRole.OPERATOR,
        )
        self.client.force_authenticate(user=self.operator)
        self.inv = UnregisteredInventory.objects.create(
            tag_serial='SER900', tid='TID900', vehicle_type='car',
            status=UnregisteredInventoryStatus.BOOTH_ASSIGNED, booth_assigned_id=2,
        )

    def _payload(self, **over):
        base = {
            'tid': 'TID900', 'amount': '500', 'consumer_name': 'Ali',
            'phone': '03007778888', 'vehicle_reg': 'LEB1234', 'activation_booth_id': 2,
        }
        base.update(over)
        return base

    def test_booth_mismatch_rejected(self):
        resp = self.client.post('/api/v1/accounts/topup/cash/',
                                self._payload(activation_booth_id=5), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Booth 2', resp.json()['message'])
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, UnregisteredInventoryStatus.BOOTH_ASSIGNED)

    def test_activation_success_marks_inventory_and_audit(self):
        resp = self.client.post('/api/v1/accounts/topup/cash/',
                                self._payload(), format='json')
        self.assertEqual(resp.status_code, 201)
        data = resp.json()['data']
        self.assertTrue(data['registered'])
        self.assertIn('receipt', data)
        self.assertEqual(data['receipt']['vehicle_reg'], 'LEB1234')
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, UnregisteredInventoryStatus.ACTIVATED)
        self.assertEqual(self.inv.first_activated_booth_id, 2)
        self.assertTrue(TagActivation.objects.filter(
            tag_serial='SER900', first_scan_booth_id=2).exists())
        # Tag row created with the inventory's printed serial (not a generated one)
        self.assertTrue(Tag.objects.filter(tag_serial='SER900', tid='TID900').exists())

    def test_already_activated_rejected(self):
        self.inv.status = UnregisteredInventoryStatus.ACTIVATED
        self.inv.save(update_fields=['status'])
        resp = self.client.post('/api/v1/accounts/topup/cash/',
                                self._payload(), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_no_booth_id_preserves_flutter_behavior(self):
        # No activation_booth_id and a TID not in inventory → plain register, untouched inventory
        resp = self.client.post('/api/v1/accounts/topup/cash/',
                                self._payload(tid='TID901', vehicle_reg='LEB9999',
                                              activation_booth_id=None), format='json')
        self.assertEqual(resp.status_code, 201)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, UnregisteredInventoryStatus.BOOTH_ASSIGNED)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `mtag_backend/`):
```bash
./venv/Scripts/python.exe manage.py test apps.vehicles.tests_inventory.BoothTopupActivationTest -v 2
```
Expected: FAIL — `test_booth_mismatch_rejected` returns 201 instead of 400; `test_activation_success_marks_inventory_and_audit` finds inventory still `booth_assigned` and no `TagActivation`; `receipt` key missing from `data`.

- [ ] **Step 3: Add booth parsing + inventory lookup near the top of `CashTopupView.post`**

In `apps/accounts/views.py`, in `CashTopupView.post`, extend the imports line (currently `from apps.vehicles.models import Tag, TagStatus, Vehicle`) to:
```python
        from apps.vehicles.models import (
            Tag, TagStatus, Vehicle, UnregisteredInventory,
            UnregisteredInventoryStatus, TagActivation,
        )
```

Immediately after the existing `plate_raw = (request.data.get('vehicle_reg') or '').strip()` line, add:
```python
        booth_id = request.data.get('activation_booth_id')
        try:
            booth_id = int(booth_id) if booth_id is not None else None
        except (ValueError, TypeError):
            booth_id = None
```

After the existing `tag = (Tag.objects.select_related(...).filter(tid=tid).first())` line, add:
```python
        inv = UnregisteredInventory.objects.filter(tid=tid).first()
        do_booth = booth_id is not None and inv is not None
        if do_booth:
            if inv.status == UnregisteredInventoryStatus.ACTIVATED:
                return error_response("Tag already activated.", status_code=400)
            if inv.booth_assigned_id and inv.booth_assigned_id != booth_id:
                return error_response(
                    f"Tag assigned to Booth {inv.booth_assigned_id}, not Booth {booth_id}.",
                    status_code=400,
                )
```

- [ ] **Step 4: Create the Tag with the inventory serial, and record inventory activation**

In the register branch (the `else:` after the existing-registered-tag block), find the tag-creation section:
```python
                if tag:  # inventory tag — assign + activate
                    tag.vehicle = vehicle
                    if epc:
                        tag.epc = epc
                    tag.status = TagStatus.ACTIVE
                    tag.save()
                else:    # brand-new tag — create with a generated serial
```
Change the `else:` to `elif do_booth:` handling first, so the block reads:
```python
                if tag:  # existing Tag row found by tid — assign + activate
                    tag.vehicle = vehicle
                    if epc:
                        tag.epc = epc
                    tag.status = TagStatus.ACTIVE
                    tag.save()
                elif do_booth:  # inventory tag — create Tag with its printed serial
                    tag = Tag.objects.create(
                        tag_serial=inv.tag_serial, tid=tid, epc=epc, vehicle=vehicle,
                        expiry_date=date(2099, 12, 31), status=TagStatus.ACTIVE,
                    )
                else:    # brand-new tag — create with a generated serial
```
(Leave the generated-serial body that follows unchanged.)

Then, immediately after the `txn = Transaction.objects.create(...)` call in the register branch (right before the `logger.info("Cash topup + register ...` line), add:
```python
                if do_booth:
                    inv.status = UnregisteredInventoryStatus.ACTIVATED
                    inv.activated_for_account = account
                    inv.first_activated_booth_id = booth_id
                    inv.first_activated_at = timezone.now()
                    inv.save(update_fields=[
                        'status', 'activated_for_account',
                        'first_activated_booth_id', 'first_activated_at',
                    ])
                    TagActivation.objects.get_or_create(
                        tag_serial=inv.tag_serial,
                        defaults=dict(
                            tid=tid, first_scan_booth_id=booth_id,
                            created_account=account, activation_type='auto_created',
                        ),
                    )
```

- [ ] **Step 5: Return the receipt object to the client**

Change the final return section (currently):
```python
        # ── Topup committed. Print receipt best-effort (never fails the topup). ─
        resp_data['printed'] = print_topup_receipt(receipt)
        return success_response(data=resp_data, message=resp_msg, status_code=resp_status)
```
to:
```python
        # ── Topup committed. Print receipt best-effort (never fails the topup). ─
        resp_data['printed'] = print_topup_receipt(receipt)
        resp_data['receipt'] = receipt
        return success_response(data=resp_data, message=resp_msg, status_code=resp_status)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```bash
./venv/Scripts/python.exe manage.py test apps.vehicles.tests_inventory.BoothTopupActivationTest -v 2
```
Expected: PASS (4 tests OK).

- [ ] **Step 7: Run the full inventory + accounts suites to check for regressions**

Run:
```bash
./venv/Scripts/python.exe manage.py test apps.vehicles apps.accounts -v 1
```
Expected: PASS (no regressions).

- [ ] **Step 8: Commit**

```bash
git add mtag_backend/apps/accounts/views.py mtag_backend/apps/vehicles/tests_inventory.py
git commit -m "feat(backend): make cash topup booth-aware for inventory activation"
```

---

## Task 2: Backend — `TopupLookupView` echoes inventory status

**Files:**
- Modify: `mtag_backend/apps/accounts/views.py:26-54` (`TopupLookupView.post`)
- Test: `mtag_backend/apps/vehicles/tests_inventory.py` (add to `BoothTopupActivationTest`)

**Interfaces:**
- Consumes: `apps.vehicles.models.UnregisteredInventory`.
- Produces: `POST /accounts/topup/lookup/` — when `found=False` and the TID matches an inventory row, the response `data` additionally includes `inventory_status` (str) and `booth_assigned_id` (int|null).

- [ ] **Step 1: Write the failing test**

Append this method to `BoothTopupActivationTest` in `tests_inventory.py`:
```python
    def test_lookup_reports_inventory_status(self):
        resp = self.client.post('/api/v1/accounts/topup/lookup/',
                                {'tid': 'TID900'}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertFalse(data['found'])
        self.assertEqual(data['inventory_status'], 'booth_assigned')
        self.assertEqual(data['booth_assigned_id'], 2)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
./venv/Scripts/python.exe manage.py test apps.vehicles.tests_inventory.BoothTopupActivationTest.test_lookup_reports_inventory_status -v 2
```
Expected: FAIL with `KeyError: 'inventory_status'`.

- [ ] **Step 3: Add inventory info to the not-found branch**

In `TopupLookupView.post`, change the final not-found return (currently):
```python
        # Not registered (unknown tag, or unassigned inventory tag) → register flow.
        return success_response(data={'found': False, 'tid': tid, 'epc': tag.epc if tag else ''})
```
to:
```python
        # Not registered (unknown tag, or unassigned inventory tag) → register flow.
        from apps.vehicles.models import UnregisteredInventory
        data = {'found': False, 'tid': tid, 'epc': tag.epc if tag else ''}
        inv = UnregisteredInventory.objects.filter(tid=tid).first()
        if inv is not None:
            data['inventory_status'] = inv.status
            data['booth_assigned_id'] = inv.booth_assigned_id
        return success_response(data=data)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
./venv/Scripts/python.exe manage.py test apps.vehicles.tests_inventory.BoothTopupActivationTest.test_lookup_reports_inventory_status -v 2
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mtag_backend/apps/accounts/views.py mtag_backend/apps/vehicles/tests_inventory.py
git commit -m "feat(backend): topup lookup echoes inventory status + assigned booth"
```

---

## Task 3: Frontend — add `topupLookup` / `cashTopup` to `accountsApi`

**Files:**
- Modify: `rfid-frontend/src/services/api.ts`

**Interfaces:**
- Consumes: existing module-private `apiFetch`, `accountsApi`.
- Produces: exported `apiFetch` and `BASE_URL` (for Task 4); `accountsApi.topupLookup(tid)` → `TopupLookupResult`; `accountsApi.cashTopup(payload)` → `CashTopupResult`; exported interfaces `TopupLookupResult`, `CashTopupResult`.

- [ ] **Step 1: Export `apiFetch` and `BASE_URL`**

In `api.ts`, change the first line:
```typescript
const BASE_URL = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000/api/v1';
```
to:
```typescript
export const BASE_URL = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000/api/v1';
```
and change the core wrapper declaration:
```typescript
async function apiFetch<T>(endpoint: string, options: RequestInit = {}, isRetry = false): Promise<T> {
```
to:
```typescript
export async function apiFetch<T>(endpoint: string, options: RequestInit = {}, isRetry = false): Promise<T> {
```

- [ ] **Step 2: Add topup types + methods**

Directly above `export const accountsApi = {`, add:
```typescript
export interface TopupLookupResult {
  found: boolean;
  tid: string;
  epc: string;
  consumer_name?: string;
  cnic?: string;
  phone?: string;
  plate?: string;
  balance?: string;
  inventory_status?: 'unregistered' | 'booth_assigned' | 'activated';
  booth_assigned_id?: number | null;
}

export interface CashTopupReceipt {
  receipt_no: string;
  datetime: string;
  consumer_name: string;
  vehicle_reg: string;
  tid: string;
  amount: string;
  balance_before: string;
  balance_after: string;
  payment: string;
  operator: string;
}

export interface CashTopupResult {
  registered: boolean;
  consumer_name: string;
  plate?: string;
  amount_added: string;
  new_balance: string;
  printed?: boolean;
  receipt?: CashTopupReceipt;
}
```

Inside the `accountsApi` object (after the existing `plateTopup` method), add:
```typescript
  topupLookup: (tid: string) =>
    apiFetch<TopupLookupResult>('/accounts/topup/lookup/', {
      method: 'POST',
      body: JSON.stringify({ tid }),
    }),

  cashTopup: (payload: {
    tid: string;
    amount: string;
    epc?: string;
    consumer_name?: string;
    cnic?: string;
    phone?: string;
    vehicle_reg?: string;
    activation_booth_id?: number;
  }) =>
    apiFetch<CashTopupResult>('/accounts/topup/cash/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
```

- [ ] **Step 3: Type-check**

Run (from `rfid-frontend/`):
```bash
npx tsc -b --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add rfid-frontend/src/services/api.ts
git commit -m "feat(frontend): add accountsApi.topupLookup + cashTopup (cookie auth)"
```

---

## Task 4: Frontend — rewrite `inventoryApi` onto `apiFetch`

**Files:**
- Rewrite: `rfid-frontend/src/services/inventoryApi.ts`

**Interfaces:**
- Consumes: `apiFetch`, `BASE_URL` from `./api` (Task 3).
- Produces: `inventoryApi.list(params)` → `InventoryListResult`; `inventoryApi.checkStatus(tagSerial)` → `InventoryCheckResponse`; `inventoryApi.assignBooth(payload)` → `{ assigned: number }`; `inventoryApi.upload(file)` → `{ added: number; skipped: number; errors: string[] }`; exported interfaces `InventoryItem`, `InventoryListResult`, `InventoryCheckResponse`. Removes `activateQuick`, `activateExisting`, `searchAccounts`.

- [ ] **Step 1: Replace the whole file**

Replace the entire contents of `rfid-frontend/src/services/inventoryApi.ts` with:
```typescript
import { apiFetch, BASE_URL } from './api';

export interface InventoryItem {
  id: string;
  tag_serial: string;
  tid: string;
  vehicle_plate: string;
  vehicle_type: string;
  status: 'unregistered' | 'booth_assigned' | 'activated';
  booth_assigned_id?: number;
  first_activated_booth_id?: number;
  created_at: string;
}

export interface InventoryListResult {
  items: InventoryItem[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface InventoryCheckResponse {
  found: boolean;
  status: 'unregistered' | 'booth_assigned' | 'activated' | 'not_in_inventory';
  booth_assigned_id?: number;
  first_activated_booth_id?: number;
  vehicle_plate?: string;
  vehicle_type?: string;
  can_activate?: boolean;
  activation_required?: boolean;
}

export interface InventoryListParams {
  page?: number;
  per_page?: number;
  search?: string;
  status?: string;
  booth_assigned_id?: string | number;
  vehicle_type?: string;
}

export const inventoryApi = {
  list: (params: InventoryListParams = {}) => {
    const qs = new URLSearchParams();
    if (params.page) qs.append('page', String(params.page));
    if (params.per_page) qs.append('per_page', String(params.per_page));
    if (params.search) qs.append('search', params.search);
    if (params.status) qs.append('status', params.status);
    if (params.booth_assigned_id) qs.append('booth_assigned_id', String(params.booth_assigned_id));
    if (params.vehicle_type) qs.append('vehicle_type', params.vehicle_type);
    return apiFetch<InventoryListResult>(`/vehicles/inventory/?${qs.toString()}`);
  },

  checkStatus: (tagSerial: string) =>
    apiFetch<InventoryCheckResponse>(
      `/vehicles/inventory/check/${encodeURIComponent(tagSerial)}/`,
    ),

  assignBooth: (payload: { inventory_ids: string[]; booth_id: number; assigned_by?: string }) =>
    apiFetch<{ assigned: number }>('/vehicles/inventory/assign-booth/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Multipart upload: apiFetch always sets JSON Content-Type, so use raw fetch
  // with credentials so the httpOnly auth cookie is sent (matches vehiclesApi.uploadTagInventory).
  upload: async (file: File): Promise<{ added: number; skipped: number; errors: string[] }> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BASE_URL}/vehicles/inventory/upload/`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    });
    const json = await res.json();
    if (!res.ok) {
      throw new Error(json.message || 'Upload failed');
    }
    return json.data;
  },
};
```

- [ ] **Step 2: Type-check (expect errors in consumers — that is fine, they're fixed in Tasks 5–7)**

Run (from `rfid-frontend/`):
```bash
npx tsc -b --noEmit
```
**Gate is file-scoped.** The repo has PRE-EXISTING type errors unrelated to this task that will remain until later tasks: `InventoryActivationModal.tsx` (uses removed methods — fixed in Task 5), `InventoryManagement.tsx` / `BoothAssignmentPage.tsx` / `InventoryCheckWarning.tsx` (pre-existing `addToast` 2-arg + unused-import errors — fixed in Tasks 6/7/8), and `Reports.tsx:408` (unrelated pre-existing debt, out of scope — will remain after this whole branch). The only requirement for THIS task: **no error line references `inventoryApi.ts`**. Verify with:
```bash
npx tsc -b --noEmit 2>&1 | grep "inventoryApi.ts" || echo "inventoryApi.ts clean"
```
Expected: `inventoryApi.ts clean`. (Do not commit yet — proceed to Task 5, which fixes the modal, then commit Tasks 4+5 together in Task 5 Step 5.)

- [ ] **Step 3: Verify no other files import the removed methods**

Run (from repo root):
```bash
grep -rn "activateQuick\|activateExisting\|searchAccounts" rfid-frontend/src
```
Expected: matches only in `components/InventoryActivationModal.tsx` (fixed next task).

---

## Task 5: Frontend — rewrite `InventoryActivationModal` (topup-app flow + tokens + receipt)

**Files:**
- Rewrite: `rfid-frontend/src/components/InventoryActivationModal.tsx`

**Interfaces:**
- Consumes: `accountsApi.topupLookup`, `accountsApi.cashTopup`, `CashTopupResult` (Task 3); `useToast`.
- Produces: same component props as before — `{ tag: { tag_serial: string; tid: string; vehicle_plate?: string; vehicle_type?: string; booth_assigned_id?: number }, activationBoothId: number, onSuccess: (result: CashTopupResult) => void, onClose: () => void }` — so the existing call site in `TollOperations.tsx:792` needs no changes.

- [ ] **Step 1: Replace the whole file**

Replace the entire contents of `rfid-frontend/src/components/InventoryActivationModal.tsx` with:
```tsx
import { useState, useEffect } from 'react';
import { X, Loader2, User, Phone, CreditCard, CheckCircle, Wallet } from 'lucide-react';
import { useToast } from '@/context/ToastContext';
import { accountsApi, type CashTopupResult, type TopupLookupResult } from '@/services/api';

interface InventoryActivationModalProps {
  tag: {
    tag_serial: string;
    tid: string;
    vehicle_plate?: string;
    vehicle_type?: string;
    booth_assigned_id?: number;
  };
  activationBoothId: number;
  onSuccess: (result: CashTopupResult) => void;
  onClose: () => void;
}

const PRESETS = [500, 1000, 2000, 5000];

// Format digits into CNIC XXXXX-XXXXXXX-X (UI only; digits-only sent to API).
const formatCnic = (raw: string) => {
  const d = raw.replace(/\D/g, '').slice(0, 13);
  if (d.length <= 5) return d;
  if (d.length <= 12) return `${d.slice(0, 5)}-${d.slice(5)}`;
  return `${d.slice(0, 5)}-${d.slice(5, 12)}-${d.slice(12)}`;
};

export default function InventoryActivationModal({
  tag,
  activationBoothId,
  onSuccess,
  onClose,
}: InventoryActivationModalProps) {
  const { addToast } = useToast();

  const [looking, setLooking] = useState(true);
  const [found, setFound] = useState(false);
  const [balance, setBalance] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [cnic, setCnic] = useState('');
  const [vehicleReg, setVehicleReg] = useState('');
  const [amount, setAmount] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [receipt, setReceipt] = useState<CashTopupResult | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const r: TopupLookupResult = await accountsApi.topupLookup(tag.tid);
        if (!active) return;
        setFound(r.found);
        if (r.found) {
          setName(r.consumer_name ?? '');
          setPhone(r.phone ?? '');
          setCnic(r.cnic ? formatCnic(r.cnic) : '');
          setVehicleReg(r.plate ?? '');
          setBalance(r.balance ?? '0');
        }
      } catch {
        if (active) addToast({ type: 'error', title: 'Lookup failed', message: 'Could not look up the tag.' });
      } finally {
        if (active) setLooking(false);
      }
    })();
    return () => { active = false; };
  }, [tag.tid, addToast]);

  const submit = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      addToast({ type: 'error', title: 'Validation', message: 'Enter a valid amount greater than zero.' });
      return;
    }
    if (!found && (!name.trim() || !phone.trim() || !vehicleReg.trim())) {
      addToast({ type: 'error', title: 'Validation', message: 'Name, phone and vehicle registration are required to register.' });
      return;
    }
    setSubmitting(true);
    try {
      const result = await accountsApi.cashTopup({
        tid: tag.tid,
        amount: String(parseFloat(amount)),
        epc: '',
        consumer_name: name.trim(),
        cnic: cnic.replace(/\D/g, ''),
        phone: phone.trim(),
        vehicle_reg: vehicleReg.trim(),
        activation_booth_id: activationBoothId,
      });
      setReceipt(result);
      addToast({ type: 'success', title: result.registered ? 'Registered & Activated' : 'Topped Up', message: `New balance PKR ${parseFloat(result.new_balance).toLocaleString()}.` });
      setTimeout(() => onSuccess(result), 1800);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Activation failed';
      addToast({ type: 'error', title: 'Failed', message });
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls =
    'w-full px-3 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all disabled:opacity-60';

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-2xl max-w-md w-full shadow-xl">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-[var(--border-custom)]">
          <div>
            <h2 className="text-lg font-bold text-[var(--text-primary)]">Activate Tag</h2>
            <p className="text-sm text-[var(--text-secondary)] mt-0.5 font-mono">{tag.tag_serial}</p>
          </div>
          <button
            onClick={onClose}
            disabled={submitting || !!receipt}
            className="p-1.5 rounded-lg text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors disabled:opacity-50"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6">
          {looking ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="animate-spin text-[var(--accent-blue)]" size={28} />
            </div>
          ) : receipt ? (
            <div className="animate-fade-in-up">
              <div className="flex flex-col items-center text-center mb-4">
                <div className="w-12 h-12 rounded-full bg-[var(--accent-emerald)]/10 flex items-center justify-center mb-2">
                  <CheckCircle className="text-[var(--accent-emerald)]" size={28} />
                </div>
                <p className="font-semibold text-[var(--text-primary)]">
                  {receipt.registered ? 'Registered & Activated' : 'Topped Up'}
                </p>
              </div>
              {receipt.receipt && (
                <div className="space-y-2 text-sm bg-[var(--bg-elevated)] rounded-xl p-4">
                  {([
                    ['Receipt', receipt.receipt.receipt_no],
                    ['Consumer', receipt.receipt.consumer_name],
                    ['Vehicle', receipt.receipt.vehicle_reg],
                    ['Amount', `PKR ${parseFloat(receipt.receipt.amount).toLocaleString()}`],
                    ['New Balance', `PKR ${parseFloat(receipt.receipt.balance_after).toLocaleString()}`],
                  ] as [string, string][]).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">{k}</span>
                      <span className="font-medium text-[var(--text-primary)]">{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {found ? (
                <div className="flex items-center justify-between bg-[var(--bg-elevated)] rounded-xl px-4 py-3">
                  <div>
                    <p className="font-semibold text-[var(--text-primary)]">{name}</p>
                    <p className="text-xs text-[var(--text-secondary)]">{phone} · {vehicleReg}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider">Balance</p>
                    <p className="font-bold text-[var(--accent-emerald)]">
                      PKR {parseFloat(balance ?? '0').toLocaleString()}
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div>
                    <label className="block text-sm font-medium text-[var(--text-primary)] mb-1"><User size={14} className="inline mr-1.5" />Customer Name</label>
                    <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" disabled={submitting} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--text-primary)] mb-1"><Phone size={14} className="inline mr-1.5" />Phone</label>
                    <input className={inputCls} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="03001234567" disabled={submitting} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--text-primary)] mb-1"><CreditCard size={14} className="inline mr-1.5" />CNIC (optional)</label>
                    <input className={inputCls} value={cnic} onChange={(e) => setCnic(formatCnic(e.target.value))} placeholder="XXXXX-XXXXXXX-X" disabled={submitting} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">Vehicle Registration</label>
                    <input className={`${inputCls} uppercase`} value={vehicleReg} onChange={(e) => setVehicleReg(e.target.value)} placeholder="LEB1234" disabled={submitting} />
                  </div>
                </>
              )}

              <div>
                <label className="block text-sm font-medium text-[var(--text-primary)] mb-1"><Wallet size={14} className="inline mr-1.5" />Amount (Cash)</label>
                <input className={inputCls} type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="500" disabled={submitting} />
                <div className="flex gap-2 flex-wrap mt-2">
                  {PRESETS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setAmount(String(p))}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                        amount === String(p)
                          ? 'bg-[var(--accent-emerald)] text-white border-[var(--accent-emerald)]'
                          : 'bg-[var(--bg-elevated)] border-[var(--border-custom)] text-[var(--text-secondary)] hover:border-[var(--accent-emerald)] hover:text-[var(--accent-emerald)]'
                      }`}
                    >
                      +{p.toLocaleString()}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button onClick={onClose} disabled={submitting} className="flex-1 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-custom)] text-[var(--text-primary)] text-sm font-medium rounded-xl hover:bg-[var(--bg-surface)] transition-colors disabled:opacity-50">Cancel</button>
                <button onClick={submit} disabled={submitting} className="flex-1 py-2.5 bg-[var(--accent-blue)] text-white text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2">
                  {submitting && <Loader2 className="animate-spin" size={16} />}
                  {found ? 'Top Up' : 'Register & Activate'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check (file-scoped)**

Run (from `rfid-frontend/`):
```bash
npx tsc -b --noEmit 2>&1 | grep -E "inventoryApi.ts|InventoryActivationModal.tsx" || echo "task files clean"
```
Expected: `task files clean`. (Pre-existing errors remain in `InventoryManagement.tsx`/`BoothAssignmentPage.tsx`/`InventoryCheckWarning.tsx` — fixed in Tasks 6/7/8 — and in the unrelated `Reports.tsx:408`; those are out of scope for this task.)

- [ ] **Step 3: Lint**

Run:
```bash
npm run lint
```
Expected: no new errors in `inventoryApi.ts` or `InventoryActivationModal.tsx`.

- [ ] **Step 4: Manual verification**

Start the frontend (`npm run dev`) and backend, log in as admin, go to Toll Operations, and scan/enter a booth-assigned inventory tag to open the modal. Confirm: lookup runs; for a new tag the register fields show; presets set the amount; submitting shows the receipt card; a wrong-booth tag shows the backend "Booth X, not Booth Y" error via toast. Confirm the modal reads correctly in both light and dark mode (theme toggle in the top bar).

- [ ] **Step 5: Commit (Tasks 4 + 5 together)**

```bash
git add rfid-frontend/src/services/inventoryApi.ts rfid-frontend/src/components/InventoryActivationModal.tsx
git commit -m "feat(frontend): activation modal uses topup-app flow via cookie-auth api"
```

---

## Task 6: Frontend — restyle `InventoryManagement` + route through `inventoryApi`

**Files:**
- Modify: `rfid-frontend/src/pages/InventoryManagement.tsx`

**Interfaces:**
- Consumes: `inventoryApi.list`, `inventoryApi.upload` (Task 4); `useToast`.
- Produces: no exported interface change (default-exported page component).

- [ ] **Step 1: Replace the data layer (remove raw fetch + fake auth)**

At the top, add the import:
```typescript
import { inventoryApi } from '@/services/inventoryApi';
```
Delete the `const API_BASE = ...` line. **Also remove the unused `user`**: delete the line `const { user } = useAuth();` and the `import { useAuth } from '@/context/AuthContext';` line (both are unused and currently cause `TS6133`).

**Important — `addToast` signature:** this project's `addToast` takes a single object `{ type, title, message? }` (see `TopupPage.tsx`), NOT `(message, level)`. The existing inventory code uses the wrong 2-arg form (a pre-existing `TS2554` error). Use the object form everywhere below.

Replace the body of `fetchInventory` with:
```typescript
  const fetchInventory = async (page = 1) => {
    try {
      setLoading(true);
      const data = await inventoryApi.list({
        page,
        per_page: 50,
        search: search || undefined,
        status: statusFilter !== 'All' ? statusFilter.toLowerCase() : undefined,
        booth_assigned_id: boothFilter !== 'All' ? boothFilter : undefined,
        vehicle_type: typeFilter !== 'All' ? typeFilter.toLowerCase() : undefined,
      });
      setInventory(data.items);
      setCurrentPage(data.page);
      setTotalPages(data.pages);
    } catch (err: any) {
      addToast({ type: 'error', title: 'Error', message: err.message || 'Failed to fetch inventory' });
    } finally {
      setLoading(false);
    }
  };
```
Replace the body of `handleUpload` with:
```typescript
  const handleUpload = async () => {
    if (!uploadFile) {
      addToast({ type: 'error', title: 'Validation', message: 'Please select a file' });
      return;
    }
    try {
      setIsUploading(true);
      setUploadResult(null);
      const data = await inventoryApi.upload(uploadFile);
      setUploadResult(data);
      addToast({ type: 'success', title: 'Uploaded', message: `${data.added} tags added successfully` });
      setUploadFile(null);
      setTimeout(() => {
        setShowUploadModal(false);
        fetchInventory(1);
      }, 2000);
    } catch (err: any) {
      addToast({ type: 'error', title: 'Upload Failed', message: err.message || 'Upload failed' });
    } finally {
      setIsUploading(false);
    }
  };
```

- [ ] **Step 2: Replace the outer wrapper**

Change the root return wrapper from:
```tsx
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
```
to:
```tsx
    <div className="animate-fade-in-up">
      <div className="max-w-7xl mx-auto">
```
(and leave the closing `</div></div>` as-is). The upload modal keeps its own `fixed inset-0` overlay.

- [ ] **Step 3: Apply the design-token color mapping across the file**

Apply these exact replacements to **every** occurrence in the JSX (header, filters card, stat cards, table, pagination, and the upload modal panel). This is a find-and-replace of hardcoded classes with tokens:

| Find (hardcoded) | Replace (token) |
|---|---|
| `bg-white` | `bg-[var(--bg-surface)]` |
| `bg-gray-50` (as a surface, e.g. pagination footer / hover) | `bg-[var(--bg-elevated)]` |
| `bg-gray-100` (table head / secondary btn) | `bg-[var(--bg-elevated)]` |
| `bg-gray-200` (buttons) | `bg-[var(--bg-elevated)]` |
| `hover:bg-gray-200` / `hover:bg-gray-300` / `hover:bg-gray-50` | `hover:bg-[var(--bg-elevated)]` |
| `text-gray-900` | `text-[var(--text-primary)]` |
| `text-gray-800` | `text-[var(--text-primary)]` |
| `text-gray-700` | `text-[var(--text-secondary)]` |
| `text-gray-600` | `text-[var(--text-secondary)]` |
| `text-gray-400` (icons) | `text-[var(--text-tertiary)]` |
| `border-gray-300` / `border-b` / `border-t` (neutral borders) | `border-[var(--border-custom)]` |
| `bg-blue-600` + `hover:bg-blue-700` (primary btn) | `bg-[var(--accent-blue)]` + `hover:opacity-90` |
| `text-blue-600` / `text-blue-700` | `text-[var(--accent-blue)]` |
| `focus:ring-blue-500` | `focus:ring-[var(--accent-blue)]/20 focus:border-[var(--accent-blue)]` |
| `text-green-700` / `text-green-600` / `text-green-400` | `text-[var(--accent-emerald)]` |
| `shadow` (cards) | `shadow-sm` |
| `rounded-lg` (cards/inputs) | `rounded-xl` |

For the status badges, replace the `statusColors` map with token-based classes:
```typescript
const statusColors: Record<string, string> = {
  unregistered: 'bg-[var(--bg-elevated)] text-[var(--text-secondary)]',
  booth_assigned: 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]',
  activated: 'bg-[var(--accent-emerald)]/10 text-[var(--accent-emerald)]',
};
```

- [ ] **Step 4: Type-check (file-scoped) + lint**

Run (from `rfid-frontend/`):
```bash
npx tsc -b --noEmit 2>&1 | grep "InventoryManagement.tsx" || echo "InventoryManagement.tsx clean"
npm run lint
```
Expected: `InventoryManagement.tsx clean` (all its prior `TS2554`/`TS6133` errors gone), and lint clean for this file. Do NOT run `npm run build` yet — it runs `tsc -b` over the whole project and still fails on the unrelated pre-existing `Reports.tsx:408`, which is out of scope for this branch. Also verify no hardcoded-color classes remain:
```bash
grep -nE "bg-white|bg-gray-|text-gray-|bg-blue-|text-blue-|text-green-" src/pages/InventoryManagement.tsx || echo "no hardcoded colors"
```
Expected: `no hardcoded colors`.

- [ ] **Step 5: Manual verification**

`npm run dev`, log in as admin, open **Inventory Management**. Confirm the page renders inside the dashboard chrome (no full-page gray band, single padding), the table loads (auth works — no 401), filters/upload work, and it looks correct in light AND dark mode.

- [ ] **Step 6: Commit**

```bash
git add rfid-frontend/src/pages/InventoryManagement.tsx
git commit -m "style(frontend): inventory management uses design tokens + cookie-auth api"
```

---

## Task 7: Frontend — restyle `BoothAssignmentPage` + route through `inventoryApi`

**Files:**
- Modify: `rfid-frontend/src/pages/BoothAssignmentPage.tsx`

**Interfaces:**
- Consumes: `inventoryApi.list`, `inventoryApi.assignBooth` (Task 4); `useToast`.
- Produces: no exported interface change.

- [ ] **Step 1: Replace the data layer**

Add import:
```typescript
import { inventoryApi } from '@/services/inventoryApi';
```
Delete the `const API_BASE = ...` line. **Also remove the unused `X` import** (from the `lucide-react` import list — it currently causes `TS6133`).

**Important — `addToast` signature:** use the single-object form `{ type, title, message? }` (NOT `(message, level)`), same as Task 6. The existing 2-arg calls in this file are pre-existing `TS2554` errors; also convert the two validation toasts already in `handleAssign` (`'Please select at least one item'`, `'Please select a booth'`) to the object form.

Replace `fetchUnregisteredInventory` body with:
```typescript
  const fetchUnregisteredInventory = async (page = 1) => {
    try {
      setLoading(true);
      const data = await inventoryApi.list({ page, per_page: 50, status: 'unregistered' });
      setInventory(data.items);
      setCurrentPage(data.page);
      setTotalPages(data.pages);
    } catch (err: any) {
      addToast({ type: 'error', title: 'Error', message: err.message || 'Failed to fetch inventory' });
    } finally {
      setLoading(false);
    }
  };
```
Replace the whole body of `handleAssign` with:
```typescript
  const handleAssign = async () => {
    if (selectedItems.size === 0) {
      addToast({ type: 'error', title: 'Validation', message: 'Please select at least one item' });
      return;
    }
    if (!selectedBooth) {
      addToast({ type: 'error', title: 'Validation', message: 'Please select a booth' });
      return;
    }
    try {
      setIsAssigning(true);
      const data = await inventoryApi.assignBooth({
        inventory_ids: Array.from(selectedItems),
        booth_id: parseInt(selectedBooth),
      });
      addToast({ type: 'success', title: 'Assigned', message: `${data.assigned} tags assigned to Booth ${selectedBooth}` });
      setSelectedItems(new Set());
      setSelectedBooth('');
      fetchUnregisteredInventory(1);
    } catch (err: any) {
      addToast({ type: 'error', title: 'Assignment Failed', message: err.message || 'Assignment failed' });
    } finally {
      setIsAssigning(false);
    }
  };
```

- [ ] **Step 2: Replace the outer wrapper**

Change:
```tsx
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
```
to:
```tsx
    <div className="animate-fade-in-up">
      <div className="max-w-7xl mx-auto">
```

- [ ] **Step 3: Apply the same design-token mapping as Task 6 Step 3**

Apply the identical find/replace table from Task 6 Step 3 to every hardcoded class in this file, including: the header title/subtitle, the three stat cards, the action bar (booth `<select>` + Assign button), the table (header row, checkboxes, selected-row highlight, cells), and pagination. For the selected-row highlight, change `bg-blue-50` → `bg-[var(--accent-blue)]/10` and the row hover `hover:bg-gray-50` → `hover:bg-[var(--bg-elevated)]`. For the "Selected" stat number `text-blue-700` → `text-[var(--accent-blue)]`.

- [ ] **Step 4: Type-check (file-scoped) + lint**

Run (from `rfid-frontend/`):
```bash
npx tsc -b --noEmit 2>&1 | grep "BoothAssignmentPage.tsx" || echo "BoothAssignmentPage.tsx clean"
npm run lint
grep -nE "bg-white|bg-gray-|text-gray-|bg-blue-|text-blue-|bg-blue-50|text-green-" src/pages/BoothAssignmentPage.tsx || echo "no hardcoded colors"
```
Expected: `BoothAssignmentPage.tsx clean`, lint clean, `no hardcoded colors`. Do NOT run `npm run build` (it still fails on the unrelated pre-existing `Reports.tsx:408`, out of scope).

- [ ] **Step 5: Manual verification**

`npm run dev`, log in as admin, open **Booth Assignment**. Confirm list loads (no 401), selecting rows + a booth and clicking Assign works, and the page matches the app style in light AND dark mode.

- [ ] **Step 6: Commit**

```bash
git add rfid-frontend/src/pages/BoothAssignmentPage.tsx
git commit -m "style(frontend): booth assignment uses design tokens + cookie-auth api"
```

---

## Task 8: Frontend — restyle `InventoryCheckWarning`

**Files:**
- Rewrite: `rfid-frontend/src/components/InventoryCheckWarning.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces: same props `{ status: 'booth_mismatch' | 'not_assigned' | 'activation_required' | null; boothAssignedId?: number; currentBoothId: number }` — call site in `TollOperations.tsx:780` unchanged.

- [ ] **Step 1: Replace the whole file**

Replace the entire contents with:
```tsx
import { AlertTriangle, Info } from 'lucide-react';

interface InventoryCheckWarningProps {
  status: 'booth_mismatch' | 'not_assigned' | 'activation_required' | null;
  boothAssignedId?: number;
  currentBoothId: number;
}

export default function InventoryCheckWarning({
  status,
  boothAssignedId,
  currentBoothId,
}: InventoryCheckWarningProps) {
  if (!status) return null;

  const warnings = {
    booth_mismatch: {
      icon: AlertTriangle,
      title: 'Booth Mismatch',
      message: `This tag is assigned to Booth ${boothAssignedId}, not Booth ${currentBoothId}. It cannot be activated at this booth.`,
      accent: 'var(--accent-rose)',
    },
    not_assigned: {
      icon: AlertTriangle,
      title: 'Not Assigned',
      message: `This tag has not been assigned to any booth yet. Please assign it first from the Booth Assignment page.`,
      accent: 'var(--accent-amber)',
    },
    activation_required: {
      icon: Info,
      title: 'Activation Required',
      message: `This tag is assigned to your booth but has not been activated yet. Please complete the activation.`,
      accent: 'var(--accent-blue)',
    },
  };

  const warning = warnings[status];
  if (!warning) return null;

  const Icon = warning.icon;

  return (
    <div
      className="p-4 rounded-xl border flex gap-3 bg-[var(--bg-surface)] shadow-sm"
      style={{ borderColor: warning.accent }}
    >
      <Icon className="flex-shrink-0" size={20} style={{ color: warning.accent }} />
      <div>
        <h4 className="font-semibold" style={{ color: warning.accent }}>{warning.title}</h4>
        <p className="text-sm text-[var(--text-secondary)]">{warning.message}</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check (file-scoped) + lint**

This task removes the unused `AlertCircle` import (`TS6133`) by replacing the whole file. Run (from `rfid-frontend/`):
```bash
npx tsc -b --noEmit 2>&1 | grep "InventoryCheckWarning.tsx" || echo "InventoryCheckWarning.tsx clean"
npm run lint
```
Expected: `InventoryCheckWarning.tsx clean` and lint clean. (After this task the ONLY remaining project type error is the unrelated pre-existing `Reports.tsx:408`, which is out of scope for this branch — confirm with `npx tsc -b --noEmit 2>&1` that every other error line is gone.)

- [ ] **Step 3: Manual verification**

In Toll Operations, trigger a booth-mismatch scan and confirm the warning card renders with the rose accent and is readable in light AND dark mode.

- [ ] **Step 4: Commit**

```bash
git add rfid-frontend/src/components/InventoryCheckWarning.tsx
git commit -m "style(frontend): inventory check warning uses design tokens"
```

---

## Self-Review

**Spec coverage:**
- Spec §1 UI consistency → Tasks 5, 6, 7, 8 (wrapper removal + token mapping + dark mode). ✓
- Spec §2 auth-layer fix → Tasks 3 (export `apiFetch`), 4 (rewrite `inventoryApi`), 5/6/7 (consume it; no more `localStorage` bearer). ✓
- Spec §3 logic parity (TID lookup → register-or-topup, cash-only, CNIC digits-only, `vehicle_reg`, receipt) → Task 5 (frontend) + Tasks 1, 2 (backend booth-aware + lookup echo + receipt in response). ✓
- Spec "Approach A" (extend topup endpoints, Flutter-safe) → Task 1 gates all inventory/booth logic on `activation_booth_id` present, with `test_no_booth_id_preserves_flutter_behavior`. ✓
- Spec "drop payment-method selector, cash-only" → Task 5 (no payment_method field). ✓
- Spec "link-existing not lost (reuse owner by phone)" → backend `CashTopupView` already does `User.objects.filter(phone=...)`; no task needed, register path covers it. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; test bodies are concrete. ✓

**Type consistency:** `accountsApi.topupLookup`→`TopupLookupResult`, `accountsApi.cashTopup`→`CashTopupResult` (Task 3) consumed with those exact names/types in Task 5. `inventoryApi.list/checkStatus/assignBooth/upload` (Task 4) consumed in Tasks 6/7 with matching signatures. Modal prop `onSuccess: (result: CashTopupResult) => void` matches the existing `TollOperations.tsx` call site (which ignores the arg). ✓

**Note on `Tag.tag_serial` length:** `Tag.tag_serial` is `max_length=24` while `UnregisteredInventory.tag_serial` is `max_length=50`. Real serials (e.g. `SER001`, chip serials) are short; if a >24-char serial is ever uploaded, Task 1's `Tag.objects.create(tag_serial=inv.tag_serial, ...)` would raise. Accepted constraint (matches existing CSV template); out of scope to widen the column.
