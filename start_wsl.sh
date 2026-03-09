#!/bin/bash
# Quick start script for WSL/Linux
# Runs both backend and frontend

echo "============================================================"
echo "🚀 Starting Advanced RAG Question Generator (v2.0) in WSL"
echo "============================================================"

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Warning: Ollama doesn't seem to be running"
    echo "   Start it with: ollama serve"
    echo "   Or: sudo systemctl start ollama (if installed as service)"
    echo ""
fi

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# Check directories exist
if [ ! -d "$BACKEND_DIR" ] || [ ! -d "$FRONTEND_DIR" ]; then
    echo "❌ Error: backend or frontend directory not found!"
    echo "Current directory: $PROJECT_DIR"
    exit 1
fi

# Start backend in background
echo ""
echo "📦 Starting Backend API..."
echo "   URL: http://localhost:8601"
cd "$BACKEND_DIR"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8601 > backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# Wait for backend to start
echo ""
echo "⏳ Waiting for backend to initialize (10 seconds)..."
sleep 10

# Start frontend
echo ""
echo "🎨 Starting Frontend UI..."
echo "   URL: http://localhost:8602"
cd "$FRONTEND_DIR"
python3 -m streamlit run streamlit_app.py --server.port 8602 &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

echo ""
echo "============================================================"
echo "✅ System is running!"
echo "============================================================"
echo ""
echo "📝 Access the UI:"
echo "   - From WSL/Linux: http://localhost:8602"
echo "   - From Windows: http://$(hostname).local:8602"
echo "   - Or use Windows IP if above doesn't work"
echo ""
echo "📚 Usage:"
echo "   1. Go to 'Knowledge Addition' tab"
echo "   2. Enter folder path (use WSL paths like /mnt/c/...)"
echo "   3. Click 'Start Ingestion' to load documents"
echo "   4. Go to 'Query & Questions' tab to search"
echo ""
echo "💡 Features:"
echo "   - Smart Chunking (keeps formulas/examples intact)"
echo "   - Hybrid Search (semantic + keyword)"
echo "   - Content Classification (theory/formula/exercise)"
echo "   - Auto-Resumable (restarts from where it left off)"
echo ""
echo "⌨️  Press Ctrl+C to stop both services"
echo "============================================================"

# Wait for user interrupt
trap "echo ''; echo '🛑 Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '✅ Shutdown complete'; exit 0" INT

# Keep script running
wait
