# Phase 2 Implementation Plan: Booth Operations Integration

**Status:** 🟢 STARTING  
**Target:** 2026-07-11 to 2026-07-15 (5 days)

---

## 📋 Overview

Integrate the inventory management system with booth operations (toll entry/exit).

**Key Feature:** When a tag is scanned at a booth:
1. ✅ Check if tag exists in unregistered_inventory
2. ✅ If unregistered → Show activation modal
3. ✅ If already activated → Proceed with toll operation
4. ✅ If not assigned to booth → Show error

---

## 🎯 Phase 2 Scope

### Backend Changes

#### 1. Add Inventory Check Endpoint
```
GET /api/v1/vehicles/inventory/check/{tag_serial}/
Response:
{
  "status": "unregistered|booth_assigned|activated",
  "booth_assigned_id": 2,
  "can_activate_at_booth": 2
}
```

#### 2. Modify Tag Activation Views
- Update TagActivationQuickCreateView to handle booth validation
- Update TagActivationLinkExistingView to handle booth validation
- Add error messages for booth mismatch

#### 3. Logging & Audit
- Log all activation attempts
- Track failed activations with reason
- Audit trail for booth operations

### Frontend Changes

#### 1. TollOperations.tsx Enhancement
```typescript
When tag is scanned:
├─ Check if unregistered
├─ If yes → Show ActivationModal
├─ If no → Continue with toll operation

ActivationModal:
├─ Show tag details
├─ Option 1: Quick Create
│  └─ Customer name, phone, topup
├─ Option 2: Link Existing
│  └─ Search existing customer
└─ Proceed to toll after activation
```

#### 2. New Components

**InventoryActivationModal.tsx**
- Quick create account
- Link to existing account
- Validation & error handling

**InventoryCheckWarning.tsx**
- Show if tag not assigned to this booth
- Show activation status

---

## 🔄 Workflow: Tag Scan at Booth

```
User scans tag at Entry/Exit
  │
  ├─ Check unregistered_inventory table
  │
  ├─ If status = "unregistered"
  │  │
  │  └─ Check booth_assigned_id
  │     │
  │     ├─ If not assigned → Show error "Tag not assigned to this booth"
  │     │
  │     ├─ If assigned to different booth → Show error "Tag assigned to Booth X, not Booth Y"
  │     │
  │     └─ If assigned to THIS booth → Show ActivationModal
  │        │
  │        ├─ User selects: Quick Create OR Link Existing
  │        │
  │        ├─ Quick Create:
  │        │  ├─ Enter customer name, phone, initial topup
  │        │  ├─ System creates: User, Vehicle, Account
  │        │  ├─ Records: TagActivation (auto_created)
  │        │  └─ Updates: UnregisteredInventory status=activated
  │        │
  │        └─ Link Existing:
  │           ├─ Search for existing customer
  │           ├─ Select customer from results
  │           ├─ Records: TagActivation (linked)
  │           └─ Updates: UnregisteredInventory status=activated
  │
  ├─ If status = "booth_assigned"
  │  │
  │  └─ Show error "Tag must be activated first"
  │
  └─ If status = "activated" OR tag not in inventory table
     │
     └─ Proceed with normal toll operation
```

---

## 📂 Files to Modify/Create

### Backend

```
mtag_backend/apps/vehicles/views.py
  ├─ Add InventoryCheckView
  ├─ Update TagActivationQuickCreateView (booth validation)
  └─ Update TagActivationLinkExistingView (booth validation)

mtag_backend/apps/vehicles/urls.py
  └─ Add route: GET /inventory/check/{tag_serial}/

mtag_backend/apps/vehicles/tests_inventory.py
  ├─ Add test_inventory_check
  ├─ Add test_activation_booth_mismatch
  └─ Add test_activation_not_assigned
```

### Frontend

```
rfid-frontend/src/pages/TollOperations.tsx
  └─ Add inventory check logic to entry/exit forms

rfid-frontend/src/components/InventoryActivationModal.tsx (NEW)
  ├─ Display tag details
  ├─ Quick create form
  ├─ Link existing form
  └─ Success confirmation

rfid-frontend/src/components/InventoryCheckWarning.tsx (NEW)
  ├─ Show booth mismatch error
  ├─ Show not assigned error
  └─ Show activation required error

rfid-frontend/src/services/inventoryApi.ts (NEW)
  ├─ checkInventoryStatus()
  ├─ activateTagQuick()
  └─ activateTagLink()
```

---

## 🎯 Daily Breakdown

### Day 1: Backend Inventory Check
```
[ ] Create InventoryCheckView
[ ] Add URL route
[ ] Test endpoint with Postman
[ ] Add unit tests
```

### Day 2: Backend Validation
```
[ ] Update TagActivationQuickCreateView
[ ] Update TagActivationLinkExistingView
[ ] Add booth mismatch validation
[ ] Add error messages
[ ] Test full activation flow
```

### Day 3: Frontend Setup
```
[ ] Create inventoryApi service
[ ] Create InventoryActivationModal component
[ ] Create InventoryCheckWarning component
[ ] Test components in isolation
```

### Day 4: TollOperations Integration
```
[ ] Add inventory check to entry form
[ ] Add inventory check to exit form
[ ] Wire up activation modal
[ ] Test full workflow
```

### Day 5: Testing & Polish
```
[ ] End-to-end testing
[ ] Error handling verification
[ ] UI/UX polish
[ ] Documentation
[ ] Production readiness
```

---

## ✅ Success Criteria

```
✅ Tag scan checks unregistered_inventory
✅ Unregistered tags show activation modal
✅ Quick create account works
✅ Link existing account works
✅ Booth assignment validation works
✅ Booth mismatch shows error
✅ First activation booth recorded
✅ Activated tags proceed to toll
✅ No data loss on errors
✅ Full audit trail logged
```

---

## 🚀 Implementation Order

1. **Backend: Inventory Check**
   - GET endpoint to check tag status
   - Test with Postman

2. **Backend: Booth Validation**
   - Update activation endpoints
   - Add validation logic

3. **Frontend: Services**
   - Create API client functions
   - Error handling

4. **Frontend: Components**
   - Activation modal
   - Warning messages

5. **Frontend: Integration**
   - Connect to TollOperations
   - Full workflow

6. **Testing**
   - End-to-end tests
   - Error scenarios
   - Edge cases

---

**Next: Start with Backend InventoryCheckView** 🚀

