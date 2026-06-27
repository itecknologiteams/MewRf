#!/bin/bash
# Update script: Replace TBD URL with actual Railway URL
# Usage: ./update-railway-url.sh https://qtag-api-xxx.railway.app

if [ -z "$1" ]; then
    echo "Usage: ./update-railway-url.sh https://your-railway-url.railway.app"
    echo ""
    echo "Example:"
    echo "  ./update-railway-url.sh https://qtag-api-staging-x7k2.railway.app"
    exit 1
fi

RAILWAY_URL="$1"
API_URL="$RAILWAY_URL/api/v1"

echo "🚀 Updating files with Railway URL: $API_URL"
echo ""

# File 1: STAGING-PRODUCTION-SETUP.md
echo "📝 Updating docs/deployment/STAGING-PRODUCTION-SETUP.md..."
sed -i "s|https://<staging-domain>/api/v1|$API_URL|g" docs/deployment/STAGING-PRODUCTION-SETUP.md

# File 2: DELIVERY-PACKAGE-FOR-TESTING.md
echo "📝 Updating docs/DELIVERY-PACKAGE-FOR-TESTING.md..."
sed -i "s|https://staging-api.yourdomain.com/api/v1|$API_URL|g" docs/DELIVERY-PACKAGE-FOR-TESTING.md

# File 3: POSTMAN COLLECTION
echo "📝 Updating docs/postman/JazzCash-TopUp-API-Collection.json..."
sed -i "s|http://localhost:8000/api/v1|$API_URL|g" docs/postman/JazzCash-TopUp-API-Collection.json
sed -i "s|http://192.168.78.13:8000/api/v1|$API_URL|g" docs/postman/JazzCash-TopUp-API-Collection.json

# File 4: PERSONAL COLLECTION
echo "📝 Updating docs/postman/QTag-JazzCash-Personal-Collection.json..."
sed -i "s|http://localhost:8000/api/v1|$API_URL|g" docs/postman/QTag-JazzCash-Personal-Collection.json

echo ""
echo "✅ All files updated!"
echo ""
echo "Next steps:"
echo "1. git add ."
echo "2. git commit -m 'chore: Update API URL to Railway ($RAILWAY_URL)'"
echo "3. git push origin main"
echo ""
echo "Then share updated files with testing team ✓"
