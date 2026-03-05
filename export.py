"""
MARC-03 Corpus Builder -- Export utilities.

Produces CSV exports, MARC-02 context blocks, audit CSVs, and corpus stats.
No Streamlit imports -- this module is framework-agnostic.
"""

import csv
import io
from typing import Dict, List

from ingestion import wc
from models import AuditEntry, Document

# Columns written to the corpus CSV (text excluded by default to keep size manageable)
_BASE_COLS: List[str] = [
    "doc_id",
    "title",
    "episode",
    "research_theme",
    "region",
    "period",
    "language",
    "source_type",
    "source_name",
    "ideology_tag",
    "quadrad_actor",
    "publication_date",
    "url",
    "notes",
    "word_count",
]


def to_csv(docs: List[Document], include_text: bool = False) -> str:
    """Serialise a list of documents to a CSV string.

    Parameters
    ----------
    docs:
        The documents to export.
    include_text:
        When True, a ``text`` column is inserted after ``title``.

    Returns
    -------
    str
        UTF-8 CSV content ready for download.
    """
    cols = _BASE_COLS.copy()
    if include_text:
        cols.insert(cols.index("episode"), "text")

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow(cols)
    for doc in docs:
        writer.writerow([getattr(doc, c, "") for c in cols])
    return buf.getvalue()


def to_context_block(
    docs: List[Document],
    topic_filter: str = "All",
    max_docs: int = 30,
) -> str:
    """Generate a MARC-02-compatible context block from corpus documents.

    Each entry contains the document ID, source, date, type, ideology,
    theme, and a 400-character text snippet. Entries are separated by
    ``---`` so MARC-02 can parse them as discrete sources.

    Parameters
    ----------
    docs:
        Documents to include (should already be filtered before calling).
    topic_filter:
        Label used in the block header (display only).
    max_docs:
        Maximum number of documents to include (default 30).

    Returns
    -------
    str
        Multi-line text block suitable for pasting into a MARC-02 context field.
    """
    header = f"RESEARCH CORPUS -- {topic_filter} -- {len(docs)} documents\n"
    entries: List[str] = [header]
    for doc in docs[:max_docs]:
        snippet = doc.text[:400] + "..." if len(doc.text) > 400 else doc.text
        entries.append(
            f"[{doc.doc_id}] {doc.source_name} ({doc.publication_date}) "
            f"{doc.source_type}/{doc.ideology_tag} | {doc.research_theme} | "
            f"ep:{doc.episode}\n{snippet}"
        )
    return "\n---\n".join(entries)


def audit_to_csv(entries: List[AuditEntry]) -> str:
    """Serialise audit entries to a CSV string for inter-rater analysis.

    The output is designed for import into statistical tools (R, Python) to
    compute Cohen's Kappa between raters.

    Parameters
    ----------
    entries:
        All audit entries to export.

    Returns
    -------
    str
        UTF-8 CSV content ready for download.
    """
    cols = [
        "audit_id",
        "doc_id",
        "rater",
        "agency_score",
        "uncertainty_score",
        "temporal_score",
        "security_score",
        "total_score",
        "notes",
        "rated_at",
    ]
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow(cols)
    for entry in entries:
        writer.writerow([getattr(entry, c, "") for c in cols])
    return buf.getvalue()


def corpus_stats(docs: List[Document]) -> Dict:
    """Compute summary statistics for the corpus.

    Parameters
    ----------
    docs:
        The full list of documents to analyse.

    Returns
    -------
    dict
        Keys: total, total_words, by_source_type, by_language, by_period,
        by_ideology, by_episode, by_theme. Each ``by_*`` value is a
        ``{label: count}`` dict.
    """
    stats: Dict = {
        "total": len(docs),
        "total_words": sum(d.word_count for d in docs),
        "by_source_type": {},
        "by_language": {},
        "by_period": {},
        "by_ideology": {},
        "by_episode": {},
        "by_theme": {},
    }
    dimension_map = [
        ("by_source_type", "source_type"),
        ("by_language",    "language"),
        ("by_period",      "period"),
        ("by_ideology",    "ideology_tag"),
        ("by_episode",     "episode"),
        ("by_theme",       "research_theme"),
    ]
    for doc in docs:
        for key, attr in dimension_map:
            val = getattr(doc, attr, "")
            stats[key][val] = stats[key].get(val, 0) + 1
    return stats
