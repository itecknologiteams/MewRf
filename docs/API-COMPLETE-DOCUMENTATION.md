# 📘 QTag JazzCash TopUp API — Complete Documentation

**For Testing Team & Integration Partners**

---

## 📋 Table of Contents

1. [Quick Start](#-quick-start)
2. [API Overview](#-api-overview)
3. [Testing Environment](#-testing-environment)
4. [Postman Setup](#-postman-setup)
5. [Test Inventory](#-test-inventory)
6. [API Endpoints](#-api-endpoints)
7. [Test Cases](#-test-cases)
8. [Error Handling](#-error-handling)
9. [Troubleshooting](#-troubleshooting)

---

## 🚀 Quick Start

### In 3 Minutes:

1. **Import Postman Collection**
   ```
   File → Import → JazzCash-TopUp-API-Collection.json
   ```

2. **Set API URL**
   ```
   base_url = http://221.120.248.114:8000/api/v1
   ```

3. **Run First Test**
   ```
   Click: "Kashif Mughal (1500 PKR)"
   Click: Send
   Expected: 200 OK with consumer details
   ```

---

## 📊 API Overview

### Purpose
QTag JazzCash TopUp API enables:
- **Tag Inquiry** — Look up consumer details by RFID tag
- **Payment Processing** — Credit balance after payment confirmation

### Features
- ✅ **Idempotent Payments** — Safe to retry failed requests
- ✅ **Real-time Balance Updates** — Instant confirmation
- ✅ **Comprehensive Error Handling** — Clear error messages
- ✅ **Production Ready** — Tested & deployed

### Architecture
```
JazzCash Platform
      ↓ (HTTP POST)
QTag API (221.120.248.114:8000)
      ↓ (SQL Query)
PostgreSQL (192.168.21.31:6632)
```

---

## 🖥️ Testing Environment

### Server Details
```
Machine:        Testing Server (QTag Backend)
Internal IP:    192.168.20.69:8000/api/v1
External IP:    221.120.248.114:8000/api/v1
OS:             Linux (Ubuntu)
Database:       PostgreSQL on 192.168.21.31:6632
Status:         ✅ Running
```

### Connectivity
```
Testing Team Laptop
    ↓ (curl/Postman)
221.120.248.114:8000 (API Server)
    ↓ (SQL)
192.168.21.31:6632 (Database Server)
```

---

## 📱 Postman Setup

### Step 1: Import Collection

**Method 1: Direct Import**
```
1. Open Postman Desktop App
2. Click "Import" (top-left)
3. Select: JazzCash-TopUp-API-Collection.json
4. Click "Import"
```

**Method 2: Drag & Drop**
```
1. Drag the .json file
2. Drop into Postman window
3. Confirm import
```

**Result:** Collection appears in left sidebar

### Step 2: Configure Environment

**Set Variables:**
```
In Postman, top-right dropdown:
Click "Environment Selector"
Set or Create "Testing Machine":

base_url = http://221.120.248.114:8000/api/v1
jazzcash_salt = TEST_SALT_DEV
pp_SecureHash = (leave blank)
```

**Verify:**
```
Top-right should show:
"Testing Machine" (environment selected)
```

### Step 3: Run Your First Request

**Find the Request:**
```
Left Sidebar:
├─ 1️⃣ TAG INQUIRY
│  └─ Kashif Mughal (1500 PKR) ← Click here
```

**Send the Request:**
```
Main Panel:
- Request body pre-filled ✓
- Click "Send" button
```

**Expected Response (200):**
```json
{
  "success": true,
  "message": "OK",
  "data": {
    "consumer_name": "Kashif Mughal",
    "vehicle_registration": "ABC-8123",
    "current_balance": "1500.00",
    "tid": "E28011052000704A8F9F0AE3",
    "status": "active"
  }
}
```

---

## 🗄️ Test Inventory

### Pre-loaded Test Data

**3 Consumer Profiles (Ready to Use):**

#### Consumer 1: Kashif Mughal
```
Tag ID (TID):         E28011052000704A8F9F0AE3
Vehicle Plate:        ABC-8123
Current Balance:      1500.00 PKR
Status:               active
Use Case:             Main test consumer
```

#### Consumer 2: Ahmed Khan
```
Tag ID (TID):         E2801105200070D4FB330A36
Vehicle Plate:        MNP-5890
Current Balance:      3000.00 PKR
Status:               active
Use Case:             Secondary test consumer
```

#### Consumer 3: Fatima Ali
```
Tag ID (TID):         E28011052000708A1B2C3D4E
Vehicle Plate:        BMQ-4532
Current Balance:      500.00 PKR
Status:               active
Use Case:             Low balance test
```

### Inventory Summary

```
Total Consumers:      3
Total Balances:       1500 + 3000 + 500 = 5000 PKR
Total Tags:           3 (all active)
Database:             tag_db @ 192.168.21.31:6632
Created:              2026-06-29
Status:               Ready for Testing ✓
```

---

## 🔌 API Endpoints

### Endpoint 1: Tag Inquiry (Read-Only)

**Purpose:** Look up a tag and get consumer details

**Method & Path:**
```
POST /payments/jazzcash/inquiry/
```

**Full URL:**
```
http://221.120.248.114:8000/api/v1/payments/jazzcash/inquiry/
```

**Request Body:**
```json
{
  "tid": "E28011052000704A8F9F0AE3",
  "pp_SecureHash": ""
}
```

**Field Details:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| tid | string | Yes | RFID tag ID (24 hex chars) |
| pp_SecureHash | string | No (Dev) | HMAC-SHA256 signature (for production) |

**Success Response (200):**
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

**Error Response (404):**
```json
{
  "success": false,
  "message": "Tag not found"
}
```

**When to Use:**
- Before processing a topup
- To verify consumer details
- To show current balance

---

### Endpoint 2: Payment Notification (Idempotent)

**Purpose:** Credit balance after payment confirmation

**Method & Path:**
```
POST /payments/jazzcash/payment/
```

**Full URL:**
```
http://221.120.248.114:8000/api/v1/payments/jazzcash/payment/
```

**Request Body:**
```json
{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "500.00",
  "jazzcash_txn_id": "JC_KASHIF_001",
  "pp_SecureHash": ""
}
```

**Field Details:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| tid | string | Yes | RFID tag ID |
| amount | string/number | Yes | Amount to add (PKR) |
| jazzcash_txn_id | string | Yes | Unique transaction ID (idempotency key) |
| pp_SecureHash | string | No (Dev) | HMAC-SHA256 signature |

**Success Response — First Request (200):**
```json
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "success": true,
    "jazzcash_txn_id": "JC_KASHIF_001",
    "new_balance": "2000.00",
    "topup_id": "36ac6d87-7940-4425-8726-ed849dc9c97b"
  }
}
```

**Success Response — Duplicate Request (200):**
```json
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "success": true,
    "already_processed": true,
    "jazzcash_txn_id": "JC_KASHIF_001",
    "new_balance": "2000.00"
  }
}
```

**Key Feature — Idempotency:**
```
If you send the SAME jazzcash_txn_id twice:
- First request:  Balance increases ✓
- Second request: Returns already_processed=true
                  Balance DOES NOT increase again ✓
                  Status: 200 (success)

This is safe to retry on network failures!
```

**Error Response — Invalid Amount (400):**
```json
{
  "success": false,
  "message": "Amount must be greater than zero"
}
```

**When to Use:**
- After customer confirms payment in JazzCash app
- Always include unique jazzcash_txn_id
- Safe to retry if request times out

---

## 🧪 Test Cases

### TC-1: Existing Tag Inquiry

**Goal:** Verify tag lookup returns consumer details

**Steps in Postman:**
```
1. Sidebar → 1️⃣ TAG INQUIRY → Kashif Mughal
2. Click "Send"
```

**Verify:**
```
✓ Status: 200
✓ success: true
✓ consumer_name: "Kashif Mughal"
✓ vehicle_registration: "ABC-8123"
✓ current_balance: "1500.00"
✓ tid: "E28011052000704A8F9F0AE3"
```

---

### TC-2: Invalid Tag Error

**Goal:** Verify error handling for non-existent tags

**Steps in Postman:**
```
1. Sidebar → 1️⃣ TAG INQUIRY → Invalid Tag
2. Click "Send"
```

**Verify:**
```
✓ Status: 404
✓ success: false
✓ message contains: "not found"
```

---

### TC-3: Payment Processing

**Goal:** Process topup and verify balance update

**Steps in Postman:**
```
1. Sidebar → 2️⃣ PAYMENT NOTIFICATION → Ahmed - Add 500 PKR
2. Click "Send"
```

**Expected:**
```
Before: Ahmed balance = 3000.00 PKR
After:  Ahmed balance = 3500.00 PKR (+500)
```

**Verify:**
```
✓ Status: 200
✓ success: true
✓ new_balance: "3500.00"
✓ already_processed: false (or missing)
```

---

### TC-4: Idempotency Test

**Goal:** Verify duplicate requests don't double-credit

**Steps in Postman:**
```
1. Sidebar → 2️⃣ PAYMENT NOTIFICATION → Ahmed - Add 500 PKR
2. Click "Send" (First request)
3. Click "Send" again (Second request - SAME jazzcash_txn_id)
```

**Expected:**
```
First:  Balance: 3000 → 3500 (increased)
Second: Balance: 3500 (UNCHANGED - already_processed=true)
```

**Verify:**
```
First Request:
✓ already_processed: false (or missing)
✓ new_balance: "3500.00"

Second Request (SAME txn_id):
✓ already_processed: true ← KEY POINT!
✓ new_balance: "3500.00" (NO CHANGE)
✓ Status: 200 (success, not error)
```

---

### TC-5: Validation Test (Zero Amount)

**Goal:** Verify validation rejects zero amounts

**Steps in Postman:**
```
1. Sidebar → 2️⃣ PAYMENT NOTIFICATION → Error - Zero Amount
2. Click "Send"
```

**Verify:**
```
✓ Status: 400
✓ success: false
✓ message: "Amount must be greater than zero"
```

---

### TC-6: Validation Test (Negative Amount)

**Goal:** Verify validation rejects negative amounts

**Steps in Postman:**
```
1. Sidebar → 2️⃣ PAYMENT NOTIFICATION → Error - Negative Amount
2. Click "Send"
```

**Verify:**
```
✓ Status: 400
✓ success: false
✓ message: "Amount must be greater than zero"
```

---

## ❌ Error Handling

### Error Response Format

**All errors follow this structure:**

```json
{
  "success": false,
  "message": "Error description",
  "errors": {
    "field_name": ["error details"]
  }
}
```

### Common HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Inquiry succeeded, payment succeeded |
| 400 | Bad Request | Invalid amount, missing field |
| 401 | Unauthorized | Invalid signature (production) |
| 404 | Not Found | Tag doesn't exist |
| 500 | Server Error | Database issue |

### Error Messages

| Message | Cause | Fix |
|---------|-------|-----|
| "Tag not found" | Invalid TID | Use valid TID from inventory |
| "Amount must be greater than zero" | amount ≤ 0 | Use amount > 0 |
| "Invalid signature" | Wrong pp_SecureHash | Recompute hash correctly |
| "tid is required" | Missing tid field | Add tid to request |
| "jazzcash_txn_id is required" | Missing txn ID | Add unique txn_id |

---

## 🆘 Troubleshooting

### Connection Errors

**Error:** `Failed to connect to 221.120.248.114 port 8000`

**Cause:** API server not running or firewall blocking

**Fix:**
```
1. Verify API URL is correct: 221.120.248.114:8000
2. Check if server is running (ask backend team)
3. Check firewall settings
4. Try internal IP: 192.168.20.69:8000
```

---

### 404 Tag Not Found

**Error:** `"success": false, "message": "Tag not found"`

**Cause:** Invalid TID provided

**Fix:**
```
Use one of the 3 test tags:
- E28011052000704A8F9F0AE3 (Kashif)
- E2801105200070D4FB330A36 (Ahmed)
- E28011052000708A1B2C3D4E (Fatima)
```

---

### 400 Bad Request

**Error:** `"success": false, "message": "Invalid request"`

**Cause:** Malformed request body

**Fix:**
```
1. Check JSON syntax (use Postman validator)
2. Verify all required fields present
3. Ensure amount > 0
4. Ensure tid is 24 hex characters
```

---

### Response Times Slow

**Symptoms:** Requests taking > 2 seconds

**Cause:** Network latency or server load

**Fix:**
```
1. Try internal IP (192.168.20.69) instead of external
2. Check database server status
3. Check network connectivity
```

---

## 📊 Test Checklist

```
Before Testing:
[ ] Postman installed
[ ] Collection imported
[ ] Environment set (base_url, jazzcash_salt)
[ ] Can reach 221.120.248.114:8000

Tag Inquiry Tests:
[ ] TC-1: Kashif tag returns consumer details (200)
[ ] TC-2: Invalid tag returns error (404)
[ ] TC-3: Ahmed tag returns consumer details (200)
[ ] TC-4: Fatima tag returns consumer details (200)

Payment Tests:
[ ] TC-5: Kashif topup processes, balance increases (200)
[ ] TC-6: Ahmed topup processes, balance increases (200)
[ ] TC-7: Fatima topup processes, balance increases (200)
[ ] TC-8: Duplicate payment (same txn_id) returns already_processed=true

Validation Tests:
[ ] TC-9: Zero amount rejected (400)
[ ] TC-10: Negative amount rejected (400)

Overall:
[ ] All responses follow envelope format
[ ] All response times < 1 second
[ ] No database errors in logs
[ ] Ready to sign off ✓
```

---

## 📞 Support & Contact

**Technical Issues:** ali.asif@itecknologi.com  
**Server Issues:** shaneel@itecknologi.com  
**API Questions:** See sections above

---

## 📝 Additional Resources

- **API Spec:** docs/api/jazzcash-topup-api-v1.md
- **Testing Guide:** docs/API-TESTING-GUIDE.md
- **Postman Collection:** docs/postman/JazzCash-TopUp-API-Collection.json

---

## ✅ Sign-Off

**API Status:** ✅ Ready for Testing  
**Test Data:** ✅ Loaded & Verified  
**Documentation:** ✅ Complete  
**Last Updated:** 2026-06-29  
**Version:** 1.0

---

**Happy Testing! 🚀**

