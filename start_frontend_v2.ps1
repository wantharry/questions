# Start the enhanced Streamlit frontend (Multi-Index UI) via WSL
Write-Host "Starting Enhanced Frontend (Multi-Index UI) on port 8602..." -ForegroundColor Cyan
wsl bash -c 'cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp && ./venv/bin/streamlit run frontend/streamlit_app_v2.py --server.port 8602 --server.address 0.0.0.0'
