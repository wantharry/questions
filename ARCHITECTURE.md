# Architecture Documentation

## System Overview

The RAG Question Generator is a modular, production-ready system for processing documents and generating educational questions using local LLMs.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                           │
│                    (Streamlit Web App)                           │
└─────────────────────────────────────────────────────────────────┘
                            │ HTTP
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                      REST API Layer                              │
│                      (FastAPI)                                   │
├─────────────────────────────────────────────────────────────────┤
│  Endpoints:                                                      │
│  • /api/ingest          - Document ingestion                    │
│  • /api/query          - Knowledge base queries                 │
│  • /api/generate-questions - Question generation                │
│  • /health             - System health check                    │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ↓                    ↓                    ↓
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  Ingestion   │   │  Retrieval   │   │  Question    │
    │   Manager    │   │   System     │   │  Generator   │
    └──────────────┘   └──────────────┘   └──────────────┘
           │                    │                    │
           ↓                    ↓                    ↓
    ┌──────────────────────────────────────────────────────┐
    │            Pluggable Components Layer                 │
    ├───────────────┬──────────────┬──────────────────────┤
    │  Document     │  Embeddings  │  Vector Store        │
    │  Processors   │  (STrans)    │  (FAISS)             │
    └───────────────┴──────────────┴──────────────────────┘
                            │
                            ↓
                    ┌──────────────┐
                    │  LLM Layer   │
                    │  (Ollama)    │
                    └──────────────┘
```

## Core Components

### 1. FastAPI Backend (`backend/app/`)

**Purpose**: REST API for document processing, retrieval, and question generation.

**Key Files**:
- `main.py`: API endpoints and application lifecycle
- `config.py`: Configuration management with Pydantic
- `models.py`: Request/response models

### 2. Ingestion Pipeline (`backend/app/ingestion/`)

**Purpose**: Process documents, extract text, chunk, and embed.

**Components**:

#### Document Processor (`document_processor.py`)
- Routes documents to appropriate extractors
- Computes file hashes for change detection
- Handles errors gracefully

#### Extractors (`ingestion/extractors/`)
- `pdf_extractor.py`: PyMuPDF-based PDF processing
- `html_extractor.py`: BeautifulSoup HTML parsing
- `image_extractor.py`: OCR with Tesseract
- `text_extractor.py`: Plain text, Markdown, DOCX

#### Chunker (`chunker.py`)
- Recursive character splitting with configurable overlap
- Preserves semantic boundaries (paragraphs, sentences)
- Attaches metadata to each chunk

#### Embedder (`embedder.py`)
- Sentence Transformers integration
- Batch processing for efficiency
- Normalized embeddings for cosine similarity

#### Ingestion Manager (`ingestion_manager.py`)
- Orchestrates the entire pipeline
- Resumable processing with SQLite checkpoints
- Batch processing with configurable checkpoints
- Comprehensive error handling and logging

**Data Flow**:
```
Documents → Extract → Chunk → Embed → Store
                                      ↓
                              FAISS + SQLite
```

### 3. Vector Storage (`backend/app/vectorstore/`)

#### FAISS Manager (`faiss_manager.py`)
- Manages FAISS index lifecycle
- Supports multiple index types (Flat, IVF, HNSW)
- Persistent storage with pickle
- Metadata association

#### Metadata DB (`metadata_db.py`)
- SQLAlchemy ORM models
- Tracks document processing status
- Stores chunk metadata
- Ingestion logging

**Schema**:
```
documents
├── id (PK)
├── file_path (unique)
├── file_hash (for change detection)
├── status (pending/processing/completed/failed)
├── metadata (JSON)
└── chunks (1:N relationship)

chunks
├── id (PK)
├── chunk_id (unique)
├── document_id (FK)
├── content
├── page_number
└── metadata
```

### 4. LLM Integration (`backend/app/llm/`)

**Purpose**: Pluggable LLM abstraction with multiple providers.

#### Base LLM (`base_llm.py`)
- Abstract interface for all LLM providers
- Standardized response format
- Streaming support

#### Providers
- `ollama_llm.py`: Ollama integration (default)
- `openai_llm.py`: OpenAI API (also works with vLLM)
- Designed for easy extension (llama.cpp, etc.)

#### LLM Manager (`llm_manager.py`)
- Factory pattern for provider selection
- Singleton instance management
- Health checking

#### Prompts (`prompts.py`)
- Subject-specific templates (Math, Physics, Chemistry)
- Difficulty-based variations
- Question type specifications

#### Question Generator (`question_generator.py`)
- Retrieves relevant context
- Formats prompts
- Parses LLM responses
- Handles JSON and text formats

### 5. Retrieval System (`backend/app/retrieval/`)

#### Retriever (`retriever.py`)
- Embeds queries
- Semantic search via FAISS
- Formats context for LLM
- Returns ranked results with metadata

**Retrieval Flow**:
```
Query → Embed → FAISS Search → Rank → Format Context
```

### 6. Streamlit Frontend (`frontend/streamlit_app.py`)

**Purpose**: Two-tab UI for knowledge management and querying.

**Features**:
- Real-time status monitoring
- Progress tracking for ingestion
- Interactive query interface
- Question generation with customization

**Tabs**:
1. **Knowledge Addition**: Upload and process documents
2. **Query & Questions**: Query knowledge base and generate questions

## Design Patterns

### 1. Plugin Architecture

**LLM Abstraction**:
```python
BaseLLM (ABC)
├── OllamaLLM
├── OpenAILLM
└── [Your Custom LLM]  # Easy to add
```

**Benefits**:
- Swap providers without code changes
- Test with different models easily
- Extend for proprietary systems

### 2. Factory Pattern

**LLMManager**:
- Creates appropriate LLM instance based on config
- Manages singleton instance
- Handles provider-specific initialization

### 3. Repository Pattern

**Vector Store & Metadata DB**:
- Abstracts storage details
- Enables easy migration (FAISS → Chroma, etc.)
- Consistent interface

### 4. Strategy Pattern

**Extractors**:
- Common interface for all document types
- DocumentProcessor routes to appropriate strategy
- Easy to add new formats

## Data Flow

### Ingestion Pipeline

```
1. User selects folder
   ↓
2. Scan for matching files
   ↓
3. For each file:
   a. Compute hash
   b. Check if processed (skip if unchanged)
   c. Route to appropriate extractor
   d. Extract text/images
   e. Chunk text (recursive splitting)
   f. Generate embeddings (batch)
   g. Store in FAISS + SQLite
   h. Checkpoint every N documents
   ↓
4. Save final index
```

### Query Pipeline

```
1. User enters query
   ↓
2. Embed query
   ↓
3. FAISS similarity search
   ↓
4. Retrieve top K chunks
   ↓
5. Format context
   ↓
6. Generate LLM prompt
   ↓
7. Call LLM
   ↓
8. Return answer + sources
```

### Question Generation Pipeline

```
1. User specifies parameters
   (subject, difficulty, type, count)
   ↓
2. Retrieve relevant context
   (semantic search on subject/topic)
   ↓
3. Load subject-specific template
   ↓
4. Format prompt with context
   ↓
5. Generate questions via LLM
   ↓
6. Parse response (JSON preferred)
   ↓
7. Return structured questions
```

## Scalability Considerations

### Current Design (Single Machine)

- **Documents**: Handles 20GB+ PDFs
- **Vector Store**: FAISS scales to millions of vectors
- **Concurrent Users**: FastAPI async handles multiple requests
- **Memory**: ~2-4GB typical usage

### Future Scaling Options

1. **Distributed Processing**:
   - Celery for background ingestion
   - Redis for task queue
   - Multiple workers

2. **Database Scaling**:
   - PostgreSQL instead of SQLite
   - Connection pooling

3. **Vector Store**:
   - Qdrant or Milvus for distributed vectors
   - Sharding by subject/date

4. **LLM Serving**:
   - vLLM for high throughput
   - Load balancing across GPUs

## Configuration Management

### Environment Variables (`.env`)

**Categories**:
1. **LLM**: Provider, model, URL, temperature
2. **Embeddings**: Model, dimension, device
3. **Processing**: Chunk size, overlap, workers
4. **Storage**: Paths for data, logs, models
5. **API**: Host, port, workers

**Validation**: Pydantic Settings ensures type safety and validation.

## Error Handling

### Levels

1. **Document Level**: Mark failed, continue with others
2. **API Level**: Return HTTP error codes with details
3. **UI Level**: Display user-friendly messages
4. **Logging**: Comprehensive logs for debugging

### Resumability

- SQLite tracks processing status
- FAISS checkpoints every N documents
- Can restart ingestion anytime
- Skips already-processed files

## Performance Optimizations

1. **Batch Embedding**: Process chunks in batches
2. **Parallel Processing**: ThreadPoolExecutor for documents
3. **Lazy Loading**: Models loaded on first use
4. **Caching**: FAISS indices persisted to disk
5. **Async API**: FastAPI async for I/O operations

## Testing Strategy

### Unit Tests
- Individual extractors
- Chunking logic
- Embedding generation
- LLM response parsing

### Integration Tests
- End-to-end ingestion
- Query pipeline
- Question generation

### Manual Testing
- UI workflows
- Large document sets
- Edge cases (empty files, corrupted PDFs)

## Security Considerations

### Current Implementation
- Local-only deployment
- No authentication (single-user)
- File system access controls

### Production Enhancements
- Add API authentication (JWT)
- Input validation (file paths, sizes)
- Rate limiting
- CORS configuration
- HTTPS/TLS

## Monitoring & Observability

### Logging
- Structured logging with Loguru
- Multiple log files (app, errors, ingestion)
- Automatic rotation and compression

### Metrics (Future)
- Prometheus exporters
- Grafana dashboards
- Query latency tracking
- Ingestion throughput

### Health Checks
- `/health` endpoint
- LLM availability check
- Vector store statistics

## Extension Points

### Adding New Components

1. **New Document Format**:
   - Create extractor in `ingestion/extractors/`
   - Implement `extract()` method
   - Add to DocumentProcessor routing

2. **New LLM Provider**:
   - Inherit from BaseLLM
   - Implement required methods
   - Add to LLMManager factory

3. **New Vector Store**:
   - Create manager in `vectorstore/`
   - Implement add/search interface
   - Update configuration

4. **New Question Type**:
   - Add to QuestionType enum
   - Create prompt template
   - Update parser logic

## Best Practices

1. **Configuration**: Use environment variables, never hardcode
2. **Validation**: Pydantic models for all data
3. **Logging**: Log at appropriate levels with context
4. **Error Handling**: Graceful degradation, informative messages
5. **Documentation**: Docstrings, type hints, comments
6. **Modularity**: Single responsibility, loose coupling
7. **Testing**: Write tests for critical paths

## Deployment

### Local Development
```bash
# Terminal 1
python -m app.main

# Terminal 2
streamlit run streamlit_app.py
```

### Production (Future)
- Docker containers
- Nginx reverse proxy
- Systemd services
- Log aggregation

---

This architecture prioritizes **modularity**, **pluggability**, and **maintainability** while delivering production-ready performance for large-scale document processing.
