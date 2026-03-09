# Stop All Services - Backend + Frontend
# Usage: .\stop_all.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Stopping RAG Question Generator" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$BACKEND_PORT = 8601
$FRONTEND_PORT = 8602
$stopped = 0

# Function to stop processes on port
function Stop-ProcessOnPort {
    param([int]$Port, [string]$ServiceName)
    
    Write-Host "Checking $ServiceName (port $Port)..." -ForegroundColor Yellow
    
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    
    if ($null -eq $connections) {
        Write-Host "  No $ServiceName running on port $Port" -ForegroundColor Gray
        return 0
    }
    
    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    
    foreach ($processId in $pids) {
        try {
            $process = Get-Process -Id $processId -ErrorAction Stop
            Write-Host "  Stopping process: $($process.Name) (PID: $processId)" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Host "  Stopped $($process.Name)" -ForegroundColor Green
            $script:stopped++
        }
        catch {
            Write-Host "  Could not stop PID $processId" -ForegroundColor Yellow
        }
    }
    
    return 1
}

# Stop backend
Stop-ProcessOnPort -Port $BACKEND_PORT -ServiceName "Backend"

# Stop frontend
Stop-ProcessOnPort -Port $FRONTEND_PORT -ServiceName "Frontend"

# Also stop any lingering WSL processes running uvicorn or streamlit
Write-Host ""
Write-Host "Cleaning up WSL processes..." -ForegroundColor Yellow

try {
    # Kill uvicorn and streamlit processes in WSL
    wsl bash -c "pkill -f 'uvicorn.*8601' 2>/dev/null; pkill -f 'streamlit.*8602' 2>/dev/null; echo 'WSL cleanup done'"
    $script:stopped++
}
catch {
    Write-Host "  No WSL processes to clean" -ForegroundColor Gray
}

# Clean up any remaining WSL host processes if needed
$wslProcesses = Get-Process | Where-Object { 
    $_.ProcessName -eq "wsl" -or $_.ProcessName -eq "wslhost" 
} | Where-Object {
    # Only stop if command line contains our project path
    try {
        $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        $cmdLine -like "*questionsapp*" -and ($cmdLine -like "*uvicorn*" -or $cmdLine -like "*streamlit*")
    }
    catch {
        $false
    }
}

if ($wslProcesses) {
    Write-Host "Stopping WSL host processes..." -ForegroundColor Yellow
    foreach ($proc in $wslProcesses) {
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            Write-Host "  Stopped WSL process (PID: $($proc.Id))" -ForegroundColor Green
            $script:stopped++
        }
        catch {
            Write-Host "  Could not stop WSL process $($proc.Id)" -ForegroundColor Yellow
        }
    }
}

# Final status
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($stopped -gt 0) {
    Write-Host "  Services Stopped ($stopped processes)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "All services stopped" -ForegroundColor Green
} else {
    Write-Host "  No Services Were Running" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "No services needed to be stopped" -ForegroundColor Gray
}

Write-Host ""
Write-Host "To start services run: .\start_all.ps1" -ForegroundColor Yellow
Write-Host ""
