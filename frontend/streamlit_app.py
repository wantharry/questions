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


def start_ingestion(folder_path: str, recursive: bool, file_patterns: list, force_reprocess: bool, target_index: Optional[str] = None, model: Optional[str] = None):
    """Start document ingestion."""
    try:
        payload = {
            "folder_path": folder_path,
            "recursive": recursive,
            "file_patterns": file_patterns,
            "force_reprocess": force_reprocess,
        }
        if target_index:
            payload["target_index"] = target_index
        if model:
            payload["model"] = model

        # Add session token if available
        headers = {}
        if st.session_state.session_token:
            headers["X-Session-Token"] = st.session_state.session_token

        response = requests.post(f"{API_BASE_URL}/api/ingest", json=payload, headers=headers)
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


def get_available_models():
    """Get available Ollama models."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/llm/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('models', []), data.get('default')
        return [], None
    except:
        return [], None


def get_available_indexes():
    """Get available indexes."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/indexes", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [idx['name'] for idx in data.get('indexes', [])]
        return []
    except:
        return []


def query_knowledge_base(query: str, top_k: int = 5, model: Optional[str] = None, index_filter: Optional[list] = None):
    """Query the knowledge base."""
    try:
        payload = {
            "query": query,
            "top_k": top_k,
        }
        if model:
            payload["model"] = model
        if index_filter:
            payload["index_filter"] = index_filter

        # Add session token if available
        headers = {}
        if st.session_state.session_token:
            headers["X-Session-Token"] = st.session_state.session_token

        response = requests.post(f"{API_BASE_URL}/api/query", json=payload, headers=headers, timeout=60)
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
    model: Optional[str] = None,
    index_filter: Optional[list] = None,
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
        if model:
            payload["model"] = model
        if index_filter:
            payload["index_filter"] = index_filter

        # Add session token if available
        headers = {}
        if st.session_state.session_token:
            headers["X-Session-Token"] = st.session_state.session_token

        response = requests.post(
            f"{API_BASE_URL}/api/generate-questions",
            json=payload,
            headers=headers,
            timeout=360  # 6 minutes for large batches (45+ questions takes 3-5 min)
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Question generation error: {e}")
        return None


def upload_user_documents(uploaded_files):
    """Upload files for a user."""
    try:
        headers = {}
        if st.session_state.session_token:
            headers["X-Session-Token"] = st.session_state.session_token

        files = [("files", (f.name, f.getbuffer(), "application/octet-stream")) for f in uploaded_files]

        response = requests.post(
            f"{API_BASE_URL}/api/documents/upload",
            files=files,
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json()
    except Exception as e:
        return False, {"error": str(e)}


def get_user_documents():
    """Get list of user's uploaded documents."""
    try:
        headers = {}
        if st.session_state.session_token:
            headers["X-Session-Token"] = st.session_state.session_token

        response = requests.get(
            f"{API_BASE_URL}/api/documents",
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def ingest_user_documents():
    """Trigger ingestion of user's uploaded documents."""
    try:
        headers = {}
        if st.session_state.session_token:
            headers["X-Session-Token"] = st.session_state.session_token

        response = requests.post(
            f"{API_BASE_URL}/api/documents/ingest",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json()
    except Exception as e:
        return False, {"error": str(e)}


def get_user_index_name() -> Optional[str]:
    """Get the user's personal index name."""
    if st.session_state.user_id:
        return f"user_{st.session_state.user_id[:8]}"
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
    .session-box {
        padding: 0.75rem;
        border-radius: 0.5rem;
        background-color: #e7f3ff;
        border: 1px solid #b3d9ff;
        color: #004085;
    }
</style>
""", unsafe_allow_html=True)

# Session Management
def init_session_state():
    """Initialize session state variables."""
    if 'session_token' not in st.session_state:
        st.session_state.session_token = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'username' not in st.session_state:
        st.session_state.username = None

init_session_state()

# Login/Logout UI
with st.container():
    col1, col2, col3 = st.columns([2, 2, 1])

    if st.session_state.session_token:
        # User is logged in
        with col1:
            st.markdown(f"""
            <div class="session-box">
            👤 <b>Logged in as:</b> {st.session_state.username}
            </div>
            """, unsafe_allow_html=True)

        with col3:
            if st.button("🚪 Logout", key="logout_btn"):
                try:
                    requests.post(
                        f"{API_BASE_URL}/api/session/logout",
                        json={"session_token": st.session_state.session_token},
                        timeout=5
                    )
                except:
                    pass
                st.session_state.session_token = None
                st.session_state.user_id = None
                st.session_state.username = None
                st.rerun()
    else:
        # User is not logged in - show login form
        st.markdown("### 🔐 Login to Continue")

        login_col1, login_col2 = st.columns([2, 1])

        with login_col1:
            username = st.text_input(
                "Username",
                placeholder="Enter your name",
                key="login_username"
            )

        with login_col2:
            login_btn = st.button("Login", key="login_btn", use_container_width=True)

        if login_btn:
            if not username.strip():
                st.error("Please enter a username")
            else:
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/api/session/create",
                        json={"username": username.strip()},
                        timeout=5
                    )

                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.session_token = data['session_token']
                        st.session_state.user_id = data['user_id']
                        st.session_state.username = username.strip()
                        st.success(f"✅ Welcome, {username}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Login failed: {response.json().get('detail', 'Unknown error')}")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to API. Make sure the backend is running.")
                except Exception as e:
                    st.error(f"Login error: {str(e)}")

# Title and header (shown after login check)
st.title("📚 RAG Question Generator")
st.markdown("Local knowledge base with AI-powered question generation")

# If not logged in, show a message and stop
if not st.session_state.session_token:
    st.info("👆 Please login above to get started")
    st.stop()

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
tab1, tab2, tab3, tab4 = st.tabs(["📁 Knowledge Addition", "🔍 Query & Questions", "🏗️ Index Management", "📤 Upload Documents"])

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
        
        # Target index selection
        st.markdown("---")
        st.markdown("**Optional Settings**")
        
        # Model selection
        available_models, default_model = get_available_models()
        if available_models:
            model_names = [m['name'] for m in available_models]
            ingestion_model_select = st.selectbox(
                "🤖 LLM Model (for processing)",
                options=["Use Default (Recommended)"] + model_names,
                index=0,
                help=f"Default: {default_model}. Most ingestion doesn't require LLM, but you can select a specific model if needed.",
                key="ingestion_model"
            )
            ingestion_model = None if ingestion_model_select == "Use Default (Recommended)" else ingestion_model_select
        else:
            ingestion_model = None
        
        st.markdown("**Target Index** (Optional)")
        
        # Fetch available custom indexes
        try:
            response = requests.get(f"{API_BASE_URL}/api/indexes", timeout=2)
            if response.status_code == 200:
                indexes_data = response.json()
                all_indexes = [idx['name'] for idx in indexes_data.get('indexes', [])]
                custom_indexes = [idx['name'] for idx in indexes_data.get('indexes', []) if idx['is_custom']]
                
                if custom_indexes:
                    use_custom_index = st.checkbox(
                        "Ingest into a specific custom index",
                        value=False,
                        help="Check this to select a custom index. Leave unchecked for automatic content-based routing."
                    )
                    
                    target_index = None
                    if use_custom_index:
                        target_index = st.selectbox(
                            "Select target index",
                            options=custom_indexes,
                            help="Documents will be added to this index instead of automatic routing"
                        )
                        st.caption(f"✅ Documents will be added to: **{target_index}**")
                    else:
                        st.caption("📊 Documents will be automatically routed to predefined indexes based on content type")
                else:
                    target_index = None
                    st.caption("📊 Documents will be automatically routed to predefined indexes. Create custom indexes in the 'Index Management' tab.")
            else:
                target_index = None
                st.caption("📊 Using automatic content-based routing")
        except:
            target_index = None
            st.caption("📊 Using automatic content-based routing")
        
        st.markdown("---")
        
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
                            wsl_path, recursive, file_patterns, force_reprocess, target_index, ingestion_model
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
        
        # Fetch available models and indexes
        available_models, default_model = get_available_models()
        available_indexes = get_available_indexes()
        
        # Model and Index Selection
        col_opt1, col_opt2 = st.columns(2)
        
        with col_opt1:
            if available_models:
                model_names = [m['name'] for m in available_models]
                default_idx = model_names.index(default_model) if default_model in model_names else 0
                selected_model = st.selectbox(
                    "🤖 LLM Model",
                    options=["Use Default"] + model_names,
                    index=0,
                    help=f"Default: {default_model}"
                )
                query_model = None if selected_model == "Use Default" else selected_model
            else:
                query_model = None
                st.caption("🤖 Using default model")
        
        with col_opt2:
            if available_indexes:
                # Auto-select user's index if available
                user_index = get_user_index_name()
                default_indexes = []
                if user_index and user_index in available_indexes:
                    default_indexes = [user_index]

                selected_indexes = st.multiselect(
                    "📑 Search Indexes",
                    options=available_indexes,
                    default=default_indexes,
                    help="Leave empty to search all indexes. Your personal index is pre-selected."
                )
                query_indexes = selected_indexes if selected_indexes else None
            else:
                query_indexes = None
                st.caption("📑 Searching all indexes")
        
        query_text = st.text_area(
            "Enter your question:",
            placeholder="What are Newton's laws of motion?",
            height=100
        )
        
        col1, col2 = st.columns([3, 1])
        with col1:
            query_button = st.button("🔍 Search", type="primary", use_container_width=True)
        with col2:
            top_k = st.selectbox("Top K Results", [5, 10, 20, 30, 50], index=4)
        
        if query_button and query_text:
            with st.spinner("Searching knowledge base..."):
                result = query_knowledge_base(query_text, top_k, model=query_model, index_filter=query_indexes)
                
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
        
        # Fetch available models and indexes
        available_models, default_model = get_available_models()
        available_indexes = get_available_indexes()
        
        # Model and Index Selection in expander
        with st.expander("⚙️ Advanced Options (Model & Index Selection)", expanded=False):
            col_adv1, col_adv2 = st.columns(2)
            
            with col_adv1:
                if available_models:
                    model_names = [m['name'] for m in available_models]
                    questions_model_select = st.selectbox(
                        "🤖 LLM Model",
                        options=["Use Default"] + model_names,
                        index=0,
                        help=f"Default: {default_model}",
                        key="questions_model"
                    )
                    questions_model = None if questions_model_select == "Use Default" else questions_model_select
                else:
                    questions_model = None
                    st.caption("🤖 Using default model")
            
            with col_adv2:
                if available_indexes:
                    # Auto-select user's index if available
                    user_index = get_user_index_name()
                    default_indexes = []
                    if user_index and user_index in available_indexes:
                        default_indexes = [user_index]

                    questions_indexes = st.multiselect(
                        "📑 Source Indexes",
                        options=available_indexes,
                        default=default_indexes,
                        help="Leave empty to use all indexes for context. Your personal index is pre-selected.",
                        key="questions_indexes"
                    )
                    questions_index_filter = questions_indexes if questions_indexes else None
                else:
                    questions_index_filter = None
                    st.caption("📑 Using all indexes")
        
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
            num_questions = st.slider("Number of Questions", 1, 100, 5)
            
            topic = st.text_input(
                "Specific Topic (optional)",
                placeholder="e.g., thermodynamics, calculus, organic chemistry"
            )
        
        if st.button("✨ Generate Questions", type="primary", use_container_width=True):
            with st.spinner(f"Generating {num_questions} {difficulty} questions..."):
                result = generate_questions(
                    subject, difficulty, question_type, num_questions, 
                    topic or None, 
                    model=questions_model, 
                    index_filter=questions_index_filter
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

# ========== TAB 3: Index Management ==========
with tab3:
    st.header("🏗️ Manage Vector Indexes")
    st.markdown("Create and manage custom indexes for organizing your documents by topic, source, or any criteria.")
    
    # Create two columns
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📋 Existing Indexes")
        
        # Refresh button
        if st.button("🔄 Refresh Index List"):
            st.rerun()
        
        # Fetch and display indexes
        try:
            response = requests.get(f"{API_BASE_URL}/api/indexes", timeout=5)
            if response.status_code == 200:
                indexes_data = response.json()
                indexes = indexes_data.get('indexes', [])
                
                if indexes:
                    # Create a DataFrame for better display
                    df_data = []
                    for idx in indexes:
                        df_data.append({
                            'Name': idx['name'],
                            'Documents': idx['document_count'],
                            'Dimension': idx['dimension'],
                            'Type': '🔒 Predefined' if not idx['is_custom'] else '✨ Custom'
                        })
                    
                    df = pd.DataFrame(df_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
                    st.caption(f"**Total Indexes:** {len(indexes)} ({sum(1 for i in indexes if i['is_custom'])} custom)")
                    
                    # Delete custom index section
                    st.markdown("---")
                    st.subheader("🗑️ Delete Custom Index")
                    
                    custom_indexes = [idx['name'] for idx in indexes if idx['is_custom']]
                    
                    if custom_indexes:
                        index_to_delete = st.selectbox(
                            "Select index to delete",
                            options=custom_indexes,
                            help="⚠️ Only custom indexes can be deleted. Predefined indexes are protected."
                        )
                        
                        if st.button("🗑️ Delete Index", type="secondary"):
                            with st.spinner(f"Deleting index '{index_to_delete}'..."):
                                try:
                                    del_response = requests.delete(
                                        f"{API_BASE_URL}/api/indexes/{index_to_delete}",
                                        timeout=10
                                    )
                                    if del_response.status_code == 200:
                                        st.success(f"✅ Index '{index_to_delete}' deleted successfully!")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        error_msg = del_response.json().get('detail', 'Unknown error')
                                        st.error(f"❌ Failed to delete index: {error_msg}")
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
                    else:
                        st.info("No custom indexes to delete. Predefined indexes cannot be deleted.")
                
                else:
                    st.warning("No indexes found")
            else:
                st.error(f"Failed to fetch indexes: {response.status_code}")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Cannot connect to API: {str(e)}")
            st.info("Make sure the backend is running on port 8601")
    
    with col2:
        st.subheader("➕ Create New Index")
        
        with st.form("create_index_form"):
            st.markdown("Create a custom index for organizing specific documents.")
            
            index_name = st.text_input(
                "Index Name",
                placeholder="e.g., jee_physics, ncert_chemistry",
                help="Use lowercase letters, numbers, underscores, and hyphens only"
            )
            
            description = st.text_area(
                "Description (Optional)",
                placeholder="Brief description of what this index will contain...",
                help="This helps you remember the purpose of this index"
            )
            
            # Advanced options
            with st.expander("⚙️ Advanced Options"):
                embedding_dim = st.number_input(
                    "Embedding Dimension",
                    min_value=128,
                    max_value=1536,
                    value=384,
                    step=128,
                    help="Default: 384 (matches sentence-transformers/all-MiniLM-L6-v2). Change only if using a different embedding model."
                )
            
            submit_button = st.form_submit_button("✨ Create Index", type="primary")
            
            if submit_button:
                if not index_name:
                    st.error("⚠️ Index name is required!")
                elif not re.match(r'^[a-z0-9_-]+$', index_name):
                    st.error("⚠️ Index name must contain only lowercase letters, numbers, underscores, and hyphens")
                else:
                    with st.spinner(f"Creating index '{index_name}'..."):
                        try:
                            payload = {
                                "index_name": index_name,
                                "description": description,
                                "embedding_dimension": embedding_dim
                            }
                            
                            response = requests.post(
                                f"{API_BASE_URL}/api/indexes",
                                json=payload,
                                timeout=10
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                st.success(f"✅ Index '{index_name}' created successfully!")
                                
                                with st.expander("📊 Index Details"):
                                    st.json(result.get('index_info', {}))
                                
                                time.sleep(1)
                                st.rerun()
                            else:
                                error_data = response.json()
                                error_msg = error_data.get('detail', 'Unknown error')
                                st.error(f"❌ Failed to create index: {error_msg}")
                        
                        except requests.exceptions.RequestException as e:
                            st.error(f"❌ API Error: {str(e)}")
                        except Exception as e:
                            st.error(f"❌ Unexpected error: {str(e)}")
    
    # Usage guide
    st.markdown("---")
    st.markdown("""
    ### 📖 How to Use Custom Indexes
    
    1. **Create an Index**: Use the form above to create a new index (e.g., `jee_physics`)
    2. **Ingest Documents**: In the "Knowledge Addition" tab, select your new index from the dropdown when ingesting documents
    3. **Search**: When querying, you can search across all indexes or specific ones
    
    ### 💡 Use Cases
    
    - **By Source**: Separate indexes for different textbooks or courses (e.g., `ncert`, `jee_material`)
    - **By Topic**: Physics, Chemistry, Math as separate indexes
    - **By Level**: Basic, Intermediate, Advanced content
    - **By Exam**: JEE, NEET, Board exam preparation materials
    
    ### 🔒 Predefined Indexes
    
    These indexes are always available and cannot be deleted:
    - **theory**: Explanations, definitions, theorems
    - **formula**: Equations, derivations, formulas
    - **exercise**: Problems, practice questions
    - **solution**: Worked examples, solutions
    - **general**: Mixed or unclassified content
    
    Documents are automatically routed to these indexes based on content classification.
    """)

# ========== TAB 4: Upload Documents ==========
with tab4:
    st.header("📤 Upload Your Documents")
    st.markdown("Upload PDF, DOCX, TXT, HTML, or Markdown files to your personal knowledge base.")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### Upload Files")

        uploaded_files = st.file_uploader(
            "Choose files to upload",
            type=["pdf", "docx", "txt", "md", "html", "htm"],
            accept_multiple_files=True,
            help="Select one or more files. Supported: PDF, DOCX, TXT, Markdown, HTML"
        )

        col_upload, col_ingest = st.columns(2)

        with col_upload:
            upload_btn = st.button("📤 Upload Files", use_container_width=True)

        with col_ingest:
            ingest_btn = st.button("🚀 Upload & Ingest", type="primary", use_container_width=True)

        if upload_btn and uploaded_files:
            with st.spinner(f"Uploading {len(uploaded_files)} file(s)..."):
                success, result = upload_user_documents(uploaded_files)
                if success:
                    st.success(f"✅ {result.get('message', 'Files uploaded successfully!')}")
                    st.json(result.get('files', []))
                else:
                    st.error(f"❌ Upload failed: {result.get('error', 'Unknown error')}")

        if ingest_btn and uploaded_files:
            with st.spinner(f"Uploading and ingesting {len(uploaded_files)} file(s)..."):
                success, result = upload_user_documents(uploaded_files)
                if success:
                    st.success(f"✅ {result.get('message', 'Files uploaded!')}")

                    # Now start ingestion
                    with st.spinner("Starting ingestion..."):
                        ingest_success, ingest_result = ingest_user_documents()
                        if ingest_success:
                            st.success(f"✅ Ingestion started! Files will be indexed into: **{ingest_result.get('target_index')}**")
                            st.info(f"📁 Location: `{ingest_result.get('upload_dir')}`")
                        else:
                            st.error(f"❌ Ingestion failed: {ingest_result.get('error', 'Unknown error')}")
                else:
                    st.error(f"❌ Upload failed: {result.get('error', 'Unknown error')}")

    with col2:
        st.markdown("### Your Documents")

        if st.button("🔄 Refresh List"):
            st.rerun()

        docs_result = get_user_documents()
        if docs_result:
            files = docs_result.get('files', [])
            count = docs_result.get('count', 0)

            st.metric("Total Files", count)

            if files:
                st.markdown("**Recent Uploads:**")
                for file_info in sorted(files, key=lambda x: x.get('uploaded_at', ''), reverse=True)[:5]:
                    file_size_kb = file_info['size'] / 1024
                    st.caption(f"📄 **{file_info['filename']}** ({file_size_kb:.1f} KB)")
                    st.caption(f"   Uploaded: {file_info.get('uploaded_at', 'N/A')}")
            else:
                st.info("No files uploaded yet.")
        else:
            st.warning("Unable to fetch document list")

    # Instructions and user index info
    st.markdown("---")

    user_index = get_user_index_name()
    if user_index:
        st.info(f"🔒 **Your Personal Index:** `{user_index}` — Only you can see and search these documents")

    st.markdown("""
    ### 📚 How to Use

    1. **Upload Files**: Select one or more documents from your computer
    2. **Click "Upload & Ingest"**: Files are uploaded and automatically indexed
    3. **Search & Generate**: Your documents appear in your personal index when querying or generating questions

    ### ✨ Features

    - 🔒 **Privacy**: Your documents are only searchable by you
    - ⚡ **Instant Indexing**: Files are processed in the background
    - 🔍 **Full Search**: Use Query or Generate Questions tabs to search your documents
    - 📊 **Progress Tracking**: Monitor ingestion status in the Knowledge Addition tab

    ### 📋 Supported Formats

    - **PDF** (`.pdf`) — Including scanned PDFs with OCR
    - **DOCX** (`.docx`) — Microsoft Word documents
    - **Text** (`.txt`) — Plain text files
    - **Markdown** (`.md`) — Markdown documents
    - **HTML** (`.html`, `.htm`) — Web pages and HTML content
    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "RAG Question Generator v2.0 (Hybrid Architecture) | Powered by Local LLM"
    "</div>",
    unsafe_allow_html=True
)
