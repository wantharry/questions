"""
Enhanced Streamlit UI for the RAG Question Generator with Multiple Index Support.
Supports creating custom indexes, uploading files, and querying specific indexes.
"""
import os
import streamlit as st
import requests
import time
import re
import json
from pathlib import Path
from typing import Optional, List
import pandas as pd


# Configuration - use BACKEND_URL env var (set in Docker), fallback to localhost for local dev
API_BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8601")


# ---------------------------------------------------------------------------
# LaTeX rendering helpers
# ---------------------------------------------------------------------------

# Unicode superscript/subscript → LaTeX conversion tables
_UNICODE_SUPERSCRIPTS = {
    '⁰':'0','¹':'1','²':'2','³':'3','⁴':'4',
    '⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9',
    'ⁿ':'n','ⁱ':'i','⁺':'+','⁻':'-','⁼':'=','⁽':'(','⁾':')',
}
_UNICODE_SUBSCRIPTS = {
    '₀':'0','₁':'1','₂':'2','₃':'3','₄':'4',
    '₅':'5','₆':'6','₇':'7','₈':'8','₉':'9',
    '₊':'+','₋':'-','₌':'=','₍':'(','₎':')',
    'ₐ':'a','ₑ':'e','ₒ':'o','ₙ':'n','ₓ':'x',
}
_SUP_PAT = re.compile('[' + ''.join(re.escape(c) for c in _UNICODE_SUPERSCRIPTS) + ']+')
_SUB_PAT = re.compile('[' + ''.join(re.escape(c) for c in _UNICODE_SUBSCRIPTS) + ']+')

# Build codepoint → ASCII map for Unicode mathematical alphanumeric letters
# (Mathematical Bold/Italic/Sans-Serif/Monospace/Double-Struck A-Z and a-z)
_MATH_ALPHA_MAP: dict = {}
for _start, _base in [
    (0x1D400, 65), (0x1D41A, 97),  # Bold A-Z, a-z
    (0x1D434, 65), (0x1D44E, 97),  # Italic A-Z, a-z
    (0x1D468, 65), (0x1D482, 97),  # Bold Italic A-Z, a-z
    (0x1D538, 65), (0x1D552, 97),  # Double-Struck A-Z, a-z
    (0x1D5A0, 65), (0x1D5BA, 97),  # Sans-Serif A-Z, a-z
    (0x1D5D4, 65), (0x1D5EE, 97),  # Bold Sans-Serif A-Z, a-z
    (0x1D608, 65), (0x1D622, 97),  # Italic Sans-Serif A-Z, a-z
    (0x1D670, 65), (0x1D68A, 97),  # Monospace A-Z, a-z
]:
    for _i in range(26):
        _MATH_ALPHA_MAP[_start + _i] = chr(_base + _i)

# Unicode mathematical digits 0-9 (Bold, Double-Struck, Sans-Serif, etc.)
for _start in [0x1D7CE, 0x1D7D8, 0x1D7E2, 0x1D7EC, 0x1D7F6]:
    for _i in range(10):
        _MATH_ALPHA_MAP[_start + _i] = chr(48 + _i)


def _norm_unicode_math(text: str) -> str:
    """Remove invisible chars, normalize Unicode math letters and super/subscripts."""
    # 1. Strip zero-width and soft-hyphen/BOM invisible characters
    text = re.sub(r'[\u200b\u200c\u200d\u2060\u00ad\ufeff]', '', text)

    # 2. Convert Unicode mathematical letter variants → plain ASCII
    result = []
    for ch in text:
        cp = ord(ch)
        result.append(_MATH_ALPHA_MAP[cp] if cp in _MATH_ALPHA_MAP else ch)
    text = ''.join(result)

    # 3. Convert Unicode super/subscript characters to LaTeX ^ and _
    def _sup(m):
        v = ''.join(_UNICODE_SUPERSCRIPTS[c] for c in m.group())
        return f'^{{{v}}}' if len(v) > 1 else f'^{v}'

    def _sub(m):
        v = ''.join(_UNICODE_SUBSCRIPTS[c] for c in m.group())
        return f'_{{{v}}}' if len(v) > 1 else f'_{v}'

    text = _SUP_PAT.sub(_sup, text)
    text = _SUB_PAT.sub(_sub, text)
    return text


def _find_math_spans(text: str) -> list:
    """Return list of (start, end, is_math) spans for complete LaTeX expressions."""
    spans = []
    i = 0
    while i < len(text):
        if i < len(text) - 1 and text[i] == '\\' and text[i+1].isalpha():
            start = i
            j = i + 1
            while j < len(text):
                ch = text[j]
                if ch.isalnum() or ch in r'\{}[]()^_+-*/=<>,.| ' or ch.isspace():
                    j += 1
                else:
                    break
            end = j
            while end > start and text[end-1].isspace():
                end -= 1
            if '\\' in text[start:end]:
                spans.append((start, end, True))
                i = end
                continue
        i += 1

    result = []
    pos = 0
    for start, end, is_math in spans:
        if pos < start:
            result.append((pos, start, False))
        result.append((start, end, True))
        pos = end
    if pos < len(text):
        result.append((pos, len(text), False))
    return result if spans else [(0, len(text), False)]


def _wrap_exprs(text: str) -> str:
    """Wrap complete LaTeX math expressions with $ delimiters."""
    parts = []
    for start, end, is_math in _find_math_spans(text):
        seg = text[start:end]
        parts.append(f'${seg}$' if is_math else seg)
    return ''.join(parts)


def _delimit_line(line: str) -> str:
    """Add $ delimiters to bare LaTeX commands in a single line."""
    if not re.search(r'\\[a-zA-Z]', line):
        return line
    parts = re.split(r'(\$\$[^$]*?\$\$|\$[^$\n]+?\$)', line)
    out = []
    for i, seg in enumerate(parts):
        if i % 2 == 1:
            out.append(seg)
        elif re.search(r'\\[a-zA-Z]', seg):
            out.append(_wrap_exprs(seg))
        else:
            out.append(seg)
    return ''.join(out)


def render_latex_text(text: str) -> str:
    r"""Normalise LLM output so Streamlit/KaTeX renders all math correctly."""
    if not text:
        return text

    # ------------------------------------------------------------------
    # Step 1: Unicode normalization
    #   - Remove zero-width/invisible chars (U+200B etc.)
    #   - Convert Unicode math letter variants (𝑚𝑜𝑑 → mod)
    #   - Convert Unicode superscripts (² → ^2) and subscripts (₂ → _2)
    # ------------------------------------------------------------------
    text = _norm_unicode_math(text)

    # ------------------------------------------------------------------
    # Step 2: Restore control characters that JSON parsing corrupts.
    #   json.loads() treats \f \b \r \t \n as escape sequences, silently
    #   converting \frac → (form-feed)rac, \beta → (backspace)eta, etc.
    # ------------------------------------------------------------------
    text = re.sub(r'\x0c([a-zA-Z])', r'\\f\1', text)  # \frac, \forall …
    text = re.sub(r'\x08([a-zA-Z])', r'\\b\1', text)  # \beta, \bar …
    text = re.sub(r'\x0d([a-zA-Z])', r'\\r\1', text)  # \rho, \right …
    text = re.sub(r'\x09(au|heta|imes|ilde|o\b|ext|op\b)', r'\\t\1', text)
    text = re.sub(r'\n(abla|eq\b|ot\b|u\b)', r'\\n\1', text)

    # ------------------------------------------------------------------
    # Step 3: Fix misplaced $ delimiters.
    #   LLMs sometimes write  ($\sqrt{5})^2  where the ( is outside $.
    #   We swap: ($\ → $(\  so the paren is included in math mode.
    # ------------------------------------------------------------------
    text = re.sub(r'([(])(\$+)(\\)', r'\2\1\3', text)

    # ------------------------------------------------------------------
    # Step 4: Convert explicit LaTeX block/inline delimiters
    # ------------------------------------------------------------------
    text = re.sub(r'\\\[(.+?)\\\]', r'$$\1$$', text, flags=re.DOTALL)
    text = re.sub(r'\\\((.+?)\\\)', r'$\1$',   text, flags=re.DOTALL)

    # ------------------------------------------------------------------
    # Step 5: Auto-delimit bare LaTeX commands, line by line
    # ------------------------------------------------------------------
    return '\n'.join(_delimit_line(line) for line in text.split('\n'))


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
    llm_model: Optional[str] = None,
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
        if llm_model:
            payload["settings"] = {"retrieval_llm": llm_model}
        
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


# ──────────────────────────────────────────────────────────────────
# Index Creation Presets – best defaults for common use cases
# ──────────────────────────────────────────────────────────────────
INDEX_PRESETS = {
    "📚 Academic": {
        "label": "Textbooks, lecture notes, course materials",
        "retrieval_mode": "hybrid",
        "use_classification": False,
        "chunk_size": 800,
        "chunk_overlap": 100,
        "high_recall_chunking": True,
        "late_chunk_vectors": True,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "overview_llm": "None",
        "enable_contextual_retrieval": False,
        "context_window": 5,
        "retrieval_llm": "qwen2.5:7b",
        "batch_size": 32,
    },
    "📄 General": {
        "label": "PDFs, reports, mixed documents",
        "retrieval_mode": "hybrid",
        "use_classification": False,
        "chunk_size": 512,
        "chunk_overlap": 64,
        "high_recall_chunking": True,
        "late_chunk_vectors": True,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "overview_llm": "None",
        "enable_contextual_retrieval": False,
        "context_window": 5,
        "retrieval_llm": "qwen2.5:7b",
        "batch_size": 32,
    },
    "🔬 Research": {
        "label": "Academic papers, articles, technical reports",
        "retrieval_mode": "hybrid",
        "use_classification": False,
        "chunk_size": 1000,
        "chunk_overlap": 150,
        "high_recall_chunking": True,
        "late_chunk_vectors": True,
        "embedding_model": "sentence-transformers/all-mpnet-base-v2",
        "overview_llm": "None",
        "enable_contextual_retrieval": False,
        "context_window": 5,
        "retrieval_llm": "qwen2.5:7b",
        "batch_size": 16,
    },
    "⚡ Quick": {
        "label": "Fast indexing for quick prototyping",
        "retrieval_mode": "vector",
        "use_classification": False,
        "chunk_size": 256,
        "chunk_overlap": 32,
        "high_recall_chunking": False,
        "late_chunk_vectors": False,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "overview_llm": "None",
        "enable_contextual_retrieval": False,
        "context_window": 5,
        "retrieval_llm": "qwen2.5:7b",
        "batch_size": 64,
    },
}
_DEFAULT_PRESET = "📚 Academic"


def _init_ci_state():
    """Initialise session-state keys for the Create-Index form (first run only)."""
    preset = INDEX_PRESETS[_DEFAULT_PRESET]
    defaults = {
        "ci_preset":             _DEFAULT_PRESET,
        "ci_retrieval_mode":     preset["retrieval_mode"],
        "ci_use_classification": preset["use_classification"],
        "ci_chunk_size":         preset["chunk_size"],
        "ci_chunk_overlap":      preset["chunk_overlap"],
        "ci_high_recall":        preset["high_recall_chunking"],
        "ci_late_chunk":         preset["late_chunk_vectors"],
        "ci_embedding_model":    preset["embedding_model"],
        "ci_overview_llm":       preset["overview_llm"],
        "ci_enable_contextual":  preset["enable_contextual_retrieval"],
        "ci_context_window":     preset["context_window"],
        "ci_retrieval_llm":      preset["retrieval_llm"],
        "ci_batch_size":         preset["batch_size"],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# Page configuration
st.set_page_config(
    page_title="RAG Question Generator - Multi-Index",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS
st.markdown("""
<style>
    /* ── Layout ── */
    .main .block-container { padding-top: 1.5rem; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #f1f5f9;
        border-radius: 10px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        padding-left: 20px;
        padding-right: 20px;
        border-radius: 8px;
        font-weight: 500;
        font-size: 0.9rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.12);
    }

    /* ── Index cards ── */
    .index-card {
        padding: 1rem 1.25rem;
        border-radius: 12px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        margin-bottom: 0.7rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ── Config summary card ── */
    .config-summary {
        background: linear-gradient(135deg, #eff6ff 0%, #f0f4ff 100%);
        border: 1px solid #c7d4f7;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        line-height: 1.9;
        margin-bottom: 1rem;
    }
    .config-summary .cs-title {
        font-size: 1rem;
        font-weight: 700;
        color: #1e3a8a;
        margin-bottom: 0.5rem;
    }
    .config-summary .cs-row {
        font-size: 0.875rem;
        color: #334155;
    }
    .config-summary .cs-foot {
        font-size: 0.78rem;
        color: #64748b;
        margin-top: 0.6rem;
        padding-top: 0.5rem;
        border-top: 1px solid #dbe4f7;
    }

    /* ── Success / info boxes ── */
    .success-box {
        padding: 1.2rem 1.4rem;
        border-radius: 10px;
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        color: #166534;
        line-height: 1.7;
    }
    .info-box {
        padding: 1.2rem 1.4rem;
        border-radius: 10px;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e40af;
    }

    /* ── Metric cards ── */
    div[data-testid="metric-container"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.6rem 0.8rem;
    }

    /* ── Divider ── */
    hr { border-color: #e2e8f0; margin: 1rem 0; }

    /* ── Section headers ── */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.25rem;
    }
    .section-sub {
        font-size: 0.85rem;
        color: #64748b;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialise Create-Index session state on every rerun (no-op after first run)
_init_ci_state()

# Title and header
_title_col, _status_col = st.columns([5, 1])
with _title_col:
    st.title("📚 RAG Question Generator")
    st.caption("Create and manage multiple knowledge bases · Powered by hybrid retrieval")
with _status_col:
    if check_api_health():
        st.success("🟢 Backend connected")
    else:
        st.error("🔴 Backend offline")

# No sidebar content

# Main tabs
tab1, tab2, tab3 = st.tabs(["📑 Indexes", "📁 Add Documents", "🔍 Query & Questions"])

# ========== TAB 1: Index Management ==========
with tab1:

    col_create, col_indexes = st.columns([12, 9], gap="large")

    # ─────────────────────────────────────────────────────────────
    # LEFT: Create New Index
    # ─────────────────────────────────────────────────────────────
    with col_create:
        st.markdown("<div class='section-header'>✨ Create New Index</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-sub'>Pick a profile, name your index, then hit Create. Advanced settings are pre-configured for best results.</div>", unsafe_allow_html=True)

        ci_name = st.text_input(
            "Index Name *",
            placeholder="e.g. physics_textbooks",
            help="Lowercase letters, numbers, and underscores only",
            key="ci_name_field",
        )
        ci_desc = st.text_input(
            "Description",
            placeholder="Optional — e.g. Undergraduate physics course materials",
            key="ci_desc_field",
        )

        st.markdown("**Profile** — choose what best matches your documents")
        p_cols = st.columns(len(INDEX_PRESETS))
        for _pi, (_pname, _pdata) in enumerate(INDEX_PRESETS.items()):
            with p_cols[_pi]:
                _is_active = (st.session_state.ci_preset == _pname)
                if st.button(
                    _pname,
                    key=f"ci_preset_btn_{_pi}",
                    use_container_width=True,
                    type="primary" if _is_active else "secondary",
                    help=_pdata["label"],
                ):
                    st.session_state.ci_preset = _pname
                    for _field, _ss_key in [
                        ("retrieval_mode",              "ci_retrieval_mode"),
                        ("use_classification",          "ci_use_classification"),
                        ("chunk_size",                  "ci_chunk_size"),
                        ("chunk_overlap",               "ci_chunk_overlap"),
                        ("high_recall_chunking",        "ci_high_recall"),
                        ("late_chunk_vectors",          "ci_late_chunk"),
                        ("embedding_model",             "ci_embedding_model"),
                        ("overview_llm",                "ci_overview_llm"),
                        ("enable_contextual_retrieval", "ci_enable_contextual"),
                        ("context_window",              "ci_context_window"),
                        ("retrieval_llm",               "ci_retrieval_llm"),
                        ("batch_size",                  "ci_batch_size"),
                    ]:
                        st.session_state[_ss_key] = _pdata[_field]
                    st.rerun()

        st.caption(f"ℹ️ *{INDEX_PRESETS[st.session_state.ci_preset]['label']}*")

        with st.expander("⚙️ Advanced Settings", expanded=False):
            st.caption("Auto-configured from the profile above. Tweak only if needed.")

            _mode_opts = ["hybrid", "vector", "fts"]
            _mode_labels = {"hybrid": "Hybrid — best results", "vector": "Semantic only", "fts": "Keyword only"}
            st.radio(
                "Retrieval Mode",
                _mode_opts,
                format_func=lambda x: _mode_labels[x],
                horizontal=True,
                key="ci_retrieval_mode",
            )
            
            st.checkbox(
                "📊 Enable Content Classification",
                key="ci_use_classification",
                help="Split content by type (theory/formula/exercise). Disable for unified single-index mode (recommended for custom collections)."
            )

            _adv1, _adv2 = st.columns(2)
            with _adv1:
                st.number_input("Chunk Size", min_value=100, max_value=4000, step=50, key="ci_chunk_size")
                st.checkbox("Late-chunk Vectors", key="ci_late_chunk",
                            help="Embed chunks with surrounding context for richer vectors")
            with _adv2:
                st.number_input("Chunk Overlap", min_value=0, max_value=500, step=10, key="ci_chunk_overlap")
                st.checkbox("High-recall Chunking", key="ci_high_recall",
                            help="Smaller sub-chunks for finer-grained retrieval")

            _emb_opts = [
                "sentence-transformers/all-MiniLM-L6-v2",
                "sentence-transformers/all-mpnet-base-v2",
                "BAAI/bge-small-en-v1.5",
            ]
            st.selectbox("Embedding Model", _emb_opts, key="ci_embedding_model")

            _adv3, _adv4 = st.columns(2)
            with _adv3:
                st.number_input("Batch Size", min_value=1, max_value=256, key="ci_batch_size")
            with _adv4:
                _llm_opts = ["None", "qwen3:0.6b", "qwen2.5:7b", "llama3.2:3b"]
                st.selectbox("Overview LLM", _llm_opts, key="ci_overview_llm",
                             help="LLM used to generate paragraph overviews during ingestion")

            st.checkbox("Enable Contextual Retrieval", key="ci_enable_contextual",
                        help="Prepend chunk context summaries for improved relevance")
            if st.session_state.ci_enable_contextual:
                _adv5, _adv6 = st.columns(2)
                with _adv5:
                    st.number_input("Context Window", min_value=1, max_value=20, key="ci_context_window")
                with _adv6:
                    _ctx_llm_opts = ["qwen2.5:7b", "qwen3:0.6b", "llama3.2:3b"]
                    st.selectbox("Contextual LLM", _ctx_llm_opts, key="ci_retrieval_llm")

        # Config summary pill row
        _rm = st.session_state.ci_retrieval_mode
        _rm_emoji = {"hybrid": "🔀", "vector": "🧠", "fts": "🔍"}.get(_rm, "🔀")
        _emb_short = st.session_state.ci_embedding_model.split("/")[-1]
        _hr_icon = "✅" if st.session_state.ci_high_recall else "—"
        _lc_icon = "✅" if st.session_state.ci_late_chunk  else "—"
        st.markdown(
            f"""<div class="config-summary">
  <div class="cs-title">{st.session_state.ci_preset}</div>
  <div class="cs-row">{_rm_emoji} <b>Retrieval:</b> {_rm.capitalize()} &nbsp;·&nbsp;
     📦 <b>Chunk:</b> {st.session_state.ci_chunk_size} / {st.session_state.ci_chunk_overlap} overlap &nbsp;·&nbsp;
     🔬 High-recall: {_hr_icon} &nbsp;·&nbsp; ⚡ Late-chunk: {_lc_icon}</div>
  <div class="cs-foot">🤖 {_emb_short} &nbsp;·&nbsp; batch {st.session_state.ci_batch_size}</div>
</div>""",
            unsafe_allow_html=True,
        )

        if st.button("✨ Create Index", type="primary", use_container_width=True, key="ci_create_btn"):
            _ci_name_val = st.session_state.get("ci_name_field", "").strip()
            _ci_desc_val = st.session_state.get("ci_desc_field", "").strip()
            if not _ci_name_val:
                st.error("Please enter an Index Name.")
            else:
                _config = {
                    "index_name":                  _ci_name_val,
                    "description":                 _ci_desc_val or None,
                    "retrieval_mode":              st.session_state.ci_retrieval_mode,
                    "use_classification":          st.session_state.ci_use_classification,
                    "chunk_size":                  st.session_state.ci_chunk_size,
                    "chunk_overlap":               st.session_state.ci_chunk_overlap,
                    "high_recall_chunking":        st.session_state.ci_high_recall,
                    "late_chunk_vectors":          st.session_state.ci_late_chunk,
                    "embedding_model":             st.session_state.ci_embedding_model,
                    "overview_llm":                st.session_state.ci_overview_llm if st.session_state.ci_overview_llm != "None" else None,
                    "enable_contextual_retrieval": st.session_state.ci_enable_contextual,
                    "context_window":              st.session_state.ci_context_window,
                    "retrieval_llm":               st.session_state.ci_retrieval_llm if st.session_state.ci_enable_contextual else None,
                    "batch_size":                  st.session_state.ci_batch_size,
                }
                _success, _result = create_index(_config)
                if _success:
                    st.success(f"✅ Index '{_ci_name_val}' created!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Failed: {_result.get('error', 'Unknown error')}")

    # ─────────────────────────────────────────────────────────────
    # RIGHT: Existing Indexes
    # ─────────────────────────────────────────────────────────────
    with col_indexes:
        _idx_hdr, _idx_btn = st.columns([3, 1])
        with _idx_hdr:
            st.markdown("<div class='section-header'>📂 Your Indexes</div>", unsafe_allow_html=True)
        with _idx_btn:
            if st.button("🔄", help="Refresh list", key="refresh_indexes"):
                st.rerun()

        indexes_data = list_indexes()
        if not indexes_data or not indexes_data.get("indexes"):
            st.markdown(
                "<div class='info-box'>No indexes yet. Create your first one on the left.</div>",
                unsafe_allow_html=True,
            )
        else:
            _mode_badge = {"hybrid": "🔀 Hybrid", "vector": "🧠 Semantic", "fts": "🔍 Keyword"}
            for idx in indexes_data["indexes"]:
                _badge = _mode_badge.get(idx["retrieval_mode"], idx["retrieval_mode"])
                st.markdown(
                    f"""<div class='index-card'>
  <div style='display:flex;justify-content:space-between;align-items:flex-start'>
    <div><b>📊 {idx['index_name']}</b></div>
    <div style='font-size:0.78rem;color:#64748b'>{_badge}</div>
  </div>
  <div style='font-size:0.82rem;color:#475569;margin-top:4px'>
    {idx['chunk_count']:,} chunks &nbsp;·&nbsp; {idx['document_count']} docs
  </div>
  <div style='font-size:0.78rem;color:#94a3b8;margin-top:2px'>{idx.get('description') or '—'}</div>
</div>""",
                    unsafe_allow_html=True,
                )
                _BUILTIN_INDEXES = {"theory", "formula", "exercise", "solution", "general"}
                if idx['index_name'] in _BUILTIN_INDEXES:
                    st.caption("🔒 Built-in index — cannot be deleted")
                else:
                    if st.button(f"🗑️ Delete {idx['index_name']}", key=f"del_{idx['index_name']}", use_container_width=True):
                        _del_ok, _del_res = delete_index(idx["index_name"])
                        if _del_ok:
                            st.success(f"Deleted {idx['index_name']}")
                            time.sleep(0.8)
                            st.rerun()
                        else:
                            st.error(_del_res.get("error", "Unknown error"))


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
        
        # Live progress — auto-refresh every 2 seconds while ingestion is running
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
            
            # Auto-refresh every 2 seconds
            time.sleep(2)
            st.rerun()


# ========== TAB 3: Query & Questions ==========
with tab3:
    st.header("🔍 Query & Generate Questions")
    
    # Select index for querying
    indexes_data = list_indexes()
    indexes_list = indexes_data['indexes'] if indexes_data and indexes_data.get('indexes') else []
    index_names = ["All Indexes"] + [idx['index_name'] for idx in indexes_list]

    col_idx_sel, col_idx_info = st.columns([3, 2])
    with col_idx_sel:
        selected_query_index = st.selectbox(
            "Search in Index",
            index_names,
            help="Choose which index to search (All = search all indexes)"
        )
    with col_idx_info:
        if selected_query_index == "All Indexes":
            total_docs = sum(idx.get('document_count', 0) for idx in indexes_list)
            total_chunks = sum(idx.get('chunk_count', 0) for idx in indexes_list)
            st.metric("Total docs (all indexes)", f"{total_docs:,}")
            st.metric("Total chunks", f"{total_chunks:,}")
        else:
            sel_idx = next((idx for idx in indexes_list if idx['index_name'] == selected_query_index), None)
            if sel_idx:
                st.metric("Documents in index", f"{sel_idx.get('document_count', 0):,}")
                st.metric("Chunks", f"{sel_idx.get('chunk_count', 0):,}")

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

        # Model selection — always visible
        query_model = st.selectbox(
            "🤖 Model",
            ["qwen2.5:7b", "qwen3:0.6b", "llama3.2:3b", "Default"],
            index=0,
            key="query_model",
            help="LLM used to generate the answer"
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
                retrieval_llm = query_model  # use the top-level selector
                st.caption(f"Model: **{query_model}**")
            
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
                    st.markdown(answer_text)
                    st.caption(f"Processing time: {result['processing_time']:.2f}s")
                    
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
                            chunk_text = render_latex_text(chunk['content'])
                            st.markdown(chunk_text)
    
    # Sub-tab 2: Generate Questions
    with subtab2:
        st.markdown("Generate practice questions from your knowledge base")

        # Model selection — always visible
        gen_model = st.selectbox(
            "🤖 Model",
            ["qwen2.5:7b", "qwen3:0.6b", "llama3.2:3b", "Default"],
            index=0,
            key="gen_model",
            help="LLM used to generate questions"
        )

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
                    subject, difficulty, question_type, num_questions, topic or None, query_index,
                    llm_model=gen_model if gen_model != "Default" else None
                )
                
                if result and result.get('questions'):
                    st.success(f"✅ Generated {len(result['questions'])} questions!")
                    
                    st.markdown(f"*Processing time: {result['processing_time']:.2f}s*")
                    
                    st.markdown("---")
                    for i, q in enumerate(result['questions'], 1):
                        with st.container(border=True):
                            st.markdown(f"**Question {i}**")
                            question_text = render_latex_text(q['question'])
                            st.markdown(question_text)

                            if q.get('options'):
                                for opt in q['options']:
                                    st.markdown(render_latex_text(f"- {opt}"))

                            with st.expander("Show Answer"):
                                ans_text = render_latex_text(str(q['correct_answer']))
                                st.markdown(f"**Answer:** {ans_text}")
                                if q.get('explanation'):
                                    exp_text = render_latex_text(q['explanation'])
                                    st.markdown(f"**Explanation:** {exp_text}")

# Footer
st.markdown("---")
st.markdown("*Multi-Index RAG System | Powered by Hybrid Retrieval*")
