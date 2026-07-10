# Inventory & Booth-wise Tag Assignment System

**Version:** 1.0  
**Date:** 2026-06-24  
**Purpose:** Unregistered inventory management and booth-wise activation tracking

---

## 📋 Overview

### Current State
```
Vehicles (registered)
├─ Has owner info
├─ Has account
└─ Can process toll
```

### New State
```
INVENTORY (Unregistered)
├─ Just tag + vehicle info
├─ No owner/account
└─ Not active yet

      ↓ (Via Portal)

BOOTH ASSIGNMENT
├─ Assign inventory to booth
├─ Still unregistered
└─ Ready for activation

      ↓ (First scan at booth)

TAG ACTIVATION
├─ Tag scanned first time
├─ Becomes active
├─ Shows booth that activated it
└─ Can process toll
```

---

## 🗄️ Database Schema

### 1. Master DB - Unregistered Inventory

```sql
CREATE TABLE unregistered_inventory (
    id UUID PRIMARY KEY,
    tag_serial VARCHAR(50) UNIQUE NOT NULL,
    tid VARCHAR(50) UNIQUE NOT NULL,
    epc VARCHAR(100),
    vehicle_plate VARCHAR(20),
    vehicle_type VARCHAR(20),  -- car, truck, bus, etc
    vehicle_color VARCHAR(20),
    notes TEXT,
    
    status VARCHAR(20),  -- unregistered, booth_assigned, activated
    
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100),
    
    booth_assigned_id INT,  -- Which booth (1-7)
    booth_assigned_at TIMESTAMP,
    
    first_activated_booth_id INT,  -- Which booth first scanned it
    first_activated_at TIMESTAMP,
    
    activated_for_account_id UUID REFERENCES accounts(id),
    
    FOREIGN KEY (first_activated_booth_id) REFERENCES toll_plazas(id)
);

Status Flow:
unregistered → booth_assigned → activated
```

### 2. Portal - Booth Assignment Table

```sql
CREATE TABLE booth_inventory_assignments (
    id UUID PRIMARY KEY,
    inventory_id UUID NOT NULL REFERENCES unregistered_inventory(id),
    booth_id INT NOT NULL REFERENCES toll_plazas(id),
    
    assigned_at TIMESTAMP DEFAULT NOW(),
    assigned_by VARCHAR(100),
    
    is_active BOOLEAN DEFAULT FALSE,
    activated_at TIMESTAMP,
    
    notes TEXT
);

Example:
┌────────────────────────────────────┐
│ inventory_id │ booth_id │ status   │
├────────────────────────────────────┤
│ INV-001      │ 1        │ assigned │
│ INV-002      │ 2        │ assigned │
│ INV-003      │ 3        │ activated│
└────────────────────────────────────┘
```

### 3. Tag Activation Tracking

```sql
-- Automatically created when tag is first scanned
CREATE TABLE tag_activations (
    id UUID PRIMARY KEY,
    tag_serial VARCHAR(50) UNIQUE NOT NULL,
    tid VARCHAR(50) UNIQUE NOT NULL,
    
    first_scan_booth_id INT NOT NULL,
    first_scan_at TIMESTAMP NOT NULL,
    
    created_account_id UUID REFERENCES accounts(id),
    
    activation_type VARCHAR(20),  -- auto_created, manual
    
    created_at TIMESTAMP DEFAULT NOW()
);

Example:
┌──────────────────────────────────────┐
│ tag_serial │ tid        │ booth_id   │
├──────────────────────────────────────┤
│ SER-001    │ E2801105...│ 1          │
│ SER-002    │ E2801105...│ 2          │
│ SER-003    │ E2801105...│ 3          │
└──────────────────────────────────────┘
```

---

## 🎯 Workflow

### Step 1: Upload Unregistered Inventory

```
Admin Portal
    ↓
Upload CSV/Excel with:
├─ tag_serial
├─ tid
├─ vehicle_plate
├─ vehicle_type
└─ vehicle_color

    ↓

Backend:
├─ Validate tags not duplicate
├─ Insert into unregistered_inventory
├─ status = "unregistered"
└─ Show upload summary
```

**API Endpoint:**
```
POST /api/inventory/upload
Content-Type: multipart/form-data

Request:
file: <CSV file>

Response:
{
  "success": true,
  "added": 100,
  "duplicates": 5,
  "errors": ["Invalid TID for row 3"]
}

Database Result:
unregistered_inventory table updated with 100 new tags
```

---

### Step 2: Booth-wise Assignment (Portal)

```
Admin Portal
    ↓
1. View unregistered inventory
2. Filter by: vehicle type, status
3. Select tags to assign
4. Choose booth (Plaza 1-7)
5. Click "Assign to Booth"

    ↓

Backend:
├─ Update booth_assigned_id
├─ Update status = "booth_assigned"
├─ Create record in booth_inventory_assignments
└─ Show confirmation
```

**API Endpoint:**
```
POST /api/inventory/assign-booth

Request:
{
  "inventory_ids": ["INV-001", "INV-002", "INV-003"],
  "booth_id": 2,
  "assigned_by": "admin@company.com"
}

Response:
{
  "success": true,
  "assigned": 3,
  "booth_id": 2,
  "message": "3 tags assigned to Booth 2"
}

Database Result:
- unregistered_inventory.booth_assigned_id = 2
- booth_inventory_assignments created
- status = "booth_assigned"
```

---

### Step 3: Tag Activation (First Scan at Booth)

```
Booth 2 - RFID Scanner
    ↓
Vehicle arrives at toll
    ↓
Scan RFID tag: tag_serial = "SER-002"
    ↓
Check unregistered_inventory:
├─ Found: SER-002
├─ Status: "booth_assigned"
├─ Assigned to: Booth 2 ✅
    ↓
Activation Options:
1️⃣ Quick Activation (Auto-create account)
2️⃣ Link to Existing Account
```

#### Option 1: Quick Activation (Create New Account)

```
Booth Staff:
├─ Enters customer name
├─ Enters phone number
├─ Enters vehicle details (from tag)
    ↓
Backend:
├─ Create Account (owner) in accounts table
├─ Create Vehicle registration in vehicles table
├─ Create TopUp record (initial balance)
├─ Update unregistered_inventory:
│  ├─ status = "activated"
│  ├─ activated_for_account_id = <new_account_id>
│  ├─ first_activated_booth_id = 2
│  └─ first_activated_at = NOW()
├─ Create tag_activations record
└─ Show confirmation
```

**API Endpoint:**
```
POST /api/inventory/activate

Request:
{
  "tag_serial": "SER-002",
  "tid": "E2801105...",
  "customer_name": "Sheikh Ali",
  "customer_phone": "03001234567",
  "initial_topup": 1000,
  "payment_method": "CASH",
  "activation_booth_id": 2
}

Response:
{
  "success": true,
  "account_created": true,
  "account_id": "UUID-123",
  "message": "Tag activated at Booth 2 for customer: Sheikh Ali"
}

Database Result:
✅ unregistered_inventory.status = "activated"
✅ unregistered_inventory.first_activated_booth_id = 2
✅ New vehicle created
✅ New account created
✅ Inventory now active for toll collection
```

#### Option 2: Link to Existing Account

```
Booth Staff:
├─ Search for customer (by phone/name)
├─ Select existing account
├─ Click "Link Tag"
    ↓
Backend:
├─ Update unregistered_inventory:
│  ├─ activated_for_account_id = <existing_account_id>
│  ├─ first_activated_booth_id = 2
│  ├─ first_activated_at = NOW()
│  └─ status = "activated"
├─ Create tag_activations record
└─ Show confirmation
```

**API Endpoint:**
```
POST /api/inventory/activate-existing

Request:
{
  "tag_serial": "SER-002",
  "tid": "E2801105...",
  "account_id": "UUID-existing",
  "activation_booth_id": 2
}

Response:
{
  "success": true,
  "account_id": "UUID-existing",
  "message": "Tag linked to existing account"
}

Database Result:
✅ unregistered_inventory linked to account
✅ Now active for that account's toll collection
```

---

## 📊 Inventory Dashboard (Portal)

### View All Inventory

```
Dashboard shows:

Total: 1000 tags
├─ Unregistered: 600
│  ├─ Status: Waiting for assignment
│  └─ Action: Assign to booth
│
├─ Booth Assigned: 300
│  ├─ Booth 1: 50 tags
│  ├─ Booth 2: 80 tags
│  └─ Action: Ready for activation
│
└─ Activated: 100
   ├─ Booth 1: 30 tags
   ├─ Booth 2: 40 tags
   └─ Shows: Which booth activated
```

### Inventory List View

```
┌─────────────────────────────────────────────────────────┐
│ Tag Serial │ Vehicle │ Status       │ Booth    │ Action│
├─────────────────────────────────────────────────────────┤
│ SER-001    │ Car     │ Unregistered │ -        │ Assign│
│ SER-002    │ Truck   │ Assigned     │ Booth 2  │ View │
│ SER-003    │ Bus     │ Activated    │ Booth 3* │ View │
└─────────────────────────────────────────────────────────┘

* Booth 3 = Where it was first activated
```

### Filter Options

```
Status:
├─ All
├─ Unregistered
├─ Booth Assigned
└─ Activated

Vehicle Type:
├─ All
├─ Car
├─ Truck
├─ Bus
└─ Motorcycle

Booth:
├─ All
├─ Booth 1
├─ Booth 2
└─ ... Booth 7
```

---

## 🔄 Inventory Status Flow

```
                    Unregistered
                         │
                    (Upload CSV)
                         │
                         ↓
                   Booth Assigned
                         │
                  (First Scan at Booth)
                         │
                         ↓
                      Activated
        (Active in toll system, linked to account)
        
Tracking:
✅ Created at: Master DB
✅ Assigned to: Which booth (1-7)
✅ Activated by: Which booth first scanned it
✅ Activated for: Which account/customer
```

---

## 🎯 Key Features

### 1. Inventory Upload

```
✅ CSV/Excel upload
✅ Bulk tag import
✅ Duplicate detection
✅ Error reporting
✅ Preview before confirm
```

### 2. Booth Assignment

```
✅ Select multiple tags
✅ Assign to booth
✅ View assignment history
✅ Reassign if needed
```

### 3. Activation Tracking

```
✅ First booth activation recorded
✅ Customer linked to tag
✅ Account auto-created or linked
✅ Toll collection enabled
```

### 4. Reports

```
✅ Inventory by status
✅ Inventory by booth
✅ Activation rate
✅ Unused inventory
```

---

## 📋 Frontend Pages Needed

### 1. Inventory Management Page

```
Route: /admin/inventory

Features:
├─ Upload unregistered tags
├─ View all inventory
├─ Filter by status/booth
├─ Assign to booth
├─ Bulk actions
└─ Download report
```

### 2. Booth Assignment Page

```
Route: /admin/booth-assignment

Features:
├─ View unregistered tags
├─ Select tags
├─ Choose booth
├─ Confirm assignment
└─ View assignment history
```

### 3. Booth Operations (Modified)

```
Route: /booth/operations

When scanning tag:
├─ Check if in unregistered_inventory
├─ If yes:
│  ├─ Check booth_assigned_id
│  ├─ If assigned to this booth → Activate
│  ├─ If assigned to different booth → Reject
│  └─ If unassigned → Reject
├─ Show activation form
├─ Quick create or link account
└─ Complete activation
```

---

## ✅ Implementation Checklist

### Backend (Django)

```
Models:
[ ] UnregisteredInventory model
[ ] BoothInventoryAssignment model
[ ] TagActivation model

API Endpoints:
[ ] POST /api/inventory/upload (bulk upload)
[ ] GET /api/inventory (list unregistered)
[ ] POST /api/inventory/assign-booth (booth assignment)
[ ] POST /api/inventory/activate (quick create)
[ ] POST /api/inventory/activate-existing (link to account)
[ ] GET /api/inventory/reports (stats)

Serializers:
[ ] UnregisteredInventorySerializer
[ ] BoothAssignmentSerializer
[ ] ActivationSerializer
```

### Frontend (React)

```
Pages:
[ ] InventoryManagement.tsx
[ ] BoothAssignmentPage.tsx
[ ] ActivationModal.tsx

Components:
[ ] InventoryTable.tsx
[ ] InventoryFilters.tsx
[ ] UploadModal.tsx
[ ] AssignmentModal.tsx
[ ] ActivationForm.tsx

Context/Hooks:
[ ] useInventory() - fetch and manage
[ ] useAssignment() - booth assignment logic
```

---

## 🚀 Deployment Order

```
1. Database migration (create tables)
2. Django models & serializers
3. API endpoints implementation
4. Frontend: Inventory management page
5. Frontend: Booth assignment page
6. Booth operations: Tag activation
7. Testing & validation
8. Deployment
```

---

**Document Complete** ✅

Ready for implementation!
