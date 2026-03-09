"""
Enhanced Streamlit UI for the RAG Question Generator with Multiple Index Support.
Supports creating custom indexes, uploading files, and querying specific indexes.
"""
import streamlit as st
import requests
import time
import re
import json
from pathlib import Path
from typing import Optional, List
import pandas as pd


# Configuration
API_BASE_URL = "http://localhost:8601"


def render_latex_text(text: str) -> str:
    r"""Convert LaTeX expressions to Streamlit-compatible format."""
    if not text:
        return text

    text = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', text, flags=re.DOTALL)
    text = re.sub(r'\\\((.*?)\\\)', r'$\1$', text, flags=re.DOTALL)

    lines = text.split('\n')
    result_lines = []
    for line in lines:
        if '$' in line or '$$' in line:
            result_lines.append(line)
        elif any(cmd in line for cmd in [r'\frac', r'\sqrt', r'\int', r'\sum', r'\prod',
                                         r'\sin', r'\cos', r'\tan', r'\log', r'\exp',
                                         r'\alpha', r'\beta', r'\gamma', r'\delta', r'\pi',
                                         r'\infty', r'\partial', r'\nabla', r'\pm', r'\times']):
            if '{' in line or '^' in line or '_' in line:
                result_lines.append(f"${line}$")
            else:
                result_lines.append(line)
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)


def convert_windows_to_wsl_path(path: str) -> str:
    """Convert Windows path to WSL path format."""
    windows_pattern = r'^([A-Za-z]):[/\\]'
    match = re.match(windows_pattern, path)
    if match:
        drive = match.group(1).lower()
        wsl_path = re.sub(windows_pattern, f'/mnt/{drive}/', path)
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


def list_indexes():
    """Get list of all indexes."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/indexes")
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def create_index(config: dict):
    """Create a new index."""
    try:
        response = requests.post(f"{API_BASE_URL}/api/indexes/create", json=config)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, {"error": str(e)}


def delete_index(index_name: str):
    """Delete an index."""
    try:
        response = requests.delete(
            f"{API_BASE_URL}/api/indexes/{index_name}",
            json={"index_name": index_name, "confirm": True}
        )
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, {"error": str(e)}


def start_index_ingestion(index_name: str, folder_path: str, file_patterns: List[str], recursive: bool, force_reprocess: bool):
    """Start ingestion for a specific index."""
    try:
        payload = {
            "index_name": index_name,
            "folder_path": folder_path,
            "recursive": recursive,
            "file_patterns": file_patterns,
            "force_reprocess": force_reprocess,
        }
        response = requests.post(f"{API_BASE_URL}/api/indexes/{index_name}/ingest", json=payload)
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


def query_knowledge_base(query: str, top_k: int = 5, index_name: Optional[str] = None, settings: Optional[dict] = None):
    """Query the knowledge base."""
    try:
        payload = {
            "query": query,
            "top_k": top_k,
        }
        if index_name:
            payload["index_name"] = index_name
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
    index_name: Optional[str] = None,
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
        if index_name:
            payload["index_name"] = index_name
        
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
    page_title="RAG Question Generator - Multi-Index",
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
    .index-card {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Title and header
st.title("📚 RAG Question Generator - Multi-Index")
st.markdown("Create and manage multiple knowledge bases with custom configurations")

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
            
            with st.expander("⚙️ Configuration"):
                st.text(f"Architecture: {stats['configuration'].get('architecture', 'v1')}")
                st.text(f"LLM: {stats['configuration']['llm_provider']}")
                st.text(f"Model: {stats['configuration']['llm_model']}")
    else:
        st.error("❌ API Not Connected")
        st.warning("Make sure the backend is running")

# Main tabs
tab1, tab2, tab3 = st.tabs(["📑 Indexes", "📁 Add Documents", "🔍 Query & Questions"])

# ========== TAB 1: Index Management ==========
with tab1:
    st.header("Index Management")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("Create and manage multiple knowledge base indexes")
    with col2:
        if st.button("🔄 Refresh Indexes"):
            st.rerun()
    
    # List existing indexes
    indexes_data = list_indexes()
    if indexes_data and indexes_data.get('indexes'):
        st.markdown("### Existing Indexes")
        
        for idx in indexes_data['indexes']:
            with st.container():
                st.markdown(f"""
                <div class='index-card'>
                    <h4>📊 {idx['index_name']}</h4>
                    <p><strong>Mode:</strong> {idx['retrieval_mode']} | <strong>Chunks:</strong> {idx['chunk_count']} | <strong>Docs:</strong> {idx['document_count']}</p>
                    <p><small>{idx.get('description', 'No description')}</small></p>
                </div>
                """, unsafe_allow_html=True)
                
                col_a, col_b = st.columns([4, 1])
                with col_b:
                    if st.button(f"🗑️ Delete", key=f"del_{idx['index_name']}"):
                        success, result = delete_index(idx['index_name'])
                        if success:
                            st.success(f"Deleted {idx['index_name']}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Error: {result.get('error', 'Unknown error')}")
    
    st.markdown("---")
    
    # Create new index form
    st.markdown("### Create New Index")
    
    with st.form("create_index_form"):
        st.markdown("#### INDEX CONFIGURATION")
        
        index_name = st.text_input(
            "Index Name",
            placeholder="physics_textbooks",
            help="Unique name for this index"
        )
        
        description = st.text_area(
            "Description (optional)",
            placeholder="Physics textbooks for undergraduate level",
            height=60
        )
        
        st.markdown("---")
        st.markdown("#### RETRIEVAL MODE")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            retrieval_mode = st.radio(
                "Mode",
                ["hybrid", "vector", "fts"],
                index=0,
                help="Hybrid combines semantic + keyword search"
            )
        
        st.markdown("---")
        st.markdown("#### CHUNKING SETTINGS")
        
        col1, col2 = st.columns(2)
        with col1:
            late_chunk_vectors = st.checkbox("Late-chunk vectors", value=True)
            chunk_size = st.number_input("Chunk size", min_value=100, max_value=4000, value=512)
        
        with col2:
            high_recall_chunking = st.checkbox("High-recall chunking", value=True)
            chunk_overlap = st.number_input("Chunk overlap", min_value=0, max_value=500, value=64)
        
        st.markdown("---")
        st.markdown("#### MODELS")
        
        col1, col2 = st.columns(2)
        with col1:
            embedding_model = st.selectbox(
                "Embedding model",
                [
                    "sentence-transformers/all-MiniLM-L6-v2",
                    "sentence-transformers/all-mpnet-base-v2",
                    "BAAI/bge-small-en-v1.5",
                    "Qwen/Qwen3-Embedding-0.6B",
                ],
                index=0
            )
        
        with col2:
            overview_llm = st.selectbox(
                "Overview LLM",
                ["qwen3:0.6b", "qwen2.5:7b", "llama3.2:3b", "None"],
                index=1
            )
        
        st.markdown("---")
        st.markdown("#### CONTEXTUAL RETRIEVAL")
        
        enable_contextual = st.checkbox("Enable", value=False)
        
        if enable_contextual:
            col1, col2 = st.columns(2)
            with col1:
                context_window = st.number_input("Context window", min_value=1, max_value=20, value=5)
            with col2:
                retrieval_llm = st.selectbox(
                    "Retrieval LLM",
                    ["qwen3:0.6b", "qwen2.5:7b", "llama3.2:3b"],
                    index=1
                )
        else:
            context_window = 5
            retrieval_llm = "qwen2.5:7b"
        
        st.markdown("---")
        st.markdown("#### BATCH SIZE")
        
        batch_size = st.number_input("Batch size", min_value=1, max_value=256, value=32)
        
        st.markdown("---")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            cancel_button = st.form_submit_button("Cancel", use_container_width=True)
        with col2:
            submit_button = st.form_submit_button("✨ Create Index", type="primary", use_container_width=True)
        
        if submit_button:
            if not index_name:
                st.error("Please enter an index name")
            else:
                config = {
                    "index_name": index_name,
                    "retrieval_mode": retrieval_mode,
                    "late_chunk_vectors": late_chunk_vectors,
                    "high_recall_chunking": high_recall_chunking,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                    "embedding_model": embedding_model,
                    "overview_llm": overview_llm if overview_llm != "None" else None,
                    "enable_contextual_retrieval": enable_contextual,
                    "context_window": context_window,
                    "retrieval_llm": retrieval_llm if enable_contextual else None,
                    "batch_size": batch_size,
                    "description": description if description else None,
                }
                
                success, result = create_index(config)
                if success:
                    st.success(f"✅ Index '{index_name}' created successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Failed to create index: {result.get('error', 'Unknown error')}")


# ========== TAB 2: Document Addition ==========
with tab2:
    st.header("Add Documents to Index")
    
    # Select index
    indexes_data = list_indexes()
    if not indexes_data or not indexes_data.get('indexes'):
        st.warning("⚠️ No indexes available. Please create an index first in the 'Indexes' tab.")
    else:
        index_names = [idx['index_name'] for idx in indexes_data['indexes']]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            selected_index = st.selectbox(
                "Select Index",
                index_names,
                help="Choose which index to add documents to"
            )
            
            # Folder path input
            folder_path = st.text_input(
                "Folder Path",
                placeholder="/mnt/c/Users/data/physics_books",
                help="Enter the path in WSL format: /mnt/c/..."
            )
            
            st.caption("💡 **WSL Path Format**: Windows `C:\\folder` → WSL `/mnt/c/folder`")
            
            # Options
            recursive = st.checkbox("Scan subdirectories recursively", value=True)
            force_reprocess = st.checkbox("Force reprocess existing documents", value=False)
            
            # File patterns
            st.markdown("**File Types to Process**")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                pdf = st.checkbox("PDF", value=True, key="pdf_add")
                html = st.checkbox("HTML", value=True, key="html_add")
            with col_b:
                docx = st.checkbox("DOCX", value=True, key="docx_add")
                md = st.checkbox("Markdown", value=True, key="md_add")
            with col_c:
                txt = st.checkbox("Text", value=True, key="txt_add")
                images = st.checkbox("Images", value=False, key="img_add")
            
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
                    wsl_path = convert_windows_to_wsl_path(folder_path)
                    if wsl_path != folder_path:
                        st.info(f"📍 Converted path: `{wsl_path}`")
                    
                    success, result = start_index_ingestion(
                        selected_index, wsl_path, file_patterns, recursive, force_reprocess
                    )
                    if success:
                        st.success(f"✅ Ingestion started for index '{selected_index}'!")
                    else:
                        st.error(f"Failed: {result.get('error', 'Unknown error')}")
        
        with col2:
            st.markdown("### 📊 Status")
            if st.button("🔄 Refresh", key="status_refresh"):
                st.rerun()
            
            ingestion_status = get_ingestion_status()
            if ingestion_status:
                if ingestion_status['is_running']:
                    st.warning("⏳ Running...")
                    total = ingestion_status['total_documents']
                    processed = ingestion_status['processed_documents']
                    skipped = ingestion_status.get('skipped_documents', 0)
                    pct = ingestion_status['progress_percentage']
                    
                    st.progress(min(pct / 100, 1.0))
                    st.caption(f"{processed + skipped}/{total} ({pct:.0f}%)")
                    
                    current = ingestion_status.get('current_document')
                    if current:
                        st.caption(f"📄 {Path(current).name}")
                else:
                    st.success("✅ Ready")
        
        # Live progress
        if ingestion_status and ingestion_status['is_running']:
            st.markdown("---")
            st.markdown("### ⏳ Ingestion in Progress")
            
            total = ingestion_status['total_documents']
            processed = ingestion_status['processed_documents']
            skipped = ingestion_status.get('skipped_documents', 0)
            failed = ingestion_status['failed_documents']
            done = processed + skipped
            pct = ingestion_status['progress_percentage']
            
            st.progress(min(pct / 100, 1.0))
            st.caption(f"**Progress:** {done} of {total} files ({pct:.1f}%)")
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total", total)
            m2.metric("✅ Processed", processed)
            m3.metric("⏭️ Skipped", skipped)
            m4.metric("❌ Failed", failed)


# ========== TAB 3: Query & Questions ==========
with tab3:
    st.header("🔍 Query & Generate Questions")
    
    # Select index for querying
    indexes_data = list_indexes()
    index_names = ["All Indexes"] + ([idx['index_name'] for idx in indexes_data['indexes']] if indexes_data and indexes_data.get('indexes') else [])
    
    selected_query_index = st.selectbox(
        "Search in Index",
        index_names,
        help="Choose which index to search (All = search all indexes)"
    )
    
    query_index = None if selected_query_index == "All Indexes" else selected_query_index
    
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
        
        # Query execution
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
                result = query_knowledge_base(query_text, top_k, query_index, query_settings)
                
                if result:
                    st.markdown("### Answer")
                    answer_text = render_latex_text(result['answer'])
                    st.markdown(f"<div class='success-box'>{answer_text}</div>", unsafe_allow_html=True)
                    
                    st.markdown(f"*Processing time: {result['processing_time']:.2f}s*")
                    
                    st.markdown("---")
                    st.markdown("### Retrieved Sources")
                    
                    for i, chunk in enumerate(result['retrieved_chunks'], 1):
                        content_type = chunk.get('content_type', 'unknown')
                        difficulty = chunk.get('difficulty', 'unknown')
                        
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
                placeholder="e.g., thermodynamics, calculus"
            )
        
        if st.button("✨ Generate Questions", type="primary", use_container_width=True):
            with st.spinner(f"Generating {num_questions} {difficulty} questions..."):
                result = generate_questions(
                    subject, difficulty, question_type, num_questions, topic or None, query_index
                )
                
                if result and result.get('questions'):
                    st.success(f"✅ Generated {len(result['questions'])} questions!")
                    
                    st.markdown(f"*Processing time: {result['processing_time']:.2f}s*")
                    
                    st.markdown("---")
                    for i, q in enumerate(result['questions'], 1):
                        st.markdown(f"### Question {i}")
                        
                        question_text = render_latex_text(q['question'])
                        st.markdown(question_text)
                        
                        if q.get('options'):
                            for opt in q['options']:
                                st.markdown(f"- {opt}")
                        
                        with st.expander("Show Answer"):
                            st.markdown(f"**Answer:** {q['correct_answer']}")
                            if q.get('explanation'):
                                st.markdown(f"**Explanation:** {q['explanation']}")

# Footer
st.markdown("---")
st.markdown("*Multi-Index RAG System | Powered by Hybrid Retrieval*")
