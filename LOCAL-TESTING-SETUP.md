# QTag JazzCash API — Local Testing Setup

Personal development & testing guide. No staging environment needed!

---

## 1. Quick Setup (5 minutes)

### Step 1: Import Postman Collection

1. Open Postman
2. Click **Import** (top-left)
3. Select `docs/postman/QTag-JazzCash-Personal-Collection.json`
4. Collection imported ✓

### Step 2: Configure Environment

**Option A — Local Development (Laptop)**
```
base_url: http://localhost:8000/api/v1
jazzcash_salt: TEST_SALT_DEV
```

**Option B — Staging (Remote)**
```
base_url: http://192.168.78.13:8000/api/v1
jazzcash_salt: [ask team]
```

---

## 2. Understanding pp_SecureHash

The `pp_SecureHash` field is required for all requests. It's an HMAC-SHA256 signature.

### How to Compute (Manual)

```
1. Take request fields (except pp_SecureHash)
2. Sort by key name (ascending)
3. Build string: SALT&key1=value1&key2=value2&…

Example:
  SALT = "TEST_SALT_DEV"
  tid = "E28011052000704A8F9F0AE3"
  amount = "500.00"
  jazzcash_txn_id = "JC001"
  
  String = "TEST_SALT_DEV&amount=500.00&jazzcash_txn_id=JC001&tid=E28011052000704A8F9F0AE3"
  
4. Compute HMAC_SHA256:
   Hash = HMAC_SHA256(key="TEST_SALT_DEV", message=String)
   
5. Convert to UPPERCASE HEX:
   pp_SecureHash = "9F3C1A2B4D..."
```

### Tools to Compute Hash

**Online (Quick):**
- https://www.freeformatter.com/hmac-generator.html
  - Algorithm: SHA256
  - Key: `TEST_SALT_DEV` (or your SALT)
  - Message: Your sorted string

**Python (Accurate):**
```python
import hmac
import hashlib

SALT = "TEST_SALT_DEV"
message = "TEST_SALT_DEV&amount=500.00&jazzcash_txn_id=JC001&tid=E28011052000704A8F9F0AE3"
hash_obj = hmac.new(SALT.encode(), message.encode(), hashlib.sha256)
pp_SecureHash = hash_obj.hexdigest().upper()
print(pp_SecureHash)
```

**JavaScript (Node.js):**
```javascript
const crypto = require('crypto');

const SALT = "TEST_SALT_DEV";
const message = "TEST_SALT_DEV&amount=500.00&jazzcash_txn_id=JC001&tid=E28011052000704A8F9F0AE3";
const hash = crypto.createHmac('sha256', SALT).update(message).digest('hex').toUpperCase();
console.log(hash);
```

---

## 3. Test Data (Local)

Use these tags for testing:

| E-Tag Num | Name | Plate | Balance | Notes |
|-----------|------|-------|---------|-------|
| E28011052000704A8F9F0AE3 | Kashif Mughal | BP-3641 | 1500.00 | Main test tag |
| E2801105200070D4FB330A36 | Ahmed Khan | KR-5890 | 3000.00 | Secondary tag |
| E28011052000708A1B2C3D4E | Fatima Ali | LS-1234 | 500.00 | Low balance |

---

## 4. Test Workflow

### Test 1: Tag Inquiry (No Hash Needed in Dev)

If `JAZZCASH_VERIFY_HASH=False` (development mode):

```
POST http://localhost:8000/api/v1/payments/jazzcash/inquiry/

{
  "tid": "E28011052000704A8F9F0AE3"
}
```

**Expected Response (200):**
```json
{
  "success": true,
  "message": "OK",
  "data": {
    "consumer_id": "...",
    "vehicle_registration": "BP-3641",
    "customer_name": "Kashif Mughal",
    "tid": "E28011052000704A8F9F0AE3",
    "current_balance": "1500.00",
    "status": "active"
  }
}
```

---

### Test 2: Payment Notification

```
POST http://localhost:8000/api/v1/payments/jazzcash/payment/

{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "500.00",
  "jazzcash_txn_id": "JC001_DEV_TEST"
}
```

**Expected Response (200):**
```json
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "jazzcash_txn_id": "JC001_DEV_TEST",
    "new_balance": "2000.00",
    "topup_id": "..."
  }
}
```

---

### Test 3: Idempotency (Duplicate Transaction)

Send same request as Test 2 again:

```
POST http://localhost:8000/api/v1/payments/jazzcash/payment/

{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "500.00",
  "jazzcash_txn_id": "JC001_DEV_TEST"  ← SAME as before
}
```

**Expected Response (200):**
```json
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "already_processed": true,
    "jazzcash_txn_id": "JC001_DEV_TEST",
    "new_balance": "2000.00"  ← NO DOUBLE-CREDIT!
  }
}
```

---

## 5. Postman Variables Guide

### Pre-configured Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `{{base_url}}` | Backend URL | `http://localhost:8000/api/v1` |
| `{{jazzcash_salt}}` | SALT for hashing | `TEST_SALT_DEV` |
| `{{pp_SecureHash}}` | Computed signature | (leave blank in dev) |

### How to Use in Postman

1. **Click** the variable name in request
2. Postman auto-suggests: `{{base_url}}`
3. At runtime, replaces with actual value

---

## 6. Postman Tips & Tricks

### Auto-compute Hash (Advanced)

In Postman, use **Tests** tab to auto-compute hash:

```javascript
// Add this to your request's "Tests" tab
const SALT = pm.variables.get('jazzcash_salt');
const tid = pm.request.body.raw ? JSON.parse(pm.request.body.raw).tid : '';
const amount = pm.request.body.raw ? JSON.parse(pm.request.body.raw).amount : '';
const txn_id = pm.request.body.raw ? JSON.parse(pm.request.body.raw).jazzcash_txn_id : '';

// Build sorted string (just for demo — implement full sorting in production)
const message = `${SALT}&amount=${amount}&jazzcash_txn_id=${txn_id}&tid=${tid}`;

// You'll need to compute HMAC externally or use pre-request script
console.log('Message to hash:', message);
```

### Save Request Templates

After first successful request, **Save as Template** for reuse.

---

## 7. Common Errors & Fixes

### Error: "Cannot GET /api/v1/..."
- **Cause:** Backend not running
- **Fix:** `python manage.py runserver` in MewRf directory

### Error: 401 Invalid Signature
- **Cause:** `pp_SecureHash` wrong or SALT mismatch
- **Fix:** Recompute hash, verify SALT, check field sorting order

### Error: 404 Tag Not Found
- **Cause:** TID doesn't exist in database
- **Fix:** Use one of the test tags above, or scan real tag from device

### Error: "amount must be greater than zero"
- **Cause:** Amount is 0 or negative
- **Fix:** Use positive amount like "500.00"

---

## 8. Ready-to-Use Commands

### Copy-Paste (Development — No Hash)

**Tag Inquiry:**
```bash
curl -X POST http://localhost:8000/api/v1/payments/jazzcash/inquiry/ \
  -H "Content-Type: application/json" \
  -d '{"tid":"E28011052000704A8F9F0AE3"}'
```

**Payment:**
```bash
curl -X POST http://localhost:8000/api/v1/payments/jazzcash/payment/ \
  -H "Content-Type: application/json" \
  -d '{
    "tid":"E28011052000704A8F9F0AE3",
    "amount":"500.00",
    "jazzcash_txn_id":"JC_TEST_001"
  }'
```

---

## 9. Next Steps

1. ✅ Import Postman collection (`QTag-JazzCash-Personal-Collection.json`)
2. ✅ Set `base_url = http://localhost:8000/api/v1`
3. ✅ Run local backend: `python manage.py runserver`
4. ✅ Send first request (Tag Inquiry)
5. ✅ Compute `pp_SecureHash` when moving to production

---

## 10. Questions?

- **API Logic:** Check `mtag_backend/apps/accounts/views.py` (CashTopupView, TopupLookupView)
- **Signature:** See `docs/api/jazzcash-topup-api-v1.md` §4
- **Test Data:** See `docs/deployment/STAGING-PRODUCTION-SETUP.md` §4

**Happy testing! 🚀**

