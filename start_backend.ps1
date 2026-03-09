# Start backend server
Write-Host "Starting backend on port 8601..." -ForegroundColor Cyan
wsl bash -c 'cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp && ./venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8601 --app-dir backend'
