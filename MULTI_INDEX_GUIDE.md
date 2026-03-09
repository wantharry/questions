# Multi-Index Feature Guide

## Overview

The Multi-Index feature allows you to create and manage multiple separate knowledge bases (indexes) with different configurations. This is useful when you want to:

- Separate different subjects (e.g., physics, chemistry, math)
- Use different chunking strategies for different types of documents
- Compare different embedding models or retrieval modes
- Keep project-specific knowledge bases isolated

## Features

### Index Management

- **Create Custom Indexes**: Define indexes with custom names and configurations
- **Multiple Retrieval Modes**: Choose between hybrid (semantic + keyword), vector-only, or full-text search
- **Flexible Chunking**: Configure chunk size, overlap, and chunking strategies per index
- **Model Selection**: Choose different embedding models and LLMs for each index
- **Contextual Retrieval**: Optional context-aware retrieval for better results

### Document Management

- **Index-Specific Ingestion**: Upload different documents to different indexes
- **File Type Support**: PDF, HTML, DOCX, Markdown, Text, and Images
- **Batch Processing**: Efficient batch processing with configurable batch sizes
- **Progress Tracking**: Real-time ingestion progress monitoring

### Querying

- **Index Selection**: Query specific indexes or search across all indexes
- **Advanced Retrieval**: Hybrid search combining semantic understanding and keyword matching
- **Content Classification**: Automatic classification of content (theory, formula, exercise, etc.)
- **Rich Results**: Results include content type, difficulty level, and similarity scores

## Getting Started

### 1. Start the Backend

```powershell
# From the repository root
.\start_backend.ps1
```

The backend will start on `http://localhost:8601`.

### 2. Start the Enhanced Frontend

You can use either the original UI or the new multi-index UI:

**Original UI (single index):**
```powershell
.\start_frontend.ps1
```

**Enhanced Multi-Index UI:**
```powershell
.\start_frontend_v2.ps1
```

Both will start on `http://localhost:8602`.

### 3. Create Your First Index

1. Open the browser at `http://localhost:8602`
2. Go to the **"Indexes"** tab
3. Fill in the index configuration:
   - **Index Name**: `physics_textbooks` (or any unique name)
   - **Description**: Brief description of what this index contains
   - **Retrieval Mode**: Select `hybrid` (recommended)
   - **Chunk Size**: 512 (default, good for most documents)
   - **Chunk Overlap**: 64 (default)
   - **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (default)
4. Click **"Create Index"**

### 4. Add Documents to Your Index

1. Go to the **"Add Documents"** tab
2. Select the index you just created from the dropdown
3. Enter the folder path containing your documents:
   - Windows path example: `C:\Users\data\physics`
   - Converts automatically to WSL format: `/mnt/c/Users/data/physics`
4. Select file types to process (PDF, HTML, DOCX, etc.)
5. Click **"Start Ingestion"**
6. Monitor progress in real-time

### 5. Query Your Knowledge Base

1. Go to the **"Query & Questions"** tab
2. Select which index to search (or "All Indexes")
3. Enter your question in the query box
4. Click **"Search"**

The system will:
- Retrieve relevant chunks from the selected index(es)
- Classify content by type (theory, formula, exercise, etc.)
- Generate a comprehensive answer using the LLM
- Display sources with metadata and similarity scores

## Configuration Options

### Retrieval Mode

- **Hybrid** (Recommended): Combines semantic vector search with keyword-based BM25 search
  - Best for: General purpose, diverse queries
  - Pros: Handles both conceptual and specific queries well

- **Vector**: Pure semantic search using embeddings
  - Best for: Conceptual queries, understanding meaning
  - Pros: Excellent at finding semantically similar content

- **FTS** (Full-Text Search): Keyword-based search only
  - Best for: Exact phrase matching, specific terms
  - Pros: Fast, precise for known keywords

### Chunking Settings

- **Chunk Size**: Number of characters per chunk (100-4000)
  - Smaller chunks (256-512): More precise retrieval, better for Q&A
  - Larger chunks (1000-2000): More context, better for understanding

- **Chunk Overlap**: Overlap between consecutive chunks (0-500)
  - Higher overlap: Better continuity, avoids splitting concepts
  - Lower overlap: More unique content, faster processing

- **High-Recall Chunking**: Creates overlapping chunks for better recall
  - Enable for: Critical content where missing results is worse than extra results

- **Late-Chunk Vectors**: Computes embeddings during indexing (not on-the-fly)
  - Enable for: Normal operation (recommended)

### Embedding Models

Available models (fastest to slowest, least to most accurate):

1. **sentence-transformers/all-MiniLM-L6-v2** (Default)
   - Dimension: 384
   - Speed: Very Fast
   - Quality: Good
   - Best for: Most applications, fast queries

2. **sentence-transformers/all-mpnet-base-v2**
   - Dimension: 768
   - Speed: Fast
   - Quality: Better
   - Best for: Higher quality retrieval

3. **BAAI/bge-small-en-v1.5**
   - Dimension: 384
   - Speed: Fast
   - Quality: Very Good
   - Best for: Academic content

4. **Qwen/Qwen3-Embedding-0.6B**
   - Dimension: varies
   - Speed: Slower
   - Quality: Excellent
   - Best for: Maximum quality (requires more resources)

### Contextual Retrieval

When enabled, the system prepends context to each chunk before embedding:

- **Context Window**: Number of surrounding chunks to consider (1-20)
  - Larger window: More context, but slower processing
  - Recommended: 3-5

- **Retrieval LLM**: LLM used to generate contextual summaries
  - `qwen2.5:7b` (Recommended): Good balance
  - `qwen3:0.6b`: Faster, less accurate
  - `llama3.2:3b`: Alternative option

## Use Cases

### Example 1: Subject-Specific Indexes

Create separate indexes for different subjects:

```
Index: "physics_undergrad"
- Chunk Size: 512
- Embedding: all-MiniLM-L6-v2
- Mode: hybrid
Documents: Physics textbooks, lecture notes

Index: "math_advanced"
- Chunk Size: 768  (larger for proofs)
- Embedding: all-mpnet-base-v2
- Mode: vector (conceptual queries)
Documents: Advanced math texts, research papers

Index: "chemistry_practical"
- Chunk Size: 384  (smaller for procedures)
- Embedding: bge-small-en-v1.5
- Mode: hybrid
Documents: Lab manuals, practical guides
```

### Example 2: Comparing Approaches

Create multiple indexes with the same documents but different configs:

```
Index: "baseline"
- Chunk Size: 512
- Overlap: 64
- Mode: hybrid
- Embedding: all-MiniLM-L6-v2

Index: "high_quality"
- Chunk Size: 768
- Overlap: 128
- Mode: hybrid
- Embedding: all-mpnet-base-v2

Index: "speed_optimized"
- Chunk Size: 256
- Overlap: 32
- Mode: vector
- Embedding: all-MiniLM-L6-v2
```

Then compare query results across indexes to find the best configuration.

### Example 3: Project Isolation

Keep different projects separate:

```
Index: "project_alpha_docs"
Index: "project_beta_specs"
Index: "general_reference"
```

Query specific indexes to avoid cross-contamination of results.

## API Endpoints

The backend exposes RESTful APIs for index management:

### Create Index
```http
POST /api/indexes/create
Content-Type: application/json

{
  "index_name": "my_index",
  "retrieval_mode": "hybrid",
  "chunk_size": 512,
  "chunk_overlap": 64,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "description": "My custom index"
}
```

### List Indexes
```http
GET /api/indexes
```

### Get Index Info
```http
GET /api/indexes/{index_name}
```

### Delete Index
```http
DELETE /api/indexes/{index_name}
Content-Type: application/json

{
  "index_name": "my_index",
  "confirm": true
}
```

### Ingest into Index
```http
POST /api/indexes/{index_name}/ingest
Content-Type: application/json

{
  "index_name": "my_index",
  "folder_path": "/mnt/c/Users/data/docs",
  "recursive": true,
  "file_patterns": ["*.pdf", "*.html"],
  "force_reprocess": false
}
```

### Query with Index Selection
```http
POST /api/query
Content-Type: application/json

{
  "query": "Explain quantum mechanics",
  "top_k": 5,
  "index_name": "physics_textbooks"  // Optional
}
```

### Generate Questions from Index
```http
POST /api/generate-questions
Content-Type: application/json

{
  "subject": "physics",
  "difficulty": "medium",
  "question_type": "multiple_choice",
  "num_questions": 5,
  "topic": "quantum mechanics",
  "index_name": "physics_textbooks"  // Optional
}
```

## Tips and Best Practices

### Performance

1. **Batch Size**: 
   - Higher (64-256): Faster ingestion, more memory
   - Lower (8-32): Slower but more stable

2. **Chunk Size vs Retrieval**:
   - Smaller chunks: More precise, may miss context
   - Larger chunks: More context, may be less precise

3. **Embedding Model**:
   - Start with `all-MiniLM-L6-v2` (fast, good quality)
   - Upgrade to `all-mpnet-base-v2` if quality is insufficient

### Quality

1. **Use Hybrid Mode**: Best overall performance for most use cases

2. **Enable High-Recall Chunking**: For critical applications where you can't afford to miss relevant content

3. **Context Window**: Start with 3-5, increase if results lack context

4. **Chunk Overlap**: Use 10-20% of chunk size (e.g., 64 for 512 chunks)

### Organization

1. **Descriptive Index Names**: Use clear, descriptive names like `physics_quantum_mechanics` instead of `index1`

2. **Add Descriptions**: Always add descriptions to indexes for future reference

3. **Separate by Topic**: Create separate indexes for distinct topics or subjects

4. **Version Control**: Create new indexes for major document updates instead of reprocessing

## Troubleshooting

### Index Creation Fails

- **Error: Index already exists**
  - Solution: Choose a different index name or delete the existing index

- **Error: Invalid embedding model**
  - Solution: Make sure the model name is spelled correctly and supported

### Ingestion Fails

- **Error: Path not found**
  - Solution: Verify the path exists and is in WSL format (`/mnt/c/...`)

- **Error: No files found**
  - Solution: Check file patterns and ensure files match the patterns

### Query Returns No Results

- **Empty index**
  - Solution: Verify documents were ingested successfully (check index stats)

- **Index mismatch**
  - Solution: Make sure you selected the correct index in the dropdown

- **Query too specific**
  - Solution: Try a more general query or use "All Indexes"

## Architecture

The multi-index system extends the existing hybrid RAG architecture:

```
Frontend (streamlit_app_v2.py)
    │
    ├─ Index Management
    │   └─ Create/List/Delete Indexes
    │
    ├─ Document Upload
    │   └─ Index-Specific Ingestion
    │
    └─ Querying
        └─ Index-Specific or Cross-Index Search

Backend (FastAPI)
    │
    ├─ Index Manager
    │   └─ Custom index configurations (in-memory)
    │
    ├─ Multi-Index Manager
    │   ├─ theory_index (FAISS)
    │   ├─ formula_index (FAISS)
    │   ├─ exercise_index (FAISS)
    │   ├─ solution_index (FAISS)
    │   └─ general_index (FAISS)
    │
    ├─ BM25 Index (sparse retrieval)
    │
    ├─ Hybrid Retriever
    │   └─ Combines FAISS + BM25
    │
    └─ LLM (Ollama)
        └─ Answer generation
```

## Future Enhancements

Planned features for future releases:

- [ ] Persistent index configuration (database storage)
- [ ] Index sharing and export/import
- [ ] Multi-model comparison dashboard
- [ ] Advanced scheduling for batch ingestion
- [ ] Index aliases and redirects
- [ ] Cross-index similarity analysis
- [ ] Index merging and splitting
- [ ] Role-based access control per index
- [ ] Cost/performance analytics per index
- [ ] A/B testing framework for configurations

## Additional Resources

- **Documentation**: See [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- **Installation**: See [INSTALLATION.md](INSTALLATION.md) for setup instructions
- **Scripts**: See [SCRIPTS_README.md](SCRIPTS_README.md) for automation scripts
- **Quick Start**: See [QUICKSTART.md](QUICKSTART.md) for getting started

## Support

For issues, questions, or contributions:

1. Check existing documentation
2. Review error logs in `backend/data/logs/`
3. Verify backend health at `http://localhost:8601/docs`
4. Check Streamlit logs in the terminal

---

**Version**: 2.0  
**Last Updated**: March 2026  
**Requires**: Backend v1.0+, Ollama with qwen2.5:7b
