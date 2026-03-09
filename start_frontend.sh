#!/bin/bash
# Start frontend service (original UI)
# Usage: ./start_frontend.sh

echo "=========================================="
echo "  Starting Frontend on port 8602"
echo "=========================================="
echo ""

# Get the project directory
PROJECT_DIR="/mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp"
cd "$PROJECT_DIR" || exit 1

# Activate virtual environment
source venv/bin/activate

# Start frontend
cd frontend
echo "Starting Streamlit..."
streamlit run streamlit_app.py --server.port 8602 --server.address 0.0.0.0
