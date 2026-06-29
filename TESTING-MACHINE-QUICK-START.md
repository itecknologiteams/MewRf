# 🖥️ Testing Machine — Quick Start

**Deploy backend on testing machine in 10 minutes.**

---

## 🔗 URLs

```
Internal IP:  192.168.20.69
External IP:  221.120.248.114

API Endpoint:
http://221.120.248.114:8000/api/v1

Or internal:
http://192.168.20.69:8000/api/v1
```

---

## 🚀 Quick Deploy (Copy-Paste)

```bash
# SSH to testing machine
ssh user@192.168.20.69
# Or: ssh user@221.120.248.114

# Clone repo
cd ~
git clone https://github.com/your-username/MewRf.git
cd MewRf

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r mtag_backend/requirements.txt

# Configure database
cd mtag_backend
python manage.py migrate

# Run server
python manage.py runserver 0.0.0.0:8000

# ✓ API is now live at:
# http://221.120.248.114:8000/api/v1
```

---

## 📋 Step-by-Step

| Step | Command | Time |
|------|---------|------|
| 1. Clone | `git clone ...` | 2 min |
| 2. Venv | `python3 -m venv venv` | 1 min |
| 3. Install | `pip install -r requirements.txt` | 3 min |
| 4. Migrate | `python manage.py migrate` | 2 min |
| 5. Run | `python manage.py runserver 0.0.0.0:8000` | 1 min |
| **Total** | - | **~9 min** |

---

## ✅ Test API

```bash
# From your laptop
curl http://221.120.248.114:8000/api/v1/payments/jazzcash/inquiry/ \
  -H "Content-Type: application/json" \
  -d '{"tid":"E28011052000704A8F9F0AE3"}'

# Expected: 200 OK with consumer details
```

---

## 📱 Postman

1. Import: `docs/postman/JazzCash-TopUp-API-Collection.json`
2. Variable: `base_url = http://221.120.248.114:8000/api/v1`
3. Run tests ✓

---

## 🆘 Issues

| Problem | Solution |
|---------|----------|
| Port 8000 busy | `lsof -i :8000` then `kill -9 <PID>` |
| Module not found | `source venv/bin/activate` |
| DB error | `python manage.py migrate --run-syncdb` |
| API not responding | `ps aux \| grep runserver` |

---

## 📞 Commands Reference

```bash
# SSH access
ssh user@192.168.20.69
ssh user@221.120.248.114

# Stop server
pkill -f runserver

# Check logs
tail -f mtag_backend/server.log

# Run in background
nohup python manage.py runserver 0.0.0.0:8000 > server.log 2>&1 &
```

---

## 🔐 Credentials

```
Username: operator_test
Password: Operator@1234
Role: Operator
```

---

## 📊 Test Checklist

```
[ ] Server running
[ ] API responding
[ ] Postman collection updated
[ ] 5 test cases passing
[ ] Results reported
```

---

**Done! API ready for testing! 🎉**

