"""Tests for web metadata lookup service (mock-based, no real HTTP calls)."""

import pytest
from unittest.mock import patch, MagicMock

from src.metadata import BookMetadata
from src.web_lookup import WebMetadataLookup, WebMetadata, _title_similarity
from src.config import Settings


@pytest.fixture
def lookup():
    """WebMetadataLookup with short timeout for tests."""
    settings = Settings(web_lookup_enabled=True, web_lookup_timeout=5)
    return WebMetadataLookup(settings)


@pytest.fixture
def lookup_disabled():
    settings = Settings(web_lookup_enabled=False, web_lookup_timeout=5)
    return WebMetadataLookup(settings)


# ── Title similarity ─────────────────────────────────────────────

def test_title_similarity_identical():
    assert _title_similarity("EMC for Product Designers", "EMC for Product Designers") == 1.0


def test_title_similarity_partial():
    score = _title_similarity("EMC for Product Designers", "EMC Product Designers Guide")
    assert 0.3 < score < 1.0


def test_title_similarity_empty():
    assert _title_similarity("", "anything") == 0.0
    assert _title_similarity("something", "") == 0.0


# ── Disabled lookup ──────────────────────────────────────────────

def test_lookup_disabled_returns_none(lookup_disabled):
    meta = BookMetadata(title="Test Book", isbn="1234567890")
    assert lookup_disabled.lookup(meta) is None


# ── CrossRef mock ────────────────────────────────────────────────

def test_crossref_search(lookup):
    mock_response = {
        "message": {
            "items": [
                {
                    "title": ["EMC for Product Designers"],
                    "author": [{"given": "Tim", "family": "Williams"}],
                    "DOI": "10.1016/B978-0-08-097709-6.00001-X",
                    "ISSN": ["0950-1371"],
                    "ISBN": [],
                    "publisher": "Newnes",
                    "issued": {"date-parts": [[2017]]},
                }
            ]
        }
    }
    with patch.object(lookup._session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = lookup._search_crossref("EMC for Product Designers", "Tim Williams")

    assert result is not None
    assert result.doi == "10.1016/B978-0-08-097709-6.00001-X"
    assert result.issn == "0950-1371"
    assert result.publisher == "Newnes"
    assert result.year == 2017
    assert result.source_api == "crossref"
    assert result.confidence > 0


def test_crossref_empty_results(lookup):
    mock_response = {"message": {"items": []}}
    with patch.object(lookup._session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = lookup._search_crossref("Nonexistent Book", "")

    assert result is None


# ── OpenLibrary ISBN mock ────────────────────────────────────────

def test_openlibrary_isbn(lookup):
    mock_response = {
        "title": "EMC for Product Designers",
        "publishers": ["Newnes"],
        "publish_date": "2017",
    }
    with patch.object(lookup._session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = lookup._search_openlibrary("9780081007167")

    assert result is not None
    assert result.isbn == "9780081007167"
    assert result.publisher == "Newnes"
    assert result.year == 2017
    assert result.confidence == 0.9


def test_openlibrary_isbn_not_found(lookup):
    with patch.object(lookup._session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        result = lookup._search_openlibrary("0000000000")

    assert result is None


# ── OpenLibrary title search mock ────────────────────────────────

def test_openlibrary_title_search(lookup):
    mock_response = {
        "docs": [
            {
                "title": "EMC for Product Designers",
                "author_name": ["Tim Williams"],
                "isbn": ["9780081007167"],
                "publisher": ["Newnes"],
                "first_publish_year": 2017,
            }
        ]
    }
    with patch.object(lookup._session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = lookup._search_openlibrary_by_title("EMC for Product Designers")

    assert result is not None
    assert result.publisher == "Newnes"
    assert result.source_api == "openlibrary"


# ── Google Books mock ────────────────────────────────────────────

def test_google_books_isbn(lookup):
    mock_response = {
        "items": [
            {
                "volumeInfo": {
                    "title": "EMC for Product Designers",
                    "authors": ["Tim Williams"],
                    "publisher": "Newnes",
                    "publishedDate": "2017-01-01",
                    "industryIdentifiers": [
                        {"type": "ISBN_13", "identifier": "9780081007167"}
                    ],
                }
            }
        ]
    }
    with patch.object(lookup._session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = lookup._search_google_books(title="", isbn="9780081007167")

    assert result is not None
    assert result.isbn == "9780081007167"
    assert result.publisher == "Newnes"
    assert result.confidence == 0.85


def test_google_books_no_args(lookup):
    result = lookup._search_google_books(title="", isbn="")
    assert result is None


# ── Merge logic ──────────────────────────────────────────────────

def test_merge_fills_empty_fields(lookup):
    target = BookMetadata(title="EMC Book", author="Tim Williams", isbn="123")
    web = WebMetadata(
        doi="10.1234/test",
        issn="0950-1371",
        publisher="Newnes",
        isbn="999",  # should NOT overwrite existing
        author="Other Author",  # should NOT overwrite existing
        year=2020,
    )

    result = lookup.merge_into(target, web)

    assert result.doi == "10.1234/test"
    assert result.issn == "0950-1371"
    assert result.publisher == "Newnes"
    assert result.isbn == "123"  # preserved
    assert result.author == "Tim Williams"  # preserved
    assert result.year == 2020


def test_merge_does_not_overwrite(lookup):
    target = BookMetadata(
        title="Test", doi="existing-doi", issn="existing-issn",
        publisher="Existing Publisher",
    )
    web = WebMetadata(
        doi="new-doi", issn="new-issn", publisher="New Publisher",
    )

    result = lookup.merge_into(target, web)

    assert result.doi == "existing-doi"
    assert result.issn == "existing-issn"
    assert result.publisher == "Existing Publisher"


# ── Full cascade lookup mock ─────────────────────────────────────

def test_lookup_cascade_isbn_first(lookup):
    """When ISBN is available, ISBN-based APIs are tried first."""
    meta = BookMetadata(title="Test Book", isbn="1234567890")

    ol_result = WebMetadata(
        title="Test Book", isbn="1234567890",
        publisher="Publisher A", confidence=0.9, source_api="openlibrary",
    )
    with patch.object(lookup, "_search_openlibrary", return_value=ol_result), \
         patch.object(lookup, "_search_google_books", return_value=None), \
         patch.object(lookup, "_search_crossref", return_value=None):
        result = lookup.lookup(meta)

    assert result is not None
    assert result.source_api == "openlibrary"
    assert result.confidence == 0.9


def test_lookup_cascade_falls_through(lookup):
    """When ISBN lookup fails, falls through to title search."""
    meta = BookMetadata(title="Some Book")

    cr_result = WebMetadata(
        title="Some Book", doi="10.1234/x",
        confidence=0.8, source_api="crossref",
    )
    with patch.object(lookup, "_search_crossref", return_value=cr_result):
        result = lookup.lookup(meta)

    assert result is not None
    assert result.source_api == "crossref"


# ── BookMetadata new fields ──────────────────────────────────────

def test_book_metadata_new_fields():
    meta = BookMetadata(
        title="Test",
        doi="10.1234/test",
        issn="1234-5678",
        publisher="Test Publisher",
    )
    assert meta.doi == "10.1234/test"
    assert meta.issn == "1234-5678"
    assert meta.publisher == "Test Publisher"


def test_book_metadata_defaults():
    meta = BookMetadata()
    assert meta.doi == ""
    assert meta.issn == ""
    assert meta.publisher == ""


# ── Settings new fields ─────────────────────────────────────────

def test_settings_web_lookup_defaults():
    s = Settings()
    assert s.web_lookup_enabled is True
    assert s.web_lookup_timeout == 10
