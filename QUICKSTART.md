# Quick Start Scripts

## Windows PowerShell

### Start Backend
```powershell
cd backend
python -m app.main
```

### Start Frontend
```powershell
cd frontend
streamlit run streamlit_app.py
```

### Start Both (separate terminals)
```powershell
# Terminal 1
cd backend
python -m app.main

# Terminal 2
cd frontend
streamlit run streamlit_app.py
```

## Setup Ollama

1. Download Ollama from https://ollama.ai
2. Install it
3. Open a terminal and run:
```powershell
ollama pull mistral:7b-instruct
```

Alternative models:
```powershell
ollama pull llama3:8b
ollama pull phi3:mini
```

## Troubleshooting

### Backend won't start
1. Check Python version: `python --version` (need 3.9+)
2. Reinstall dependencies: `pip install -r backend/requirements.txt`
3. Check Ollama is running: `ollama list`

### Frontend can't connect
1. Make sure backend is running on port 8601
2. Check http://localhost:8601/health in browser
3. Check firewall settings

### OCR errors
1. Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
2. Add to PATH
3. Or disable OCR in .env: `ENABLE_OCR=false`

### Memory issues
1. Use smaller models: `ollama pull phi3:mini`
2. Set CPU mode in .env: `EMBEDDING_DEVICE=cpu`
3. Reduce batch size: `BATCH_SIZE=10`
