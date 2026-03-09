#!/bin/bash
# Stop all services
# Usage: ./stop_all.sh

echo "=========================================="
echo "  Stopping RAG Question Generator"
echo "=========================================="
echo ""

BACKEND_PORT=8601
FRONTEND_PORT=8602
stopped=0

# Function to stop processes on port
stop_port() {
    local port=$1
    local service_name=$2
    
    echo "Checking $service_name (port $port)..."
    
    # Find PIDs using the port
    pids=$(lsof -ti:$port 2>/dev/null)
    
    if [ -z "$pids" ]; then
        echo "  No $service_name running on port $port"
        return 0
    fi
    
    # Kill each process
    for pid in $pids; do
        echo "  Stopping PID $pid..."
        kill -9 $pid 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "  ✓ Stopped PID $pid"
            ((stopped++))
        else
            echo "  ✗ Could not stop PID $pid"
        fi
    done
    
    return 1
}

# Stop backend
stop_port $BACKEND_PORT "Backend"

# Stop frontend
stop_port $FRONTEND_PORT "Frontend"

# Also kill by process name
echo ""
echo "Cleaning up processes by name..."
pkill -f "uvicorn app.main" 2>/dev/null && echo "  ✓ Killed uvicorn processes" && ((stopped++))
pkill -f "streamlit run" 2>/dev/null && echo "  ✓ Killed streamlit processes" && ((stopped++))

# Final status
echo ""
echo "=========================================="
if [ $stopped -gt 0 ]; then
    echo "  Services Stopped ($stopped processes)"
    echo "=========================================="
    echo ""
    echo "✓ All services stopped"
else
    echo "  No Services Running"
    echo "=========================================="
    echo ""
    echo "ℹ No services were running"
fi

echo ""
echo "To start services run: ./start_all.sh"
