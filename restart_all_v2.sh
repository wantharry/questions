#!/bin/bash
# Restart all services (multi-index UI)
# Usage: ./restart_all_v2.sh

echo "=========================================="
echo "  Restarting RAG System (Multi-Index UI)"
echo "=========================================="
echo ""

PROJECT_DIR="/mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp"

# Stop
bash "$PROJECT_DIR/stop_all.sh"

echo ""
echo "Waiting 5 seconds..."
sleep 5

# Start
bash "$PROJECT_DIR/start_all_v2.sh"
