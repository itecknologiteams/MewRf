# 🖥️ Testing Machine Deployment — With Remote Database

**Deploy backend on testing machine (192.168.20.69) connected to remote database (192.168.21.31)**

---

## 🔗 Infrastructure

```
Testing Machine:   192.168.20.69:8000 (Backend API)
Database Server:   192.168.21.31:6632 (PostgreSQL)

Flow:
Testing Machine → queries → Database Server
```

---

## 📋 Database Credentials

```
Host:     192.168.21.31
Port:     6632
Database: New Banega
User:     employee_dev
Password: EmP$D3v#2026!qR4
```

---

## 🚀 Step-by-Step Setup

### **Step 1: SSH to Testing Machine**

```bash
ssh user@192.168.20.69
# Or use external IP: ssh user@221.120.248.114
```

### **Step 2: Clone Repository**

```bash
cd ~
git clone https://github.com/your-username/MewRf.git
cd MewRf
```

### **Step 3: Create Virtual Environment**

```bash
python3 -m venv venv
source venv/bin/activate
```

### **Step 4: Install Dependencies**

```bash
pip install --upgrade pip
pip install -r mtag_backend/requirements.txt
```

### **Step 5: Configure Environment (.env)**

```bash
cd mtag_backend

cat > .env << 'EOF'
DEBUG=False
SECRET_KEY=django-insecure-test-key-change-this-in-production
ALLOWED_HOSTS=192.168.20.69,221.120.248.114,localhost,127.0.0.1

# Remote Database Configuration
DATABASE_URL=postgresql://employee_dev:EmP%24D3v%232026%21qR4@192.168.21.31:6632/New%20Banega
# Unencoded: postgresql://employee_dev:EmP$D3v#2026!qR4@192.168.21.31:6632/New Banega

# Or explicit format:
DB_ENGINE=django.db.backends.postgresql
DB_HOST=192.168.21.31
DB_PORT=6632
DB_NAME=New Banega
DB_USER=employee_dev
DB_PASSWORD=EmP$D3v#2026!qR4

# JWT & Auth
JWT_EXPIRATION=3600
SECRET_KEY_JWT=test-jwt-key-change-in-production

# Topup Receipt Printing
TOPUP_RECEIPT_PRINT_ENABLED=False
POS_PRINTER_NAME=POS80
RECEIPT_LOGO_PATH=/path/to/receipt_logo.png

# JazzCash Integration
JAZZCASH_VERIFY_HASH=False
JAZZCASH_INTEGRITY_SALT=TEST_SALT_DEV
EOF

# Verify
cat .env
```

---

### **Step 6: Test Database Connection**

```bash
# Test psycopg2 connection
python3 << 'EOF'
import psycopg2

try:
    conn = psycopg2.connect(
        host="192.168.21.31",
        port=6632,
        database="New Banega",
        user="employee_dev",
        password="EmP$D3v#2026!qR4"
    )
    print("✓ Database connection successful!")
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    print("PostgreSQL version:", cursor.fetchone())
    cursor.close()
    conn.close()
except Exception as e:
    print("✗ Connection failed:", e)
EOF
```

**Expected output:**
```
✓ Database connection successful!
PostgreSQL version: (PostgreSQL 12.x ..., ...)
```

---

### **Step 7: Run Django Migrations**

```bash
cd mtag_backend

# Show migration status
python manage.py showmigrations

# Run migrations
python manage.py migrate

# Expected output:
# Operations to perform:
#   Apply all migrations: admin, auth, accounts, vehicles, ...
# Running migrations:
#   Applying accounts.0001_initial... OK
#   Applying auth.0001_initial... OK
#   ... (more migrations)
```

---

### **Step 8: Create Test Data** (Optional)

```bash
python manage.py shell << 'EOF'
from apps.users.models import User
from apps.vehicles.models import Tag, Vehicle
from decimal import Decimal

# Create operator user
operator = User.objects.create_user(
    phone='03009999999',
    password='Operator@1234',
    full_name='Test Operator',
    is_operator=True
)
print(f"✓ Created operator: {operator.phone}")

# Create test vehicle owner
owner = User.objects.create_user(
    phone='03001234567',
    password='TestPass123',
    full_name='Kashif Mughal',
    cnic='35202-1234567-8'
)
print(f"✓ Created owner: {owner.full_name}")

# Create test vehicle
vehicle = Vehicle.objects.create(
    plate_number='BP-3641',
    vehicle_type='car',
    owner=owner
)
print(f"✓ Created vehicle: {vehicle.plate_number}")

# Create test tag
tag = Tag.objects.create(
    tid='E28011052000704A8F9F0AE3',
    tag_serial='TID20260629001',
    vehicle=vehicle,
    status='ACTIVE'
)
print(f"✓ Created tag: {tag.tid}")

# Create account with balance
from apps.accounts.models import Account
account = Account.objects.create(
    vehicle=vehicle,
    user=owner,
    balance=Decimal('1500.00')
)
print(f"✓ Created account: balance {account.balance} PKR")

print("\n✓ All test data created successfully!")
EOF
```

---

### **Step 9: Run Server**

```bash
python manage.py runserver 0.0.0.0:8000
```

**Expected output:**
```
Starting development server at http://0.0.0.0:8000/
Django version 6.0.4, using settings 'config.settings.base'
Starting development server at http://0.0.0.0:8000/
```

API is now live at:
- **External:** http://221.120.248.114:8000/api/v1
- **Internal:** http://192.168.20.69:8000/api/v1

---

## ✅ Verify Setup

```bash
# From your laptop - Test tag inquiry
curl -X POST http://221.120.248.114:8000/api/v1/payments/jazzcash/inquiry/ \
  -H "Content-Type: application/json" \
  -d '{"tid":"E28011052000704A8F9F0AE3"}'

# Expected response (200):
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

## 📝 .env File (Ready to Copy)

```bash
DEBUG=False
SECRET_KEY=django-insecure-test-key-change-this-in-production
ALLOWED_HOSTS=192.168.20.69,221.120.248.114,localhost,127.0.0.1

DB_ENGINE=django.db.backends.postgresql
DB_HOST=192.168.21.31
DB_PORT=6632
DB_NAME=New Banega
DB_USER=employee_dev
DB_PASSWORD=EmP$D3v#2026!qR4

JWT_EXPIRATION=3600
SECRET_KEY_JWT=test-jwt-key-change-in-production

TOPUP_RECEIPT_PRINT_ENABLED=False
POS_PRINTER_NAME=POS80
RECEIPT_LOGO_PATH=/path/to/receipt_logo.png

JAZZCASH_VERIFY_HASH=False
JAZZCASH_INTEGRITY_SALT=TEST_SALT_DEV
```

---

## 🚀 Quick Deploy (One Command)

```bash
# Full setup in one go:
cd ~ && \
git clone https://github.com/your-username/MewRf.git && \
cd MewRf && \
python3 -m venv venv && \
source venv/bin/activate && \
pip install -r mtag_backend/requirements.txt && \
cd mtag_backend && \
python manage.py migrate && \
python manage.py runserver 0.0.0.0:8000
```

---

## 🔧 Troubleshooting

### **Connection to Database Failed**

```bash
# Check if port 6632 is accessible from testing machine
telnet 192.168.21.31 6632

# If hangs: check firewall on database server
# If "Connection refused": PostgreSQL not running or listening on 6632
```

### **Password Special Characters Error**

The password `EmP$D3v#2026!qR4` has special characters:
- `$` → `%24`
- `#` → `%23`
- `!` → `%21`

DATABASE_URL should be:
```
postgresql://employee_dev:EmP%24D3v%232026%21qR4@192.168.21.31:6632/New%20Banega
```

Or use .env with unencoded values (Django handles encoding).

### **Migration Fails**

```bash
# Check database tables
python manage.py dbshell
# Then: \dt  (list tables)
# Then: \q   (quit)

# If tables exist, reset migrations
python manage.py migrate --fake-initial
```

### **API Says "No account found"**

Make sure test data is created:
```bash
python manage.py shell
>>> from apps.accounts.models import Account
>>> Account.objects.all().count()  # Should be > 0
```

---

## 📱 Postman Setup

```
base_url = http://221.120.248.114:8000/api/v1
jazzcash_salt = TEST_SALT_DEV
pp_SecureHash = (leave blank for testing)
```

---

## ✅ Complete Checklist

```
[ ] Testing machine has Python 3 + Git
[ ] Repo cloned
[ ] Venv created & activated
[ ] Requirements installed
[ ] .env created with remote DB credentials
[ ] Database connection test passed
[ ] Migrations ran successfully
[ ] Test data created
[ ] Server running on 0.0.0.0:8000
[ ] API responds to curl requests
[ ] Postman collection updated
```

---

## 📊 Final Architecture

```
┌──────────────────────────┐
│  Postman / Testing Team  │
└────────────┬─────────────┘
             │ HTTP Requests
             ▼
┌─────────────────────────────────────┐
│  Testing Machine (192.168.20.69)    │
│  - Django Backend                   │
│  - API on port 8000                 │
│  - Accessible via 221.120.248.114   │
└─────────────────┬───────────────────┘
                  │ DB Queries
                  ▼
    ┌─────────────────────────────┐
    │ Database Server (192.168.21.31) │
    │ - PostgreSQL on port 6632   │
    │ - Database: New Banega      │
    │ - User: employee_dev        │
    └─────────────────────────────┘
```

---

## 🎯 Next Steps

1. ✅ Deploy backend on testing machine
2. ✅ Connect to remote database
3. ✅ Run migrations
4. ✅ Create test data
5. ✅ API accessible to testing team
6. ✅ Postman tests can run

---

**Time to Deploy:** ~10 minutes  
**API Ready at:** http://221.120.248.114:8000/api/v1 ✓

