# Script PowerShell para iniciar ambos servicios en ventanas independientes
$baseDir = Split-Path -Parent $PSScriptRoot

Write-Host "Iniciando Payment Mock API (puerto 5002)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$baseDir'; python payment_service/app.py"

Start-Sleep -Seconds 1

Write-Host "Iniciando Order API (puerto 5001)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$baseDir'; python order_service/app.py"

Write-Host "`nAmbos servicios han sido lanzados en ventanas independientes." -ForegroundColor Yellow
Write-Host "Order API: http://127.0.0.1:5001"
Write-Host "Payment Mock API: http://127.0.0.1:5002"
