"""
MARC-03 Corpus Builder -- Validation logic.

All validation rules for Document objects live here. The validate() function
is pure (no side effects) and is safe to call from any context.
"""

import re
from typing import List, Set, Tuple

from ingestion import wc
from models import (
    EPISODES,
    IDEOLOGY_TAGS,
    LANGUAGES,
    QUADRAD_ACTORS,
    RESEARCH_THEMES,
    SOURCE_TYPES,
    Document,
)

DATE_RE: re.Pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MIN_WORDS: int = 150


def validate(
    doc: Document,
    existing_ids: Set[str],
    editing_id: str = "",
) -> Tuple[List[str], List[str]]:
    """Validate a Document and return (errors, warnings).

    Parameters
    ----------
    doc:
        The document to validate.
    existing_ids:
        The full set of doc_ids currently in the database.
    editing_id:
        When editing an existing document, pass its current doc_id so the
        uniqueness check ignores it.

    Returns
    -------
    Tuple[List[str], List[str]]
        (errors, warnings). Errors block saving; warnings are advisory.
    """
    errors: List[str] = []
    warnings: List[str] = []

    ids = existing_ids - ({editing_id} if editing_id else set())

    # doc_id
    if not doc.doc_id.strip():
        errors.append("doc_id is required.")
    elif doc.doc_id in ids:
        errors.append(f"doc_id '{doc.doc_id}' already exists.")

    # text
    if not doc.text.strip():
        errors.append("Document text is required.")
    else:
        count = wc(doc.text)
        if count < MIN_WORDS:
            warnings.append(
                f"Text is short ({count:,} words; minimum recommended is {MIN_WORDS})."
            )

    # publication date
    if not doc.publication_date.strip():
        errors.append("Publication date is required.")
    elif not DATE_RE.match(doc.publication_date):
        errors.append("Publication date must be in YYYY-MM-DD format.")

    # controlled vocabularies
    if doc.language not in LANGUAGES:
        errors.append(f"Language must be one of: {', '.join(LANGUAGES)}.")

    if doc.source_type not in SOURCE_TYPES:
        errors.append(f"Source type must be one of: {', '.join(SOURCE_TYPES)}.")

    if doc.ideology_tag not in IDEOLOGY_TAGS:
        errors.append(f"Ideology tag must be one of: {', '.join(IDEOLOGY_TAGS)}.")
    elif doc.source_type in ("gov_agency", "intl_org") and doc.ideology_tag != "NA":
        errors.append("Ideology tag must be 'NA' for gov_agency and intl_org sources.")

    if doc.research_theme not in RESEARCH_THEMES:
        errors.append(
            f"Research theme must be one of: {', '.join(RESEARCH_THEMES)}."
        )

    if doc.quadrad_actor not in QUADRAD_ACTORS:
        errors.append(
            f"QUADRAD actor must be one of: {', '.join(QUADRAD_ACTORS)}."
        )

    if doc.episode not in EPISODES:
        warnings.append(f"Episode '{doc.episode}' is not in the standard list.")

    # advisory fields
    if not doc.url.strip() or doc.url == "NA":
        warnings.append("URL is missing — consider adding a source link.")

    if not doc.source_name.strip():
        warnings.append("Source / institution name is missing.")

    return errors, warnings


def suggest_id(source: str, date: str, existing_ids: Set[str]) -> str:
    """Generate a collision-free document ID from source name and date.

    Format: ``{SourceSlug}_{YYYYMMDD}_{NNN}``

    Parameters
    ----------
    source:
        Institution or source name (alphanumerics extracted, max 15 chars).
    date:
        Publication date string (digits only extracted, max 8 chars).
    existing_ids:
        Set of IDs already in use.

    Returns
    -------
    str
        A unique candidate ID.
    """
    base = re.sub(r"[^A-Za-z0-9]", "", source)[:15]
    d = re.sub(r"[^0-9]", "", date)[:8]
    n, cand = 1, f"{base}_{d}_001"
    while cand in existing_ids:
        n += 1
        cand = f"{base}_{d}_{n:03d}"
    return cand
