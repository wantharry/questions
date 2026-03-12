#!/bin/bash

# Check status of backend and frontend services
# Usage: ./status.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "========================================"
echo "Service Status"
echo "========================================"

# Check Backend
echo ""
echo "Backend (Port 8601):"
if curl -s http://localhost:8601/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:8601/health)
    echo "  Status: ✓ RUNNING"
    echo "  Details: $HEALTH" | python3 -m json.tool 2>/dev/null || echo "  Health: OK"
else
    if ps aux | grep -i "uvicorn" | grep -v grep > /dev/null 2>&1; then
        echo "  Status: ⏳ STARTING (not yet responding)"
    else
        echo "  Status: ✗ STOPPED"
    fi
fi

# Check Frontend
echo ""
echo "Frontend (Port 8602):"
if curl -s http://localhost:8602/ > /dev/null 2>&1; then
    echo "  Status: ✓ RUNNING"
    echo "  URL: http://localhost:8602"
else
    if ps aux | grep -i "streamlit" | grep -v grep > /dev/null 2>&1; then
        echo "  Status: ⏳ STARTING (not yet responding)"
    else
        echo "  Status: ✗ STOPPED"
    fi
fi

# Show process info
echo ""
echo "Active Processes:"
ps aux | grep -E "uvicorn|streamlit" | grep -v grep | awk '{print "  " $0}' || echo "  No services running"

echo ""
echo "========================================"
echo ""
