# Start both backend and enhanced frontend (Multi-Index UI)
# Automatically stops any running instances first
$ErrorActionPreference = "Stop"

Write-Host "=== Starting RAG System (Multi-Index UI) ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop any existing services
Write-Host "Step 1: Stopping any existing services..." -ForegroundColor Yellow
& "$PSScriptRoot\stop_all.ps1"

Write-Host ""
Write-Host "Waiting for cleanup..." -ForegroundColor Gray
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Step 2: Starting fresh services..." -ForegroundColor Green
Write-Host ""

# Function to check if a port is in use
function Test-Port {
    param($Port)
    $connection = Test-NetConnection -ComputerName localhost -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
    return $connection
}

# Start backend
Write-Host "Starting Backend on port 8601 via WSL..." -ForegroundColor Green

$backendCmd = "cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp && source venv/bin/activate && cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8601 > /tmp/rag_backend.log 2>&1"

Start-Process wsl -ArgumentList "bash", "-c", $backendCmd -WindowStyle Hidden

Write-Host "Waiting for backend to start..." -ForegroundColor Yellow
Write-Host "(Backend loads embedding model on startup - allow up to 2 minutes)" -ForegroundColor Gray

$maxWait = 60
$waited = 0
while (-not (Test-Port 8601) -and $waited -lt $maxWait) {
    Start-Sleep -Seconds 2
    $waited++
    if ($waited % 10 -eq 0) {
        Write-Host "  Still waiting... ($($waited*2)s / $($maxWait*2)s)" -ForegroundColor Gray
    }
}

if (Test-Port 8601) {
    Write-Host "Backend started successfully!" -ForegroundColor Green
} else {
    Write-Host "Backend failed to start. Checking logs..." -ForegroundColor Red
    wsl bash -c "tail -20 /tmp/rag_backend.log 2>/dev/null || echo 'No log file found'"
    exit 1
}

Write-Host ""

# Start enhanced frontend
Write-Host "Starting Enhanced Frontend (Multi-Index UI) on port 8602 via WSL..." -ForegroundColor Green

$frontendCmd = "cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp && source venv/bin/activate && cd frontend && streamlit run streamlit_app_v2.py --server.port 8602 --server.address 0.0.0.0"

Start-Process wsl -ArgumentList "bash", "-c", $frontendCmd -WindowStyle Hidden

Write-Host "Waiting for frontend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 8

if (Test-Port 8602) {
    Write-Host "Frontend started successfully!" -ForegroundColor Green
} else {
    Write-Host "Frontend may still be starting..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== RAG System Started ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Frontend (Multi-Index UI): http://localhost:8602" -ForegroundColor White
Write-Host "Backend API: http://localhost:8601" -ForegroundColor White
Write-Host "API Docs: http://localhost:8601/docs" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to open the frontend in your browser..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Start-Process "http://localhost:8602"

Write-Host ""
Write-Host "Press any key to exit (this won't stop the services)..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
