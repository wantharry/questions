# Start frontend UI
Write-Host "Starting frontend on port 8602..." -ForegroundColor Cyan
wsl bash -c 'cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp && ./venv/bin/streamlit run frontend/streamlit_app.py --server.port 8602'
