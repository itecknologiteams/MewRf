# Update script: Replace TBD URL with actual Railway URL
# Usage: .\update-railway-url.ps1 https://qtag-api-xxx.railway.app

param(
    [string]$RailwayUrl
)

if (-not $RailwayUrl) {
    Write-Host "Usage: .\update-railway-url.ps1 https://your-railway-url.railway.app"
    Write-Host ""
    Write-Host "Example:"
    Write-Host "  .\update-railway-url.ps1 https://qtag-api-staging-x7k2.railway.app"
    exit 1
}

$ApiUrl = "$RailwayUrl/api/v1"

Write-Host "🚀 Updating files with Railway URL: $ApiUrl" -ForegroundColor Green
Write-Host ""

# File 1: STAGING-PRODUCTION-SETUP.md
Write-Host "📝 Updating docs/deployment/STAGING-PRODUCTION-SETUP.md..."
$file1 = "docs/deployment/STAGING-PRODUCTION-SETUP.md"
$content1 = Get-Content $file1 -Raw
$content1 = $content1 -replace 'https://<staging-domain>/api/v1', $ApiUrl
Set-Content $file1 $content1 -Encoding UTF8

# File 2: DELIVERY-PACKAGE-FOR-TESTING.md
Write-Host "📝 Updating docs/DELIVERY-PACKAGE-FOR-TESTING.md..."
$file2 = "docs/DELIVERY-PACKAGE-FOR-TESTING.md"
$content2 = Get-Content $file2 -Raw
$content2 = $content2 -replace 'https://staging-api\.yourdomain\.com/api/v1', $ApiUrl
Set-Content $file2 $content2 -Encoding UTF8

# File 3: POSTMAN COLLECTION
Write-Host "📝 Updating docs/postman/JazzCash-TopUp-API-Collection.json..."
$file3 = "docs/postman/JazzCash-TopUp-API-Collection.json"
$content3 = Get-Content $file3 -Raw
$content3 = $content3 -replace 'http://localhost:8000/api/v1', $ApiUrl
$content3 = $content3 -replace 'http://192\.168\.78\.13:8000/api/v1', $ApiUrl
Set-Content $file3 $content3 -Encoding UTF8

# File 4: PERSONAL COLLECTION
Write-Host "📝 Updating docs/postman/QTag-JazzCash-Personal-Collection.json..."
$file4 = "docs/postman/QTag-JazzCash-Personal-Collection.json"
$content4 = Get-Content $file4 -Raw
$content4 = $content4 -replace 'http://localhost:8000/api/v1', $ApiUrl
Set-Content $file4 $content4 -Encoding UTF8

Write-Host ""
Write-Host "✅ All files updated!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. git add ."
Write-Host "2. git commit -m 'chore: Update API URL to Railway ($RailwayUrl)'"
Write-Host "3. git push origin main"
Write-Host ""
Write-Host "Then share updated files with testing team ✓" -ForegroundColor Green
