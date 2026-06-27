# 🚂 Railway Deployment Guide — QTag API

**Deploy to Railway in 15 minutes. Testing team gets public URL.**

---

## ✅ Prerequisites

- [ ] Railway account (free signup: railway.app)
- [ ] GitHub account with MewRf repo access
- [ ] Git installed locally

---

## 🚀 Step-by-Step Deployment

### **Step 1: Create Railway Account** (2 min)

1. Go to https://railway.app
2. Click **"Sign Up"** (use GitHub)
3. Authorize GitHub access
4. Done ✓

---

### **Step 2: Create New Project** (1 min)

1. Dashboard → **"New Project"**
2. Select **"Deploy from GitHub"**
3. Select repository: **MewRf**
4. Confirm ✓

---

### **Step 3: Configure Service** (3 min)

Railway auto-detects Django. Configure:

**Environment Variables:**

Click **"Variables"** → Add these:

```
DJANGO_SETTINGS_MODULE = config.settings.base
DEBUG = False
ALLOWED_HOSTS = *.railway.app
SECRET_KEY = [auto-generated, don't change]
```

Database:
- Click **"Add Database"** → **"PostgreSQL"**
- Railway auto-configures DATABASE_URL
- Done ✓

---

### **Step 4: Configure Procfile** (1 min)

Create `Procfile` in project root:

```
web: python mtag_backend/manage.py migrate && gunicorn config.wsgi --log-file -
```

Or Railway auto-detects. If not, create above file.

---

### **Step 5: Deploy** (5 min)

1. Push code to GitHub:
```bash
git add .
git commit -m "Deploy to Railway"
git push origin main
```

2. Railway auto-deploys from main branch
3. Watch build logs in Railway dashboard
4. Wait for "✓ Deployment Successful"

---

### **Step 6: Get Public URL** (1 min)

1. Railway Dashboard → Your Project
2. Click **"Deployments"** → Latest deployment
3. Look for **"Railway URL"** or **"Public URL"**
4. Copy URL: `https://qtag-api-xxx.railway.app`

---

## 🔗 Your Public URL Format

```
https://[project-name]-[random].railway.app
Example: https://qtag-api-staging-x7k2.railway.app
```

---

## ✅ Post-Deployment Checklist

```
[ ] Backend running on Railway
[ ] Database migrated
[ ] API responds to requests
[ ] HTTPS working
[ ] Test with curl:
```

**Quick Test:**
```bash
curl https://qtag-api-xxx.railway.app/api/v1/payments/jazzcash/inquiry/ \
  -H "Content-Type: application/json" \
  -d '{"tid":"E28011052000704A8F9F0AE3"}'

Expected: 200 response with consumer details
```

---

## 🔧 Troubleshooting

### **Build Failed**

**Symptom:** Railway shows red ✗ error

**Check:**
1. Procfile correct?
2. requirements.txt has all dependencies?
3. No syntax errors in code?

**Fix:**
```bash
# Check locally first
python manage.py runserver

# If works locally, push again
git push origin main
```

---

### **502 Bad Gateway**

**Symptom:** `https://qtag-api-xxx.railway.app` shows 502

**Cause:** App not running properly

**Fix:**
1. Check Railway logs
2. Verify environment variables
3. Check database connection
4. Restart deployment

---

### **Database Connection Error**

**Symptom:** API works but database fails

**Fix:**
```python
# settings/base.py should have:
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default='postgresql://...',
        conn_max_age=600
    )
}
```

Railway sets `DATABASE_URL` automatically.

---

## 🌐 Now Use in Postman

Once Railway URL is ready:

### **Update Postman Collection:**

In Postman variables:
```
base_url = https://qtag-api-xxx.railway.app/api/v1
```

### **Share with Testing Team:**

```
Here's the public API URL for testing:

API Endpoint: https://qtag-api-xxx.railway.app/api/v1

Test Credentials:
- Username: operator_test
- Password: Operator@1234

Postman Collection: [attached]
Test Cases: [attached]

Please import collection and run tests.
```

---

## 📊 Testing Team Workflow

```
1. Gets URL: https://qtag-api-xxx.railway.app/api/v1
2. Opens Postman
3. Imports collection
4. Updates base_url variable
5. Runs 5 test cases ✓
6. Reports results
```

---

## 💰 Railway Pricing

```
Free Tier:
- 500 hours/month of runtime
- Perfect for staging/testing
- No credit card needed (limited)

Paid:
- $5/month usage-based
- Recommend for production
```

---

## 📝 After Deployment

### **Update Documentation:**

1. **STAGING-PRODUCTION-SETUP.md**
```markdown
| **Staging** | `https://qtag-api-xxx.railway.app/api/v1` | ✅ Active |
```

2. **Postman Collection**
```json
"base_url": "https://qtag-api-xxx.railway.app/api/v1"
```

3. **DELIVERY-PACKAGE-FOR-TESTING.md**
```markdown
Staging URL: https://qtag-api-xxx.railway.app/api/v1
```

---

## 🎯 Quick Command Reference

```bash
# Check if requirements.txt has everything
pip freeze > requirements.txt

# Test locally before pushing
python manage.py runserver

# Push to trigger Railway deployment
git push origin main

# Check Railway logs
railway logs

# Get project info
railway status
```

---

## ✅ Complete Checklist

- [ ] Railway account created
- [ ] GitHub repo connected
- [ ] Environment variables set
- [ ] Database (PostgreSQL) added
- [ ] Procfile created
- [ ] Code pushed to GitHub
- [ ] Deployment successful (green ✓)
- [ ] Public URL obtained
- [ ] API responds to test request
- [ ] Postman collection updated
- [ ] Testing team notified
- [ ] Testing team can access API

---

## 📞 Railway Support

- Docs: https://docs.railway.app
- Status: https://status.railway.app
- Community: Discord link on Railway

---

## 🎉 Result

```
Before: API works locally only (192.168.78.13)
After:  API works publicly! (https://qtag-api-xxx.railway.app)

Testing team anywhere → Can use Postman → Can test APIs ✓
```

---

**Time to Deploy:** ~15 minutes  
**Cost:** Free (or $5/month)  
**Result:** Public, HTTPS-enabled, Production-ready API ✓

