# Check Status of All Services
# Usage: .\status.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Service Status Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$BACKEND_PORT = 8601
$FRONTEND_PORT = 8602

# Function to check service status
function Get-ServiceStatus {
    param([int]$Port, [string]$ServiceName, [string]$HealthUrl)
    
    Write-Host "[$ServiceName]" -ForegroundColor Cyan
    Write-Host "  Port: $Port" -ForegroundColor Gray
    
    # Check if port is listening
    $listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    
    if ($null -eq $listening) {
        Write-Host "  Status: ✗ NOT RUNNING" -ForegroundColor Red
        Write-Host ""
        return $false
    }
    
    # Get process info
    $pid = $listening[0].OwningProcess
    try {
        $process = Get-Process -Id $pid -ErrorAction Stop
        Write-Host "  Process: $($process.Name) (PID: $pid)" -ForegroundColor Gray
        Write-Host "  CPU: $([math]::Round($process.CPU, 2))s" -ForegroundColor Gray
        Write-Host "  Memory: $([math]::Round($process.WorkingSet64 / 1MB, 2)) MB" -ForegroundColor Gray
    }
    catch {
        Write-Host "  Process: Unknown (PID: $pid)" -ForegroundColor Gray
    }
    
    # Try health check if URL provided
    if ($HealthUrl) {
        try {
            $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Host "  Health: ✓ HEALTHY" -ForegroundColor Green
                
                # Parse health response for backend
                if ($ServiceName -eq "Backend API") {
                    try {
                        $health = $response.Content | ConvertFrom-Json
                        Write-Host "  Version: $($health.version)" -ForegroundColor Gray
                        Write-Host "  LLM: $($health.llm_provider)" -ForegroundColor Gray
                        Write-Host "  Documents: $($health.total_documents)" -ForegroundColor Gray
                    }
                    catch {
                        # Ignore parsing errors
                    }
                }
            }
        }
        catch {
            Write-Host "  Health: ⚠ UNREACHABLE" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  Status: ✓ RUNNING" -ForegroundColor Green
    }
    
    Write-Host ""
    return $true
}

# Check Backend
$backendRunning = Get-ServiceStatus -Port $BACKEND_PORT -ServiceName "Backend API" -HealthUrl "http://localhost:$BACKEND_PORT/health"

# Check Frontend
$frontendRunning = Get-ServiceStatus -Port $FRONTEND_PORT -ServiceName "Frontend UI" -HealthUrl "http://localhost:$FRONTEND_PORT"

# Check Ollama (LLM service)
Write-Host "[Ollama LLM]" -ForegroundColor Cyan
try {
    $ollama = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    if ($ollama.StatusCode -eq 200) {
        Write-Host "  Status: ✓ RUNNING" -ForegroundColor Green
        try {
            $models = ($ollama.Content | ConvertFrom-Json).models
            Write-Host "  Models: $($models.Count) loaded" -ForegroundColor Gray
        }
        catch {}
    }
}
catch {
    Write-Host "  Status: ✗ NOT RUNNING" -ForegroundColor Red
    Write-Host "  Note: Required for LLM-based features" -ForegroundColor Yellow
}
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($backendRunning -and $frontendRunning) {
    Write-Host "✓ All services running normally" -ForegroundColor Green
    Write-Host ""
    Write-Host "Access Points:" -ForegroundColor Cyan
    Write-Host "  Backend API:  http://localhost:$BACKEND_PORT" -ForegroundColor Gray
    Write-Host "  API Docs:     http://localhost:$BACKEND_PORT/docs" -ForegroundColor Gray
    Write-Host "  Frontend UI:  http://localhost:$FRONTEND_PORT" -ForegroundColor Gray
}
elseif ($backendRunning) {
    Write-Host "⚠ Backend running, but frontend is down" -ForegroundColor Yellow
    Write-Host "  Run: .\start_all.ps1" -ForegroundColor Gray
}
elseif ($frontendRunning) {
    Write-Host "⚠ Frontend running, but backend is down" -ForegroundColor Yellow
    Write-Host "  Run: .\start_all.ps1" -ForegroundColor Gray
}
else {
    Write-Host "✗ No services running" -ForegroundColor Red
    Write-Host "  Run: .\start_all.ps1" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  .\start_all.ps1   - Start all services" -ForegroundColor Gray
Write-Host "  .\stop_all.ps1    - Stop all services" -ForegroundColor Gray
Write-Host "  .\restart_all.ps1 - Restart all services" -ForegroundColor Gray
Write-Host ""
