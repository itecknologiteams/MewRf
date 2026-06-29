# 🧪 QTag JazzCash API — Testing Guide

**For Testing Team: Complete API Testing Flow**

---

## 🔗 API URLs

```
Internal:  http://192.168.20.69:8000/api/v1
External:  http://221.120.248.114:8000/api/v1
```

---

## 📱 Postman Setup

### Import Collection
1. File → Import
2. Select: `docs/postman/JazzCash-TopUp-API-Collection.json`

### Configure Variables
```
base_url = http://221.120.248.114:8000/api/v1
jazzcash_salt = TEST_SALT_DEV
pp_SecureHash = (leave blank for testing)
```

---

## 🧪 Test Data (Ready to Use)

| Tag (TID) | Customer | Plate | Balance | Status |
|-----------|----------|-------|---------|--------|
| E28011052000704A8F9F0AE3 | Kashif Mughal | ABC-8123 | 1500.00 PKR | active |
| E2801105200070D4FB330A36 | Ahmed Khan | MNP-5890 | 3000.00 PKR | active |
| E28011052000708A1B2C3D4E | Fatima Ali | BMQ-4532 | 500.00 PKR | active |

---

## 📍 Endpoint 1: Tag Inquiry

**Read-only. Look up a tag and get consumer details.**

```
POST /payments/jazzcash/inquiry/
```

### Request
```json
{
  "tid": "E28011052000704A8F9F0AE3",
  "pp_SecureHash": ""
}
```

### Success Response (200)
```json
{
  "success": true,
  "message": "OK",
  "data": {
    "success": true,
    "consumer_id": "62dbf8b8-e08a-487f-b4c9-ea886a5e930c",
    "vehicle_registration": "ABC-8123",
    "customer_name": "Kashif Mughal",
    "tid": "E28011052000704A8F9F0AE3",
    "current_balance": "1500.00",
    "status": "active"
  }
}
```

### Error Response (404)
```json
{
  "success": false,
  "message": "Tag not found"
}
```

---

## 💳 Endpoint 2: Payment Notification

**Credit balance after payment. Idempotent on `jazzcash_txn_id`.**

```
POST /payments/jazzcash/payment/
```

### Request
```json
{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "500.00",
  "jazzcash_txn_id": "JC001",
  "pp_SecureHash": ""
}
```

### Success Response — First Time (200)
```json
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "success": true,
    "jazzcash_txn_id": "JC001",
    "new_balance": "2000.00",
    "topup_id": "36ac6d87-7940-4425-8726-ed849dc9c97b"
  }
}
```

### Success Response — Duplicate (Idempotent, 200)
```json
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "success": true,
    "already_processed": true,
    "jazzcash_txn_id": "JC001",
    "new_balance": "2000.00"
  }
}
```

### Error Response (400)
```json
{
  "success": false,
  "message": "Amount must be greater than zero"
}
```

---

## 🧪 Test Cases

### TC-1: Tag Inquiry (Existing Tag)

**Goal:** Verify tag lookup returns consumer details

**Request:**
```json
{
  "tid": "E28011052000704A8F9F0AE3"
}
```

**Expected:**
- Status: 200
- Consumer found: Kashif Mughal
- Balance: 1500.00 PKR

**Verification:**
- ✓ success = true
- ✓ vehicle_registration = ABC-8123
- ✓ current_balance = 1500.00

---

### TC-2: Tag Inquiry (Non-existent Tag)

**Goal:** Verify error handling for invalid tag

**Request:**
```json
{
  "tid": "INVALID_TAG_12345678"
}
```

**Expected:**
- Status: 404
- Error: "Tag not found"

**Verification:**
- ✓ success = false
- ✓ message contains "not found"

---

### TC-3: Payment Processing (First Time)

**Goal:** Process topup and verify balance update

**Request:**
```json
{
  "tid": "E2801105200070D4FB330A36",
  "amount": "1000.00",
  "jazzcash_txn_id": "JC_TEST_001"
}
```

**Expected:**
- Status: 200
- New balance: 4000.00 (3000 + 1000)
- topup_id: (UUID)

**Verification:**
- ✓ success = true
- ✓ new_balance = 4000.00
- ✓ jazzcash_txn_id echoed back

---

### TC-4: Payment Processing (Duplicate)

**Goal:** Verify idempotency — same transaction should not double-credit

**Request (same as TC-3):**
```json
{
  "tid": "E2801105200070D4FB330A36",
  "amount": "1000.00",
  "jazzcash_txn_id": "JC_TEST_001"
}
```

**Expected:**
- Status: 200
- already_processed: true
- Balance: 4000.00 (NOT 5000 — no double-credit!)

**Verification:**
- ✓ success = true
- ✓ already_processed = true
- ✓ new_balance unchanged (4000.00)

---

### TC-5: Payment with Invalid Amount

**Goal:** Verify validation for invalid amounts

**Request:**
```json
{
  "tid": "E28011052000708A1B2C3D4E",
  "amount": "-500.00",
  "jazzcash_txn_id": "JC_INVALID"
}
```

**Expected:**
- Status: 400
- Error: "Amount must be greater than zero"

**Verification:**
- ✓ success = false
- ✓ message contains "greater than zero"

---

### TC-6: Payment with Zero Amount

**Goal:** Verify zero amount rejection

**Request:**
```json
{
  "tid": "E28011052000708A1B2C3D4E",
  "amount": "0.00",
  "jazzcash_txn_id": "JC_ZERO"
}
```

**Expected:**
- Status: 400
- Error: "Amount must be greater than zero"

---

## ✅ Test Checklist

```
Endpoint: Tag Inquiry
[ ] TC-1: Existing tag returns consumer details (200)
[ ] TC-2: Invalid tag returns error (404)

Endpoint: Payment
[ ] TC-3: Payment processes, balance increases (200)
[ ] TC-4: Duplicate payment marked as already_processed (no double-credit)
[ ] TC-5: Negative amount rejected (400)
[ ] TC-6: Zero amount rejected (400)

Overall
[ ] All responses follow envelope format (success, message, data/errors)
[ ] Response times < 1 second
[ ] No database errors in backend logs
```

---

## 🔧 Using Postman

### Step 1: Import Collection
```
File → Import → JazzCash-TopUp-API-Collection.json
```

### Step 2: Set Variables
```
Click: Environment Selector (top-right)
Select: "Testing Machine"
Or manually set:
  base_url = http://221.120.248.114:8000/api/v1
  jazzcash_salt = TEST_SALT_DEV
```

### Step 3: Run Test Cases
```
1. Click: "1️⃣ TAG INQUIRY"
2. Select: "Inquiry - Existing Tag (Kashif)"
3. Click: Send
4. Verify response matches TC-1 expected output
5. Repeat for other test cases
```

### Step 4: Report Results
```
For each test case:
✓ PASS   (if response matches expected)
✗ FAIL   (if response differs)

Note any issues or edge cases found
```

---

## 📊 Response Envelope Format

**All responses follow this structure:**

### Success (200)
```json
{
  "success": true,
  "message": "OK",
  "data": {
    "key1": "value1",
    "key2": "value2"
  }
}
```

### Error (400/401/404)
```json
{
  "success": false,
  "message": "Error description",
  "errors": {
    "field": ["error message"]
  }
}
```

---

## 🔐 Authentication

**For testing:** Leave `pp_SecureHash` blank

**For production:** HMAC-SHA256 signature required
- Algorithm: HMAC_SHA256(key=SALT, message=sorted_fields)
- Salt: shared via secure channel

---

## 📝 Test Report Template

```
Test Date: _______________
Tester Name: _____________
Environment: Testing Machine (192.168.20.69:8000)

Test Results:
[ ] TC-1: Tag Inquiry (Existing)     ✓ PASS / ✗ FAIL
[ ] TC-2: Tag Inquiry (Invalid)      ✓ PASS / ✗ FAIL
[ ] TC-3: Payment (First Time)       ✓ PASS / ✗ FAIL
[ ] TC-4: Payment (Duplicate)        ✓ PASS / ✗ FAIL
[ ] TC-5: Payment (Negative Amount)  ✓ PASS / ✗ FAIL
[ ] TC-6: Payment (Zero Amount)      ✓ PASS / ✗ FAIL

Overall Status: ___________
Issues Found: ______________
Performance Notes: _________
```

---

## 🆘 Troubleshooting

### Connection Refused
```
Error: Could not connect to server
Fix: Verify API URL is correct
     Check if server is running
     Check firewall settings
```

### 404 Not Found
```
Error: "Not Found" / "Tag not found"
Cause: Invalid TID or endpoint path
Fix: Use correct TID from test data
     Verify endpoint path: /payments/jazzcash/inquiry/
```

### 400 Bad Request
```
Error: "Invalid request"
Cause: Missing required field or invalid format
Fix: Check request JSON syntax
     Verify all required fields present
     Ensure amount > 0
```

### 500 Server Error
```
Error: Internal server error
Cause: Backend issue
Action: Report to development team with:
        - Request sent
        - Response received
        - Backend logs (if available)
```

---

## 📞 Support

**API Issues:** ali.asif@itecknologi.com  
**Server Issues:** shaneel@itecknologi.com

**Questions:**
- Endpoint documentation: See section above
- Test data: See test data table
- Response format: See response envelope section

---

## 🎯 Success Criteria

✅ All 6 test cases pass  
✅ Response times < 1 second  
✅ No database errors  
✅ Idempotency working (TC-4)  
✅ Validation working (TC-5, TC-6)  
✅ Error messages clear  

---

**Status:** Ready for Testing ✓  
**Date:** 2026-06-29  
**API Version:** v1

