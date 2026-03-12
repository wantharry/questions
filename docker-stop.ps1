#!/usr/bin/env pwsh
# Docker stop script for QuestionsApp

Write-Host "🛑 Stopping QuestionsApp Docker services..." -ForegroundColor Cyan

# Check if Docker is running
try {
    docker ps | Out-Null
} catch {
    Write-Host "❌ Docker is not running." -ForegroundColor Red
    exit 1
}

# Parse arguments
$RemoveVolumes = $args -contains "--volumes" -or $args -contains "-v"
$WithOllama = $args -contains "--with-ollama"

# Build command
$ComposeCmd = "docker-compose"
if ($WithOllama) {
    $ComposeCmd += " --profile with-ollama"
}

# Stop services
if ($RemoveVolumes) {
    Write-Host "⚠️  Removing volumes (this will delete all data)..." -ForegroundColor Yellow
    Invoke-Expression "$ComposeCmd down -v"
} else {
    Invoke-Expression "$ComposeCmd down"
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ All services stopped successfully!" -ForegroundColor Green
    
    if ($RemoveVolumes) {
        Write-Host "🗑️  All volumes removed." -ForegroundColor Yellow
    } else {
        Write-Host "💾 Data volumes preserved." -ForegroundColor Green
        Write-Host "   To remove volumes: ./docker-stop.ps1 --volumes" -ForegroundColor White
    }
} else {
    Write-Host "❌ Failed to stop services." -ForegroundColor Red
    exit 1
}
