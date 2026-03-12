#!/bin/bash

# Restart both backend and frontend services
# Usage: ./restart_all.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "========================================"
echo "Restarting Backend and Frontend Services"
echo "========================================"

# Stop services
echo "Stopping services..."
./stop_all.sh

# Wait a moment
sleep 2

# Start services
echo ""
./start_all.sh
