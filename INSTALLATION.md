# Installation Guide - RAG Question Generator

Complete step-by-step installation guide for Windows.

## Prerequisites

- Windows 10/11
- Python 3.9 or higher
- At least 8GB RAM (32GB recommended for large datasets)
- ~5GB free disk space for models

## Step 1: Install Python

1. Download Python from https://www.python.org/downloads/
2. Run installer
3. ✅ **Important**: Check "Add Python to PATH"
4. Click "Install Now"

Verify installation:
```powershell
python --version
```
Should show Python 3.9 or higher.

## Step 2: Install Ollama (Local LLM)

### Option A: Ollama (Recommended - Free & Easy)

1. Download from https://ollama.ai/download
2. Run the installer
3. Open PowerShell and pull a model:

```powershell
# Mistral 7B (recommended)
ollama pull mistral:7b-instruct

# OR Llama 3 8B (alternative)
ollama pull llama3:8b

# OR Phi-3 Mini (faster, less accurate)
ollama pull phi3:mini
```

Verify:
```powershell
ollama list
```

### Option B: OpenAI API (Cloud-based)

Skip Ollama installation and configure `.env` with:
```ini
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
LLM_MODEL=gpt-4
```

## Step 3: Install Tesseract OCR (Optional)

For extracting text from scanned PDFs and images:

1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run installer (default location is fine)
3. Add to PATH:
   - Search "Environment Variables" in Windows
   - Edit "Path" under System Variables
   - Add: `C:\Program Files\Tesseract-OCR`
4. Restart PowerShell

Verify:
```powershell
tesseract --version
```

**If you skip this step**: Set `ENABLE_OCR=false` in `.env`

## Step 4: Clone/Download the Project

```powershell
cd C:\Users\YourName\Projects
# If you have the code, navigate to it
cd IIT\questions\questionsapp
```

## Step 5: Install Python Dependencies

### Backend Dependencies

```powershell
cd backend
pip install -r requirements.txt
```

This will install:
- FastAPI (web framework)
- Sentence Transformers (embeddings)
- FAISS (vector database)
- PyMuPDF (PDF processing)
- And more...

Wait for installation to complete (~5 minutes).

### Frontend Dependencies

```powershell
cd ..\frontend
pip install -r requirements.txt
```

This installs:
- Streamlit (UI framework)
- Requests (API client)

## Step 6: Configure Environment

```powershell
cd ..
copy .env.example .env
```

Edit `.env` with your preferred text editor. Default settings work for Ollama setup.

### Key Settings:

```ini
# LLM Configuration
LLM_PROVIDER=ollama
LLM_MODEL=mistral:7b-instruct
LLM_BASE_URL=http://localhost:11434

# Embeddings (download automatically on first run)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu  # or 'cuda' if you have GPU

# Processing
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
ENABLE_OCR=true  # Set to false if no Tesseract
```

## Step 7: First Run

Open **TWO** PowerShell windows.

### Terminal 1 - Start Backend:

```powershell
cd C:\Users\YourName\Projects\IIT\questions\questionsapp\backend
python -m app.main
```

You should see:
```
INFO: Starting application...
INFO: Initialized LLM provider: ollama
INFO: Application started successfully
INFO: Uvicorn running on http://0.0.0.0:8601
```

### Terminal 2 - Start Frontend:

```powershell
cd C:\Users\YourName\Projects\IIT\questions\questionsapp\frontend
streamlit run streamlit_app.py
```

Browser should open automatically to http://localhost:8602

## Step 8: Verify Installation

1. Check backend health: http://localhost:8601/health
2. Check frontend UI: http://localhost:8602
3. In the UI sidebar, you should see "✅ API Connected"

## Step 9: Ingest Your First Documents

1. In the UI, go to "Knowledge Addition" tab
2. Enter a folder path with PDFs: `C:\Users\YourName\Documents\PDFs`
3. Click "Start Ingestion"
4. Wait for processing to complete

## Troubleshooting

### Error: "No module named 'app'"

```powershell
# Make sure you're in the backend directory
cd backend
python -m app.main
```

### Error: "Ollama not available"

```powershell
# Check if Ollama is running
ollama list

# If not installed, reinstall from https://ollama.ai
```

### Error: "pytesseract not found"

Either:
1. Install Tesseract and add to PATH
2. OR set `ENABLE_OCR=false` in `.env`

### Error: CUDA/GPU errors

```ini
# Use CPU in .env
EMBEDDING_DEVICE=cpu
```

### Port already in use

```powershell
# Backend (change port)
# In .env: API_PORT=8001

# Frontend
streamlit run streamlit_app.py --server.port 8502
```

### Slow processing

1. Use smaller model:
   ```powershell
   ollama pull phi3:mini
   ```
   Then set `LLM_MODEL=phi3:mini` in `.env`

2. Reduce batch size in `.env`:
   ```ini
   BATCH_SIZE=10
   ```

## Using the Application

### 1. Add Documents

**Knowledge Addition Tab**:
- Enter folder path containing PDFs/documents
- Select file types to process
- Enable "Scan subdirectories recursively" for nested folders
- Click "Start Ingestion"
- Monitor progress in real-time

### 2. Query Knowledge

**Query & Questions Tab → Query**:
- Type your question
- Select top K results (5 recommended)
- Click "Search"
- View answer with sources

### 3. Generate Questions

**Query & Questions Tab → Generate Questions**:
- Select subject (Math/Physics/Chemistry)
- Choose difficulty level
- Pick question type
- Set number of questions
- Optional: specify a topic
- Click "Generate Questions"

## Next Steps

1. **Ingest your documents**: Start with a small folder to test
2. **Try querying**: Ask questions about your documents
3. **Generate questions**: Create practice problems
4. **Experiment with settings**: Try different models and chunk sizes
5. **Monitor logs**: Check `data/logs/` for detailed information

## Advanced Configuration

### Use Better Embeddings

In `.env`:
```ini
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
EMBEDDING_DIMENSION=768
```

### Use GPU Acceleration

```ini
EMBEDDING_DEVICE=cuda
```

### Increase Processing Speed

```ini
MAX_WORKERS=8
BATCH_SIZE=100
```

### Custom Chunk Sizes

```ini
CHUNK_SIZE=1500  # Larger chunks
CHUNK_OVERLAP=300
```

## Getting Help

1. Check logs in `data/logs/`
2. Review error messages carefully
3. Verify all prerequisites are installed
4. Check that Ollama is running: `ollama list`
5. Test backend directly: http://localhost:8601/docs

## Maintenance

### Update Models

```powershell
ollama pull mistral:7b-instruct
```

### Clear Vector Store

```powershell
# Delete and restart
rm -r data/vector_store
rm -r data/metadata
```

### Update Dependencies

```powershell
cd backend
pip install -r requirements.txt --upgrade

cd ../frontend
pip install -r requirements.txt --upgrade
```

---

**Installation Complete!** 🎉

You now have a fully functional local RAG system for generating educational questions from your documents.
