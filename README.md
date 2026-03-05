# MARC-03 Corpus Builder

Multi-Agent Research Corpus Manager for PhD dissertation research.

**Dissertation:** "The Algorithmic Pivot: Trilingual AI-Mediated Narrative
Stabilization in U.S. Think Tank Briefs on the Syrian Transition (2023-2025)"
**Researcher:** Mohamed Defaa · PhD · Cyber Leadership · Capitol Technology University
**Chair:** Dr. Anthony Dehnashi

---

## Architecture

```
app.py           Main Streamlit application and UI rendering
models.py        Data classes (Document, AuditEntry) and controlled vocabularies
storage.py       SQLite CRUD layer (cached connection, WAL mode, schema migration)
ingestion.py     URL scraping, PDF extraction, HTML stripping
validation.py    Document validation rules and doc_id suggestion
export.py        CSV export, MARC-02 context blocks, audit CSV, corpus stats
requirements.txt Python dependencies
render.yaml      Render.com deployment configuration
README.md        This file
```

---

## Local Development

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
git clone https://github.com/mdefaa-netizen/corpus-builder
cd corpus-builder
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. The SQLite database is created as
`algpivot_corpus.db` in the working directory when running locally.

---

## Deployment on Render

1. Push the repository to GitHub.
2. Log in to [render.com](https://render.com) and click **New > Web Service**.
3. Connect your GitHub repository.
4. Render detects `render.yaml` automatically -- review and confirm.
5. Click **Create Web Service**.

The `render.yaml` provisions:
- A Python web service running `streamlit run app.py`
- A 1 GB persistent disk mounted at `/data`

The database is stored at `/data/algpivot_corpus.db` and survives redeployments.

No API keys are required. The application is fully self-contained.

---

## Features

### Episode selector (global)

The sidebar **Episode filter** propagates to all tabs.

| Episode | Description |
|---------|-------------|
| EP-01_Syria_Ceasefire_2024 | Syrian ceasefire monitoring (2024) |
| EP-02_Red_Sea_Houthi_2023-24 | Red Sea / Houthi campaign coverage |
| EP-03_Gulf_Normalization | Gulf normalisation discourse |
| EP-04_Digital_AI_Diplomacy | AI and digital diplomacy narratives |
| EP-05_Unassigned | Default / unclassified |

### Document ingestion

Three methods on the **Add Document** tab:

- **Paste text** -- Direct entry of any text
- **Scrape URL** -- Fetches and strips HTML from any public URL
- **Upload PDF** -- Extracts text via pdfplumber (fallback: PyPDF2)

### Metadata fields

| Field | Values |
|-------|--------|
| Language | en, ar, fr |
| Source type | think_tank, gov_agency, intl_org, media, academic |
| Ideology tag | conservative_hawkish, liberal_multilateral, restraint, centrist, NA |
| Research theme | 10 dissertation themes |
| QUADRAD actor | Saudi_Arabia, Qatar, UAE, Turkey, All_four, Not_applicable |
| Episode | 5 predefined episodes |

Institution autofill pre-populates source type and ideology tag for 40+
institutions. Doc ID is auto-generated from source name and publication date.

### Flattening Audit

Four-dimension rubric for measuring algorithmic narrative flattening:

| Dimension | Description | Scale |
|-----------|-------------|-------|
| Agency | Degree to which actor agency is reduced | 0-3 |
| Uncertainty | Degree to which ambiguity is erased | 0-3 |
| Temporal | Degree to which historical context collapses | 0-3 |
| Security | Degree to which security framing dominates | 0-3 |

**Total: /12** (0 = no flattening, 12 = maximum flattening)

Multiple raters can score the same document. Export the audit CSV and compute
Cohen's Kappa for inter-rater reliability:

```r
# R
library(irr)
kappa2(ratings[, c("rater1", "rater2")])
```

```python
# Python
from sklearn.metrics import cohen_kappa_score
cohen_kappa_score(rater1_scores, rater2_scores)
```

### Validation

The **Validate** tab runs corpus-wide checks. Export is blocked until all
errors are resolved.

**Errors** (block save/export):
- Missing doc_id, text, or publication date
- Duplicate doc_id
- Invalid date format (must be YYYY-MM-DD)
- Invalid controlled vocabulary value
- Ideology tag not NA for gov_agency / intl_org sources

**Warnings** (advisory, do not block export):
- Text below 150 words
- Missing URL
- Missing institution name

### Export

- **Corpus CSV** -- All metadata; optional full-text column
- **Audit CSV** -- All flattening scores for inter-rater analysis
- **MARC-02 context block** -- Formatted block for pasting into MARC-02

---

## Database

SQLite with WAL mode. Schema:

```sql
documents (
    doc_id, title, text, episode, research_theme, region, period,
    language, source_type, source_name, ideology_tag, quadrad_actor,
    publication_date, url, notes, word_count, added_at
)

audit_entries (
    audit_id, doc_id, rater, agency_score, uncertainty_score,
    temporal_score, security_score, total_score, notes, rated_at
)
```

Schema migrations run automatically on startup. Upgrading from the original
`corpus_app.py` is non-destructive -- existing documents are preserved.
