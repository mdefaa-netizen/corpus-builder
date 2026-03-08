"""
CB-01 — Corpus Builder v2
ALG-PIVOT · Mohamed Defaa · Capitol Technology University
Trilingual corpus ingestion, annotation, and export for dissertation research.
"""

import os
import sqlite3
import hashlib
import hmac
import re
import io
import csv
import datetime
import time
import streamlit as st

# ── Optional heavy imports ────────────────────────────────────────────────────
try:
    import requests
    from bs4 import BeautifulSoup
    SCRAPE_AVAILABLE = True
except ImportError:
    SCRAPE_AVAILABLE = False

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    try:
        import PyPDF2
        PDF_AVAILABLE = True
        PDFPLUMBER = False
    except ImportError:
        PDF_AVAILABLE = False

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

APP_PASSWORD = os.environ.get("CB01_PASSWORD", "algpivot2026")

DB_PATH = os.environ.get("CB01_DB_PATH",
    "/data/corpus.db" if os.path.isdir("/data") else "corpus.db"
)

INSTITUTIONS = {
    "Brookings": {"code": "Brookings", "source_type": "think_tank", "ideology": "liberal_multilateral"},
    "CAP":       {"code": "CAP",       "source_type": "think_tank", "ideology": "liberal_multilateral"},
    "Carnegie":  {"code": "Carnegie",  "source_type": "think_tank", "ideology": "liberal_multilateral"},
    "Heritage":  {"code": "Heritage",  "source_type": "think_tank", "ideology": "conservative_hawkish"},
    "AEI":       {"code": "AEI",       "source_type": "think_tank", "ideology": "conservative_hawkish"},
    "Hudson":    {"code": "Hudson",    "source_type": "think_tank", "ideology": "conservative_hawkish"},
    "FDD":       {"code": "FDD",       "source_type": "think_tank", "ideology": "conservative_hawkish"},
    "Quincy":    {"code": "Quincy",    "source_type": "think_tank", "ideology": "restraint"},
    "AtlanticC": {"code": "AtlanticC", "source_type": "think_tank", "ideology": "liberal_multilateral"},
    "Wilson":    {"code": "Wilson",    "source_type": "think_tank", "ideology": "liberal_multilateral"},
    "Other":     {"code": "Other",     "source_type": "other",      "ideology": "NA"},
}

EPISODES   = ["Syrian_Transition", "Normalization_Quadrad", "Reconstruction"]
LANGUAGES  = {"English": "en", "Arabic": "ar", "French": "fr"}
DOC_TYPES  = ["policy_brief", "research_report", "testimony", "working_paper", "government_document", "other"]
IDEOLOGIES = ["liberal_multilateral", "conservative_hawkish", "restraint", "NA"]
SOURCE_TYPES = ["think_tank", "government", "ngo", "academic", "media", "intl_org", "other"]

# ═══════════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM  (ALG-PIVOT canonical palette + IBM Plex)
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

/* ── Root ── */
:root {
    --bg:      #0d1117;
    --surface: #161b22;
    --border:  #30363d;
    --accent:  #58a6ff;
    --accent2: #3fb950;
    --warn:    #d29922;
    --danger:  #f85149;
    --text:    #e6edf3;
    --muted:   #8b949e;
    --mono:    'IBM Plex Mono', monospace;
    --sans:    'IBM Plex Sans', sans-serif;
}

/* ── Global ── */
html, body, [class*="css"] {
    font-family: var(--sans) !important;
    color: var(--text) !important;
    background-color: var(--bg) !important;
}

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; padding-bottom: 4rem; }

/* ── Headings ── */
h1, h2, h3 { font-family: var(--mono) !important; letter-spacing: -0.02em; }
h1 { color: var(--accent) !important; font-size: 1.4rem !important; }
h2 { color: var(--text) !important;   font-size: 1.1rem !important; border-bottom: 1px solid var(--border); padding-bottom: 0.4rem; margin-top: 1.5rem; }
h3 { color: var(--muted) !important;  font-size: 0.9rem !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }

/* ── Inputs — the critical fix ── */
input, textarea, select,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input,
.stTextInput input,
.stTextArea textarea {
    background-color: var(--surface) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    font-family: var(--sans) !important;
}

input:focus, textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(88,166,255,0.15) !important;
    outline: none !important;
}

/* ── Selectbox / Dropdown — THE KEY FIX ── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[role="listbox"],
[data-testid="stSelectbox"] div[role="option"],
[data-testid="stMultiSelect"] > div > div,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
.stSelectbox div[data-baseweb="select"] div,
div[data-baseweb="select"] {
    background-color: var(--surface) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
}

/* Dropdown menu popup */
div[data-baseweb="popover"],
div[data-baseweb="popover"] *,
ul[data-testid="stSelectboxVirtualDropdown"],
ul[data-testid="stSelectboxVirtualDropdown"] li,
div[role="listbox"],
div[role="listbox"] div,
div[role="option"],
li[role="option"] {
    background-color: var(--surface) !important;
    color: var(--text) !important;
}

div[role="option"]:hover,
li[role="option"]:hover {
    background-color: var(--border) !important;
    color: var(--accent) !important;
}

/* Selected value text inside selectbox */
[data-testid="stSelectbox"] span,
[data-testid="stSelectbox"] p,
div[data-baseweb="select"] span {
    color: var(--text) !important;
}

/* ── Buttons ── */
.stButton > button {
    background-color: var(--surface) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
    border-radius: 4px !important;
    transition: border-color 0.15s, color 0.15s;
}
.stButton > button:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}
.stButton > button[kind="primary"] {
    background-color: var(--accent) !important;
    color: #0d1117 !important;
    border-color: var(--accent) !important;
    font-weight: 600 !important;
}

/* ── Download button ── */
[data-testid="stDownloadButton"] button {
    background-color: var(--accent2) !important;
    color: #0d1117 !important;
    border-color: var(--accent2) !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
}

/* ── Metrics ── */
[data-testid="metric-container"] {
    background-color: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    padding: 0.8rem !important;
}
[data-testid="metric-container"] label { color: var(--muted) !important; font-family: var(--mono) !important; font-size: 0.75rem !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: var(--accent) !important; font-family: var(--mono) !important; }

/* ── Dataframe ── */
[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: 4px; }

/* ── Alerts ── */
.stAlert { border-radius: 4px !important; }

/* ── Tabs ── */
[data-testid="stTab"] { font-family: var(--mono) !important; font-size: 0.8rem !important; }
button[data-baseweb="tab"] { color: var(--muted) !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--accent) !important; border-bottom-color: var(--accent) !important; }

/* ── Expander ── */
[data-testid="stExpander"] details {
    background-color: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}
[data-testid="stExpander"] summary { color: var(--muted) !important; font-family: var(--mono) !important; font-size: 0.8rem !important; }

/* ── Code / mono spans ── */
code { background-color: var(--border) !important; color: var(--accent) !important; padding: 0.1rem 0.3rem; border-radius: 3px; font-family: var(--mono) !important; }

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 1rem 0; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }

/* ── Doc card ── */
.doc-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.6rem;
    font-family: var(--mono);
    font-size: 0.78rem;
}
.doc-card .doc-id  { color: var(--accent); font-weight: 600; }
.doc-card .doc-meta { color: var(--muted); margin-top: 0.2rem; }
.doc-card .doc-score { color: var(--accent2); }

/* ── Status badge ── */
.badge {
    display: inline-block;
    padding: 0.1rem 0.5rem;
    border-radius: 12px;
    font-family: var(--mono);
    font-size: 0.7rem;
    font-weight: 600;
    margin-left: 0.4rem;
}
.badge-en  { background: rgba(88,166,255,0.15); color: #58a6ff; }
.badge-ar  { background: rgba(210,153,34,0.15);  color: #d29922; }
.badge-fr  { background: rgba(63,185,80,0.15);   color: #3fb950; }
.badge-lib { background: rgba(63,185,80,0.15);   color: #3fb950; }
.badge-con { background: rgba(248,81,73,0.15);   color: #f85149; }
.badge-res { background: rgba(88,166,255,0.15);  color: #58a6ff; }
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id          TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            institution     TEXT NOT NULL,
            source_type     TEXT NOT NULL,
            ideology_tag    TEXT NOT NULL,
            language        TEXT NOT NULL,
            pub_date        TEXT NOT NULL,
            doc_type        TEXT NOT NULL,
            episode         TEXT NOT NULL,
            url             TEXT,
            ai_status       TEXT DEFAULT 'unknown',
            word_count      INTEGER,
            full_text       TEXT NOT NULL,
            -- Flattening rubric
            agency_shift    INTEGER DEFAULT NULL,
            uncert_deletion INTEGER DEFAULT NULL,
            temp_compress   INTEGER DEFAULT NULL,
            sec_reclass     INTEGER DEFAULT NULL,
            flat_total      INTEGER DEFAULT NULL,
            rater_1         TEXT DEFAULT NULL,
            rater_2         TEXT DEFAULT NULL,
            notes           TEXT,
            created_at      TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def doc_exists(doc_id: str) -> bool:
    conn = get_db()
    row = conn.execute("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
    conn.close()
    return row is not None

def insert_doc(data: dict) -> None:
    conn = get_db()
    conn.execute("""
        INSERT INTO documents
        (doc_id, title, institution, source_type, ideology_tag, language,
         pub_date, doc_type, episode, url, ai_status, word_count, full_text,
         agency_shift, uncert_deletion, temp_compress, sec_reclass,
         flat_total, rater_1, rater_2, notes, created_at)
        VALUES
        (:doc_id,:title,:institution,:source_type,:ideology_tag,:language,
         :pub_date,:doc_type,:episode,:url,:ai_status,:word_count,:full_text,
         :agency_shift,:uncert_deletion,:temp_compress,:sec_reclass,
         :flat_total,:rater_1,:rater_2,:notes,:created_at)
    """, data)
    conn.commit()
    conn.close()

def update_annotation(doc_id, d1, d2, d3, d4, rater, notes):
    total = (d1 or 0) + (d2 or 0) + (d3 or 0) + (d4 or 0)
    conn = get_db()
    conn.execute("""
        UPDATE documents SET
            agency_shift=?, uncert_deletion=?, temp_compress=?, sec_reclass=?,
            flat_total=?, rater_1=?, notes=?
        WHERE doc_id=?
    """, (d1, d2, d3, d4, total, rater, notes, doc_id))
    conn.commit()
    conn.close()

def get_all_docs():
    conn = get_db()
    rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_db()
    total  = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    by_lang= conn.execute("SELECT language, COUNT(*) n FROM documents GROUP BY language").fetchall()
    by_ep  = conn.execute("SELECT episode, COUNT(*) n FROM documents GROUP BY episode").fetchall()
    by_ideo= conn.execute("SELECT ideology_tag, COUNT(*) n FROM documents GROUP BY ideology_tag").fetchall()
    annotated = conn.execute("SELECT COUNT(*) FROM documents WHERE flat_total IS NOT NULL").fetchone()[0]
    conn.close()
    return {"total": total, "by_lang": by_lang, "by_ep": by_ep,
            "by_ideo": by_ideo, "annotated": annotated}

def delete_doc(doc_id):
    conn = get_db()
    conn.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def check_password(pw: str) -> bool:
    correct = APP_PASSWORD.encode()
    return hmac.compare_digest(hashlib.sha256(pw.encode()).digest(),
                               hashlib.sha256(correct).digest())

def word_count(text: str) -> int:
    return len(re.findall(r'\S+', text))

def generate_doc_id(inst_code, pub_date, lang, seq=None):
    """Format: InstitutionCode_YYYYMM_lang_###"""
    ym = pub_date.replace("-", "")[:6]
    if seq is None:
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE doc_id LIKE ?",
            (f"{inst_code}_{ym}_{lang}_%",)
        ).fetchone()[0]
        conn.close()
        seq = count + 1
    return f"{inst_code}_{ym}_{lang}_{seq:03d}"

def extract_pdf(file_bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception as e:
            return f"[PDF extraction failed: {e}]"

def extract_docx(file_bytes) -> str:
    try:
        from docx import Document as DocxDoc
        doc = DocxDoc(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        return f"[DOCX extraction failed: {e}]"

def scrape_url(url: str) -> str:
    if not SCRAPE_AVAILABLE:
        return "[requests/beautifulsoup4 not installed]"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (research-bot ALG-PIVOT)"}
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script","style","nav","footer","header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        return f"[Scrape failed: {e}]"

def validate_doc(data: dict) -> tuple[list, list]:
    """Returns (hard_errors, soft_warnings)."""
    errors, warnings = [], []
    if not data.get("doc_id"):
        errors.append("Missing doc_id")
    elif doc_exists(data["doc_id"]):
        errors.append(f"Duplicate doc_id: {data['doc_id']}")
    if not data.get("pub_date") or not re.match(r"\d{4}-\d{2}-\d{2}", data["pub_date"]):
        errors.append("Missing or malformatted pub_date (YYYY-MM-DD)")
    if data.get("language") not in ("en","ar","fr"):
        errors.append("Invalid language code (must be en / ar / fr)")
    if not data.get("source_type"):
        errors.append("Missing source_type")
    if data.get("ideology_tag") not in IDEOLOGIES:
        errors.append("Invalid ideology_tag")
    if data.get("source_type") in ("gov_agency","intl_org") and data.get("ideology_tag") != "NA":
        errors.append("gov_agency / intl_org sources must have ideology_tag = NA")
    wc = word_count(data.get("full_text",""))
    if wc < 500:
        if wc < 150:
            errors.append(f"Text too short: {wc} words (minimum 500 for inclusion; hard block at 150)")
        else:
            warnings.append(f"Text is {wc} words (below 500-word inclusion minimum — flagged)")
    if not data.get("url"):
        warnings.append("No URL provided")
    return errors, warnings

def docs_to_csv(docs: list) -> str:
    if not docs:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(docs[0].keys()))
    writer.writeheader()
    writer.writerows(docs)
    return buf.getvalue()

def docs_to_marc_context(docs: list) -> str:
    out = []
    for d in docs[:30]:
        snippet = (d.get("full_text") or "")[:400].replace("\n"," ")
        out.append(
            f"[{d['doc_id']}] {d['institution']} | {d['language'].upper()} | "
            f"{d['episode']} | {d['ideology_tag']}\n"
            f"Title: {d['title']}\n"
            f"Text excerpt: {snippet}...\n"
        )
    return "\n---\n".join(out)

# ═══════════════════════════════════════════════════════════════════════════════
# AUTH GATE
# ═══════════════════════════════════════════════════════════════════════════════

def auth_gate():
    st.markdown(CSS, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<h1 style='text-align:center; font-size:1.1rem;'>CB-01 · Corpus Builder</h1>"
            "<p style='text-align:center; color:#8b949e; font-family:IBM Plex Mono,monospace; font-size:0.75rem;'>"
            "ALG-PIVOT · Mohamed Defaa · Capitol Technology University</p>",
            unsafe_allow_html=True
        )
        st.markdown("<br>", unsafe_allow_html=True)
        pw = st.text_input("Access key", type="password", placeholder="Enter password")
        if st.button("Authenticate", use_container_width=True):
            if check_password(pw):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: INGEST
# ═══════════════════════════════════════════════════════════════════════════════

def page_ingest():
    st.markdown("## ADD DOCUMENT")

    # ── Institution autofill ──────────────────────────────────────────────────
    inst_names = list(INSTITUTIONS.keys())
    inst_label = st.selectbox("Institution", inst_names, key="inst_sel")
    inst_data  = INSTITUTIONS[inst_label]

    col1, col2 = st.columns(2)
    with col1:
        source_type  = st.selectbox("Source type",  SOURCE_TYPES,
                                    index=SOURCE_TYPES.index(inst_data["source_type"]),
                                    key="src_type")
    with col2:
        ideology     = st.selectbox("Ideology tag", IDEOLOGIES,
                                    index=IDEOLOGIES.index(inst_data["ideology"]),
                                    key="ideology")

    col1, col2 = st.columns(2)
    with col1:
        lang_label   = st.selectbox("Language", list(LANGUAGES.keys()), key="lang")
        language     = LANGUAGES[lang_label]
    with col2:
        episode      = st.selectbox("Episode", EPISODES, key="episode")

    col1, col2 = st.columns(2)
    with col1:
        pub_date     = st.text_input("Publication date (YYYY-MM-DD)",
                                     value=datetime.date.today().strftime("%Y-%m-%d"),
                                     key="pub_date")
    with col2:
        doc_type     = st.selectbox("Document type", DOC_TYPES, key="doc_type")

    ai_status    = st.selectbox("AI status", ["unknown","ai_assisted","human_only","confirmed_ai"],
                                key="ai_status")
    title        = st.text_input("Document title", key="title")
    url          = st.text_input("Source URL (optional)", key="url")

    # ── Auto-generate doc_id ─────────────────────────────────────────────────
    if pub_date and re.match(r"\d{4}-\d{2}", pub_date):
        suggested_id = generate_doc_id(inst_data["code"], pub_date, language)
    else:
        suggested_id = ""
    doc_id = st.text_input("Document ID (auto-generated, editable)", value=suggested_id, key="doc_id")

    # ── Ingestion method tabs ─────────────────────────────────────────────────
    st.markdown("### Text ingestion")
    tab_paste, tab_upload, tab_scrape = st.tabs(["📋 Paste text", "📁 Upload file", "🌐 Scrape URL"])

    full_text = ""

    with tab_paste:
        full_text_paste = st.text_area("Paste document text here", height=250, key="paste_text")
        full_text = full_text_paste

    with tab_upload:
        uploaded = st.file_uploader("Upload PDF, DOCX, or TXT",
                                    type=["pdf","docx","txt","md"],
                                    key="file_upload")
        if uploaded:
            raw = uploaded.read()
            if uploaded.name.endswith(".pdf"):
                full_text = extract_pdf(raw)
            elif uploaded.name.endswith(".docx"):
                full_text = extract_docx(raw)
            else:
                full_text = raw.decode("utf-8", errors="replace")
            st.success(f"Extracted {word_count(full_text):,} words from {uploaded.name}")
            st.text_area("Extracted text (editable)", value=full_text, height=200, key="upload_preview")
            full_text = st.session_state.get("upload_preview", full_text)

    with tab_scrape:
        scrape_url_input = st.text_input("URL to scrape", key="scrape_url_input")
        if st.button("Scrape", key="scrape_btn"):
            if scrape_url_input:
                with st.spinner("Fetching…"):
                    full_text = scrape_url(scrape_url_input)
                st.success(f"Fetched {word_count(full_text):,} words")
                st.text_area("Scraped text (editable)", value=full_text, height=200, key="scrape_preview")
                full_text = st.session_state.get("scrape_preview", full_text)
            else:
                st.warning("Enter a URL first.")

    # Resolve final text across tabs
    active_text = (
        st.session_state.get("scrape_preview")
        or st.session_state.get("upload_preview")
        or full_text_paste
        or ""
    )

    notes = st.text_area("Notes (optional)", height=80, key="notes")

    # ── Validate + Save ───────────────────────────────────────────────────────
    col_v, col_s = st.columns([1, 1])
    with col_v:
        if st.button("✔ Validate", use_container_width=True):
            data = dict(
                doc_id=doc_id, title=title, institution=inst_label,
                source_type=source_type, ideology_tag=ideology, language=language,
                pub_date=pub_date, doc_type=doc_type, episode=episode,
                url=url, ai_status=ai_status, word_count=word_count(active_text),
                full_text=active_text, agency_shift=None, uncert_deletion=None,
                temp_compress=None, sec_reclass=None, flat_total=None,
                rater_1=None, rater_2=None, notes=notes,
                created_at=datetime.datetime.utcnow().isoformat()
            )
            errors, warnings = validate_doc(data)
            if errors:
                for e in errors:
                    st.error(f"✗ {e}")
            else:
                st.success("✓ Validation passed")
            for w in warnings:
                st.warning(f"⚠ {w}")
            st.session_state["validated_data"] = data if not errors else None

    with col_s:
        if st.button("💾 Save to corpus", use_container_width=True, type="primary"):
            data = dict(
                doc_id=doc_id, title=title, institution=inst_label,
                source_type=source_type, ideology_tag=ideology, language=language,
                pub_date=pub_date, doc_type=doc_type, episode=episode,
                url=url, ai_status=ai_status, word_count=word_count(active_text),
                full_text=active_text, agency_shift=None, uncert_deletion=None,
                temp_compress=None, sec_reclass=None, flat_total=None,
                rater_1=None, rater_2=None, notes=notes,
                created_at=datetime.datetime.utcnow().isoformat()
            )
            errors, warnings = validate_doc(data)
            if errors:
                for e in errors:
                    st.error(f"✗ {e}")
            else:
                insert_doc(data)
                st.success(f"✓ Saved: `{doc_id}` ({word_count(active_text):,} words)")
                for w in warnings:
                    st.warning(f"⚠ {w}")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: CORPUS
# ═══════════════════════════════════════════════════════════════════════════════

def page_corpus():
    st.markdown("## CORPUS BROWSER")
    docs = get_all_docs()
    if not docs:
        st.info("No documents yet. Use the **Add** tab to ingest your first document.")
        return

    # ── Filters ───────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        f_lang = st.selectbox("Language", ["All","en","ar","fr"], key="f_lang")
    with col2:
        f_ep   = st.selectbox("Episode", ["All"] + EPISODES, key="f_ep")
    with col3:
        f_ideo = st.selectbox("Ideology", ["All"] + IDEOLOGIES, key="f_ideo")

    filtered = docs
    if f_lang != "All":
        filtered = [d for d in filtered if d["language"] == f_lang]
    if f_ep != "All":
        filtered = [d for d in filtered if d["episode"] == f_ep]
    if f_ideo != "All":
        filtered = [d for d in filtered if d["ideology_tag"] == f_ideo]

    st.caption(f"Showing {len(filtered)} of {len(docs)} documents")

    for d in filtered:
        lang_badge = f"<span class='badge badge-{d['language']}'>{d['language'].upper()}</span>"
        if "liberal" in d["ideology_tag"]:
            ideo_badge = f"<span class='badge badge-lib'>LIB</span>"
        elif "conservative" in d["ideology_tag"]:
            ideo_badge = f"<span class='badge badge-con'>CON</span>"
        else:
            ideo_badge = f"<span class='badge badge-res'>{d['ideology_tag'][:3].upper()}</span>"

        flat = f"<span class='doc-score'>Flat: {d['flat_total']}/12</span>" if d["flat_total"] is not None else "<span style='color:#8b949e'>Flat: —</span>"

        st.markdown(
            f"<div class='doc-card'>"
            f"<span class='doc-id'>{d['doc_id']}</span>{lang_badge}{ideo_badge}"
            f"<div class='doc-meta'>{d['institution']} · {d['episode']} · {d['pub_date']} · {d['word_count']:,} words · {flat}</div>"
            f"<div class='doc-meta' style='margin-top:0.3rem'>{d['title'][:120]}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        with st.expander(f"Details / Annotate — {d['doc_id']}"):
            st.text_area("Full text", value=d["full_text"], height=180, key=f"txt_{d['doc_id']}", disabled=True)
            st.markdown("**Flattening annotation** (0 = none, 3 = strong)")
            ac1, ac2, ac3, ac4 = st.columns(4)
            with ac1:
                d1 = st.selectbox("Agency Shift", [None,0,1,2,3],
                                  index=([None,0,1,2,3].index(d["agency_shift"]) if d["agency_shift"] in [None,0,1,2,3] else 0),
                                  key=f"d1_{d['doc_id']}")
            with ac2:
                d2 = st.selectbox("Uncert. Deletion", [None,0,1,2,3],
                                  index=([None,0,1,2,3].index(d["uncert_deletion"]) if d["uncert_deletion"] in [None,0,1,2,3] else 0),
                                  key=f"d2_{d['doc_id']}")
            with ac3:
                d3 = st.selectbox("Temporal Compress.", [None,0,1,2,3],
                                  index=([None,0,1,2,3].index(d["temp_compress"]) if d["temp_compress"] in [None,0,1,2,3] else 0),
                                  key=f"d3_{d['doc_id']}")
            with ac4:
                d4 = st.selectbox("Security Reclass.", [None,0,1,2,3],
                                  index=([None,0,1,2,3].index(d["sec_reclass"]) if d["sec_reclass"] in [None,0,1,2,3] else 0),
                                  key=f"d4_{d['doc_id']}")
            rater = st.text_input("Rater initials", value=d["rater_1"] or "", key=f"rater_{d['doc_id']}")
            annot_notes = st.text_area("Annotation notes", value=d["notes"] or "", height=60, key=f"anotes_{d['doc_id']}")

            rc1, rc2 = st.columns(2)
            with rc1:
                if st.button("Save annotation", key=f"save_ann_{d['doc_id']}"):
                    update_annotation(d["doc_id"], d1, d2, d3, d4, rater, annot_notes)
                    st.success("Annotation saved.")
                    st.rerun()
            with rc2:
                if st.button("🗑 Delete document", key=f"del_{d['doc_id']}"):
                    delete_doc(d["doc_id"])
                    st.warning(f"Deleted {d['doc_id']}")
                    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: VALIDATE
# ═══════════════════════════════════════════════════════════════════════════════

def page_validate():
    st.markdown("## CORPUS VALIDATION")
    docs = get_all_docs()
    if not docs:
        st.info("No documents to validate.")
        return

    total_errors, total_warnings = 0, 0
    issues = []
    for d in docs:
        errors, warnings = [], []
        if not d.get("title"):
            warnings.append("Missing title")
        if d.get("word_count", 0) < 500:
            warnings.append(f"Under 500 words ({d['word_count']})")
        if d.get("flat_total") is None:
            warnings.append("Not yet annotated")
        if not d.get("url"):
            warnings.append("No URL")
        if errors or warnings:
            issues.append((d["doc_id"], errors, warnings))
            total_errors   += len(errors)
            total_warnings += len(warnings)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total documents", len(docs))
    c2.metric("Hard errors",     total_errors,   delta=None)
    c3.metric("Soft warnings",   total_warnings, delta=None)

    annotated = sum(1 for d in docs if d.get("flat_total") is not None)
    st.progress(annotated / len(docs) if docs else 0,
                text=f"Annotation progress: {annotated}/{len(docs)} documents")

    if issues:
        st.markdown("### Issues by document")
        for doc_id, errors, warnings in issues:
            with st.expander(f"{'🔴' if errors else '🟡'} {doc_id}"):
                for e in errors:   st.error(e)
                for w in warnings: st.warning(w)
    else:
        st.success("✓ No issues found.")

    # ── Kappa reminder ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Inter-rater reliability")
    st.info(
        "After both raters have scored the first 20 documents, compute Cohen's κ externally:\n\n"
        "```python\nfrom sklearn.metrics import cohen_kappa_score\n"
        "κ = cohen_kappa_score(rater1_scores, rater2_scores)\n```\n\n"
        "Minimum κ ≥ 0.70 required on all four dimensions before full annotation."
    )

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def page_export():
    st.markdown("## EXPORT")
    docs = get_all_docs()
    stats = get_stats()

    # ── Corpus stats ─────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total",      stats["total"])
    c2.metric("Annotated",  stats["annotated"])
    c3.metric("Languages",  len(stats["by_lang"]))
    c4.metric("Episodes",   len(stats["by_ep"]))

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**By language**")
        for row in stats["by_lang"]:
            st.caption(f"{row[0].upper()}: {row[1]}")
    with col_b:
        st.markdown("**By ideology**")
        for row in stats["by_ideo"]:
            st.caption(f"{row[0]}: {row[1]}")

    st.markdown("---")

    if not docs:
        st.info("No documents to export.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Full corpus CSV")
        csv_data = docs_to_csv(docs)
        st.download_button(
            "⬇ Download corpus.csv",
            data=csv_data,
            file_name=f"alg_pivot_corpus_{datetime.date.today()}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        st.markdown("### MARC-02 context block")
        marc_block = docs_to_marc_context(docs)
        st.download_button(
            "⬇ Download marc_context.txt",
            data=marc_block,
            file_name=f"marc_context_{datetime.date.today()}.txt",
            mime="text/plain",
            use_container_width=True
        )
        st.caption("First 30 documents · 400 char excerpt each · ready for MARC-02 context field")

    st.markdown("---")
    st.markdown("### Annotation audit CSV")
    annotated = [d for d in docs if d.get("flat_total") is not None]
    if annotated:
        audit_csv = docs_to_csv(annotated)
        st.download_button(
            "⬇ Download annotation_audit.csv",
            data=audit_csv,
            file_name=f"annotation_audit_{datetime.date.today()}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("No annotated documents yet.")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: STATS
# ═══════════════════════════════════════════════════════════════════════════════

def page_stats():
    st.markdown("## CORPUS STATISTICS")
    stats = get_stats()
    docs  = get_all_docs()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total documents",  stats["total"])
    c2.metric("Annotated",        stats["annotated"])
    c3.metric("Target",           "1,500")

    st.progress(stats["total"] / 1500, text=f"Corpus completion: {stats['total']}/1500")

    col_l, col_e, col_i = st.columns(3)
    with col_l:
        st.markdown("**Language distribution**")
        for r in stats["by_lang"]:
            st.caption(f"`{r[0].upper()}` — {r[1]} docs")
    with col_e:
        st.markdown("**Episode distribution**")
        for r in stats["by_ep"]:
            st.caption(f"`{r[0]}` — {r[1]} docs")
    with col_i:
        st.markdown("**Ideology distribution**")
        for r in stats["by_ideo"]:
            st.caption(f"`{r[0]}` — {r[1]} docs")

    if stats["annotated"] > 0:
        st.markdown("---")
        st.markdown("**Flattening score distribution**")
        annotated = [d for d in docs if d.get("flat_total") is not None]
        low    = sum(1 for d in annotated if d["flat_total"] <= 3)
        mid    = sum(1 for d in annotated if 4 <= d["flat_total"] <= 7)
        high   = sum(1 for d in annotated if d["flat_total"] >= 8)
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Low (0–3)",      low)
        cc2.metric("Moderate (4–7)", mid)
        cc3.metric("High (8–12)",    high)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="CB-01 · ALG-PIVOT Corpus Builder",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.markdown(CSS, unsafe_allow_html=True)

    # ── Auth ──────────────────────────────────────────────────────────────────
    if not st.session_state.get("authenticated"):
        auth_gate()

    init_db()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            "<div style='font-family:IBM Plex Mono,monospace; font-size:1rem; "
            "color:#58a6ff; font-weight:600; margin-bottom:0.2rem'>CB-01</div>"
            "<div style='font-family:IBM Plex Mono,monospace; font-size:0.65rem; "
            "color:#8b949e; margin-bottom:1.5rem'>CORPUS BUILDER · ALG-PIVOT</div>",
            unsafe_allow_html=True
        )
        stats = get_stats()
        st.metric("Corpus size", stats["total"])
        st.metric("Annotated",   stats["annotated"])
        st.markdown("---")
        nav = st.radio(
            "Navigation",
            ["Add document", "Corpus browser", "Validate", "Export", "Statistics"],
            key="nav"
        )
        st.markdown("---")
        if st.button("🔒 Lock", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()
        st.caption(f"DB: `{os.path.basename(DB_PATH)}`")

    # ── Page routing ──────────────────────────────────────────────────────────
    if nav == "Add document":
        page_ingest()
    elif nav == "Corpus browser":
        page_corpus()
    elif nav == "Validate":
        page_validate()
    elif nav == "Export":
        page_export()
    elif nav == "Statistics":
        page_stats()

if __name__ == "__main__":
    main()
