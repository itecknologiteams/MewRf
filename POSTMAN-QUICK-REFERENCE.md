# 📋 Postman Quick Reference — QTag JazzCash API

**Print this or keep handy!**

---

## 🚀 Setup (2 minutes)

```
1. Open Postman
2. Import: docs/postman/QTag-JazzCash-Personal-Collection.json
3. Set base_url: http://localhost:8000/api/v1
4. Done ✓
```

---

## 🧪 Test Data

| Tag | Name | Plate | Balance |
|-----|------|-------|---------|
| E28011052000704A8F9F0AE3 | Kashif | BP-3641 | 1500 |
| E2801105200070D4FB330A36 | Ahmed | KR-5890 | 3000 |
| E28011052000708A1B2C3D4E | Fatima | LS-1234 | 500 |

---

## 📍 Endpoints

### 1️⃣ Tag Inquiry
```
POST /payments/jazzcash/inquiry/

Request:
{
  "tid": "E28011052000704A8F9F0AE3"
}

Response (200):
{
  "success": true,
  "data": {
    "customer_name": "Kashif Mughal",
    "vehicle_registration": "BP-3641",
    "current_balance": "1500.00"
  }
}
```

---

### 2️⃣ Payment Notification
```
POST /payments/jazzcash/payment/

Request:
{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "500.00",
  "jazzcash_txn_id": "JC001"
}

Response (200):
{
  "success": true,
  "data": {
    "new_balance": "2000.00",
    "jazzcash_txn_id": "JC001"
  }
}
```

---

## 🔐 Signature (pp_SecureHash)

**In Development:** Leave blank (hash verification disabled)

**For Staging/Production:**

```python
# Python example
import hmac, hashlib

SALT = "your_salt_here"
fields = {
  "amount": "500.00",
  "jazzcash_txn_id": "JC001",
  "tid": "E28011052000704A8F9F0AE3"
}

# Sort by key
sorted_fields = sorted(fields.items())

# Build message
message = f"{SALT}&" + "&".join(f"{k}={v}" for k, v in sorted_fields)

# Compute hash
hash_hex = hmac.new(
  SALT.encode(),
  message.encode(),
  hashlib.sha256
).hexdigest().upper()

print(hash_hex)  # Use this as pp_SecureHash
```

---

## ✅ Test Cases

| Case | Request | Expected |
|------|---------|----------|
| Inquiry (Found) | Valid TID | 200, consumer details |
| Inquiry (Not Found) | Invalid TID | 404, "Tag not found" |
| Payment (New) | Valid TID + amount | 200, new balance |
| Payment (Duplicate) | Same txn_id again | 200, already_processed=true |
| Payment (Invalid) | amount <= 0 | 400, error message |

---

## 🛠️ Common Commands (CLI)

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
  -d '{"tid":"E28011052000704A8F9F0AE3","amount":"500.00","jazzcash_txn_id":"JC001"}'
```

---

## 🔧 Environment Variables (Postman)

| Variable | Value (Dev) | Value (Staging) |
|----------|-------------|-----------------|
| base_url | localhost:8000/api/v1 | 192.168.78.13:8000/api/v1 |
| jazzcash_salt | TEST_SALT_DEV | (ask team) |
| pp_SecureHash | (leave blank) | (compute manually) |

---

## ❌ Error Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Balance updated |
| 400 | Bad Request | Invalid amount |
| 401 | Invalid Signature | Wrong pp_SecureHash |
| 404 | Not Found | Tag not found |
| 500 | Server Error | Backend error |

---

## 🎯 Test Checklist

- [ ] Can inquiry existing tag → returns consumer details
- [ ] Can process payment → balance increases
- [ ] Duplicate payment → marked as already_processed (no double-credit)
- [ ] Invalid tag → 404 error
- [ ] Invalid amount → 400 error
- [ ] Response time < 500ms
- [ ] Receipt prints (if enabled)

---

## 💡 Tips

1. **Start with inquiry** to verify tag exists
2. **Use different txn_id for each test** (e.g., JC001, JC002, JC003)
3. **Test duplicate handling** — send same request twice, verify already_processed
4. **Check database** — verify balance actually changed
5. **Monitor logs** — `tail -f django.log` to see backend behavior

---

## 📚 Full Documentation

- **Local Setup:** `LOCAL-TESTING-SETUP.md`
- **Staging/Production:** `docs/deployment/STAGING-PRODUCTION-SETUP.md`
- **API Spec:** `docs/api/jazzcash-topup-api-v1.md`
- **Postman Collection:** `docs/postman/QTag-JazzCash-Personal-Collection.json`

---

## 🆘 Stuck?

1. **Check logs:** `python manage.py runserver` output
2. **Verify tag exists:** run inquiry first
3. **Recompute hash:** verify SALT + field order
4. **Backend running?** Port 8000 open?
5. **Ask team:** ali.asif@itecknologi.com

---

**Last Updated:** 2026-06-27  
**Backend:** Django + DRF  
**Printer:** ESC/POS (POS80)

