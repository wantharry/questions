"""
Streamlit UI for the RAG Question Generator.
Two tabs: Knowledge Addition and Query/Question Generation.
"""
import streamlit as st
import requests
import time
import re
from pathlib import Path
import pandas as pd
from typing import Optional


# Configuration
API_BASE_URL = "http://localhost:8601"


def render_latex_text(text: str) -> str:
    r"""
    Convert LaTeX expressions in text to Streamlit-compatible format.
    Handles both inline $...$ and display $$...$$ math.
    Also handles bare LaTeX like \vec{A}, \hat{i}, etc.
    """
    if not text:
        return text
    
    # Protect already properly formatted LaTeX
    # Handle display math $$...$$
    text = re.sub(r'\$\$(.*?)\$\$', r'$$\1$$', text, flags=re.DOTALL)
    
    # Handle inline math $...$
    text = re.sub(r'\$([^\$]+?)\$', r'$\1$', text)
    
    # Handle bare LaTeX expressions (not already in $ or $$)
    # Common patterns: \vec{}, \hat{}, \frac{}{}, \alpha, etc.
    # This is a simplified approach - wrap bare LaTeX in $...$
    def wrap_bare_latex(match):
        latex = match.group(0)
        # Check if already in math mode
        return f"${latex}$"
    
    # Match LaTeX commands not already in $...$ or $$...$$
    # This regex looks for backslash commands
    # Only wrap if not already between $ symbols
    parts = []
    last_end = 0
    in_math = False
    
    for match in re.finditer(r'\$+', text):
        # Track if we're entering or leaving math mode
        dollar_count = len(match.group(0))
        in_math = not in_math
    
    # More robust: wrap sequences with backslash commands if not in $
    if r'\vec{' in text or r'\hat{' in text or r'\frac{' in text:
        # Split by $ to find non-math parts
        segments = re.split(r'(\$+[^\$]*\$+)', text)
        result = []
        for segment in segments:
            if segment.startswith('$'):
                # Already math mode
                result.append(segment)
            elif '\\' in segment and any(cmd in segment for cmd in [r'\vec', r'\hat', r'\frac', r'\alpha', r'\beta', r'\gamma']):
                # Has LaTeX commands but not in math mode - wrap it
                result.append(f"${segment}$")
            else:
                result.append(segment)
        return ''.join(result)
    
    return text


def convert_windows_to_wsl_path(path: str) -> str:
    """Convert Windows path to WSL path format."""
    import re
    # Check if it's a Windows path (e.g., C:\... or C:/...)
    windows_pattern = r'^([A-Za-z]):[/\\]'
    match = re.match(windows_pattern, path)
    if match:
        drive = match.group(1).lower()
        # Replace C:\ or C:/ with /mnt/c/
        wsl_path = re.sub(windows_pattern, f'/mnt/{drive}/', path)
        # Replace backslashes with forward slashes
        wsl_path = wsl_path.replace('\\', '/')
        return wsl_path
    return path


def check_api_health():
    """Check if the API is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def get_api_stats():
    """Get system statistics from API."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats")
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def start_ingestion(folder_path: str, recursive: bool, file_patterns: list, force_reprocess: bool):
    """Start document ingestion."""
    try:
        payload = {
            "folder_path": folder_path,
            "recursive": recursive,
            "file_patterns": file_patterns,
            "force_reprocess": force_reprocess,
        }
        response = requests.post(f"{API_BASE_URL}/api/ingest", json=payload)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, {"error": str(e)}


def get_ingestion_status():
    """Get ingestion status."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/ingestion/status")
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def query_knowledge_base(query: str, top_k: int = 5):
    """Query the knowledge base."""
    try:
        payload = {
            "query": query,
            "top_k": top_k,
        }
        response = requests.post(f"{API_BASE_URL}/api/query", json=payload, timeout=60)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Query error: {e}")
        return None


def generate_questions(
    subject: str,
    difficulty: str,
    question_type: str,
    num_questions: int,
    topic: Optional[str] = None,
):
    """Generate questions."""
    try:
        payload = {
            "subject": subject,
            "difficulty": difficulty,
            "question_type": question_type,
            "num_questions": num_questions,
        }
        if topic:
            payload["topic"] = topic
        
        response = requests.post(
            f"{API_BASE_URL}/api/generate-questions",
            json=payload,
            timeout=120
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Question generation error: {e}")
        return None


# Page configuration
st.set_page_config(
    page_title="RAG Question Generator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
</style>
""", unsafe_allow_html=True)

# Title and header
st.title("📚 RAG Question Generator")
st.markdown("Local knowledge base with AI-powered question generation")

# Sidebar - System Status
with st.sidebar:
    st.header("System Status")
    
    if check_api_health():
        st.success("✅ API Connected")
        
        stats = get_api_stats()
        if stats:
            st.metric("Total Documents", stats['documents']['total'])
            st.metric("Total Chunks", stats['vector_store']['total_vectors'])
            st.metric("Failed Documents", stats['documents']['failed'])
            
            with st.expander("📊 Index Statistics"):
                multi_index_stats = stats['vector_store'].get('multi_index_stats', {})
                if multi_index_stats:
                    for idx_name, idx_stats in multi_index_stats.items():
                        st.text(f"{idx_name}: {idx_stats.get('document_count', 0)} chunks")
                
                bm25_stats = stats['vector_store'].get('bm25_stats', {})
                if bm25_stats:
                    st.text(f"BM25 Index: {bm25_stats.get('doc_count', 0)} docs, {bm25_stats.get('vocab_size', 0)} terms")
            
            with st.expander("⚙️ Configuration"):
                st.text(f"Architecture: {stats['configuration'].get('architecture', 'v1')}")
                st.text(f"LLM: {stats['configuration']['llm_provider']}")
                st.text(f"Model: {stats['configuration']['llm_model']}")
                st.text(f"Embeddings: {stats['configuration']['embedding_model']}")
                st.text(f"Chunk Size: {stats['configuration']['chunk_size']}")
    else:
        st.error("❌ API Not Connected")
        st.warning("Make sure the backend is running:\n```\npython -m app.main\n```")

# Main tabs
tab1, tab2 = st.tabs(["📁 Knowledge Addition", "🔍 Query & Questions"])

# ========== TAB 1: Knowledge Addition ==========
with tab1:
    st.header("Add Documents to Knowledge Base")
    st.markdown("Load PDFs, HTML, images, and other documents into the system.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Folder path input
        folder_path = st.text_input(
            "Folder Path",
            placeholder="/mnt/c/Users/data/physics_books",
            help="Enter the path in WSL format: /mnt/c/... (Windows C:\\ becomes /mnt/c/)"
        )
        
        # WSL path helper
        st.caption("💡 **WSL Path Format**: Windows `C:\\folder` → WSL `/mnt/c/folder` | Use forward slashes `/`")
        
        # Options
        recursive = st.checkbox("Scan subdirectories recursively", value=True)
        force_reprocess = st.checkbox("Force reprocess existing documents", value=False)
        
        # File patterns
        st.markdown("**File Types to Process**")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            pdf = st.checkbox("PDF", value=True)
            html = st.checkbox("HTML", value=True)
        with col_b:
            docx = st.checkbox("DOCX", value=True)
            md = st.checkbox("Markdown", value=True)
        with col_c:
            txt = st.checkbox("Text", value=True)
            images = st.checkbox("Images", value=False)
        
        # Build file patterns
        file_patterns = []
        if pdf: file_patterns.append("*.pdf")
        if html: file_patterns.extend(["*.html", "*.htm"])
        if docx: file_patterns.append("*.docx")
        if md: file_patterns.extend(["*.md", "*.markdown"])
        if txt: file_patterns.append("*.txt")
        if images: file_patterns.extend(["*.jpg", "*.jpeg", "*.png"])
        
        # Start ingestion button
        if st.button("🚀 Start Ingestion", type="primary", use_container_width=True):
            if not folder_path:
                st.error("Please enter a folder path")
            else:
                # Auto-convert Windows paths to WSL format
                wsl_path = convert_windows_to_wsl_path(folder_path)
                if wsl_path != folder_path:
                    st.info(f"📍 Converted path: `{wsl_path}`")
                
                # Check if path exists
                if not Path(wsl_path).exists():
                    st.error(f"❌ Folder does not exist: `{wsl_path}`")
                else:
                    with st.spinner("Starting ingestion..."):
                        success, result = start_ingestion(
                            wsl_path, recursive, file_patterns, force_reprocess
                        )
                        if success:
                            st.success("✅ Ingestion started successfully!")
                            st.json(result)
                        else:
                            st.error(f"Failed to start ingestion: {result.get('error', 'Unknown error')}")
    
    with col2:
        st.markdown("### Ingestion Status")
        
        # Status refresh button
        if st.button("🔄 Refresh Status"):
            st.rerun()
        
        status = get_ingestion_status()
        if status:
            if status['is_running']:
                st.info("⏳ Ingestion in progress...")
                st.progress(status['progress_percentage'] / 100)
            else:
                st.success("✅ No active ingestion")
            
            st.metric("Processed", status['processed_documents'])
            st.metric("Total", status['total_documents'])
            st.metric("Failed", status['failed_documents'])
            
            if status['is_running']:
                # Auto-refresh while running
                time.sleep(2)
                st.rerun()
    
    # Instructions
    st.markdown("---")
    st.markdown("""
    ### 📚 Instructions
    1. **Enter the folder path** containing your documents (PDFs, DOCX, HTML, etc.)
    2. **Select file types** you want to process
    3. **Enable "Scan subdirectories"** to process all nested folders
    4. **Click "Start Ingestion"** to begin indexing
    5. **Monitor progress** in the status panel (auto-refreshes)
    
    ### ✨ Advanced Features (v2)
    - 🧠 **Smart Chunking**: Keeps formulas and examples intact
    - 🔍 **Hybrid Search**: Combines semantic + keyword matching
    - 📊 **Content Classification**: Detects theory/formula/exercise/solution
    - 🎯 **Multi-Index**: Specialized indexes for different content types
    - 🔄 **Resumable**: Automatically resumes from where it left off
    - ⚡ **Skip Processed**: Already indexed files are skipped automatically
    """)

# Tab 2: Query Interface
with tab2:
    st.header("🔍 Query Documents")
    st.caption("🚀 Powered by Hybrid Retrieval (Dense + Sparse) with Auto-Routing")
    
    # Create sub-tabs
    subtab1, subtab2 = st.tabs(["💬 Query", "❓ Generate Questions"])
    
    # Sub-tab 1: Query
    with subtab1:
        st.markdown("Ask questions about your knowledge base")
        
        query_text = st.text_area(
            "Enter your question:",
            placeholder="What are Newton's laws of motion?",
            height=100
        )
        
        col1, col2 = st.columns([3, 1])
        with col1:
            query_button = st.button("🔍 Search", type="primary", use_container_width=True)
        with col2:
            top_k = st.selectbox("Top K Results", [3, 5, 10], index=1)
        
        if query_button and query_text:
            with st.spinner("Searching knowledge base..."):
                result = query_knowledge_base(query_text, top_k)
                
                if result:
                    st.markdown("### Answer")
                    answer_text = render_latex_text(result['answer'])
                    st.markdown(f"<div class='success-box'>{answer_text}</div>", unsafe_allow_html=True)
                    
                    st.markdown(f"*Processing time: {result['processing_time']:.2f}s*")
                    
                    st.markdown("---")
                    st.markdown("### Retrieved Sources")
                    
                    for i, chunk in enumerate(result['retrieved_chunks'], 1):
                        # Enhanced display with content type and difficulty
                        content_type = chunk.get('content_type', 'unknown')
                        difficulty = chunk.get('difficulty', 'unknown')
                        
                        # Content type emoji
                        type_emoji = {
                            'theory': '📖', 'definition': '📝', 'theorem': '🔬',
                            'formula': '🔢', 'derivation': '📐', 'exercise': '✏️',
                            'worked_example': '💡', 'solution': '✅', 'diagram': '🖼️',
                            'table': '📊', 'other': '📄'
                        }.get(content_type, '📄')
                        
                        with st.expander(
                            f"{type_emoji} Source {i}: {chunk['source_file']}" +
                            (f" (Page {chunk['page_number']})" if chunk['page_number'] else "") +
                            f" - Score: {chunk['similarity_score']:.3f}"
                        ):
                            # Show metadata badges
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.caption(f"📁 Type: **{content_type}**")
                            with col_b:
                                st.caption(f"📊 Difficulty: **{difficulty}**")
                            
                            st.markdown("---")
                            st.text(chunk['content'])
    
    # Sub-tab 2: Generate Questions
    with subtab2:
        st.markdown("Generate practice questions from your knowledge base")
        
        col1, col2 = st.columns(2)
        
        with col1:
            subject = st.selectbox(
                "Subject",
                ["mathematics", "physics", "chemistry", "general"],
            )
            
            difficulty = st.selectbox(
                "Difficulty Level",
                ["easy", "medium", "hard"],
                index=1
            )
            
            question_type = st.selectbox(
                "Question Type",
                ["multiple_choice", "short_answer", "long_answer", "numerical"],
            )
        
        with col2:
            num_questions = st.slider("Number of Questions", 1, 10, 5)
            
            topic = st.text_input(
                "Specific Topic (optional)",
                placeholder="e.g., thermodynamics, calculus, organic chemistry"
            )
        
        if st.button("✨ Generate Questions", type="primary", use_container_width=True):
            with st.spinner(f"Generating {num_questions} {difficulty} questions..."):
                result = generate_questions(
                    subject, difficulty, question_type, num_questions, topic or None
                )
                
                if result and result.get('questions'):
                    st.success(f"✅ Generated {len(result['questions'])} questions!")
                    
                    st.markdown(f"*Processing time: {result['processing_time']:.2f}s*")
                    
                    # Display questions
                    st.markdown("---")
                    for i, q in enumerate(result['questions'], 1):
                        st.markdown(f"### Question {i}")
                        
                        # Render question with LaTeX support
                        question_text = render_latex_text(q['question'])
                        st.markdown(question_text)
                        
                        if q.get('options'):
                            for opt in q['options']:
                                option_text = render_latex_text(opt)
                                st.markdown(f"- {option_text}")
                        
                        with st.expander("Show Answer & Explanation"):
                            answer_text = render_latex_text(q['correct_answer'])
                            st.markdown(f"**Answer:** {answer_text}")
                            
                            explanation_text = render_latex_text(q['explanation'])
                            st.markdown(f"**Explanation:** {explanation_text}")
                            
                            st.caption(f"Difficulty: {q['difficulty']} | Type: {q['question_type']}")
                        
                        st.markdown("---")
                    
                    # Context used
                    with st.expander("View Context Used"):
                        st.text(result.get('context_used', 'No context available'))
                else:
                    st.error("Failed to generate questions. Check if documents are loaded.")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "RAG Question Generator v2.0 (Hybrid Architecture) | Powered by Local LLM"
    "</div>",
    unsafe_allow_html=True
)
