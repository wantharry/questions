# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

**Prerequisites:** Ollama must be running (`ollama serve`) with `qwen2.5:7b` pulled.

**Virtual environment** is at the repo root (`venv/`). Activate in WSL:
```bash
source venv/bin/activate
```

**Backend** (port 8601):
```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8601 --reload
```

**Frontend** (port 8602):
```bash
cd frontend && streamlit run streamlit_app.py --server.port 8602 --server.address 0.0.0.0
```

**PowerShell scripts** (from repo root, Windows):
```powershell
.\start_all.ps1      # Start both services
.\stop_all.ps1       # Stop both services
.\restart_all.ps1    # Restart after code changes
.\status.ps1         # Check service health
```

If PowerShell execution policy blocks scripts:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**API docs** available at: `http://localhost:8601/docs`

## Testing

```bash
cd backend && pytest
# Async tests use pytest-asyncio
```

## Configuration

All config lives in `backend/.env` (copy from `.env.example`). Key variables:

- `LLM_PROVIDER` / `LLM_MODEL` / `LLM_BASE_URL` — default: `ollama` / `qwen2.5:7b` / `http://localhost:11434`
- `EMBEDDING_MODEL` / `EMBEDDING_DIMENSION` — default: `sentence-transformers/all-MiniLM-L6-v2` / `384`
- `VECTOR_STORE_TYPE` — `faiss` (default) or `chroma`
- `CHUNK_SIZE` / `CHUNK_OVERLAP` — default: `1000` / `200`
- `ENABLE_OCR` — set to `false` if Tesseract is not installed

The `Settings` class in `backend/app/config.py` uses Pydantic Settings and auto-creates required directories on startup.

## Architecture

This is a **Hybrid RAG system** with two processes:

```
Streamlit UI (8602) ──HTTP──> FastAPI Backend (8601)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                  ▼
             AdvancedIngestion   HybridRetriever   QuestionGenerator
             Manager             (dense+sparse)    (LLM-powered)
                    │                 │
                    ▼                 ▼
          MultiIndexManager +   BM25Index (sparse)
          FAISS indexes (dense)
                    │
                    ▼
          SQLite (metadata/checkpoints) + FAISS files (data/)
```

### Key Backend Components (`backend/app/`)

**Ingestion pipeline** (`ingestion/`):
- `advanced_ingestion_manager.py` — Orchestrates ingestion; uses `DocumentProcessor` → `SmartChunker` → `ContentClassifier` → stores in `MultiIndexManager` + `BM25Index`. Resumable via SQLite checkpoints.
- `smart_chunker.py` — Structure-aware chunking that adapts to content type (formulas, code, prose)
- `document_processor.py` — Routes files to extractors (PDF via PyMuPDF, HTML via BeautifulSoup, images via Tesseract OCR, DOCX, plain text)
- `embedder.py` — `SentenceTransformerEmbedder` wrapping sentence-transformers

**Vector storage** (`vectorstore/`):
- `multi_index_manager.py` — Manages multiple specialized FAISS indexes by content type (`IndexType`: theory, formula, exercise, solution, general)
- `bm25_index.py` — Sparse keyword index for hybrid search
- `metadata_db.py` — SQLAlchemy ORM (SQLite); tracks `Document` → `Chunk` with processing status

**Retrieval** (`retrieval/`):
- `hybrid_retriever.py` — Combines dense FAISS + sparse BM25 results, weighted fusion, then cross-encoder reranking
- `query_router.py` — Classifies query intent (`QueryIntent` enum) to route to appropriate index(es)
- `reranker.py` — Cross-encoder reranker for final result ordering

**LLM layer** (`llm/`):
- `base_llm.py` — Abstract interface; implement to add new providers
- `ollama_llm.py` / `openai_llm.py` — Concrete providers
- `llm_manager.py` — Singleton factory; selects provider based on `LLM_PROVIDER` env var
- `prompts.py` — Subject-specific templates (Math, Physics, Chemistry); difficulty variations
- `question_generator.py` — Retrieves context via `HybridRetriever`, formats prompts, parses JSON/text LLM output

**Classification** (`classification/`):
- `content_classifier.py` — Classifies chunks into `ContentType` enum (theory, definition, formula, theorem, worked_example, exercise, solution, etc.) and `DifficultyLevel`

**Startup behavior** (`main.py`):
- `AdvancedIngestionManager` is initialized eagerly at startup (loads embedding model)
- `HybridRetriever`, `SentenceTransformerEmbedder`, and `QuestionGenerator` are **lazy-loaded** on first query

### Data directory (`data/`)
Auto-created. Contains: `vector_store/` (FAISS index files), `metadata/metadata.db` (SQLite), `logs/` (Loguru log files).

### API Endpoints
- `GET /health` — System status
- `POST /api/ingest` — Start background ingestion from a folder path
- `GET /api/ingestion/status` — Ingestion progress
- `POST /api/query` — Query knowledge base (returns answer + sources)
- `POST /api/generate-questions` — Generate questions (subject/difficulty/type/count)
- `GET /api/stats` — System statistics
- `GET /api/llm/health` — Check LLM availability

### Extension Points
- **New document format**: Add extractor in `ingestion/extractors/`, implement `extract()`, register in `DocumentProcessor`
- **New LLM provider**: Subclass `BaseLLM`, add to `LLMManager` factory
- **New question type**: Add to enum in `models.py`, add template in `prompts.py`, update parser in `question_generator.py`
