# Restart All Services - Backend + Frontend
# Usage: .\restart_all.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Restarting RAG Question Generator" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Stop all services
Write-Host "Step 1: Stopping existing services..." -ForegroundColor Yellow
Write-Host ""
& "$PSScriptRoot\stop_all.ps1"

# Wait a moment
Write-Host ""
Write-Host "Waiting for cleanup..." -ForegroundColor Gray
Start-Sleep -Seconds 3

# Start all services
Write-Host ""
Write-Host "Step 2: Starting services..." -ForegroundColor Yellow
Write-Host ""
& "$PSScriptRoot\start_all.ps1"
