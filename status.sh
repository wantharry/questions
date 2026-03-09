#!/bin/bash
# Check status of services
# Usage: ./status.sh

echo "=========================================="
echo "  RAG System Status"
echo "=========================================="
echo ""

BACKEND_PORT=8601
FRONTEND_PORT=8602

# Function to check port
check_port() {
    local port=$1
    local service=$2
    
    echo -n "$service (port $port): "
    
    if nc -z localhost $port 2>/dev/null; then
        echo "✓ RUNNING"
        
        # Get PID
        pid=$(lsof -ti:$port 2>/dev/null | head -1)
        if [ -n "$pid" ]; then
            echo "  PID: $pid"
        fi
        
        # Try to get process info
        ps_info=$(ps -p $pid -o comm= 2>/dev/null)
        if [ -n "$ps_info" ]; then
            echo "  Process: $ps_info"
        fi
        
        return 0
    else
        echo "✗ NOT RUNNING"
        return 1
    fi
}

# Check Backend
check_port $BACKEND_PORT "Backend"

# Try to get backend health
if nc -z localhost $BACKEND_PORT 2>/dev/null; then
    echo -n "  Health check: "
    health=$(curl -s http://localhost:$BACKEND_PORT/health 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "✓ OK"
        echo "  $health" | head -3
    else
        echo "✗ FAILED"
    fi
fi

echo ""

# Check Frontend
check_port $FRONTEND_PORT "Frontend"

echo ""
echo "=========================================="

# Show logs location
echo ""
echo "Logs:"
echo "  Backend:  /tmp/rag_backend.log"
echo "  Frontend: /tmp/rag_frontend.log (or rag_frontend_v2.log)"
echo ""
echo "View logs: ./view_logs.sh"
echo "Stop all:  ./stop_all.sh"
