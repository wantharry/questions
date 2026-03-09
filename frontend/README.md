# RAG Question Generator - Frontend

Streamlit UI for document ingestion and question generation.

## Two UI Options

### 1. Original UI (`streamlit_app.py`)
- Single knowledge base with automatic content-type indexing
- Simple, streamlined interface
- Automatic index management

### 2. Enhanced Multi-Index UI (`streamlit_app_v2.py`)
- Create and manage multiple custom indexes
- Configure chunking, embedding models, and retrieval modes per index
- Upload different files to different indexes
- Query specific indexes or search across all
- Advanced configuration options

## Setup

1. Install dependencies:
```powershell
pip install -r requirements.txt
```

2. Make sure the backend is running at http://localhost:8601

3. Run Streamlit:

**Original UI:**
```powershell
streamlit run streamlit_app.py
```

**Enhanced Multi-Index UI:**
```powershell
streamlit run streamlit_app_v2.py
```

Both UIs will be available at http://localhost:8602

## Features

### Original UI

#### Tab 1: Knowledge Addition
- Add documents from folders
- Recursive scanning
- Real-time progress tracking
- Resumable ingestion

#### Tab 2: Query & Questions
- **Query Sub-tab**: Ask questions about your knowledge base
- **Generate Questions Sub-tab**: Create practice questions with:
  - Subject selection (Math, Physics, Chemistry)
  - Difficulty levels (Easy, Medium, Hard)
  - Question types (Multiple choice, Short answer, etc.)
  - Topic filtering

### Enhanced Multi-Index UI

#### Tab 1: Index Management
- Create custom indexes with specific configurations
- List all available indexes (default + custom)
- Delete custom indexes
- View index statistics and metadata

#### Tab 2: Add Documents
- Select target index for ingestion
- Upload files specifically to chosen index
- Configure file types to process
- Monitor ingestion progress per index

#### Tab 3: Query & Questions
- Select which index to search (or search all)
- Query with advanced hybrid retrieval
- Generate questions from specific indexes
- Rich results with content classification

## Configuration

The UI connects to the backend at `http://localhost:8601` by default.

Edit `API_BASE_URL` in the respective UI file if your backend runs elsewhere.

## Usage Tips

### Original UI

1. **First time**: Add documents via Knowledge Addition tab
2. **Wait for ingestion**: Monitor progress before querying
3. **Query**: Use natural language questions
4. **Generate**: Select subject and difficulty for targeted questions

### Enhanced Multi-Index UI

1. **Create Index**: Start by creating an index with desired configuration
2. **Add Documents**: Upload documents to your index
3. **Monitor**: Watch ingestion progress in real-time
4. **Query**: Select your index and start asking questions
5. **Iterate**: Create multiple indexes to compare results

See [MULTI_INDEX_GUIDE.md](../MULTI_INDEX_GUIDE.md) for detailed documentation on multi-index features.

## Quick Start Scripts

From the repository root:

**Original UI:**
```powershell
.\start_frontend.ps1       # PowerShell
.\start_frontend.bat       # Command Prompt
```

**Enhanced Multi-Index UI:**
```powershell
.\start_frontend_v2.ps1    # PowerShell
.\start_frontend_v2.bat    # Command Prompt
```

**Start Everything (Backend + Enhanced UI):**
```powershell
.\start_all_v2.ps1         # PowerShell
```
