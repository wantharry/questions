# RAG Question Generator - Backend

FastAPI-based backend for document processing, RAG, and question generation.

## Setup

1. Install dependencies:
```powershell
pip install -r requirements.txt
```

2. Configure environment:
```powershell
cp ../.env.example ../.env
# Edit .env as needed
```

3. Install Ollama and pull a model:
```powershell
ollama pull mistral:7b-instruct
```

4. Run the server:
```powershell
python -m app.main
```

The API will be available at http://localhost:8601

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8601/docs
- ReDoc: http://localhost:8601/redoc

## Development

Run with auto-reload:
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8601
```

## Testing

```powershell
pytest
```

## Directory Structure

- `app/` - Main application code
  - `llm/` - LLM providers and question generation
  - `ingestion/` - Document processing and embedding
  - `vectorstore/` - Vector database management
  - `retrieval/` - Semantic search
  - `utils/` - Utilities and logging

## Environment Variables

See `.env.example` for all configuration options.

Key variables:
- `LLM_PROVIDER` - ollama, openai, vllm
- `EMBEDDING_MODEL` - HuggingFace model name
- `CHUNK_SIZE` - Text chunk size for processing
- `ENABLE_OCR` - Enable OCR for images/PDFs
