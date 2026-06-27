# QTag JazzCash Integration — Staging & Production Setup

**Confidential — For iTecknologi / JazzCash Integration Team**

---

## 1. Environment URLs

| Environment | Backend URL | Status |
|-------------|------------|--------|
| **Staging (LAN)** | `http://192.168.78.13:8000/api/v1` | Active |
| **Production** | `https://<to-be-provided>/api/v1` | Pending TLS setup |

---

## 2. API Credentials

### Authentication

All requests require:
- **Method:** HTTP POST with `Content-Type: application/json`
- **Signature:** `pp_SecureHash` (HMAC-SHA256, uppercase hex)
- **Salt:** `JAZZCASH_INTEGRITY_SALT` (exchanged out-of-band)

### HMAC-SHA256 Algorithm (pp_SecureHash)

```
1. Take all request fields except pp_SecureHash
2. Sort fields by key (ascending)
3. Build string: SALT&key1=value1&key2=value2&…
4. pp_SecureHash = UPPER(HMAC_SHA256(key=SALT, message=string))
```

**Example:**
```
SALT = "your_shared_salt_here"
String = "SALT&amount=500&jazzcash_txn_id=JC123&tid=E2801105..."
pp_SecureHash = UPPER(HMAC_SHA256(...))
```

---

## 3. Endpoints

### Endpoint 1: Tag Inquiry

**POST** `/payments/jazzcash/inquiry/`

**Request:**
```json
{
  "tid": "E28011052000704A8F9F0AE3",
  "pp_SecureHash": "9F3C..."
}
```

**Success (200):**
```json
{
  "success": true,
  "message": "OK",
  "data": {
    "consumer_id": "4f754655-5b4a-4f32-a7d2-0d508533822a",
    "vehicle_registration": "BP-3641",
    "customer_name": "Kashif Mughal",
    "tid": "E28011052000704A8F9F0AE3",
    "current_balance": "1500.00",
    "status": "active"
  }
}
```

**Error (404):**
```json
{
  "success": false,
  "message": "Tag not found"
}
```

---

### Endpoint 2: Payment Notification

**POST** `/payments/jazzcash/payment/`

**Request:**
```json
{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "500.00",
  "jazzcash_txn_id": "JC1234567890",
  "pp_SecureHash": "A7B1..."
}
```

**Success (200) — First time:**
```json
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "jazzcash_txn_id": "JC1234567890",
    "new_balance": "2000.00",
    "topup_id": "36ac6d87-7940-4425-8726-ed849dc9c97b"
  }
}
```

**Success (200) — Duplicate (idempotent):**
```json
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "already_processed": true,
    "jazzcash_txn_id": "JC1234567890",
    "new_balance": "2000.00"
  }
}
```

**Error (400):**
```json
{
  "success": false,
  "message": "Amount must be greater than zero"
}
```

---

## 4. Staging Test Inventory

| E-Tag Num | CNIC | Customer Name | Vehicle Reg | Current Balance | Status |
|-----------|------|---------------|-------------|-----------------|--------|
| E28011052000704A8F9F0AE3 | 35202-1234567-8 | Kashif Mughal | BP-3641 | 1500.00 | Active |
| E2801105200070D4FB330A36 | 35202-9876543-2 | Ahmed Khan | KR-5890 | 3000.00 | Active |
| E28011052000708A1B2C3D4E | 35202-5555555-5 | Fatima Ali | LS-1234 | 500.00 | Active |
| E28011052000701234567890 | (New) | (New) | (New) | 0.00 | Inactive |

**Test Credentials:**
- **Username:** `operator_test`
- **Password:** `Operator@1234`
- **User Role:** Operator

---

## 5. Production Credentials (To Be Provided)

| Item | Value |
|------|-------|
| Production Backend URL | `https://<domain>/api/v1` |
| Production SALT | (provided separately) |
| Production Operator ID | (provided separately) |
| Production Operator Password | (provided separately) |
| TLS Certificate | (configured on server) |

---

## 6. Important Notes

1. **Idempotency:** The `jazzcash_txn_id` field is unique and acts as an idempotency key. Retries with the same `jazzcash_txn_id` return `200` with `already_processed: true` and do NOT double-credit the balance.

2. **Tag Normalization:** TID field is normalized server-side (spaces removed, uppercased).

3. **Amount Unit:** PKR (Pakistani Rupees). Example: `"500.00"` = 500 PKR.

4. **Hash Enforcement:** On staging, `JAZZCASH_VERIFY_HASH` may be disabled for initial testing. Production will have it enabled (401 on invalid/missing signature).

5. **Source IP Allowlist:** Provide JazzCash server IP range for firewall allowlist (production).

6. **HTTPS Requirement:** Production must use HTTPS. TLS certificate setup pending.

---

## 7. Quick Start (Postman)

1. Import `JazzCash-TopUp-API-Collection.json` into Postman
2. Set environment variable: `base_url = http://192.168.78.13:8000/api/v1`
3. Update `jazzcash_salt` variable with the shared SALT
4. Test Tag Inquiry endpoint with a valid TID
5. Test Payment endpoint with a small amount

---

## Contact

**Backend Support:** ali.asif@itecknologi.com  
**Infrastructure:** shaneel@itecknologi.com  
**Last Updated:** 2026-06-27

