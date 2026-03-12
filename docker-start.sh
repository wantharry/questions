#!/bin/bash
# Docker startup script for QuestionsApp (Bash)

set -e

echo "🚀 Starting QuestionsApp with Docker..."

# Check if Docker is running
if ! docker ps >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from docker.env..."
    cp docker.env .env
    echo "✅ Created .env file. You can customize it if needed."
fi

# Parse command line arguments
WITH_OLLAMA=false
BUILD=false
NO_BUILD=false

for arg in "$@"; do
    case $arg in
        --with-ollama)
            WITH_OLLAMA=true
            shift
            ;;
        --build)
            BUILD=true
            shift
            ;;
        --no-build)
            NO_BUILD=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --with-ollama    Include Ollama container"
            echo "  --build          Force rebuild of containers"
            echo "  --no-build       Skip building, use existing images"
            echo "  --help           Show this help message"
            exit 0
            ;;
    esac
done

# Build command
COMPOSE_CMD="docker-compose"
if [ "$WITH_OLLAMA" = true ]; then
    echo "🦙 Including Ollama container..."
    COMPOSE_CMD="$COMPOSE_CMD --profile with-ollama"
fi

# Build options
if [ "$BUILD" = true ]; then
    echo "🔨 Building containers..."
    $COMPOSE_CMD build
elif [ "$NO_BUILD" = false ]; then
    # Default: build if images don't exist
    echo "🔍 Checking for existing images..."
fi

# Start services
echo "▶️  Starting services..."
if [ "$NO_BUILD" = true ]; then
    $COMPOSE_CMD up -d --no-build
else
    $COMPOSE_CMD up -d
fi

echo ""
echo "✅ QuestionsApp started successfully!"
echo ""
echo "📍 Access points:"
echo "   Frontend:  http://localhost:8602"
echo "   Backend:   http://localhost:8601"
echo "   API Docs:  http://localhost:8601/docs"

if [ "$WITH_OLLAMA" = true ]; then
    echo "   Ollama:    http://localhost:11434"
    echo ""
    echo "⚠️  Don't forget to pull the model:"
    echo "   docker exec questionsapp-ollama ollama pull qwen2.5:7b"
fi

echo ""
echo "📊 View logs:"
echo "   docker-compose logs -f"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""
