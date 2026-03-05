"""
MARC-03 Corpus Builder -- Main Streamlit application.

Entry point: ``streamlit run app.py``

Tab layout:
    Add Document | Library | Flattening Audit | Validate | Export

The episode selector lives in the sidebar and propagates to every tab.
"""

import datetime
from typing import List, Optional, Set

import requests
import streamlit as st

from export import audit_to_csv, corpus_stats, to_context_block, to_csv
from ingestion import extract_pdf, scrape_url, wc
from models import (
    AUDIT_DIMENSIONS,
    AUDIT_RUBRIC,
    EPISODES,
    IDEOLOGY_TAGS,
    INSTITUTION_AUTOFILL,
    LANGUAGES,
    PERIODS,
    QUADRAD_ACTORS,
    REGIONS,
    RESEARCH_THEMES,
    SOURCE_TYPES,
    AuditEntry,
    Document,
)
from storage import (
    all_ids,
    delete_audit,
    delete_doc,
    list_audits,
    list_docs,
    upsert_audit,
    upsert_doc,
)
from validation import MIN_WORDS, suggest_id, validate

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Corpus Builder · MARC-03",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── THEME ─────────────────────────────────────────────────────────────────────

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
html,body,[class*="css"]{font-family:'IBM Plex Sans',sans-serif;}
.stApp{background-color:#0d1117;color:#e6edf3;}
section[data-testid="stSidebar"]{background-color:#161b22;border-right:1px solid #30363d;}
div[data-testid="metric-container"]{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:.75rem 1rem;}
div[data-testid="metric-container"] label{color:#8b949e!important;font-size:.72rem!important;}
div[data-testid="metric-container"] div[data-testid="stMetricValue"]{color:#58a6ff!important;font-family:'IBM Plex Mono',monospace;}
.stTextInput input,.stTextArea textarea{background-color:#161b22!important;border:1px solid #30363d!important;color:#e6edf3!important;border-radius:6px!important;}
.stSelectbox div[data-baseweb="select"]>div{background-color:#161b22!important;border-color:#30363d!important;color:#e6edf3!important;}
.stButton>button{background:#21262d;border:1px solid #30363d;color:#e6edf3;border-radius:6px;font-size:.82rem;}
.stButton>button:hover{border-color:#58a6ff;color:#58a6ff;}
.stButton>button[kind="primary"]{background:#1f6feb;border-color:#1f6feb;color:#fff;}
.stTabs [data-baseweb="tab"]{font-family:'IBM Plex Mono',monospace;font-size:.72rem;color:#8b949e;}
.stTabs [aria-selected="true"]{color:#58a6ff!important;}
.lbl{font-family:'IBM Plex Mono',monospace;font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;color:#8b949e;margin-bottom:.3rem;}
.score-pill{display:inline-block;background:#161b22;border:1px solid #30363d;border-radius:12px;padding:.15rem .6rem;font-family:'IBM Plex Mono',monospace;font-size:.75rem;color:#58a6ff;margin:.1rem;}
</style>
""",
    unsafe_allow_html=True,
)

# ── HELPERS ───────────────────────────────────────────────────────────────────


def _idx(lst: list, val: str) -> int:
    """Return the index of val in lst, or 0 if not found."""
    try:
        return lst.index(val)
    except ValueError:
        return 0


# ── SIDEBAR ───────────────────────────────────────────────────────────────────


def _render_sidebar(all_docs: List[Document]) -> str:
    """Render the sidebar and return the selected episode filter.

    The episode selectbox is the global filter that propagates to all tabs.

    Parameters
    ----------
    all_docs:
        The unfiltered document list, used for sidebar metrics.

    Returns
    -------
    str
        Selected episode label ("All" or a specific episode key).
    """
    with st.sidebar:
        st.markdown("### CORPUS BUILDER")
        st.caption("MARC-03 · PhD Research Corpus")
        st.divider()

        episode: str = st.selectbox(
            "Episode filter",
            ["All"] + EPISODES,
            key="global_episode",
            help="Filters all tabs to show only documents from this episode.",
        )

        st.divider()

        n = len(all_docs)
        st.metric("Total documents", n)
        st.metric("Total words", f"{sum(d.word_count for d in all_docs):,}")

        if n > 0:
            st.divider()
            st.markdown("**By source type**")
            src_counts: dict = {}
            for d in all_docs:
                src_counts[d.source_type] = src_counts.get(d.source_type, 0) + 1
            for k, v in sorted(src_counts.items(), key=lambda x: -x[1]):
                st.progress(v / n, text=f"{k}: {v}")

        st.divider()
        st.caption("Mohamed Defaa · PhD · Cyber Leadership")
        st.caption("Capitol Technology University")
        st.caption("Chair: Dr. Anthony Dehnashi")
        st.caption(f"DB: `algpivot_corpus.db`")

    return episode


# ── DOCUMENT FORM ─────────────────────────────────────────────────────────────


def _doc_form(
    prefix: str,
    defaults: Document,
    existing_ids: Set[str],
    editing: bool = False,
) -> Optional[Document]:
    """Render the document metadata and text form.

    Uses direct widgets (no st.form) so word count updates live and
    institution autofill fires immediately on selection.

    Parameters
    ----------
    prefix:
        Unique string prepended to every widget key to avoid collisions.
    defaults:
        Pre-populated field values.
    existing_ids:
        All doc_ids currently in the database (for uniqueness validation).
    editing:
        True when modifying an existing document (skips ID uniqueness check
        for the document's own ID).

    Returns
    -------
    Optional[Document]
        The assembled Document on successful save, or None otherwise.
    """
    inst_names = ["-- select institution --"] + sorted(INSTITUTION_AUTOFILL.keys())
    inst = st.selectbox("Institution autofill", inst_names, key=f"{prefix}_inst")
    if inst != "-- select institution --":
        defaults.source_name  = inst
        defaults.source_type  = INSTITUTION_AUTOFILL[inst][0]
        defaults.ideology_tag = INSTITUTION_AUTOFILL[inst][1]

    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<p class="lbl">Identification</p>', unsafe_allow_html=True)
        title = st.text_input("Title", value=defaults.title, key=f"{prefix}_title")
        doc_id = st.text_input(
            "Document ID",
            value=(
                defaults.doc_id
                if editing
                else suggest_id(defaults.source_name, defaults.publication_date, existing_ids)
            ),
            key=f"{prefix}_id",
        )
        src_name = st.text_input(
            "Source / Institution", value=defaults.source_name, key=f"{prefix}_src"
        )
        pub_date = st.text_input(
            "Publication date (YYYY-MM-DD)",
            value=defaults.publication_date,
            key=f"{prefix}_date",
        )
        url = st.text_input("URL", value=defaults.url, key=f"{prefix}_url")

    with c2:
        st.markdown('<p class="lbl">Classification</p>', unsafe_allow_html=True)
        episode  = st.selectbox(
            "Episode", EPISODES,
            index=_idx(EPISODES, defaults.episode), key=f"{prefix}_episode"
        )
        theme    = st.selectbox(
            "Research theme", RESEARCH_THEMES,
            index=_idx(RESEARCH_THEMES, defaults.research_theme), key=f"{prefix}_theme"
        )
        region   = st.selectbox(
            "Region", REGIONS,
            index=_idx(REGIONS, defaults.region), key=f"{prefix}_region"
        )
        lang     = st.selectbox(
            "Language", LANGUAGES,
            index=_idx(LANGUAGES, defaults.language), key=f"{prefix}_lang"
        )
        src_type = st.selectbox(
            "Source type", SOURCE_TYPES,
            index=_idx(SOURCE_TYPES, defaults.source_type), key=f"{prefix}_srctype"
        )
        ideology = st.selectbox(
            "Ideology tag", IDEOLOGY_TAGS,
            index=_idx(IDEOLOGY_TAGS, defaults.ideology_tag), key=f"{prefix}_ideo"
        )
        period   = st.selectbox(
            "Period", PERIODS,
            index=_idx(PERIODS, defaults.period), key=f"{prefix}_period"
        )
        actor    = st.selectbox(
            "QUADRAD actor", QUADRAD_ACTORS,
            index=_idx(QUADRAD_ACTORS, defaults.quadrad_actor), key=f"{prefix}_actor"
        )

    notes = st.text_area("Notes", value=defaults.notes, height=70, key=f"{prefix}_notes")
    st.markdown('<p class="lbl">Document text</p>', unsafe_allow_html=True)
    text = st.text_area(
        "Text",
        value=defaults.text,
        height=240,
        key=f"{prefix}_text",
        label_visibility="collapsed",
    )
    count = wc(text)
    st.caption(f"{'🟢' if count >= MIN_WORDS else '🟡'} {count:,} words")

    if st.button("Save document", type="primary", key=f"{prefix}_save"):
        doc = Document(
            doc_id=doc_id.strip(),
            title=title.strip(),
            text=text.strip(),
            episode=episode,
            research_theme=theme,
            region=region,
            period=period,
            language=lang,
            source_type=src_type,
            source_name=src_name.strip(),
            ideology_tag=ideology,
            quadrad_actor=actor,
            publication_date=pub_date.strip(),
            url=url.strip() or "NA",
            notes=notes.strip(),
            word_count=count,
            added_at=defaults.added_at or datetime.datetime.utcnow().isoformat(),
        )
        errs, warns = validate(
            doc,
            existing_ids,
            editing_id=defaults.doc_id if editing else "",
        )
        if errs:
            for e in errs:
                st.error(f"ERROR: {e}")
            return None
        for w in warns:
            st.warning(f"WARNING: {w}")
        return doc

    return None


# ── TAB: ADD ──────────────────────────────────────────────────────────────────


def _tab_add(episode: str, existing_ids: Set[str]) -> None:
    """Render the Add Document tab.

    Parameters
    ----------
    episode:
        The globally selected episode; pre-populates the episode field.
    existing_ids:
        All current doc_ids for uniqueness checking and ID suggestion.
    """
    st.markdown("### Add a new document")
    method = st.radio(
        "",
        ["Paste text", "Scrape URL", "Upload PDF"],
        horizontal=True,
        label_visibility="collapsed",
        key="add_method",
    )
    st.divider()

    default_episode = episode if episode != "All" else "EP-05_Unassigned"
    prefilled = Document(episode=default_episode)

    if method == "Scrape URL":
        url_in = st.text_input(
            "URL to scrape",
            placeholder="https://brookings.edu/...",
            key="add_url_in",
        )
        if st.button("Fetch", key="add_fetch") and url_in.strip():
            with st.spinner("Fetching..."):
                try:
                    t, txt = scrape_url(url_in.strip())
                    st.session_state.update(
                        {"add_s_title": t, "add_s_text": txt, "add_s_url": url_in.strip()}
                    )
                    st.success(f"Fetched {wc(txt):,} words.")
                except requests.RequestException as exc:
                    st.error(f"Fetch failed: {exc}")
        if "add_s_text" in st.session_state:
            with st.expander("Preview fetched text"):
                st.text(st.session_state["add_s_text"][:1500] + "...")
            prefilled.text  = st.session_state.get("add_s_text", "")
            prefilled.title = st.session_state.get("add_s_title", "")
            prefilled.url   = st.session_state.get("add_s_url", "NA")

    elif method == "Upload PDF":
        pdf = st.file_uploader("Upload PDF", type=["pdf"], key="add_pdf")
        if pdf:
            with st.spinner("Extracting text..."):
                try:
                    txt = extract_pdf(pdf.read())
                    st.session_state.update(
                        {
                            "add_p_text": txt,
                            "add_p_title": pdf.name.replace(".pdf", ""),
                        }
                    )
                    st.success(f"Extracted {wc(txt):,} words.")
                except (ImportError, Exception) as exc:
                    st.error(f"PDF extraction failed: {exc}")
        if "add_p_text" in st.session_state:
            with st.expander("Preview extracted text"):
                st.text(st.session_state["add_p_text"][:1500] + "...")
            prefilled.text  = st.session_state.get("add_p_text", "")
            prefilled.title = st.session_state.get("add_p_title", "")

    st.divider()
    doc = _doc_form("add", prefilled, existing_ids)
    if doc:
        try:
            upsert_doc(doc)
            st.success(f"'{doc.doc_id}' saved.")
            for k in ["add_s_text", "add_s_title", "add_s_url", "add_p_text", "add_p_title"]:
                st.session_state.pop(k, None)
            st.rerun()
        except sqlite3.Error as exc:
            st.error(f"Database error: {exc}")


# ── TAB: LIBRARY ──────────────────────────────────────────────────────────────


def _tab_library(docs: List[Document], existing_ids: Set[str]) -> None:
    """Render the Library tab with filtering and inline editing.

    Parameters
    ----------
    docs:
        Documents to display (already episode-filtered).
    existing_ids:
        All current doc_ids for validation inside edit forms.
    """
    if not docs:
        st.info("No documents yet. Go to **Add Document** to start.")
        return

    c1, c2, c3, c4 = st.columns(4)
    f_theme = c1.selectbox("Theme",    ["All"] + RESEARCH_THEMES, key="lib_f_theme")
    f_src   = c2.selectbox("Source",   ["All"] + SOURCE_TYPES,    key="lib_f_src")
    f_lang  = c3.selectbox("Language", ["All"] + LANGUAGES,       key="lib_f_lang")
    f_q     = c4.text_input("Search",  placeholder="keyword...",   key="lib_f_q")

    filtered = docs
    if f_theme != "All":
        filtered = [d for d in filtered if d.research_theme == f_theme]
    if f_src != "All":
        filtered = [d for d in filtered if d.source_type == f_src]
    if f_lang != "All":
        filtered = [d for d in filtered if d.language == f_lang]
    if f_q.strip():
        q = f_q.lower()
        filtered = [
            d for d in filtered
            if q in d.title.lower() or q in d.source_name.lower() or q in d.text.lower()
        ]

    st.caption(f"Showing {len(filtered)} of {len(docs)} documents")
    st.divider()

    for d in filtered:
        errs, warns = validate(d, existing_ids, editing_id=d.doc_id)
        status_icon = "OK" if not errs else "ERR"
        warn_badge  = f"  W:{len(warns)}" if warns else ""
        label = f"[{status_icon}] {d.doc_id} -- {d.source_name} · {d.publication_date}{warn_badge}"

        with st.expander(label):
            ca, cb = st.columns([3, 1])
            with ca:
                st.markdown(f"**{d.title or '(no title)'}**")
                st.caption(
                    f"Source type: {d.source_type}  |  "
                    f"Ideology: {d.ideology_tag}  |  "
                    f"Language: {d.language}  |  "
                    f"Region: {d.region}  |  "
                    f"Period: {d.period}  |  "
                    f"Words: {d.word_count:,}"
                )
                st.caption(
                    f"Theme: {d.research_theme}  |  "
                    f"QUADRAD: {d.quadrad_actor}  |  "
                    f"Episode: {d.episode}"
                )
                if d.url and d.url != "NA":
                    st.caption(f"URL: {d.url[:80]}")
                if d.notes:
                    st.caption(f"Notes: {d.notes}")
                with st.expander("View text preview"):
                    st.text(d.text[:800] + ("..." if len(d.text) > 800 else ""))
            with cb:
                for e in errs:
                    st.error(e)
                for w in warns:
                    st.warning(w)
                if st.button("Edit", key=f"lib_edit_{d.doc_id}"):
                    st.session_state[f"lib_editing_{d.doc_id}"] = True
                if st.button("Delete", key=f"lib_del_{d.doc_id}"):
                    try:
                        delete_doc(d.doc_id)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Delete failed: {exc}")

            if st.session_state.get(f"lib_editing_{d.doc_id}"):
                st.divider()
                upd = _doc_form(f"lib_ed_{d.doc_id}", d, existing_ids, editing=True)
                if upd:
                    try:
                        upsert_doc(upd)
                        st.success("Updated.")
                        st.session_state.pop(f"lib_editing_{d.doc_id}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Save failed: {exc}")


# ── TAB: FLATTENING AUDIT ─────────────────────────────────────────────────────


def _tab_audit(docs: List[Document]) -> None:
    """Render the Flattening Audit tab.

    Raters score each document on four dimensions of algorithmic narrative
    flattening (agency, uncertainty, temporal, security) using a 0-3 scale.
    Total score is /12. Entries are persisted for Cohen's Kappa computation.

    Parameters
    ----------
    docs:
        Documents available for audit (already episode-filtered).
    """
    if not docs:
        st.info("No documents to audit.")
        return

    st.markdown("### Flattening Audit")
    st.caption(
        "Score each document on four dimensions of algorithmic narrative flattening. "
        "Scale: 0 = none · 1 = low · 2 = moderate · 3 = high. Total score: /12."
    )
    st.info(
        "**Inter-rater reliability:** Have two raters score the same documents "
        "independently. Export the audit CSV and compute Cohen's Kappa in R "
        "(`irr::kappa2`) or Python (`sklearn.metrics.cohen_kappa_score`)."
    )
    st.divider()

    # Document selector
    doc_options = {
        f"{d.doc_id} -- {d.source_name} ({d.publication_date})": d
        for d in docs
    }
    selected_label = st.selectbox(
        "Select document to audit", list(doc_options.keys()), key="audit_doc_select"
    )
    selected_doc = doc_options[selected_label]
    existing_audits = list_audits(selected_doc.doc_id)

    st.markdown(f"**{selected_doc.title or selected_doc.doc_id}**")
    st.caption(
        f"{selected_doc.source_name}  ·  {selected_doc.publication_date}  ·  "
        f"{selected_doc.research_theme}  ·  {selected_doc.episode}"
    )
    with st.expander("Text preview"):
        st.text(
            selected_doc.text[:600] + ("..." if len(selected_doc.text) > 600 else "")
        )

    st.divider()
    st.markdown("#### Rate this document")

    rater = st.text_input(
        "Rater initials (required)",
        max_chars=10,
        key="audit_rater",
        placeholder="e.g. MD",
    )

    scores: dict = {}
    for dim in AUDIT_DIMENSIONS:
        rubric = AUDIT_RUBRIC[dim]
        st.markdown(f"**{rubric['label']}**")
        st.caption(rubric["description"])
        anchor_md = "  ·  ".join(
            f"**{k}** = {v}" for k, v in rubric["anchors"].items()
        )
        st.caption(anchor_md)
        scores[dim] = st.slider(
            rubric["label"],
            min_value=0,
            max_value=3,
            value=0,
            key=f"audit_slider_{dim}",
            label_visibility="collapsed",
        )
        st.divider()

    total = sum(scores.values())
    severity = (
        "Low flattening"       if total <= 3  else
        "Moderate flattening"  if total <= 7  else
        "High flattening"
    )
    c_score, c_sev = st.columns([1, 3])
    c_score.metric("Total score", f"{total}/12")
    c_sev.caption(f"Severity: **{severity}**")

    audit_notes = st.text_area("Audit notes", height=80, key="audit_notes")

    if st.button("Save audit entry", type="primary", key="audit_save"):
        if not rater.strip():
            st.error("Rater initials are required.")
        else:
            ts = datetime.datetime.utcnow()
            audit_id = (
                f"{selected_doc.doc_id}_{rater.strip()}_{ts.strftime('%Y%m%dT%H%M%S')}"
            )
            entry = AuditEntry(
                audit_id=audit_id,
                doc_id=selected_doc.doc_id,
                rater=rater.strip(),
                agency_score=scores["agency"],
                uncertainty_score=scores["uncertainty"],
                temporal_score=scores["temporal"],
                security_score=scores["security"],
                total_score=total,
                notes=audit_notes.strip(),
                rated_at=ts.isoformat(),
            )
            try:
                upsert_audit(entry)
                st.success(f"Audit saved. ID: {audit_id}")
                st.rerun()
            except Exception as exc:
                st.error(f"Save failed: {exc}")

    # Existing audit entries for this document
    if existing_audits:
        st.divider()
        st.markdown(f"#### {len(existing_audits)} existing audit(s) for this document")
        for e in existing_audits:
            with st.expander(
                f"Rater: {e.rater}  ·  Score: {e.total_score}/12  ·  {e.rated_at[:10]}"
            ):
                ca, cb, cc, cd = st.columns(4)
                ca.metric("Agency",      e.agency_score)
                cb.metric("Uncertainty", e.uncertainty_score)
                cc.metric("Temporal",    e.temporal_score)
                cd.metric("Security",    e.security_score)
                if e.notes:
                    st.caption(f"Notes: {e.notes}")
                if st.button("Delete audit", key=f"audit_del_{e.audit_id}"):
                    try:
                        delete_audit(e.audit_id)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Delete failed: {exc}")


# ── TAB: VALIDATE ─────────────────────────────────────────────────────────────


def _tab_validate(docs: List[Document], existing_ids: Set[str]) -> None:
    """Render the Validate tab with corpus-wide error and warning counts.

    Parameters
    ----------
    docs:
        Documents to validate (already episode-filtered).
    existing_ids:
        All current doc_ids, used inside validate().
    """
    if not docs:
        st.info("No documents to validate.")
        return

    results = {
        d.doc_id: validate(d, existing_ids, editing_id=d.doc_id) for d in docs
    }
    total_e = sum(len(r[0]) for r in results.values())
    total_w = sum(len(r[1]) for r in results.values())

    c1, c2, c3 = st.columns(3)
    c1.metric("Documents", len(docs))
    c2.metric("Errors",    total_e)
    c3.metric("Warnings",  total_w)
    st.divider()

    if total_e == 0:
        st.success("All documents passed validation -- corpus is export-ready.")
    else:
        st.error(f"{total_e} error(s) must be fixed before export.")

    for doc_id, (errs, warns) in results.items():
        if errs or warns:
            prefix = "ERR" if errs else "WARN"
            with st.expander(f"[{prefix}] {doc_id}"):
                for e in errs:
                    st.error(e)
                for w in warns:
                    st.warning(w)


# ── TAB: EXPORT ───────────────────────────────────────────────────────────────


def _tab_export(docs: List[Document], existing_ids: Set[str]) -> None:
    """Render the Export tab.

    Export is blocked when any document has validation errors.

    Parameters
    ----------
    docs:
        Documents to export (already episode-filtered).
    existing_ids:
        All current doc_ids, used inside validate().
    """
    if not docs:
        st.info("No documents to export.")
        return

    has_errors = any(
        validate(d, existing_ids, editing_id=d.doc_id)[0] for d in docs
    )

    st.markdown("### Export corpus")
    st.caption(
        f"{len(docs)} documents · {sum(d.word_count for d in docs):,} total words"
    )
    st.divider()

    # ── CSV
    st.markdown("**Corpus CSV**")
    include_text = st.checkbox("Include full text column", key="exp_include_text")
    if has_errors:
        st.error("Fix all validation errors before exporting.")
    else:
        csv_data = to_csv(docs, include_text=include_text)
        st.download_button(
            "Download corpus.csv",
            data=csv_data,
            file_name=f"algpivot_corpus_{datetime.date.today()}.csv",
            mime="text/csv",
            type="primary",
        )

    st.divider()

    # ── Audit CSV
    st.markdown("**Audit scores CSV (for Cohen's Kappa)**")
    all_audits = list_audits()
    if all_audits:
        st.download_button(
            "Download audit_scores.csv",
            data=audit_to_csv(all_audits),
            file_name=f"algpivot_audits_{datetime.date.today()}.csv",
            mime="text/csv",
        )
        st.caption(f"{len(all_audits)} audit entries across all documents.")
    else:
        st.caption("No audit entries yet.")

    st.divider()

    # ── MARC-02 context block
    st.markdown("**MARC-02 context block**")
    t_filter = st.selectbox(
        "Filter by theme", ["All"] + RESEARCH_THEMES, key="exp_ctx_theme"
    )
    ctx_docs = docs if t_filter == "All" else [d for d in docs if d.research_theme == t_filter]
    if st.button("Generate context block", key="exp_ctx_btn"):
        block = to_context_block(ctx_docs, topic_filter=t_filter)
        st.text_area(
            "Paste into MARC-02 Context field:",
            value=block,
            height=300,
            key="exp_ctx_out",
        )
        st.caption(f"First 30 docs · {wc(block):,} words")

    st.divider()

    # ── Corpus statistics
    st.markdown("**Corpus statistics**")
    try:
        import pandas as pd

        stats = corpus_stats(docs)
        ca, cb = st.columns(2)

        with ca:
            st.caption("By source type")
            st.dataframe(
                pd.DataFrame(
                    list(stats["by_source_type"].items()), columns=["Source type", "Count"]
                ).sort_values("Count", ascending=False),
                hide_index=True,
                use_container_width=True,
            )
            st.caption("By research theme")
            st.dataframe(
                pd.DataFrame(
                    list(stats["by_theme"].items()), columns=["Theme", "Count"]
                ).sort_values("Count", ascending=False),
                hide_index=True,
                use_container_width=True,
            )

        with cb:
            st.caption("By language")
            st.dataframe(
                pd.DataFrame(
                    list(stats["by_language"].items()), columns=["Language", "Count"]
                ).sort_values("Count", ascending=False),
                hide_index=True,
                use_container_width=True,
            )
            st.caption("By episode")
            st.dataframe(
                pd.DataFrame(
                    list(stats["by_episode"].items()), columns=["Episode", "Count"]
                ).sort_values("Count", ascending=False),
                hide_index=True,
                use_container_width=True,
            )
    except ImportError:
        st.warning("Install pandas to enable statistics tables (`pip install pandas`).")


# ── MAIN ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Application entry point."""
    import sqlite3  # needed for the error type in _tab_add

    # Load unfiltered docs for sidebar metrics, then apply episode filter
    all_docs = list_docs()
    episode  = _render_sidebar(all_docs)
    docs     = list_docs(episode)
    ids      = all_ids()

    st.markdown("## Corpus Builder")
    st.caption("MARC-03 · Multi-Agent Research Corpus Manager")
    if episode != "All":
        st.caption(f"Episode filter active: **{episode}**")

    tab_add, tab_lib, tab_fla, tab_val, tab_exp = st.tabs([
        "Add Document",
        "Library",
        "Flattening Audit",
        "Validate",
        "Export",
    ])

    with tab_add:
        _tab_add(episode, ids)
    with tab_lib:
        _tab_library(docs, ids)
    with tab_fla:
        _tab_audit(docs)
    with tab_val:
        _tab_validate(docs, ids)
    with tab_exp:
        _tab_export(docs, ids)


if __name__ == "__main__":
    main()
