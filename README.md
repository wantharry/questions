# RAG Question Generator

A production-ready local Retrieval Augmented Generation (RAG) system for generating practice questions from educational documents. Built with modular, pluggable components for maximum flexibility.

## 🌟 Features

### Core Capabilities
- **Multi-format Document Processing**: PDF, HTML, DOCX, Markdown, images, text files
- **Recursive Ingestion**: Process 20GB+ of documents across hundreds of folders
- **Resumable Processing**: Automatic checkpoint saving and recovery
- **Progress Logging**: Real-time ingestion status and detailed logs
- **Incremental Updates**: Only process new or modified files

### RAG System
- **Semantic Search**: FAISS-powered vector similarity search
- **Chunking Strategies**: Recursive character splitting with configurable overlap
- **Pluggable Embeddings**: SentenceTransformers (swap models easily)
- **OCR Support**: Extract text from scanned PDFs and images

### Question Generation
- **Subject-Specific**: Math, Physics, Chemistry, or General
- **Difficulty Levels**: Easy, Medium, Hard
- **Question Types**: Multiple choice, short answer, numerical, etc.
- **LLM-Powered**: Generate questions with detailed explanations

### Architecture
- **Pluggable LLMs**: Ollama (default), OpenAI API, vLLM, llama.cpp
- **Pluggable Vector Stores**: FAISS (default), ChromaDB
- **REST API**: FastAPI backend with async support
- **Modern UI**: Streamlit with two-tab interface
- **Production Ready**: Proper logging, error handling, type safety

## 🏗️ Architecture

```
Backend (FastAPI)
├── Document Processing (PDF, HTML, images, etc.)
├── Chunking & Embedding (SentenceTransformers)
├── Vector Store (FAISS)
├── Metadata DB (SQLite)
├── LLM Integration (Ollama/OpenAI)
└── REST API

Frontend (Streamlit)
├── Knowledge Addition Tab
└── Query & Question Generation Tab
```

## 📋 Requirements

### System Requirements
- **RAM**: 8GB minimum, 32GB recommended for large datasets
- **GPU**: Optional (8GB VRAM for faster inference)
- **Storage**: ~5GB for models + your document storage

### Software Requirements
- Python 3.9+
- Ollama (for local LLM) OR OpenAI API key
- Tesseract OCR (optional, for images/scanned PDFs)

## 🚀 Quick Start

### 1. Install Ollama (Recommended)

**Windows:**
```powershell
# Download and install from https://ollama.ai
# Then pull a model:
ollama pull mistral:7b-instruct
```

**Linux/Mac:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull mistral:7b-instruct
```

### 2. Install Dependencies

```powershell
# Navigate to backend
cd backend
pip install -r requirements.txt

# Navigate to frontend
cd ../frontend
pip install -r requirements.txt
```

### 3. Configure Environment

```powershell
# Copy example config
cp .env.example .env

# Edit .env with your settings (optional)
# Default settings work out of the box with Ollama
```

### 4. Run the Application

**Terminal 1 - Backend:**
```powershell
cd backend
python -m app.main
```

**Terminal 2 - Frontend:**
```powershell
cd frontend
streamlit run streamlit_app.py
```

Access the UI at: http://localhost:8602

## 📖 Usage Guide

### Adding Documents

1. Open the **Knowledge Addition** tab
2. Enter your folder path (e.g., `C:/Users/data/physics_books`)
3. Select file types to process
4. Click **Start Ingestion**
5. Monitor progress in real-time

**Features:**
- Resumes automatically if interrupted
- Skips already-processed files
- Processes hundreds of folders recursively
- Logs all activity to `data/logs/`

### Querying Knowledge Base

1. Switch to **Query & Questions** tab
2. Select **Query** sub-tab
3. Ask natural language questions
4. View answer with source citations

### Generating Questions

1. Select **Generate Questions** sub-tab
2. Choose subject, difficulty, and question type
3. Optionally specify a topic
4. Click **Generate Questions**
5. Review questions with answers and explanations

## ⚙️ Configuration

Edit `.env` to customize:

### LLM Settings
```ini
# Ollama (default)
LLM_PROVIDER=ollama
LLM_MODEL=mistral:7b-instruct
LLM_BASE_URL=http://localhost:11434

# Or use OpenAI
# LLM_PROVIDER=openai
# OPENAI_API_KEY=your_key_here
```

### Embedding Settings
```ini
# Fast and efficient (default)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Better quality (slower)
# EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
# EMBEDDING_DIMENSION=768
```

### Processing Settings
```ini
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
BATCH_SIZE=50
ENABLE_OCR=true
MAX_WORKERS=4
```

## 🔌 Pluggable Components

### Switching LLM Providers

**Ollama (Local):**
```ini
LLM_PROVIDER=ollama
LLM_MODEL=llama3:8b
```

**OpenAI API:**
```ini
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4
```

**vLLM (Local Server):**
```ini
LLM_PROVIDER=vllm
OPENAI_BASE_URL=http://localhost:8100/v1
OPENAI_API_KEY=dummy
```

### Switching Embedding Models

Edit `EMBEDDING_MODEL` in `.env`:
```ini
# Options:
# - sentence-transformers/all-MiniLM-L6-v2 (fast, 384d)
# - sentence-transformers/all-mpnet-base-v2 (better, 768d)
# - BAAI/bge-base-en-v1.5 (best, 768d)
# - BAAI/bge-large-en-v1.5 (largest, 1024d)
```

### Switching Vector Stores

Currently supports FAISS. ChromaDB support included:
```ini
VECTOR_STORE_TYPE=faiss  # or chroma
```

## 📁 Project Structure

```
questionsapp/
├── backend/
│   ├── app/
│   │   ├── config.py               # Configuration management
│   │   ├── models.py               # Pydantic models
│   │   ├── main.py                 # FastAPI application
│   │   ├── llm/                    # LLM abstraction layer
│   │   │   ├── base_llm.py
│   │   │   ├── ollama_llm.py
│   │   │   ├── openai_llm.py
│   │   │   ├── llm_manager.py
│   │   │   ├── prompts.py
│   │   │   └── question_generator.py
│   │   ├── ingestion/
│   │   │   ├── extractors/         # Document extractors
│   │   │   ├── chunker.py
│   │   │   ├── embedder.py
│   │   │   ├── document_processor.py
│   │   │   └── ingestion_manager.py
│   │   ├── vectorstore/
│   │   │   ├── faiss_manager.py
│   │   │   └── metadata_db.py
│   │   ├── retrieval/
│   │   │   └── retriever.py
│   │   └── utils/
│   │       └── logger.py
│   └── requirements.txt
├── frontend/
│   ├── streamlit_app.py            # Streamlit UI
│   └── requirements.txt
├── data/                            # Created automatically
│   ├── vector_store/
│   ├── metadata/
│   └── logs/
└── README.md
```

## 🐛 Troubleshooting

### Ollama Not Found
```powershell
# Make sure Ollama is installed and running
ollama serve
```

### GPU Out of Memory
```ini
# Use CPU for embeddings
EMBEDDING_DEVICE=cpu
```

### OCR Errors
```powershell
# Windows: Install Tesseract
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# Add to PATH

# Or disable OCR:
ENABLE_OCR=false
```

### Import Errors
```powershell
# Reinstall dependencies
pip install -r backend/requirements.txt --upgrade
```

## 🔧 Advanced Usage

### API Endpoints

The backend exposes REST endpoints:

- `GET /health` - System health check
- `POST /api/ingest` - Start document ingestion
- `GET /api/ingestion/status` - Check ingestion progress
- `POST /api/query` - Query knowledge base
- `POST /api/generate-questions` - Generate questions
- `GET /api/stats` - System statistics

### Example API Usage

```python
import requests

# Query the knowledge base
response = requests.post(
    "http://localhost:8601/api/query",
    json={"query": "What is Newton's first law?", "top_k": 5}
)
print(response.json()["answer"])

# Generate questions
response = requests.post(
    "http://localhost:8601/api/generate-questions",
    json={
        "subject": "physics",
        "difficulty": "medium",
        "question_type": "multiple_choice",
        "num_questions": 5
    }
)
for q in response.json()["questions"]:
    print(f"Q: {q['question']}")
    print(f"A: {q['correct_answer']}\n")
```

## 📊 Performance

- **Ingestion Speed**: ~10-50 PDFs/minute (depends on size and OCR)
- **Query Latency**: 1-3 seconds (with local LLM)
- **Question Generation**: 10-30 seconds for 5 questions
- **Memory Usage**: 2-4GB (can scale with model size)

## 🤝 Contributing

This is a production-ready template. Customize and extend as needed:

1. Add new document extractors in `app/ingestion/extractors/`
2. Implement new LLM providers in `app/llm/`
3. Add new vector stores in `app/vectorstore/`
4. Extend prompts in `app/llm/prompts.py`

## 📝 License

MIT License - feel free to use and modify.

## 🙏 Acknowledgments

Built with:
- FastAPI
- Streamlit
- LangChain
- Sentence Transformers
- FAISS
- Ollama
- PyMuPDF

---

**Questions or Issues?** Check the logs in `data/logs/` for detailed error information.
