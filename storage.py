"""
MARC-03 Corpus Builder -- SQLite storage layer.

All database access goes through this module. The connection is cached by
Streamlit so it is created once per process.
"""

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import List, Set

import streamlit as st

from models import AuditEntry, Document


def get_db_path() -> Path:
    """Return the path to the SQLite database file.

    Uses /data on Render (persistent disk) and the current directory locally.
    """
    data_dir = Path("/data") if Path("/data").exists() else Path(".")
    return data_dir / "algpivot_corpus.db"


@st.cache_resource
def get_conn() -> sqlite3.Connection:
    """Return a cached, WAL-mode SQLite connection with schema initialised."""
    conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they do not yet exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id           TEXT PRIMARY KEY,
            title            TEXT DEFAULT '',
            text             TEXT DEFAULT '',
            episode          TEXT DEFAULT 'Syrian_Transition',
            research_theme   TEXT DEFAULT '',
            region           TEXT DEFAULT '',
            period           TEXT DEFAULT '',
            language         TEXT DEFAULT 'en',
            source_type      TEXT DEFAULT '',
            source_name      TEXT DEFAULT '',
            ideology_tag     TEXT DEFAULT 'NA',
            quadrad_actor    TEXT DEFAULT 'Not_applicable',
            publication_date TEXT DEFAULT '',
            url              TEXT DEFAULT 'NA',
            notes            TEXT DEFAULT '',
            word_count       INTEGER DEFAULT 0,
            added_at         TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_entries (
            audit_id          TEXT PRIMARY KEY,
            doc_id            TEXT NOT NULL,
            rater             TEXT DEFAULT '',
            agency_score      INTEGER DEFAULT 0,
            uncertainty_score INTEGER DEFAULT 0,
            temporal_score    INTEGER DEFAULT 0,
            security_score    INTEGER DEFAULT 0,
            total_score       INTEGER DEFAULT 0,
            notes             TEXT DEFAULT '',
            rated_at          TEXT DEFAULT '',
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
    """)
    _migrate(conn)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the initial schema (non-destructive migration)."""
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(documents)").fetchall()
    }
    new_columns = {
        "episode":        "TEXT DEFAULT 'Syrian_Transition'",
        "research_theme": "TEXT DEFAULT ''",
        "quadrad_actor":  "TEXT DEFAULT 'Not_applicable'",
    }
    for col, typedef in new_columns.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {col} {typedef}")


# ── DOCUMENTS ────────────────────────────────────────────────────────────────

def list_docs(episode: str = "All") -> List[Document]:
    """Return all documents ordered by publication date descending.

    Parameters
    ----------
    episode:
        If not "All", only documents belonging to that episode are returned.
    """
    if episode == "All":
        rows = get_conn().execute(
            "SELECT * FROM documents ORDER BY publication_date DESC"
        ).fetchall()
    else:
        rows = get_conn().execute(
            "SELECT * FROM documents WHERE episode=? ORDER BY publication_date DESC",
            (episode,),
        ).fetchall()
    return [Document(**dict(r)) for r in rows]


def upsert_doc(doc: Document) -> None:
    """Insert a new document or update all fields of an existing one."""
    d = asdict(doc)
    get_conn().execute(
        """
        INSERT INTO documents VALUES
            (:doc_id,:title,:text,:episode,:research_theme,:region,:period,
             :language,:source_type,:source_name,:ideology_tag,:quadrad_actor,
             :publication_date,:url,:notes,:word_count,:added_at)
        ON CONFLICT(doc_id) DO UPDATE SET
            title=excluded.title,
            text=excluded.text,
            episode=excluded.episode,
            research_theme=excluded.research_theme,
            region=excluded.region,
            period=excluded.period,
            language=excluded.language,
            source_type=excluded.source_type,
            source_name=excluded.source_name,
            ideology_tag=excluded.ideology_tag,
            quadrad_actor=excluded.quadrad_actor,
            publication_date=excluded.publication_date,
            url=excluded.url,
            notes=excluded.notes,
            word_count=excluded.word_count
        """,
        d,
    )
    get_conn().commit()


def delete_doc(doc_id: str) -> None:
    """Delete a document and all its associated audit entries."""
    conn = get_conn()
    conn.execute("DELETE FROM audit_entries WHERE doc_id=?", (doc_id,))
    conn.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
    conn.commit()


def all_ids() -> Set[str]:
    """Return the set of every doc_id currently in the database."""
    return {
        r[0]
        for r in get_conn().execute("SELECT doc_id FROM documents").fetchall()
    }


# ── AUDIT ENTRIES ────────────────────────────────────────────────────────────

def list_audits(doc_id: str = "") -> List[AuditEntry]:
    """Return audit entries ordered by rated_at descending.

    Parameters
    ----------
    doc_id:
        If provided, only entries for that document are returned.
    """
    if doc_id:
        rows = get_conn().execute(
            "SELECT * FROM audit_entries WHERE doc_id=? ORDER BY rated_at DESC",
            (doc_id,),
        ).fetchall()
    else:
        rows = get_conn().execute(
            "SELECT * FROM audit_entries ORDER BY rated_at DESC"
        ).fetchall()
    return [AuditEntry(**dict(r)) for r in rows]


def upsert_audit(entry: AuditEntry) -> None:
    """Insert a new audit entry or update an existing one."""
    d = asdict(entry)
    get_conn().execute(
        """
        INSERT INTO audit_entries VALUES
            (:audit_id,:doc_id,:rater,:agency_score,:uncertainty_score,
             :temporal_score,:security_score,:total_score,:notes,:rated_at)
        ON CONFLICT(audit_id) DO UPDATE SET
            rater=excluded.rater,
            agency_score=excluded.agency_score,
            uncertainty_score=excluded.uncertainty_score,
            temporal_score=excluded.temporal_score,
            security_score=excluded.security_score,
            total_score=excluded.total_score,
            notes=excluded.notes
        """,
        d,
    )
    get_conn().commit()


def delete_audit(audit_id: str) -> None:
    """Delete a single audit entry by its ID."""
    get_conn().execute("DELETE FROM audit_entries WHERE audit_id=?", (audit_id,))
    get_conn().commit()
