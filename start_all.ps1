# Start All Services - Backend + Frontend
# Usage: .\start_all.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Starting RAG Question Generator" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$BACKEND_PORT = 8601
$FRONTEND_PORT = 8602
$PROJECT_PATH = "/mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp"

# Function to check if port is in use
function Test-PortInUse {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -ne $connection
}

# Function to wait for service
function Wait-ForService {
    param([string]$Url, [int]$MaxAttempts = 20)
    
    Write-Host "Waiting for service at $Url..." -ForegroundColor Yellow
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Host "Service is ready!" -ForegroundColor Green
                return $true
            }
        }
        catch {
            Write-Host "  Attempt $i/$MaxAttempts..." -ForegroundColor Gray
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

# Step 1: Check if services are already running
Write-Host "[1/4] Checking existing services..." -ForegroundColor Yellow

if (Test-PortInUse $BACKEND_PORT) {
    Write-Host "Backend already running on port $BACKEND_PORT" -ForegroundColor Yellow
    $response = Read-Host "Stop and restart? (y/n)"
    if ($response -eq 'y') {
        Write-Host "Stopping existing services..." -ForegroundColor Yellow
        & "$PSScriptRoot\stop_all.ps1"
        Start-Sleep -Seconds 3
    }
}

# Step 2: Clean Python cache
Write-Host ""
Write-Host "[2/4] Cleaning Python cache..." -ForegroundColor Yellow
try {
    $cleanCmd = "cd $PROJECT_PATH/backend; find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; echo 'Cache cleaned'"
    wsl bash -c $cleanCmd
    Write-Host "Cache cleaned" -ForegroundColor Green
}
catch {
    Write-Host "Warning: Could not clean cache" -ForegroundColor Yellow
}

# Step 3: Start Backend
Write-Host ""
Write-Host "[3/4] Starting Backend API on port $BACKEND_PORT..." -ForegroundColor Yellow

$backendCmd = "cd $PROJECT_PATH; source venv/bin/activate; cd backend; uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT"

Start-Process wsl -ArgumentList "bash", "-c", $backendCmd -WindowStyle Hidden

# Wait for backend
if (Wait-ForService "http://localhost:$BACKEND_PORT/health" -MaxAttempts 15) {
    Write-Host "Backend started successfully!" -ForegroundColor Green
} else {
    Write-Host "Backend failed to start" -ForegroundColor Red
    Write-Host "Try running manually or check logs" -ForegroundColor Yellow
    exit 1
}

# Step 4: Start Frontend
Write-Host ""
Write-Host "[4/4] Starting Frontend UI on port $FRONTEND_PORT..." -ForegroundColor Yellow

$frontendCmd = "cd $PROJECT_PATH; source venv/bin/activate; cd frontend; streamlit run streamlit_app.py --server.port $FRONTEND_PORT --server.address 0.0.0.0"

Start-Process wsl -ArgumentList "bash", "-c", $frontendCmd -WindowStyle Hidden

# Wait for frontend
Start-Sleep -Seconds 8
if (Test-PortInUse $FRONTEND_PORT) {
    Write-Host "Frontend started successfully!" -ForegroundColor Green
} else {
    Write-Host "Frontend may still be starting..." -ForegroundColor Yellow
}

# Final status
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Services Started Successfully!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend API:   http://localhost:$BACKEND_PORT" -ForegroundColor Green
Write-Host "               http://localhost:$BACKEND_PORT/docs (API docs)" -ForegroundColor Gray
Write-Host ""
Write-Host "Frontend UI:   http://localhost:$FRONTEND_PORT" -ForegroundColor Green
Write-Host ""
Write-Host "To stop services: .\stop_all.ps1" -ForegroundColor Yellow
Write-Host "To view status:   .\status.ps1" -ForegroundColor Yellow
Write-Host ""
