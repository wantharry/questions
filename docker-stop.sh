#!/bin/bash
# Docker stop script for QuestionsApp

set -e

echo "🛑 Stopping QuestionsApp Docker services..."

# Check if Docker is running
if ! docker ps >/dev/null 2>&1; then
    echo "❌ Docker is not running."
    exit 1
fi

# Parse arguments
REMOVE_VOLUMES=false
WITH_OLLAMA=false

for arg in "$@"; do
    case $arg in
        --volumes|-v)
            REMOVE_VOLUMES=true
            shift
            ;;
        --with-ollama)
            WITH_OLLAMA=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --volumes, -v    Remove volumes (deletes all data)"
            echo "  --with-ollama    Include Ollama container"
            echo "  --help           Show this help message"
            exit 0
            ;;
    esac
done

# Build command
COMPOSE_CMD="docker-compose"
if [ "$WITH_OLLAMA" = true ]; then
    COMPOSE_CMD="$COMPOSE_CMD --profile with-ollama"
fi

# Stop services
if [ "$REMOVE_VOLUMES" = true ]; then
    echo "⚠️  Removing volumes (this will delete all data)..."
    $COMPOSE_CMD down -v
else
    $COMPOSE_CMD down
fi

echo "✅ All services stopped successfully!"

if [ "$REMOVE_VOLUMES" = true ]; then
    echo "🗑️  All volumes removed."
else
    echo "💾 Data volumes preserved."
    echo "   To remove volumes: ./docker-stop.sh --volumes"
fi
