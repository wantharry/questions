# Restart All Services - Backend + Enhanced Frontend (Multi-Index UI)
# Usage: .\restart_all_v2.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Restarting RAG System (Multi-Index UI)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Stop all services
Write-Host "Step 1: Stopping existing services..." -ForegroundColor Yellow
Write-Host ""
& "$PSScriptRoot\stop_all.ps1"

# Wait a moment
Write-Host ""
Write-Host "Waiting for cleanup..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Start all services with enhanced UI
Write-Host ""
Write-Host "Step 2: Starting services with enhanced UI..." -ForegroundColor Yellow
Write-Host ""
& "$PSScriptRoot\start_all_v2.ps1"
