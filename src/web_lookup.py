"""Web metadata lookup service for Bibliotheca AI.

Queries free public APIs to enrich book metadata with DOI, ISSN, and publisher.

Supported APIs:
- CrossRef (api.crossref.org): DOI/ISSN lookup, bibliographic search
- OpenLibrary (openlibrary.org): ISBN and title search for books
- Google Books (googleapis.com/books/v1): ISBN and title search
"""

import logging
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

import requests

from src.config import Settings, get_settings
from src.metadata import BookMetadata

logger = logging.getLogger("bibliotheca.web_lookup")

_USER_AGENT = "BibliothecaAI/1.0 (metadata enrichment; https://github.com/bibliotheca-ai)"


@dataclass
class WebMetadata:
    """Metadata retrieved from a web API."""

    title: str = ""
    author: str = ""
    isbn: str = ""
    doi: str = ""
    issn: str = ""
    publisher: str = ""
    year: Optional[int] = None
    source_api: str = ""  # "crossref" | "openlibrary" | "google_books"
    confidence: float = 0.0  # 0~1


class WebMetadataLookup:
    """Cascade web lookup across CrossRef, OpenLibrary, and Google Books."""

    def __init__(self, settings: Optional[Settings] = None):
        settings = settings or get_settings()
        self.timeout = settings.web_lookup_timeout
        self.enabled = settings.web_lookup_enabled
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _USER_AGENT

    def lookup(self, meta: BookMetadata) -> Optional[WebMetadata]:
        """Look up metadata using a cascade strategy.

        Order: ISBN APIs -> title+author via CrossRef -> title search fallback.
        Returns the best match or None.
        """
        if not self.enabled:
            return None

        candidates: list[WebMetadata] = []

        # 1) ISBN-based lookups (highest confidence)
        if meta.isbn:
            result = self._search_openlibrary(meta.isbn)
            if result:
                candidates.append(result)
            result = self._search_google_books(title="", isbn=meta.isbn)
            if result:
                candidates.append(result)

        # 2) Title + author via CrossRef (scholarly works)
        if meta.title:
            result = self._search_crossref(meta.title, meta.author)
            if result:
                candidates.append(result)

        # 3) Title-based fallbacks
        if meta.title and not candidates:
            result = self._search_openlibrary_by_title(meta.title)
            if result:
                candidates.append(result)
            result = self._search_google_books(title=meta.title, isbn="")
            if result:
                candidates.append(result)

        if not candidates:
            return None

        # Return highest-confidence result
        return max(candidates, key=lambda c: c.confidence)

    # ── API implementations ───────────────────────────────────────

    def _search_crossref(self, title: str, author: str) -> Optional[WebMetadata]:
        """Search CrossRef for bibliographic metadata."""
        query = title
        if author:
            query = f"{title} {author}"
        params = {"query.bibliographic": query, "rows": "3"}
        try:
            resp = self._session.get(
                "https://api.crossref.org/works",
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            items = resp.json().get("message", {}).get("items", [])
            if not items:
                return None

            best = items[0]
            cr_title = " ".join(best.get("title", []))

            # Confidence based on title similarity
            confidence = _title_similarity(title, cr_title)

            authors = best.get("author", [])
            author_str = ", ".join(
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in authors[:3]
            )

            doi = best.get("DOI", "")
            issn_list = best.get("ISSN", [])
            issn = issn_list[0] if issn_list else ""
            isbn_list = best.get("ISBN", [])
            isbn = isbn_list[0] if isbn_list else ""
            publisher = best.get("publisher", "")

            year = None
            date_parts = (
                best.get("published-print", {}).get("date-parts")
                or best.get("published-online", {}).get("date-parts")
                or best.get("issued", {}).get("date-parts")
            )
            if date_parts and date_parts[0]:
                year = date_parts[0][0]

            return WebMetadata(
                title=cr_title,
                author=author_str,
                isbn=isbn,
                doi=doi,
                issn=issn,
                publisher=publisher,
                year=year,
                source_api="crossref",
                confidence=confidence,
            )
        except Exception as e:
            logger.debug("CrossRef lookup failed: %s", e)
            return None

    def _search_openlibrary(self, isbn: str) -> Optional[WebMetadata]:
        """Look up a book by ISBN on OpenLibrary."""
        try:
            resp = self._session.get(
                f"https://openlibrary.org/isbn/{isbn}.json",
                timeout=self.timeout,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()

            title = data.get("title", "")
            publishers = data.get("publishers", [])
            publisher = publishers[0] if publishers else ""
            publish_date = data.get("publish_date", "")

            year = None
            if publish_date:
                import re
                year_match = re.search(r"\b(19|20)\d{2}\b", publish_date)
                if year_match:
                    year = int(year_match.group(0))

            return WebMetadata(
                title=title,
                isbn=isbn,
                publisher=publisher,
                year=year,
                source_api="openlibrary",
                confidence=0.9,  # ISBN match is high confidence
            )
        except Exception as e:
            logger.debug("OpenLibrary ISBN lookup failed: %s", e)
            return None

    def _search_openlibrary_by_title(self, title: str) -> Optional[WebMetadata]:
        """Search OpenLibrary by title."""
        params = {"title": title, "limit": "3"}
        try:
            resp = self._session.get(
                "https://openlibrary.org/search.json",
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            docs = resp.json().get("docs", [])
            if not docs:
                return None

            best = docs[0]
            ol_title = best.get("title", "")
            confidence = _title_similarity(title, ol_title)

            authors = best.get("author_name", [])
            author_str = ", ".join(authors[:3])
            isbn_list = best.get("isbn", [])
            isbn = isbn_list[0] if isbn_list else ""
            publishers = best.get("publisher", [])
            publisher = publishers[0] if publishers else ""
            year = best.get("first_publish_year")

            return WebMetadata(
                title=ol_title,
                author=author_str,
                isbn=isbn,
                publisher=publisher,
                year=year,
                source_api="openlibrary",
                confidence=confidence,
            )
        except Exception as e:
            logger.debug("OpenLibrary title search failed: %s", e)
            return None

    def _search_google_books(self, title: str, isbn: str) -> Optional[WebMetadata]:
        """Search Google Books by ISBN or title."""
        if isbn:
            q = f"isbn:{isbn}"
        elif title:
            q = f"intitle:{title}"
        else:
            return None

        params = {"q": q, "maxResults": "3"}
        try:
            resp = self._session.get(
                "https://www.googleapis.com/books/v1/volumes",
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                return None

            info = items[0].get("volumeInfo", {})
            gb_title = info.get("title", "")

            if isbn:
                confidence = 0.85
            else:
                confidence = _title_similarity(title, gb_title)

            authors = info.get("authors", [])
            author_str = ", ".join(authors[:3])
            publisher = info.get("publisher", "")
            published_date = info.get("publishedDate", "")

            year = None
            if published_date:
                import re
                year_match = re.search(r"\b(19|20)\d{2}\b", published_date)
                if year_match:
                    year = int(year_match.group(0))

            # Extract ISBNs from industry identifiers
            gb_isbn = ""
            for ident in info.get("industryIdentifiers", []):
                if ident.get("type") in ("ISBN_13", "ISBN_10"):
                    gb_isbn = ident.get("identifier", "")
                    break

            return WebMetadata(
                title=gb_title,
                author=author_str,
                isbn=gb_isbn or isbn,
                publisher=publisher,
                year=year,
                source_api="google_books",
                confidence=confidence,
            )
        except Exception as e:
            logger.debug("Google Books lookup failed: %s", e)
            return None

    # ── Merge helper ──────────────────────────────────────────────

    def merge_into(self, target: BookMetadata, web: WebMetadata) -> BookMetadata:
        """Merge web metadata into target, filling only empty fields.

        Existing values in target are never overwritten.
        """
        if not target.doi and web.doi:
            target.doi = web.doi
        if not target.issn and web.issn:
            target.issn = web.issn
        if not target.publisher and web.publisher:
            target.publisher = web.publisher
        if not target.isbn and web.isbn:
            target.isbn = web.isbn
        if not target.author and web.author:
            target.author = web.author
        if target.year is None and web.year is not None:
            target.year = web.year
        return target


def _title_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two titles (0~1)."""
    if not a or not b:
        return 0.0
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)
