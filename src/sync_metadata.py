"""Synchronize web-sourced metadata (DOI, ISSN, publisher) into existing books.

Usage:
    python -m src.sync_metadata              # sync all books
    python -m src.sync_metadata --dry-run    # preview changes only
    python -m src.sync_metadata --book "EMC for Product Designers"
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from src.config import get_settings, setup_logging
from src.metadata import MetadataStore, BookMetadata
from src.web_lookup import WebMetadataLookup

logger = logging.getLogger("bibliotheca.sync_metadata")


def sync_books(
    dry_run: bool = False,
    book_filter: str = "",
    confidence_threshold: float = 0.5,
) -> list[dict]:
    """Synchronize web metadata for all (or filtered) books.

    Args:
        dry_run: If True, only report changes without writing to DB.
        book_filter: If set, only sync books whose title contains this string.
        confidence_threshold: Minimum confidence to accept web results.

    Returns:
        List of change report dicts for each book processed.
    """
    settings = get_settings()
    meta_store = MetadataStore()
    lookup = WebMetadataLookup(settings)

    books = meta_store.get_all_books()
    if book_filter:
        books = [b for b in books if book_filter.lower() in b.title.lower()]

    logger.info("Syncing metadata for %d book(s)...", len(books))
    report: list[dict] = []

    for book in books:
        entry: dict = {
            "title": book.title,
            "file_path": book.file_path,
            "status": "skipped",
            "changes": {},
        }

        web_meta = lookup.lookup(book)
        if not web_meta:
            entry["status"] = "no_results"
            report.append(entry)
            logger.info("  [%s] No web results found", book.title)
            continue

        if web_meta.confidence < confidence_threshold:
            entry["status"] = "low_confidence"
            entry["confidence"] = web_meta.confidence
            entry["source_api"] = web_meta.source_api
            report.append(entry)
            logger.info(
                "  [%s] Low confidence %.2f from %s — skipped",
                book.title, web_meta.confidence, web_meta.source_api,
            )
            continue

        # Compute changes (only empty fields get filled)
        changes: dict = {}
        if not book.doi and web_meta.doi:
            changes["doi"] = web_meta.doi
        if not book.issn and web_meta.issn:
            changes["issn"] = web_meta.issn
        if not book.publisher and web_meta.publisher:
            changes["publisher"] = web_meta.publisher
        if not book.isbn and web_meta.isbn:
            changes["isbn"] = web_meta.isbn
        if not book.author and web_meta.author:
            changes["author"] = web_meta.author
        if book.year is None and web_meta.year is not None:
            changes["year"] = web_meta.year

        if not changes:
            entry["status"] = "up_to_date"
            report.append(entry)
            logger.info("  [%s] Already up to date", book.title)
            continue

        entry["changes"] = changes
        entry["confidence"] = web_meta.confidence
        entry["source_api"] = web_meta.source_api

        if dry_run:
            entry["status"] = "would_update"
            logger.info(
                "  [%s] Would update: %s (confidence=%.2f, source=%s)",
                book.title, changes, web_meta.confidence, web_meta.source_api,
            )
        else:
            # Apply changes to BookMetadata and update DB
            lookup.merge_into(book, web_meta)
            _update_book_in_db(meta_store, book)
            entry["status"] = "updated"
            logger.info(
                "  [%s] Updated: %s (confidence=%.2f, source=%s)",
                book.title, changes, web_meta.confidence, web_meta.source_api,
            )

        report.append(entry)

    meta_store.close()
    return report


def _update_book_in_db(meta_store: MetadataStore, book: BookMetadata) -> None:
    """Update a book's metadata in SQLite."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = meta_store.conn.cursor()
    cursor.execute(
        """
        UPDATE books SET
            doi = ?, issn = ?, publisher = ?,
            isbn = ?, author = ?, year = ?,
            updated_at = ?
        WHERE file_path = ?
        """,
        (
            book.doi, book.issn, book.publisher,
            book.isbn, book.author, book.year,
            now, book.file_path,
        ),
    )
    meta_store.conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync web metadata (DOI/ISSN/publisher) for existing books"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without writing to DB",
    )
    parser.add_argument(
        "--book", type=str, default="",
        help="Filter by book title (substring match)",
    )
    parser.add_argument(
        "--confidence", type=float, default=0.5,
        help="Minimum confidence threshold (default: 0.5)",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        help="Logging level",
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    report = sync_books(
        dry_run=args.dry_run,
        book_filter=args.book,
        confidence_threshold=args.confidence,
    )

    # Print JSON report
    print(json.dumps(report, indent=2, ensure_ascii=False))

    updated = sum(1 for r in report if r["status"] in ("updated", "would_update"))
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Summary: {updated}/{len(report)} books enriched")


if __name__ == "__main__":
    main()
