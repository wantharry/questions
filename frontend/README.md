# RAG Question Generator - Frontend

Streamlit UI for document ingestion and question generation.

## Setup

1. Install dependencies:
```powershell
pip install -r requirements.txt
```

2. Make sure the backend is running at http://localhost:8601

3. Run Streamlit:
```powershell
streamlit run streamlit_app.py
```

The UI will be available at http://localhost:8602

## Features

### Tab 1: Knowledge Addition
- Add documents from folders
- Recursive scanning
- Real-time progress tracking
- Resumable ingestion

### Tab 2: Query & Questions
- **Query Sub-tab**: Ask questions about your knowledge base
- **Generate Questions Sub-tab**: Create practice questions with:
  - Subject selection (Math, Physics, Chemistry)
  - Difficulty levels (Easy, Medium, Hard)
  - Question types (Multiple choice, Short answer, etc.)
  - Topic filtering

## Configuration

The UI connects to the backend at `http://localhost:8601` by default.

Edit `API_BASE_URL` in `streamlit_app.py` if your backend runs elsewhere.

## Usage Tips

1. **First time**: Add documents via Knowledge Addition tab
2. **Wait for ingestion**: Monitor progress before querying
3. **Query**: Use natural language questions
4. **Generate**: Select subject and difficulty for targeted questions
