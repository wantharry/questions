#!/bin/bash
# Start all services - Backend + Frontend (original UI)
# Usage: ./start_all.sh

echo "=========================================="
echo "  Starting RAG Question Generator"
echo "=========================================="
echo ""

# Configuration
BACKEND_PORT=8601
FRONTEND_PORT=8602
PROJECT_DIR="/mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp"

# Function to check if port is in use
check_port() {
    nc -z localhost $1 2>/dev/null
    return $?
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local max_attempts=${2:-60}
    local service_name=${3:-"Service"}
    
    echo "Waiting for $service_name at $url..."
    echo "(Backend loads embedding model on startup - allow up to 2 minutes)"
    
    for i in $(seq 1 $max_attempts); do
        if curl -s -f "$url" > /dev/null 2>&1; then
            echo "✓ $service_name is ready!"
            return 0
        fi
        
        if [ $((i % 10)) -eq 0 ]; then
            echo "  Still waiting... ($i/$max_attempts - $(echo "scale=1; $i*2/60" | bc) min)"
        fi
        sleep 2
    done
    
    echo "✗ $service_name failed to start"
    return 1
}

# Step 1: Stop any existing services
echo "[1/4] Stopping any existing services..."
bash "$PROJECT_DIR/stop_all.sh"
echo ""
echo "Waiting for cleanup..."
sleep 3

# Step 2: Clean Python cache
echo ""
echo "[2/4] Cleaning Python cache..."
cd "$PROJECT_DIR/backend" || exit 1
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
echo "✓ Cache cleaned"

# Step 3: Start Backend
echo ""
echo "[3/4] Starting Backend on port $BACKEND_PORT..."
cd "$PROJECT_DIR" || exit 1
source venv/bin/activate

cd backend
nohup uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT > /tmp/rag_backend.log 2>&1 &
BACKEND_PID=$!
disown
echo "Backend started with PID: $BACKEND_PID"

# Wait for backend
if wait_for_service "http://localhost:$BACKEND_PORT/health" 60 "Backend"; then
    echo "✓ Backend started successfully!"
else
    echo "✗ Backend failed to start. Last 20 lines of log:"
    tail -20 /tmp/rag_backend.log 2>/dev/null
    exit 1
fi

# Step 4: Start Frontend
echo ""
echo "[4/4] Starting Frontend on port $FRONTEND_PORT..."
cd "$PROJECT_DIR/frontend" || exit 1

nohup streamlit run streamlit_app.py --server.port $FRONTEND_PORT --server.address 0.0.0.0 > /tmp/rag_frontend.log 2>&1 &
FRONTEND_PID=$!
disown
echo "Frontend started with PID: $FRONTEND_PID"

# Wait for frontend
sleep 8
if check_port $FRONTEND_PORT; then
    echo "✓ Frontend started successfully!"
else
    echo "⚠ Frontend may still be starting..."
fi

# Final status
echo ""
echo "=========================================="
echo "  RAG System Started"
echo "=========================================="
echo ""
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "API Docs: http://localhost:$BACKEND_PORT/docs"
echo ""
echo "Backend PID:  $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Logs:"
echo "  Backend:  tail -f /tmp/rag_backend.log"
echo "  Frontend: tail -f /tmp/rag_frontend.log"
echo ""
echo "To stop: ./stop_all.sh"
