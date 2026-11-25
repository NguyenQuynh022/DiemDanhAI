# tools/start_tunnel.ps1
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$rootDir    = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python     = Join-Path $rootDir ".venv\Scripts\python.exe"
$cloudflare = Join-Path $PSScriptRoot "cloudflared.exe"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  EduPortal -- Cloudflare Tunnel" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# Flask Admin & Cổng thông tin :5000
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir'; & '$python' run_admin.py"

Start-Sleep -Seconds 1

# Flask GV :5001
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir'; & '$python' run_lecturer.py"

Start-Sleep -Seconds 1

# Flask SV :5002
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir'; & '$python' run_student.py"

Write-Host "Cho Flask khoi dong (4s)..." -ForegroundColor Gray
Start-Sleep -Seconds 4

# Tunnel GV :5001
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir'; & '$cloudflare' tunnel --url http://localhost:5001"

Start-Sleep -Seconds 1

# Tunnel SV :5002
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir'; & '$cloudflare' tunnel --url http://localhost:5002"

Write-Host ""
Write-Host "Xong! Nhin vao 2 terminal Cloudflare de lay URL." -ForegroundColor Green
Write-Host "Giang vien : https://xxxx.trycloudflare.com" -ForegroundColor Green
Write-Host "Sinh vien  : https://yyyy.trycloudflare.com" -ForegroundColor Yellow
