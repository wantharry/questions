#!/bin/bash
# Restart all services (original UI)
# Usage: ./restart_all.sh

echo "=========================================="
echo "  Restarting RAG Question Generator"
echo "=========================================="
echo ""

PROJECT_DIR="/mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp"

# Stop
bash "$PROJECT_DIR/stop_all.sh"

echo ""
echo "Waiting 5 seconds..."
sleep 5

# Start
bash "$PROJECT_DIR/start_all.sh"
