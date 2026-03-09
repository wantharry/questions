# Service Management Scripts

Comprehensive PowerShell scripts to manage the RAG Question Generator services.

## Available Scripts

### 🚀 `start_all.ps1`
Start both backend and frontend services.

```powershell
.\start_all.ps1
```

**What it does:**
- Checks if services are already running
- Cleans Python cache
- Starts backend API on port 8601
- Starts frontend UI on port 8602
- Waits for health checks
- Shows access URLs

**Ports:**
- Backend API: http://localhost:8601
- Backend Docs: http://localhost:8601/docs
- Frontend UI: http://localhost:8602

---

### 🛑 `stop_all.ps1`
Stop all running services.

```powershell
.\stop_all.ps1
```

**What it does:**
- Stops backend processes on port 8601
- Stops frontend processes on port 8602
- Cleans up WSL processes running uvicorn/streamlit
- Reports number of processes stopped

---

### 🔄 `restart_all.ps1`
Restart all services (stop + start).

```powershell
.\restart_all.ps1
```

**What it does:**
- Runs `stop_all.ps1`
- Waits 3 seconds
- Runs `start_all.ps1`

**Use this when:**
- You've made code changes
- Services are misbehaving
- After updating dependencies

---

### 📊 `status.ps1`
Check status of all services.

```powershell
.\status.ps1
```

**What it does:**
- Checks if backend is running (+ health check)
- Checks if frontend is running
- Checks if Ollama LLM is running
- Shows process info (PID, CPU, memory)
- Shows API version and document count
- Provides summary and access URLs

---

## Quick Reference

| Task | Command |
|------|---------|
| Start everything | `.\start_all.ps1` |
| Stop everything | `.\stop_all.ps1` |
| Restart everything | `.\restart_all.ps1` |
| Check status | `.\status.ps1` |

## Troubleshooting

### "Cannot be loaded because running scripts is disabled"

This is a PowerShell execution policy issue. Fix it by:

```powershell
# Option 1: Allow for current session only (recommended)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Option 2: Allow permanently (requires admin)
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Then run your script again.

### Services won't stop

If `stop_all.ps1` doesn't work:

```powershell
# Force kill all WSL processes
Get-Process wsl* | Stop-Process -Force

# Or restart WSL entirely
wsl --shutdown
```

### Port already in use

If you see "Address already in use":

```powershell
# Check what's using the port
Get-NetTCPConnection -LocalPort 8601
Get-NetTCPConnection -LocalPort 8602

# Stop services and try again
.\stop_all.ps1
Start-Sleep -Seconds 5
.\start_all.ps1
```

### Backend starts but frontend doesn't

This usually means Streamlit is still starting. Wait 10-15 seconds and check:

```powershell
.\status.ps1
```

If still not running after 30 seconds, try:

```powershell
.\restart_all.ps1
```

### Services crash after starting

Check backend logs:

```powershell
wsl bash -c "cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp/backend && tail -n 50 logs/app.log"
```

Common issues:
- Ollama not running: `ollama serve` in a separate terminal
- Wrong Python environment: Check venv is activated
- Missing dependencies: `pip install -r requirements.txt`

---

## Manual Start (If Scripts Fail)

### Backend:
```powershell
wsl bash -c "cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp && source venv/bin/activate && cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8601"
```

### Frontend:
```powershell
wsl bash -c "cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp && source venv/bin/activate && cd frontend && streamlit run streamlit_app.py --server.port 8602 --server.address 0.0.0.0"
```

---

## Notes

- **Hidden Windows**: Services run in hidden WSL windows for clean desktop
- **Auto Health Check**: Backend waits for health check before declaring success
- **Smart Cleanup**: Only stops processes on our specific ports
- **Cache Clean**: Python cache cleaned on start for fresh code loading
- **Port Conflict Detection**: Warns if ports already in use

## Updates

These scripts are designed to handle edge cases like:
- Services already running
- Zombie processes
- Port conflicts
- WSL host process cleanup
- Health check failures

If you encounter issues not covered here, check the script output for specific error messages.
