# 📦 QTag JazzCash API — Delivery Package for Testing Team

**Hand over this complete package to your testing team.**

---

## 📋 Package Contents

All files ready in repository. Testing team needs these **3 files only**:

### **1. Postman Collection** (Import & Test)
```
📄 docs/postman/JazzCash-TopUp-API-Collection.json
```
- Complete API endpoints (inquiry + payment)
- Pre-configured test cases
- Error scenarios
- Example requests/responses

### **2. Setup & Credentials Documentation**
```
📄 docs/deployment/STAGING-PRODUCTION-SETUP.md
```
Contains:
- ✅ Staging environment URL: `http://192.168.78.13:8000/api/v1`
- ✅ Test credentials (username/password)
- ✅ API authentication (pp_SecureHash algorithm)
- ✅ Test inventory (5 pre-configured tags)
- ✅ Endpoint documentation with examples

### **3. Test Cases & Reporting Template**
```
📄 docs/deployment/TESTING-INVENTORY-TEMPLATE.md
```
Contains:
- ✅ 5 comprehensive test cases
- ✅ Expected responses for each test
- ✅ Test data table
- ✅ Results reporting template (to fill & return)

---

## 🚀 Testing Team Instructions

### **Step 1: Import Postman Collection (2 min)**
```
1. Open Postman Desktop App
2. Click "Import" (top-left)
3. Select: JazzCash-TopUp-API-Collection.json
4. Collection imported ✓
```

### **Step 2: Configure Environment (1 min)**
```
In Postman, set these variables:
- base_url = https://<staging-url> (will be provided)
- jazzcash_salt = (will be provided)
```

⚠️ **URLs TBD** — Staging URL will be shared once deployment is ready

### **Step 3: Run Test Cases (30 min)**
```
From TESTING-INVENTORY-TEMPLATE.md:
- TC-1: Tag Inquiry (existing tag)
- TC-2: Payment (first time)
- TC-3: Idempotency (duplicate txn)
- TC-4: Tag Not Found (error test)
- TC-5: Invalid Amount (error test)
```

### **Step 4: Report Results (5 min)**
```
Fill reporting table in TESTING-INVENTORY-TEMPLATE.md
Mark: ✓ PASS or ✗ FAIL for each test
Include notes (response times, issues, etc.)
Send back to team
```

---

## 📊 Test Inventory (Ready to Use)

All tags pre-configured and active in staging:

| E-Tag Num | Customer Name | Vehicle Reg | Current Balance | Status |
|-----------|---------------|-------------|-----------------|--------|
| E28011052000704A8F9F0AE3 | Kashif Mughal | BP-3641 | 1500.00 PKR | Active |
| E2801105200070D4FB330A36 | Ahmed Khan | KR-5890 | 3000.00 PKR | Active |
| E28011052000708A1B2C3D4E | Fatima Ali | LS-1234 | 500.00 PKR | Active |

---

## 🔐 Authentication Details

### pp_SecureHash (Signature)

**What is it?** 
HMAC-SHA256 signature for request integrity.

**Algorithm:**
```
1. Sort all request fields (except pp_SecureHash) by key name
2. Build string: SALT&field1=value1&field2=value2&…
3. Compute: HMAC_SHA256(key=SALT, message=string)
4. Convert to UPPERCASE HEX
```

**Example:**
```
SALT = "shared_salt_here"
Fields: amount=500, jazzcash_txn_id=JC001, tid=E2801105...
String = "SALT&amount=500&jazzcash_txn_id=JC001&tid=E2801105..."
pp_SecureHash = UPPER(HMAC_SHA256(...))
```

**Tools to Compute:**
- Online: https://www.freeformatter.com/hmac-generator.html
  - Algorithm: SHA256
  - Key: shared_salt_here
  - Message: your sorted string

---

## 📍 API Endpoints

### **Endpoint 1: Tag Inquiry** (Read-only)
```
POST /payments/jazzcash/inquiry/

Request:
{
  "tid": "E28011052000704A8F9F0AE3",
  "pp_SecureHash": "..."
}

Response (200):
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

### **Endpoint 2: Payment Notification** (Idempotent)
```
POST /payments/jazzcash/payment/

Request:
{
  "tid": "E28011052000704A8F9F0AE3",
  "amount": "500.00",
  "jazzcash_txn_id": "JC1234567890",
  "pp_SecureHash": "..."
}

Response (200) - First time:
{
  "success": true,
  "message": "Balance updated",
  "data": {
    "jazzcash_txn_id": "JC1234567890",
    "new_balance": "2000.00",
    "topup_id": "36ac6d87-..."
  }
}

Response (200) - Duplicate (Idempotency):
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

---

## ✅ Test Checklist

Testing team should verify:

- [ ] **TC-1:** Tag inquiry returns consumer details (200)
- [ ] **TC-2:** Payment processes correctly (200, balance increases)
- [ ] **TC-3:** Duplicate payment marked as already_processed (no double-credit)
- [ ] **TC-4:** Invalid tag returns 404 error
- [ ] **TC-5:** Invalid amount returns 400 error
- [ ] **Signature:** pp_SecureHash validation works
- [ ] **Response time:** All requests < 500ms
- [ ] **Receipt printing:** Topup receipt prints to POS80 (if applicable)

---

## 🔗 Important Links

| Item | Details |
|------|---------|
| **Staging URL** | http://192.168.78.13:8000/api/v1 |
| **Test Credentials** | See STAGING-PRODUCTION-SETUP.md |
| **API Documentation** | docs/api/jazzcash-topup-api-v1.md (full spec) |
| **Postman Import** | JazzCash-TopUp-API-Collection.json |

---

## 📞 Support Contact

For questions during testing:

| Item | Contact |
|------|---------|
| **Technical Issues** | ali.asif@itecknologi.com |
| **Infrastructure/Server** | shaneel@itecknologi.com |
| **API Logic** | See docs/api/jazzcash-topup-api-v1.md |

---

## 📦 How to Hand Over

### **Option 1: Email**
```
Attach these 3 files:
1. JazzCash-TopUp-API-Collection.json
2. STAGING-PRODUCTION-SETUP.md
3. TESTING-INVENTORY-TEMPLATE.md

Subject: QTag JazzCash API - Testing Package
Body: [Copy from EMAIL-TEMPLATE-TO-JAZZCASH.txt]
```

### **Option 2: Git Repository**
```
All files already committed to:
d:\Github\MewRf\

Testing team can:
1. Clone repo
2. Navigate to docs/postman/ + docs/deployment/
3. Import Postman collection
4. Start testing
```

### **Option 3: ZIP Archive**
```
Create ZIP with:
- JazzCash-TopUp-API-Collection.json
- STAGING-PRODUCTION-SETUP.md
- TESTING-INVENTORY-TEMPLATE.md
- POSTMAN-QUICK-REFERENCE.md (bonus)
- This file (DELIVERY-PACKAGE-FOR-TESTING.md)

Send ZIP to testing team
```

---

## 🎯 Expected Timeline

| Phase | Duration | Notes |
|-------|----------|-------|
| **Setup (Postman import)** | 5 min | Import collection, set variables |
| **Test Execution** | 30-45 min | Run 5 test cases + edge cases |
| **Results Compilation** | 15 min | Fill reporting template |
| **Total** | ~1 hour | Complete testing cycle |

---

## 📝 What Testing Team Returns

After testing, they should provide:

```
1. Filled-out TESTING-INVENTORY-TEMPLATE.md with:
   - Pass/Fail status for each test case
   - Response times
   - Any issues encountered
   - Screenshots (if applicable)
   
2. Notes on:
   - API behavior
   - Performance observations
   - Any edge cases found
   - Recommendations
```

---

## ✨ Key Features

✅ **Two Endpoints:** Tag Inquiry + Payment Notification  
✅ **Idempotency:** Same transaction ID never double-credits  
✅ **Error Handling:** Comprehensive error responses (400, 401, 404, 500)  
✅ **Signature Auth:** HMAC-SHA256 for integrity  
✅ **Best Effort:** Non-blocking (topup commits before print)  
✅ **Receipt Printing:** Auto-prints on POS80 after payment  

---

## 📚 Reference Documents

All available in repository:

- `docs/api/jazzcash-topup-api-v1.md` — Complete API specification
- `docs/postman/JazzCash-TopUp-API-Collection.json` — Postman collection
- `docs/deployment/STAGING-PRODUCTION-SETUP.md` — Setup guide
- `docs/deployment/TESTING-INVENTORY-TEMPLATE.md` — Test cases
- `POSTMAN-QUICK-REFERENCE.md` — 1-page quick reference
- `LOCAL-TESTING-SETUP.md` — For local development testing

---

**Date:** 2026-06-27  
**Status:** Ready for Testing Team  
**Backend:** Django + DRF  
**Environment:** Staging (http://192.168.78.13:8000/api/v1)

---

## ✅ Ready to Send!

All files committed to git. Testing team can:
1. Clone repo
2. Navigate to docs/postman/ and docs/deployment/
3. Start testing immediately

**Package is complete and ready for handover! 🚀**

