"""
MARC-03 Corpus Builder -- Text ingestion utilities.

Provides URL scraping, PDF text extraction, and HTML stripping.
No local imports -- this module is a pure utility layer.
"""

import io
import re
from typing import Tuple

import requests


def wc(text: str) -> int:
    """Return the word count of a string."""
    return len(text.split()) if text.strip() else 0


def strip_html(html: str) -> str:
    """Strip HTML markup and return clean plain text.

    Uses BeautifulSoup when available; falls back to a regex strip.
    Removes script, style, nav, footer, header, and aside elements before
    extracting text so boilerplate is not included in the corpus.
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        lines = (line.strip() for line in soup.get_text("\n").splitlines())
        return "\n\n".join(line for line in lines if line)
    except ImportError:
        return re.sub(r"<[^>]+>", " ", html)


def scrape_url(url: str) -> Tuple[str, str]:
    """Fetch a URL and return (page_title, plain_text).

    Parameters
    ----------
    url:
        The URL to fetch.

    Returns
    -------
    Tuple[str, str]
        (title, plain_text) where title may be empty if not found.

    Raises
    ------
    requests.HTTPError
        If the server returns a 4xx or 5xx status code.
    requests.ConnectionError
        If the host cannot be reached.
    requests.Timeout
        If the request takes longer than 15 seconds.
    """
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (MARC-03 Corpus Builder)"},
        timeout=15,
    )
    response.raise_for_status()

    title = ""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "lxml")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
    except (ImportError, AttributeError):
        pass

    return title, strip_html(response.text)


def extract_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF file.

    Tries pdfplumber first for better layout handling, then falls back to
    PyPDF2. Raises ImportError if neither library is installed.

    Parameters
    ----------
    file_bytes:
        Raw bytes of the PDF file.

    Returns
    -------
    str
        Concatenated plain text from all pages.

    Raises
    ------
    ImportError
        If no supported PDF library is installed.
    """
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(pages).strip()
    except ImportError:
        pass

    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages).strip()
    except ImportError as exc:
        raise ImportError(
            "Install pdfplumber or PyPDF2 to enable PDF extraction."
        ) from exc
