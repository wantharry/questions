#!/bin/bash
# View logs for backend and frontend services
# Usage: ./view_logs.sh [backend|frontend|both]

SERVICE=${1:-both}

if [ "$SERVICE" == "backend" ] || [ "$SERVICE" == "both" ]; then
    echo "=== Backend Logs (last 30 lines) ==="
    echo ""
    if [ -f /tmp/rag_backend.log ]; then
        tail -30 /tmp/rag_backend.log
    else
        echo "No backend log file found at /tmp/rag_backend.log"
    fi
    echo ""
fi

if [ "$SERVICE" == "frontend" ] || [ "$SERVICE" == "both" ]; then
    echo "=== Frontend Logs (last 30 lines) ==="
    echo ""
    if [ -f /tmp/rag_frontend.log ]; then
        tail -30 /tmp/rag_frontend.log
    else
        echo "No frontend log file found at /tmp/rag_frontend.log"
    fi
    echo ""
fi

echo "=== To follow logs in real-time ==="
echo "Backend:  tail -f /tmp/rag_backend.log"
echo "Frontend: tail -f /tmp/rag_frontend.log"
