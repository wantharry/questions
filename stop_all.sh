#!/bin/bash

# Stop both backend and frontend services
# Usage: ./stop_all.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "========================================"
echo "Stopping Backend and Frontend Services"
echo "========================================"

# Kill uvicorn (backend)
echo "Stopping Backend..."
pkill -9 uvicorn 2>/dev/null && echo "  ✓ Backend stopped" || echo "  ℹ Backend not running"

# Kill streamlit (frontend)
echo "Stopping Frontend..."
pkill -9 streamlit 2>/dev/null && echo "  ✓ Frontend stopped" || echo "  ℹ Frontend not running"

# Clear ports if needed
lsof -ti:8601,8602 | xargs kill -9 2>/dev/null || true

echo ""
echo "========================================"
echo "All services stopped."
echo "========================================"
echo ""
