# View logs for the RAG system services
# Usage: .\view_logs.ps1 [backend|frontend|both]

param(
    [string]$Service = "both"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RAG System Logs Viewer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($Service -eq "backend" -or $Service -eq "both") {
    Write-Host "=== Backend Logs (last 30 lines) ===" -ForegroundColor Yellow
    Write-Host ""
    
    $output = wsl bash -c "if [ -f /tmp/rag_backend.log ]; then tail -30 /tmp/rag_backend.log; else echo 'No backend log file found'; fi"
    Write-Host $output
    Write-Host ""
}

if ($Service -eq "frontend" -or $Service -eq "both") {
    Write-Host "=== Frontend Logs (last 30 lines) ===" -ForegroundColor Yellow
    Write-Host ""
    
    $output = wsl bash -c "if [ -f /tmp/rag_frontend.log ]; then tail -30 /tmp/rag_frontend.log; else echo 'No frontend log file found'; fi"
    Write-Host $output
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "To follow logs in real-time, run:" -ForegroundColor Gray
Write-Host "  Backend:  wsl tail -f /tmp/rag_backend.log" -ForegroundColor White
Write-Host "  Frontend: wsl tail -f /tmp/rag_frontend.log" -ForegroundColor White
Write-Host ""
Write-Host "To check if services are running:" -ForegroundColor Gray
Write-Host "  .\status.ps1" -ForegroundColor White
