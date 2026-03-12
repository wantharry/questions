#!/usr/bin/env pwsh
# Docker startup script for QuestionsApp (PowerShell)

Write-Host "🚀 Starting QuestionsApp with Docker..." -ForegroundColor Cyan

# Check if Docker is running
try {
    docker ps | Out-Null
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  No .env file found. Creating from docker.env..." -ForegroundColor Yellow
    Copy-Item "docker.env" ".env"
    Write-Host "✅ Created .env file. You can customize it if needed." -ForegroundColor Green
}

# Parse command line arguments
$WithOllama = $args -contains "--with-ollama"
$Build = $args -contains "--build"
$NoBuild = $args -contains "--no-build"

# Build command
$ComposeCmd = "docker-compose"
if ($WithOllama) {
    Write-Host "🦙 Including Ollama container..." -ForegroundColor Cyan
    $ComposeCmd += " --profile with-ollama"
}

# Build options
if ($Build) {
    Write-Host "🔨 Building containers..." -ForegroundColor Cyan
    Invoke-Expression "$ComposeCmd build"
} elseif (-not $NoBuild) {
    # Default: build if images don't exist
    Write-Host "🔍 Checking for existing images..." -ForegroundColor Cyan
}

# Start services
Write-Host "▶️  Starting services..." -ForegroundColor Cyan
if ($NoBuild) {
    Invoke-Expression "$ComposeCmd up -d --no-build"
} else {
    Invoke-Expression "$ComposeCmd up -d"
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "" 
    Write-Host "✅ QuestionsApp started successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📍 Access points:" -ForegroundColor Cyan
    Write-Host "   Frontend:  http://localhost:8602" -ForegroundColor White
    Write-Host "   Backend:   http://localhost:8601" -ForegroundColor White
    Write-Host "   API Docs:  http://localhost:8601/docs" -ForegroundColor White
    
    if ($WithOllama) {
        Write-Host "   Ollama:    http://localhost:11434" -ForegroundColor White
        Write-Host ""
        Write-Host "⚠️  Don't forget to pull the model:" -ForegroundColor Yellow
        Write-Host "   docker exec questionsapp-ollama ollama pull qwen2.5:7b" -ForegroundColor White
    }
    
    Write-Host ""
    Write-Host "📊 View logs:" -ForegroundColor Cyan
    Write-Host "   docker-compose logs -f" -ForegroundColor White
    Write-Host ""
    Write-Host "🛑 Stop services:" -ForegroundColor Cyan
    Write-Host "   docker-compose down" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "❌ Failed to start services. Check logs:" -ForegroundColor Red
    Write-Host "   docker-compose logs" -ForegroundColor White
    exit 1
}
