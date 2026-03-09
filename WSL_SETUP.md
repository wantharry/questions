# Running in WSL (Recommended Setup)

Since your LLMs (Ollama) are in WSL, here's the recommended setup:

## 🐧 Quick Start in WSL

### Option 1: Automatic Start (Easiest)
```bash
# Make script executable
chmod +x start_wsl.sh

# Run the app
./start_wsl.sh
```

### Option 2: Manual Start (Two Terminals)

**Terminal 1 - Backend:**
```bash
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8601
```

**Terminal 2 - Frontend:**
```bash
cd frontend
python3 -m streamlit run streamlit_app.py --server.port 8602
```

---

## 🌐 Accessing from Windows Browser

Since you're running in WSL, access the UI from Windows using:

### Option 1: localhost (if WSL2)
```
http://localhost:8602
```

### Option 2: WSL hostname
```
http://$(hostname).local:8602
```

### Option 3: WSL IP address
```bash
# Get WSL IP
hostname -I | awk '{print $1}'

# Then use in Windows browser:
# http://<WSL_IP>:8602
```

---

## 📁 File Paths in WSL

When adding documents, use WSL paths:

### Windows → WSL Path Mapping
- `C:\Users\openclaw\Documents` → `/mnt/c/Users/openclaw/Documents`
- `D:\Books\Physics` → `/mnt/d/Books/Physics`

### Example in UI:
```
Folder Path: /mnt/c/Users/openclaw/harry/projects/IIT/data
```

---

## ✅ Verify Ollama is Running

Before starting the app:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it:
ollama serve

# Or if installed as service:
sudo systemctl start ollama
```

---

## 🔧 WSL-Specific Configuration

Edit `backend/.env`:
```bash
# LLM Configuration (Ollama in WSL)
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama2

# API Ports
API_PORT=8601

# Or if Ollama is on different port/host:
# LLM_BASE_URL=http://127.0.0.1:11434
```

---

## 🐛 Troubleshooting WSL

### Backend can't connect to Ollama
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check port is listening
netstat -tuln | grep 11434

# If using firewall, allow port 11434
sudo ufw allow 11434
```

### Can't access from Windows browser
```bash
# Check WSL IP
hostname -I

# Test backend from Windows:
# Open PowerShell and run:
# curl http://localhost:8601/health
```

### Permission denied on folders
```bash
# Make sure you have read access
ls -la /mnt/c/path/to/your/docs

# If permission issues, try:
sudo chmod -R 755 /mnt/c/path/to/your/docs
```

### Slow file access from /mnt/c
- WSL2 has slower access to Windows drives
- **Recommended:** Copy documents to WSL filesystem:
  ```bash
  # Copy to WSL home
  cp -r /mnt/c/Users/openclaw/Documents ~/Documents
  
  # Then use path: /home/<username>/Documents
  ```

---

## 📊 Performance Tips for WSL

1. **Store documents in WSL filesystem** (not /mnt/c):
   - Faster: `~/data/physics_books`
   - Slower: `/mnt/c/Users/.../physics_books`

2. **Install dependencies natively in WSL:**
   ```bash
   # Don't use Windows Python in WSL
   # Use WSL's Python
   python3 --version  # Should show Linux Python
   ```

3. **Use WSL2** (not WSL1):
   ```bash
   # Check version
   wsl -l -v
   
   # Upgrade to WSL2 if needed:
   wsl --set-version Ubuntu 2
   ```

---

## 🚀 Full Setup Example

```bash
# 1. Start Ollama (if not running)
ollama serve &

# 2. Navigate to project (use WSL path)
cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp

# 3. Install dependencies (if not done)
cd backend && pip3 install -r requirements.txt
cd ../frontend && pip3 install -r requirements.txt
cd ..

# 4. Make start script executable
chmod +x start_wsl.sh

# 5. Run the app
./start_wsl.sh

# 6. Open Windows browser to: http://localhost:8602
```

---

## 💡 Pro Tips

1. **Keep Ollama running:** Add to startup:
   ```bash
   # Add to ~/.bashrc
   echo "ollama serve &" >> ~/.bashrc
   ```

2. **Create alias:**
   ```bash
   # Add to ~/.bashrc
   alias start-rag="cd /path/to/project && ./start_wsl.sh"
   
   # Then just run:
   start-rag
   ```

3. **Auto-start on WSL boot:**
   ```bash
   # Create systemd service (Ubuntu 22.04+)
   sudo nano /etc/systemd/system/rag-app.service
   ```

---

## 📝 Quick Commands Reference

```bash
# Start app
./start_wsl.sh

# Stop app
# Press Ctrl+C in the terminal

# Check if running
ps aux | grep uvicorn
ps aux | grep streamlit

# Kill manually if needed
killall uvicorn streamlit

# View logs
tail -f backend/logs/app.log
tail -f backend/backend.log

# Test API
curl http://localhost:8601/health
```

---

**Ready to go! Run `./start_wsl.sh` and open http://localhost:8602 in your Windows browser** 🚀
