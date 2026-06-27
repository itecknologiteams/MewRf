# QTag JazzCash Integration — Testing Inventory Template

**For:** JazzCash Testing Team  
**Date:** 2026-06-27  
**Backend:** http://192.168.78.13:8000/api/v1 (Staging)

---

## Testing Inventory (Staging)

Use these test tags to verify the JazzCash topup flow end-to-end.

| E-Tag Num | CNIC | Customer Name | Vehicle Reg | Opening Balance | Test Scenario |
|-----------|------|---------------|-------------|-----------------|---------------|
| E28011052000704A8F9F0AE3 | 35202-1234567-8 | Kashif Mughal | BP-3641 | 1500.00 | Existing tag + topup |
| E2801105200070D4FB330A36 | 35202-9876543-2 | Ahmed Khan | KR-5890 | 3000.00 | Balance inquiry + topup |
| E28011052000708A1B2C3D4E | 35202-5555555-5 | Fatima Ali | LS-1234 | 500.00 | Low balance + topup |
| E2801105200070AAAABBBBCC | (New) | Test User 1 | XX-0001 | 0.00 | New registration + topup |
| E2801105200070DDDDEEEEFF | (New) | Test User 2 | XX-0002 | 0.00 | New registration + topup |

---

## Test Cases

### TC-1: Existing Tag Inquiry
**Request:**
```
POST /payments/jazzcash/inquiry/
{
  "tid": "E28011052000704A8F9F0AE3",
  "pp_SecureHash": "[computed-hash]"
}
```

**Expected Response:**
- Status: 200
- Consumer found: Kashif Mughal, BP-3641
- Balance shown: 1500.00 PKR

---

### TC-2: Payment Notification (First Time)
**Request:**
```
POST /payments/jazzcash/payment/
{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "500.00",
  "jazzcash_txn_id": "JC001",
  "pp_SecureHash": "[computed-hash]"
}
```

**Expected Response:**
- Status: 200
- Balance credited: 2000.00 PKR (1500 + 500)
- Transaction ID: echoed back

---

### TC-3: Idempotency Check (Duplicate TXN)
**Request (Same as TC-2):**
```
POST /payments/jazzcash/payment/
{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "500.00",
  "jazzcash_txn_id": "JC001",
  "pp_SecureHash": "[computed-hash]"
}
```

**Expected Response:**
- Status: 200
- `already_processed: true`
- Balance unchanged: 2000.00 PKR (NOT 2500)

---

### TC-4: Tag Not Found
**Request:**
```
POST /payments/jazzcash/inquiry/
{
  "tid": "INVALID_TID_XXXXXXXXXX",
  "pp_SecureHash": "[computed-hash]"
}
```

**Expected Response:**
- Status: 404
- Message: "Tag not found"

---

### TC-5: Invalid Amount
**Request:**
```
POST /payments/jazzcash/payment/
{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "-100",
  "jazzcash_txn_id": "JC002",
  "pp_SecureHash": "[computed-hash]"
}
```

**Expected Response:**
- Status: 400
- Message: "Amount must be greater than zero"

---

## Test Credentials

| Field | Value |
|-------|-------|
| Operator ID / Username | `operator_test` |
| Password | `Operator@1234` |
| Role | Operator |

---

## Reporting Results

After testing, please provide:

| Item | Status | Notes |
|------|--------|-------|
| TC-1: Existing Tag Inquiry | ✓ PASS / ✗ FAIL | |
| TC-2: Payment (First Time) | ✓ PASS / ✗ FAIL | |
| TC-3: Idempotency Check | ✓ PASS / ✗ FAIL | |
| TC-4: Tag Not Found | ✓ PASS / ✗ FAIL | |
| TC-5: Invalid Amount | ✓ PASS / ✗ FAIL | |
| Receipt Printing | ✓ WORKS / ✗ FAILS | Logo quality: |
| Response Time (avg) | ___ ms | Should be < 500ms |

---

## Additional Notes

- All amounts are in **PKR (Pakistani Rupees)**
- TID field is normalized (spaces removed, uppercased) server-side
- Responses always follow the envelope: `{ success, message, data/errors }`
- HTTP Status Codes: 200 (OK), 400 (Bad Request), 401 (Invalid Signature), 404 (Not Found), 500 (Server Error)

---

**Contact:** [Support Email]  
**Last Updated:** 2026-06-27

