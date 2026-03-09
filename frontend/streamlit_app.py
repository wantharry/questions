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
    Convert LaTeX expressions to Streamlit-compatible $...$ / $$...$$ format.

    Handles multiple LaTeX delimiters:
      \[...\]     -> $$...$$  (display math, AMS style)
      \(...\)     -> $...$    (inline math, AMS style)
      $$...$$     -> kept as-is (display math, already correct)
      $...$       -> kept as-is (inline math, already correct)
      {...}       -> wraps in $ for common formulas
    """
    if not text:
        return text

    # 1. Display math: \[...\] → $$...$$
    text = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', text, flags=re.DOTALL)

    # 2. Inline math: \(...\) → $...$
    text = re.sub(r'\\\((.*?)\\\)', r'$\1$', text, flags=re.DOTALL)

    # 3. Standalone formulas without any delimiters: if text has \frac, \sqrt, \int, etc
    # and is NOT already wrapped in $, wrap the whole line in $...$
    lines = text.split('\n')
    result_lines = []
    for line in lines:
        # Skip lines already in math mode
        if '$' in line or '$$' in line:
            result_lines.append(line)
        # Wrap lines with bare LaTeX commands in $...$
        elif any(cmd in line for cmd in [r'\frac', r'\sqrt', r'\int', r'\sum', r'\prod',
                                         r'\sin', r'\cos', r'\tan', r'\log', r'\exp',
                                         r'\alpha', r'\beta', r'\gamma', r'\delta', r'\pi',
                                         r'\infty', r'\partial', r'\nabla', r'\pm', r'\times']):
            # Only wrap if it looks like a formula (has {} or ^/_ operators)
            if '{' in line or '^' in line or '_' in line:
                result_lines.append(f"${line}$")
            else:
                result_lines.append(line)
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)


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
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
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


def query_knowledge_base(query: str, top_k: int = 5, settings: Optional[dict] = None):
    """Query the knowledge base."""
    try:
        payload = {
            "query": query,
            "top_k": top_k,
        }
        if settings:
            payload["settings"] = settings
        
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

# Fetch ingestion status once — reused across the whole page
ingestion_status = get_ingestion_status()

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
                    success, result = start_ingestion(
                        wsl_path, recursive, file_patterns, force_reprocess
                    )
                    if success:
                        st.success("✅ Ingestion started! Watch status on the right →")
                    else:
                        st.error(f"Failed to start ingestion: {result.get('error', 'Unknown error')}")
    
    with col2:
        st.markdown("### 📊 Status")
        if st.button("🔄 Refresh", key="status_refresh"):
            st.rerun()

        if ingestion_status:
            if ingestion_status['is_running']:
                st.warning("⏳ Ingestion running...")
                total = ingestion_status['total_documents']
                processed = ingestion_status['processed_documents']
                skipped = ingestion_status.get('skipped_documents', 0)
                pct = ingestion_status['progress_percentage']

                st.progress(min(pct / 100, 1.0))
                st.caption(f"{processed + skipped}/{total} ({pct:.0f}%)")

                current = ingestion_status.get('current_document')
                if current:
                    st.caption(f"📄 {current}")
            else:
                st.success("✅ Ready")
                if total := ingestion_status['total_documents']:
                    st.caption(f"📦 {total} docs")

    # Full-width live progress — always shown and always updates while running
    if ingestion_status and ingestion_status['is_running']:
        st.markdown("---")
        st.markdown("### ⏳ Ingestion in Progress")

        total = ingestion_status['total_documents']
        processed = ingestion_status['processed_documents']
        skipped = ingestion_status.get('skipped_documents', 0)
        failed = ingestion_status['failed_documents']
        done = processed + skipped
        pct = ingestion_status['progress_percentage']

        current = ingestion_status.get('current_document')
        if current:
            st.info(f"📄 **Processing:** {current}")

        st.progress(min(pct / 100, 1.0))
        st.caption(f"**Progress:** {done} of {total} files ({pct:.1f}%)")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", total)
        m2.metric("✅ Processed", processed)
        m3.metric("⏭️ Skipped", skipped)
        m4.metric("❌ Failed", failed)
    
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
        
        # Advanced Settings
        with st.expander("⚙️ Advanced Query Settings", expanded=False):
            st.markdown("#### General Settings")
            
            col1, col2 = st.columns(2)
            with col1:
                query_decomposition = st.checkbox("Query decomposition", value=False, help="Break complex queries into sub-queries")
                pruning = st.checkbox("Pruning", value=False, help="Remove irrelevant retrieved chunks")
                verify_answer = st.checkbox("Verify answer", value=True, help="Verify answer quality")
            
            with col2:
                compose_sub_answers = st.checkbox("Compose sub-answers", value=False, help="Merge answers from decomposed sub-queries")
                streaming = st.checkbox("Streaming", value=False, help="Stream response tokens (not yet implemented)")
            
            st.markdown("---")
            st.markdown("#### Retrieval Settings")
            
            col1, col2 = st.columns(2)
            with col1:
                retrieval_llm = st.selectbox(
                    "LLM",
                    ["qwen2.5:7b", "qwen3:0.6b", "llama3.2:3b", "Default"],
                    index=0,
                    help="LLM for retrieval tasks"
                )
            
            with col2:
                search_type = st.selectbox(
                    "Search type",
                    ["hybrid", "vector", "fts"],
                    index=0,
                    help="Hybrid = Vector + Full-Text Search"
                )
            
            retrieval_chunks = st.slider(
                "Retrieval chunks",
                min_value=5,
                max_value=50,
                value=20,
                help="Number of chunks to retrieve initially"
            )
            st.caption(f"{retrieval_chunks} chunks")
            
            st.markdown("---")
            st.markdown("#### Reranking & Context")
            
            ai_reranker = st.checkbox("AI reranker", value=True, help="Use AI-based reranking for better results")
            
            reranker_top_chunks = st.slider(
                "Reranker top chunks",
                min_value=3,
                max_value=20,
                value=10,
                disabled=not ai_reranker,
                help="Number of top chunks to keep after reranking"
            )
            st.caption(f"{reranker_top_chunks} chunks")
            
            expand_context_window = st.checkbox("Expand context window", value=False, help="Include surrounding chunks for more context")
            
            context_window_size = st.slider(
                "Context window size",
                min_value=0,
                max_value=5,
                value=1,
                disabled=not expand_context_window,
                help="Number of surrounding chunks to include"
            )
            st.caption(f"{context_window_size} chunks")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            query_button = st.button("🔍 Search", type="primary", use_container_width=True)
        with col2:
            top_k = st.selectbox("Top K Results", [3, 5, 10], index=1)
        
        if query_button and query_text:
            # Build settings object
            query_settings = {
                "query_decomposition": query_decomposition,
                "compose_sub_answers": compose_sub_answers,
                "pruning": pruning,
                "verify_answer": verify_answer,
                "streaming": streaming,
                "retrieval_llm": retrieval_llm if retrieval_llm != "Default" else None,
                "search_type": search_type,
                "retrieval_chunks": retrieval_chunks,
                "ai_reranker": ai_reranker,
                "reranker_top_chunks": reranker_top_chunks,
                "expand_context_window": expand_context_window,
                "context_window_size": context_window_size,
            }
            
            with st.spinner("Searching knowledge base..."):
                result = query_knowledge_base(query_text, top_k, query_settings)
                
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

# Auto-refresh while ingestion is running
# Fetch fresh status on every rerun to avoid stale data
current_status = get_ingestion_status()
if current_status and current_status['is_running']:
    time.sleep(2)
    st.rerun()
