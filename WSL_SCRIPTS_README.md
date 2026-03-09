# WSL Scripts Guide

## Pure WSL Scripts (No PowerShell)

All scripts are pure bash and run entirely in WSL. No PowerShell dependencies.

### Quick Start

```bash
cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp

# Start all services (enhanced multi-index UI)
./start_all_v2.sh

# Or start with original UI
./start_all.sh

# Check status
./status.sh

# Stop all services
./stop_all.sh

# Restart services
./restart_all_v2.sh  # or ./restart_all.sh
```

### Running from Windows

From PowerShell or CMD, prefix with `wsl bash -c`:

```powershell
wsl bash -c "cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp && ./start_all_v2.sh"
wsl bash -c "cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp && ./status.sh"
wsl bash -c "cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp && ./stop_all.sh"
```

### Available Scripts

| Script | Description |
|--------|-------------|
| `start_all.sh` | Start backend + frontend (original UI) |
| `start_all_v2.sh` | Start backend + frontend (multi-index UI) |
| `start_backend.sh` | Start backend only (foreground) |
| `start_frontend.sh` | Start frontend only (original UI, foreground) |
| `start_frontend_v2.sh` | Start frontend only (multi-index UI, foreground) |
| `stop_all.sh` | Stop all services |
| `restart_all.sh` | Restart with original UI |
| `restart_all_v2.sh` | Restart with multi-index UI |
| `status.sh` | Check service status |
| `view_logs.sh` | View service logs |

### Service URLs

- **Frontend**: http://localhost:8602
- **Backend**: http://localhost:8601
- **API Docs**: http://localhost:8601/docs

### Log Files

Logs are stored in WSL `/tmp/`:

- **Backend**: `/tmp/rag_backend.log`
- **Frontend**: `/tmp/rag_frontend.log` or `/tmp/rag_frontend_v2.log`

View logs:
```bash
# From WSL
tail -f /tmp/rag_backend.log
tail -f /tmp/rag_frontend_v2.log

# From Windows
wsl bash -c "tail -f /tmp/rag_backend.log"
```

### Startup Details

**Backend Startup:**
- Loads embedding model (~5-10 seconds)
- Loads all FAISS indexes (~5 seconds)
- Loads BM25 index (~2 seconds)
- Total startup time: ~15-30 seconds

**Frontend Startup:**
- Starts Streamlit server
- Total startup time: ~5-10 seconds

The `start_all*.sh` scripts wait for backend health check before starting frontend.

### Process Management

Scripts use `nohup` and `disown` to properly detach processes. Services continue running even after closing the terminal.

**PIDs** are displayed when starting services. You can also find them:
```bash
wsl bash -c "ps aux | grep -E 'uvicorn|streamlit'"
```

### Troubleshooting

**Services won't start:**
1. Stop all services: `./stop_all.sh`
2. Check if ports are free: `./status.sh`
3. Start again: `./start_all_v2.sh`

**Check logs for errors:**
```bash
wsl bash -c "tail -50 /tmp/rag_backend.log"
wsl bash -c "tail -50 /tmp/rag_frontend_v2.log"
```

**Kill stuck processes:**
```bash
wsl bash -c "pkill -f uvicorn"
wsl bash -c "pkill -f streamlit"
```

### System Requirements

- **Ollama**: Must be running with `qwen2.5:7b` model
- **Virtual Environment**: `venv/` at project root (activated automatically)
- **WSL**: Ubuntu or compatible distro
- **Python**: 3.9+ with all dependencies installed

### Notes

- All scripts run in WSL environment exclusively
- Virtual environment is activated automatically
- Scripts include auto-cleanup of stale processes
- Backend eagerly loads embedding model and indexes at startup
- Frontend connects to backend via localhost
