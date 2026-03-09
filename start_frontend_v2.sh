#!/bin/bash
# Start frontend service (enhanced multi-index UI)
# Usage: ./start_frontend_v2.sh

echo "=========================================="
echo "  Starting Enhanced Frontend on port 8602"
echo "=========================================="
echo ""

# Get the project directory
PROJECT_DIR="/mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp"
cd "$PROJECT_DIR" || exit 1

# Activate virtual environment
source venv/bin/activate

# Start enhanced frontend
cd frontend
echo "Starting Streamlit (Multi-Index UI)..."
streamlit run streamlit_app_v2.py --server.port 8602 --server.address 0.0.0.0
