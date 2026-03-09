#!/bin/bash
# Start backend service
# Usage: ./start_backend.sh

echo "=========================================="
echo "  Starting Backend on port 8601"
echo "=========================================="
echo ""

# Get the project directory
PROJECT_DIR="/mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp"
cd "$PROJECT_DIR" || exit 1

# Activate virtual environment
source venv/bin/activate

# Start backend
cd backend
echo "Starting uvicorn..."
uvicorn app.main:app --host 0.0.0.0 --port 8601 --reload
