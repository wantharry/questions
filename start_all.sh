#!/bin/bash

# Start both backend and frontend services
# Usage: ./start_all.sh

set -e  # Exit on error

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "========================================"
echo "Starting Backend and Frontend Services"
echo "========================================"

# Activate virtual environment
source venv/bin/activate

# Kill any existing processes on the ports
echo "Clearing ports 8601 and 8602..."
pkill -9 uvicorn 2>/dev/null || true
pkill -9 streamlit 2>/dev/null || true
lsof -ti:8601,8602 | xargs kill -9 2>/dev/null || true
sleep 2

# Start Backend
echo ""
echo "[1/2] Starting Backend on port 8601..."
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8601 > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..
echo "  Backend PID: $BACKEND_PID"

# Start Frontend
echo "[2/2] Starting Frontend on port 8602..."
cd frontend
streamlit run streamlit_app.py --server.port 8602 --server.address 0.0.0.0 > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "  Frontend PID: $FRONTEND_PID"

# Wait for services to start
echo ""
echo "Waiting for services to start..."
sleep 5

# Check backend
echo ""
if curl -s http://localhost:8601/health > /dev/null 2>&1; then
    echo "✓ Backend is running on http://localhost:8601"
else
    echo "✗ Backend failed to start (loading...)"
fi

# Check frontend
if curl -s http://localhost:8602/ > /dev/null 2>&1; then
    echo "✓ Frontend is running on http://localhost:8602"
else
    echo "✗ Frontend failed to start (loading...)"
fi

echo ""
echo "========================================"
echo "Services starting..."
echo "API Docs: http://localhost:8601/docs"
echo "UI: http://localhost:8602"
echo "========================================"
echo ""
echo "To view logs:"
echo "  Backend:  tail -f backend.log"
echo "  Frontend: tail -f frontend.log"
echo ""
