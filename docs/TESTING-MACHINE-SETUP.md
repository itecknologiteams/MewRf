# 🖥️ Testing Machine Deployment — QTag Backend

**Deploy backend on testing machine for API testing.**

Testing Machine:
- **Internal IP:** 192.168.20.69
- **External IP:** 221.120.248.114
- **OS:** Linux (Ubuntu/Debian)

---

## 📋 Prerequisites

```bash
# Check if installed
python3 --version    # Should be Python 3.8+
pip3 --version
git --version
```

If not installed:
```bash
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv git postgresql postgresql-contrib
```

---

## 🚀 Step 1: Clone Repository

```bash
# SSH to testing machine
ssh user@192.168.20.69

# Or use external IP
ssh user@221.120.248.114

# Navigate to home
cd ~

# Clone MewRf repo
git clone https://github.com/your-username/MewRf.git
cd MewRf
```

---

## 🔧 Step 2: Setup Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Verify
which python  # Should show venv path
```

---

## 📦 Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r mtag_backend/requirements.txt

# Verify
pip list | grep Django  # Should show Django 6.0.4
```

---

## 🗄️ Step 4: Setup Database

### **Option A: SQLite (Quick Testing)**

```bash
cd mtag_backend

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
# Follow prompts

# Done ✓
```

### **Option B: PostgreSQL (Recommended)**

```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database
sudo -u postgres psql << EOF
CREATE DATABASE qtag;
CREATE USER qtag_user WITH PASSWORD 'secure_password_here';
ALTER ROLE qtag_user SET client_encoding TO 'utf8';
ALTER ROLE qtag_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE qtag_user SET default_transaction_deferrable TO on;
ALTER ROLE qtag_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE qtag TO qtag_user;
\q
EOF

# Test connection
psql -h localhost -U qtag_user -d qtag
# Password: secure_password_here
# \q to exit
```

---

## ⚙️ Step 5: Configure Environment (.env)

Create `mtag_backend/.env`:

```bash
cd mtag_backend

cat > .env << 'EOF'
DEBUG=False
SECRET_KEY=your-secret-key-here-change-this-in-production
ALLOWED_HOSTS=192.168.20.69,221.120.248.114,localhost,127.0.0.1

# Database (PostgreSQL)
DATABASE_URL=postgresql://qtag_user:secure_password_here@localhost:5432/qtag

# Or SQLite
# DATABASE_URL=sqlite:///db.sqlite3

# JWT Settings
JWT_EXPIRATION=3600

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

## 🗄️ Step 6: Run Migrations

```bash
cd mtag_backend

# Apply migrations
python manage.py migrate

# Expected output:
# Operations to perform:
#   Apply all migrations: admin, auth, accounts, ...
# Running migrations:
#   Applying accounts.0001_initial... OK
#   ...
```

---

## 👤 Step 7: Create Test User

```bash
cd mtag_backend

python manage.py shell << 'EOF'
from apps.users.models import User

# Create operator user
user = User.objects.create_user(
    phone='03009999999',
    password='Operator@1234',
    full_name='Test Operator',
    is_operator=True
)
print(f"Created user: {user.phone}")

# Or create via Django shell interactively:
# python manage.py createsuperuser
EOF
```

---

## 🚀 Step 8: Start Backend Server

### **Option A: Development Server**

```bash
cd mtag_backend

# Run server on all interfaces
python manage.py runserver 0.0.0.0:8000

# Expected output:
# Starting development server at http://0.0.0.0:8000/
# Quit the server with CONTROL-C.

# Now accessible at:
# - Internal:  http://192.168.20.69:8000/api/v1
# - External:  http://221.120.248.114:8000/api/v1
```

### **Option B: Production Server (Gunicorn)**

```bash
cd mtag_backend

# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --log-file -

# Now accessible at:
# - Internal:  http://192.168.20.69:8000/api/v1
# - External:  http://221.120.248.114:8000/api/v1
```

### **Option C: Background (nohup)**

```bash
cd mtag_backend

# Start in background
nohup python manage.py runserver 0.0.0.0:8000 > server.log 2>&1 &

# Check if running
ps aux | grep runserver

# View logs
tail -f server.log

# Stop server
pkill -f runserver
```

---

## ✅ Step 9: Test Backend

From your laptop, test the API:

```bash
# Test Tag Inquiry
curl -X POST http://221.120.248.114:8000/api/v1/payments/jazzcash/inquiry/ \
  -H "Content-Type: application/json" \
  -d '{"tid":"E28011052000704A8F9F0AE3"}'

# Expected response (200):
# {
#   "success": true,
#   "message": "OK",
#   "data": { ... }
# }
```

---

## 🔗 URLs for Testing

Once running:

```
Internal URL:  http://192.168.20.69:8000/api/v1
External URL:  http://221.120.248.114:8000/api/v1
```

---

## 📝 Update Postman Collection

In Postman variables:

```
base_url = http://221.120.248.114:8000/api/v1
```

Or create environment:
```
Name: Testing Machine
base_url: http://221.120.248.114:8000/api/v1
jazzcash_salt: TEST_SALT_DEV
```

---

## 🔧 Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port
python manage.py runserver 0.0.0.0:9000
```

### ModuleNotFoundError

```bash
# Make sure venv is activated
source venv/bin/activate

# Reinstall requirements
pip install -r mtag_backend/requirements.txt
```

### Database Connection Error

```bash
# Check if PostgreSQL running
sudo systemctl status postgresql

# Check .env DATABASE_URL
cat mtag_backend/.env | grep DATABASE_URL

# Test connection
psql -h localhost -U qtag_user -d qtag
```

### Migration Error

```bash
# Show migration status
python manage.py showmigrations

# Rerun migrations
python manage.py migrate --run-syncdb
```

---

## 🎯 Quick Setup (Copy-Paste)

```bash
# SSH to testing machine
ssh user@192.168.20.69

# Clone & setup
cd ~
git clone https://github.com/your-username/MewRf.git
cd MewRf
python3 -m venv venv
source venv/bin/activate
pip install -r mtag_backend/requirements.txt

# Configure
cd mtag_backend
cp .env.example .env
# Edit .env with your settings

# Migrate & run
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

# Now accessible at:
# http://221.120.248.114:8000/api/v1 ✓
```

---

## 📊 Testing Machine Setup Checklist

```
[ ] Python 3 installed
[ ] Git installed
[ ] Repo cloned
[ ] Venv created & activated
[ ] Requirements installed
[ ] .env configured
[ ] Database migrated
[ ] Server running
[ ] API responding to requests
[ ] Postman collection updated with new URL
```

---

## 📞 Quick Help

| Issue | Command |
|-------|---------|
| Check Python | `python3 --version` |
| Activate venv | `source venv/bin/activate` |
| Check server | `ps aux \| grep runserver` |
| View logs | `tail -f mtag_backend/server.log` |
| Stop server | `pkill -f runserver` |
| Test API | `curl http://221.120.248.114:8000/api/v1/...` |

---

## 🚀 Next Steps

1. ✅ Deploy backend on testing machine
2. ✅ Verify API responds
3. ✅ Update Postman with new URLs
4. ✅ Share with testing team
5. ✅ Testing team runs test cases

---

**Once server is running, you have:**

```
Public API:   http://221.120.248.114:8000/api/v1
Internal API: http://192.168.20.69:8000/api/v1

Both can be used for testing via Postman ✓
```

