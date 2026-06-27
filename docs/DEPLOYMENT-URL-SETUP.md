# 🌐 Deployment URL Setup — Staging for Testing Team

**When you're ready to share API with external testing team, use this checklist.**

---

## 📋 What's Needed

To give testing team an accessible URL, you need:

### **Option A: Public Domain + Server** (Recommended)

```
1. Domain name (e.g., staging.qtag.io)
2. Server with public IP (AWS, Heroku, DigitalOcean, etc.)
3. TLS certificate (HTTPS)
4. DNS mapping (domain → server IP)
```

**Cost:** $5-50/month depending on provider

---

### **Option B: Production URL** (If Available)

```
If production is already live:
- Use production backend URL (https://...)
- Use test account credentials
- Use test/staging tags (if available)
```

---

### **Option C: VPN Access**

```
If testing team can join your VPN:
- Keep internal URL: http://192.168.78.13:8000/api/v1
- Setup VPN credentials for testing team
- They connect VPN → can access internal URL
```

---

## 🔧 Popular Deployment Options

| Option | Cost | Setup Time | HTTPS | Link |
|--------|------|-----------|-------|------|
| **Heroku** | Free tier | 15 min | ✅ Built-in | heroku.com |
| **Railway** | $5/month | 10 min | ✅ Built-in | railway.app |
| **DigitalOcean** | $6/month | 30 min | ✅ Let's Encrypt | digitalocean.com |
| **AWS EC2** | $10+/month | 1 hour | ⚠️ Manual | aws.amazon.com |
| **PythonAnywhere** | $5/month | 20 min | ✅ Built-in | pythonanywhere.com |

**Quickest:** Heroku or Railway (15 min)

---

## 📝 Once You Have a URL

Update these files:

### **1. STAGING-PRODUCTION-SETUP.md**
```markdown
Change:
| **Staging** | `https://<staging-domain>/api/v1` | ⏳ TBD |

To:
| **Staging** | `https://staging-api.yourdomain.com/api/v1` | ✅ Active |
```

### **2. DELIVERY-PACKAGE-FOR-TESTING.md**
```markdown
Change:
- base_url = https://<staging-url> (will be provided)

To:
- base_url = https://staging-api.yourdomain.com/api/v1
```

### **3. Postman Collection**
```json
{
  "variable": [
    {
      "key": "base_url",
      "value": "https://staging-api.yourdomain.com/api/v1"
    }
  ]
}
```

---

## ✅ Before Sharing with Testing Team

Checklist:

- [ ] Backend deployed and running
- [ ] HTTPS/TLS certificate active
- [ ] Domain DNS pointing to server
- [ ] API responds to requests (test locally first)
- [ ] Database initialized with test data
- [ ] Test tags created in database
- [ ] ALLOWED_HOSTS includes domain
- [ ] CORS enabled (if needed)
- [ ] Rate limiting configured
- [ ] Logging enabled for debugging
- [ ] Error messages appropriate (no sensitive info)

---

## 🚀 Quick Heroku Deploy (5 min)

```bash
# 1. Install Heroku CLI
# 2. Login
heroku login

# 3. Create app
heroku create qtag-staging

# 4. Add PostgreSQL
heroku addons:create heroku-postgresql:hobby-dev

# 5. Deploy from git
git push heroku main

# 6. Run migrations
heroku run python manage.py migrate

# 7. Create test data
heroku run python manage.py loaddata test_inventory.json

# 8. Get URL
heroku open
# Your URL: https://qtag-staging.herokuapp.com/api/v1
```

---

## 🎯 What Testing Team Gets

Once deployed:

```
Email to testing team:

Dear Testing Team,

API is ready for testing:

URL: https://staging-api.yourdomain.com/api/v1

Test Credentials:
- Username: operator_test
- Password: Operator@1234

Postman Collection: [attached]
Setup Guide: [attached]
Test Cases: [attached]

Please run the 5 test cases and report results.

Thanks!
```

---

## 📞 Current Status

```
✅ API Code: Ready
✅ Documentation: Ready
✅ Test Cases: Ready
✅ Postman Collection: Ready

⏳ Public URL: Pending deployment setup
⏳ Test data: Ready (once URL provided)
```

---

## Next Steps (When You're Ready)

1. **Choose deployment platform** (Heroku, Railway, DigitalOcean, etc.)
2. **Deploy backend** to public server
3. **Set up domain** & HTTPS
4. **Update files** with actual URL
5. **Share with testing team** (use DELIVERY-PACKAGE-FOR-TESTING.md)
6. **Testing team runs tests** (takes ~1 hour)
7. **Receive results** and fix any issues

---

**Until then:** All files are ready with TBD placeholders. Easy to update once you have the URL! 📦

