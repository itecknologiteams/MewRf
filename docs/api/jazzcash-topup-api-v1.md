# QTag — JazzCash Topup API (v1)

**Audience:** JazzCash integration team
**Owner:** iTecknologi / Malir Expressway (QTag)
**Status:** Draft for integration review · **Date:** 2026-06-19

This document describes the two HTTP endpoints QTag exposes for the JazzCash
tag-topup flow:

1. **Tag Inquiry** — JazzCash looks up a tag (by chip **TID**) and shows the
   consumer their details before payment.
2. **Payment Notification** — after the customer pays in the JazzCash app,
   JazzCash notifies QTag, which credits the tag's balance and records the
   transaction.

---

## 1. Flow overview

```
Customer enters TID in JazzCash app
        │
        ▼
(1) POST /payments/jazzcash/inquiry/      → QTag returns consumer details
        │
   Customer reviews + pays in JazzCash app
        │
        ▼
(2) POST /payments/jazzcash/payment/      → QTag credits balance, returns new balance
```

- (1) is **read-only** (no state change).
- (2) is the **only** state-changing call and is **idempotent** (safe to retry).

---

## 2. Base URL & environment

| Environment | Base URL |
|-------------|----------|
| Production  | `https://<qtag-host>/api/v1`  *(to be provided)* |
| Test (LAN)  | `http://<server-ip>:8000/api/v1` |

All endpoint paths below are relative to the base URL.

> **Production must use HTTPS.** The test environment runs on a LAN over HTTP.

---

## 3. Conventions

- **Method/Body:** `POST` with `Content-Type: application/json`. UTF-8.
- **Response envelope:** every response is JSON in this shape:

  ```json
  { "success": true,  "message": "OK",            "data": { ... } }
  { "success": false, "message": "Tag not found", "errors": { ... } }
  ```
  - `success` (boolean) — overall result. Check this first.
  - `message` (string) — human-readable status / error.
  - `data` (object) — present on success.
  - `errors` (object, optional) — present on validation errors.

- **HTTP status codes:**

  | Code | Meaning |
  |------|---------|
  | 200  | OK (inquiry found / payment processed / duplicate ignored) |
  | 201  | Created (reserved) |
  | 400  | Bad request (missing/invalid field, amount ≤ 0) |
  | 401  | Invalid signature (`pp_SecureHash` check failed) |
  | 404  | Tag not found / not registered |
  | 500  | Server error |

---

## 4. Authentication — `pp_SecureHash`

Each request **should** include a `pp_SecureHash` for integrity/authentication.

**Algorithm (HMAC-SHA256, uppercase hex):**

1. Take all request fields **except** `pp_SecureHash`.
2. Drop empty values; sort the remaining by key (ascending).
3. Build the string: `SALT&key1=value1&key2=value2&…`
4. `HMAC_SHA256( key = SALT, message = string )` → hex → **UPPERCASE**.

```
pp_SecureHash = UPPER( HMAC_SHA256( SALT, "SALT&amount=500&jazzcash_txn_id=JC123&tid=E2801105..." ) )
```

- `SALT` = the shared **integrity salt** exchanged out-of-band (`JAZZCASH_INTEGRITY_SALT`).
- On QTag, enforcement is controlled by a server flag (`JAZZCASH_VERIFY_HASH`).
  During initial integration it may be **disabled** (any request accepted); for
  production it is **enabled** and unsigned/invalid requests get **401**.

> **Action item:** confirm the exact hashing scheme JazzCash uses for
> `pp_SecureHash`. If it differs from the above, QTag will align to JazzCash's
> documented standard before go-live.

---

## 5. Endpoint 1 — Tag Inquiry

Look up a tag by chip TID and return the consumer's details. Read-only.

```
POST /payments/jazzcash/inquiry/
```

### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tid` | string | yes | RFID chip TID (24 hex chars). Normalized server-side (spaces removed, uppercased). |
| `pp_SecureHash` | string | prod | Integrity hash (see §4). |

```json
{ "tid": "E28011052000704A8F9F0AE3", "pp_SecureHash": "9F3C…" }
```

### Success — `200`

```json
{
  "success": true,
  "message": "OK",
  "data": {
    "success": true,
    "consumer_id": "4f754655-5b4a-4f32-a7d2-0d508533822a",
    "vehicle_registration": "BP-3641",
    "customer_name": "Kashif Mughal",
    "tid": "E28011052000704A8F9F0AE3",
    "current_balance": "1500.00",
    "status": "active"
  }
}
```

| `data` field | Type | Description |
|--------------|------|-------------|
| `consumer_id` | string (UUID) | QTag's stable consumer identifier (owner UUID). |
| `vehicle_registration` | string | Vehicle plate number. |
| `customer_name` | string | Registered consumer name. |
| `tid` | string | Echoed (normalized) TID. |
| `current_balance` | string (decimal) | Current wallet balance, in **PKR**. |
| `status` | string | `active`. |

### Not found / not registered — `404`

```json
{ "success": false, "message": "Tag not found" }
```

Other reasons: `Tag not assigned to any vehicle`, `Tag is <status>`,
`No account found for this vehicle`.

### Invalid signature — `401`

```json
{ "success": false, "message": "Invalid signature" }
```

---

## 6. Endpoint 2 — Payment Notification

Credit the tag's balance after the customer has paid. **Idempotent** on
`jazzcash_txn_id`.

```
POST /payments/jazzcash/payment/
```

### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tid` | string | yes | RFID chip TID. |
| `amount` | string\|number | yes | Amount to credit, in **PKR** (e.g. `"500.00"`). Must be > 0. *(unit: see action item)* |
| `jazzcash_txn_id` | string | yes | JazzCash's unique transaction id. Used as the **idempotency key**. (`pp_TxnRefNo` also accepted.) |
| `pp_SecureHash` | string | prod | Integrity hash (see §4). |

```json
{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "500.00",
  "jazzcash_txn_id": "JC1234567890",
  "pp_SecureHash": "A7B1…"
}
```

### Success — `200`

```json
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "success": true,
    "jazzcash_txn_id": "JC1234567890",
    "new_balance": "2000.00",
    "topup_id": "36ac6d87-7940-4425-8726-ed849dc9c97b"
  }
}
```

| `data` field | Type | Description |
|--------------|------|-------------|
| `jazzcash_txn_id` | string | Echoed transaction id. |
| `new_balance` | string (decimal) | Balance after crediting, PKR. |
| `topup_id` | string (UUID) | QTag's topup record id. |

### Duplicate (already processed) — `200`

A repeated `jazzcash_txn_id` does **not** credit again; QTag returns success
with `already_processed: true` and the current balance:

```json
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "success": true,
    "already_processed": true,
    "jazzcash_txn_id": "JC1234567890",
    "new_balance": "2000.00"
  }
}
```

### Errors — `400` / `401` / `404`

```json
{ "success": false, "message": "Amount must be greater than zero" }
```

Other reasons: `tid is required`, `jazzcash_txn_id is required`,
`Invalid amount`, `Tag not found`, `Tag not assigned to any vehicle`,
`No account found for this vehicle`, `Invalid signature` (401).

---

## 7. Idempotency (important)

- `jazzcash_txn_id` is **unique** in QTag. If JazzCash retries the payment call
  (timeout, network), QTag detects the duplicate and returns `200` with
  `already_processed: true` — the balance is credited **exactly once**.
- **Recommendation:** JazzCash should retry the payment call until it receives a
  `200` with `success: true`. Retries are safe.

---

## 8. Error catalogue

| `message` | HTTP | Endpoint | Cause |
|-----------|------|----------|-------|
| `Invalid signature` | 401 | both | `pp_SecureHash` invalid (when enforced) |
| `tid is required` | 400 | both | Missing `tid` |
| `Tag not found` | 404 / 400 | inquiry / payment | TID not registered |
| `Tag not assigned to any vehicle` | 404 / 400 | both | Tag exists but unassigned |
| `Tag is <status>` | 404 | inquiry | Tag not active |
| `No account found for this vehicle` | 404 / 400 | both | No wallet for the tag |
| `jazzcash_txn_id is required` | 400 | payment | Missing txn id |
| `Invalid amount` | 400 | payment | Non-numeric amount |
| `Amount must be greater than zero` | 400 | payment | amount ≤ 0 |

---

## 9. Action items to confirm with JazzCash

1. **`pp_SecureHash` algorithm** — confirm JazzCash's exact scheme; QTag will
   match it. Exchange the shared `SALT` securely.
2. **Amount unit** — PKR rupees (e.g. `500.00`) or paisa (`50000`)? Plus any
   **min/max** topup limits.
3. **Field names** — confirm JazzCash's request field names (`tid`, `amount`,
   `jazzcash_txn_id`) or provide their standard; QTag can map.
4. **Response codes** — does JazzCash expect specific success/error codes in the
   body (e.g. a `responseCode` like `000`)? QTag can add a mapping.
5. **Source IPs** — provide JazzCash server IP range for an **allowlist**.
6. **HTTPS** — production endpoint will be HTTPS; confirm TLS requirements.

---

## 10. Changelog

| Version | Date | Notes |
|---------|------|-------|
| v1 (draft) | 2026-06-19 | Initial inquiry + payment endpoints. |
