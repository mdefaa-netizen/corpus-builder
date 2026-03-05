"""
MARC-03 Corpus Builder -- Data models and controlled vocabularies.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

# ── CONTROLLED VOCABULARIES ──────────────────────────────────────────────────

LANGUAGES: List[str] = ["en", "ar", "fr"]

SOURCE_TYPES: List[str] = [
    "think_tank", "gov_agency", "intl_org", "media", "academic"
]

IDEOLOGY_TAGS: List[str] = [
    "conservative_hawkish", "liberal_multilateral", "restraint", "centrist", "NA"
]

PERIODS: List[str] = ["2023", "2024", "2025", "2026"]

REGIONS: List[str] = [
    "Red_Sea", "MENA", "Gulf", "Levant", "North_Africa", "Syria", "Global", "Other"
]

RESEARCH_THEMES: List[str] = [
    "Algorithmic_Diplomacy",
    "Narrative_Stabilization",
    "Syrian_Transition",
    "AI_Mediation",
    "Think_Tank_Discourse",
    "Trilingual_Analysis",
    "Digital_Governance",
    "Conflict_Resolution",
    "MENA_Geopolitics",
    "Cyber_Leadership",
]

QUADRAD_ACTORS: List[str] = [
    "Saudi_Arabia", "Qatar", "UAE", "Turkey", "All_four", "Not_applicable"
]

EPISODES: List[str] = [
    "EP-01_Syria_Ceasefire_2024",
    "EP-02_Red_Sea_Houthi_2023-24",
    "EP-03_Gulf_Normalization",
    "EP-04_Digital_AI_Diplomacy",
    "EP-05_Unassigned",
]

# ── FLATTENING AUDIT ─────────────────────────────────────────────────────────

AUDIT_DIMENSIONS: List[str] = ["agency", "uncertainty", "temporal", "security"]

AUDIT_RUBRIC: Dict[str, Dict] = {
    "agency": {
        "label": "Agency Flattening",
        "description": "Degree to which actor agency is reduced or collapsed",
        "anchors": {
            0: "Complex, distributed agency preserved",
            1: "Minor simplification of actor roles",
            2: "Moderate reduction — key actors merged or omitted",
            3: "Agency collapsed to a single monolithic actor",
        },
    },
    "uncertainty": {
        "label": "Uncertainty Flattening",
        "description": "Degree to which ambiguity and uncertainty are erased",
        "anchors": {
            0: "Uncertainty explicitly preserved throughout",
            1: "Minor hedging removed",
            2: "Moderate — probabilistic language replaced with assertions",
            3: "False certainty — all uncertainty erased",
        },
    },
    "temporal": {
        "label": "Temporal Flattening",
        "description": "Degree to which historical and temporal context is collapsed",
        "anchors": {
            0: "Full temporal context present",
            1: "Minor timeline simplification",
            2: "Moderate — historical causes absent",
            3: "Ahistorical — temporal context fully collapsed",
        },
    },
    "security": {
        "label": "Security Flattening",
        "description": "Degree to which security discourse is hypersecuritized",
        "anchors": {
            0: "Nuanced, multi-sector security framing",
            1: "Mild securitization bias",
            2: "Moderate — non-security dimensions marginalized",
            3: "Hypersecuritized — complexity erased",
        },
    },
}

# ── INSTITUTION REGISTRY ─────────────────────────────────────────────────────

INSTITUTION_AUTOFILL: Dict[str, Tuple[str, str]] = {
    # Conservative / Hawkish
    "Heritage Foundation":        ("think_tank", "conservative_hawkish"),
    "AEI":                        ("think_tank", "conservative_hawkish"),
    "Hudson Institute":           ("think_tank", "conservative_hawkish"),
    "Washington Institute":       ("think_tank", "conservative_hawkish"),
    "FDD":                        ("think_tank", "conservative_hawkish"),
    "JINSA":                      ("think_tank", "conservative_hawkish"),
    "MEF":                        ("think_tank", "conservative_hawkish"),
    "Emirates Policy Center":     ("think_tank", "conservative_hawkish"),
    "Faisal Center":              ("think_tank", "conservative_hawkish"),
    "Arab Gulf States Institute": ("think_tank", "conservative_hawkish"),
    # Liberal / Multilateral
    "Brookings":                  ("think_tank", "liberal_multilateral"),
    "Carnegie":                   ("think_tank", "liberal_multilateral"),
    "Atlantic Council":           ("think_tank", "liberal_multilateral"),
    "Wilson Center":              ("think_tank", "liberal_multilateral"),
    "Human Rights Watch":         ("think_tank", "liberal_multilateral"),
    "ICG":                        ("think_tank", "liberal_multilateral"),
    "Al Jazeera Centre":          ("media",      "liberal_multilateral"),
    "Middle East Eye":            ("media",      "liberal_multilateral"),
    # Centrist
    "CFR":                        ("think_tank", "centrist"),
    "CSIS":                       ("think_tank", "centrist"),
    "RAND":                       ("think_tank", "centrist"),
    "IISS":                       ("think_tank", "centrist"),
    "Chatham House":              ("think_tank", "centrist"),
    "IFRI":                       ("think_tank", "centrist"),
    "SWP":                        ("think_tank", "centrist"),
    "ECFR":                       ("think_tank", "centrist"),
    "Al Monitor":                 ("media",      "centrist"),
    # Restraint
    "Quincy Institute":           ("think_tank", "restraint"),
    "Cato Institute":             ("think_tank", "restraint"),
    "Stimson Center":             ("think_tank", "restraint"),
    # Government agencies
    "US DoD":                     ("gov_agency", "NA"),
    "US DoS":                     ("gov_agency", "NA"),
    "US Congress":                ("gov_agency", "NA"),
    "White House":                ("gov_agency", "NA"),
    "US CENTCOM":                 ("gov_agency", "NA"),
    "NSC":                        ("gov_agency", "NA"),
    # International organisations
    "UN":                         ("intl_org",   "NA"),
    "Arab League":                ("intl_org",   "NA"),
    "EU":                         ("intl_org",   "NA"),
    "NATO":                       ("intl_org",   "NA"),
    "OIC":                        ("intl_org",   "NA"),
    "GCC":                        ("intl_org",   "NA"),
}

# ── DATA CLASSES ─────────────────────────────────────────────────────────────

@dataclass
class Document:
    """A single corpus document with all metadata fields."""

    doc_id:           str = ""
    title:            str = ""
    text:             str = ""
    episode:          str = "EP-05_Unassigned"
    research_theme:   str = "Syrian_Transition"
    region:           str = "Syria"
    period:           str = "2024"
    language:         str = "en"
    source_type:      str = "think_tank"
    source_name:      str = ""
    ideology_tag:     str = "NA"
    quadrad_actor:    str = "Not_applicable"
    publication_date: str = ""
    url:              str = "NA"
    notes:            str = ""
    word_count:       int = 0
    added_at:         str = ""


@dataclass
class AuditEntry:
    """Flattening audit scores for a single document by one rater."""

    audit_id:          str = ""
    doc_id:            str = ""
    rater:             str = ""
    agency_score:      int = 0
    uncertainty_score: int = 0
    temporal_score:    int = 0
    security_score:    int = 0
    total_score:       int = 0
    notes:             str = ""
    rated_at:          str = ""
