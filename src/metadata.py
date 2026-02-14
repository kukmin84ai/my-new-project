"""Metadata extraction and SQLite manifest for Bibliotheca AI.

Provides:
- BookMetadata: dataclass for book-level metadata
- MetadataStore: SQLite-based manifest tracking processing state,
  file hashes for incremental processing, and book metadata
"""

import hashlib
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from src.config import Settings, get_settings

logger = logging.getLogger("bibliotheca.metadata")


@dataclass
class BookMetadata:
    """Metadata for a single book/document."""

    title: str = ""
    author: str = ""
    isbn: str = ""
    year: Optional[int] = None
    file_path: str = ""
    file_hash: str = ""
    page_count: int = 0
    language: str = ""


class MetadataStore:
    """SQLite-based metadata and processing manifest."""

    def __init__(self, db_path: Optional[str] = None):
        settings = get_settings()
        self.db_path = db_path or str(settings.sqlite_db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        logger.info("MetadataStore initialized at %s", self.db_path)

    def _init_db(self) -> None:
        """Create tables if not exist."""
        cursor = self.conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL DEFAULT '',
                isbn TEXT NOT NULL DEFAULT '',
                year INTEGER,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                page_count INTEGER DEFAULT 0,
                language TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS processing_manifest (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                chunk_count INTEGER DEFAULT 0,
                error_message TEXT DEFAULT '',
                started_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_books_file_hash
                ON books(file_hash);
            CREATE INDEX IF NOT EXISTS idx_manifest_status
                ON processing_manifest(status);
            CREATE INDEX IF NOT EXISTS idx_manifest_file_hash
                ON processing_manifest(file_hash);
            """
        )
        self.conn.commit()

    def compute_file_hash(self, file_path: Path) -> str:
        """SHA-256 hash of file contents."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                sha256.update(block)
        return sha256.hexdigest()

    def is_file_processed(self, file_path: Path) -> bool:
        """Check if file already processed (by hash match).

        Returns True only if the file hash matches a completed entry.
        """
        if not file_path.exists():
            return False

        current_hash = self.compute_file_hash(file_path)
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT status FROM processing_manifest "
            "WHERE file_path = ? AND file_hash = ? AND status = 'done'",
            (str(file_path), current_hash),
        )
        return cursor.fetchone() is not None

    def register_file(self, file_path: Path, metadata: BookMetadata) -> None:
        """Register or update a book in the metadata store."""
        now = datetime.now(timezone.utc).isoformat()
        file_hash = self.compute_file_hash(file_path)

        cursor = self.conn.cursor()

        # Upsert book metadata
        cursor.execute(
            """
            INSERT INTO books (title, author, isbn, year, file_path,
                             file_hash, page_count, language, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                title = excluded.title,
                author = excluded.author,
                isbn = excluded.isbn,
                year = excluded.year,
                file_hash = excluded.file_hash,
                page_count = excluded.page_count,
                language = excluded.language,
                updated_at = excluded.updated_at
            """,
            (
                metadata.title,
                metadata.author,
                metadata.isbn,
                metadata.year,
                str(file_path),
                file_hash,
                metadata.page_count,
                metadata.language,
                now,
                now,
            ),
        )

        # Upsert processing manifest entry
        cursor.execute(
            """
            INSERT INTO processing_manifest (file_path, file_hash, status,
                                            created_at, updated_at)
            VALUES (?, ?, 'pending', ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_hash = excluded.file_hash,
                status = 'pending',
                error_message = '',
                updated_at = excluded.updated_at
            """,
            (str(file_path), file_hash, now, now),
        )

        self.conn.commit()
        logger.info("Registered file: %s", file_path)

    def update_status(
        self,
        file_path: str,
        status: str,
        chunk_count: int = 0,
        error_message: str = "",
    ) -> None:
        """Update processing status for a file.

        Args:
            file_path: Path to the file.
            status: One of 'pending', 'processing', 'done', 'error'.
            chunk_count: Number of chunks produced (set on 'done').
            error_message: Error details (set on 'error').
        """
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.cursor()

        updates = {"status": status, "updated_at": now}
        if status == "processing":
            updates["started_at"] = now
        elif status == "done":
            updates["completed_at"] = now
            updates["chunk_count"] = chunk_count
        elif status == "error":
            updates["error_message"] = error_message

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [file_path]

        cursor.execute(
            f"UPDATE processing_manifest SET {set_clause} WHERE file_path = ?",
            values,
        )
        self.conn.commit()
        logger.info("Updated status for %s: %s", file_path, status)

    def get_all_books(self) -> list[BookMetadata]:
        """Retrieve all registered books."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM books ORDER BY created_at DESC")
        rows = cursor.fetchall()

        return [
            BookMetadata(
                title=row["title"],
                author=row["author"],
                isbn=row["isbn"],
                year=row["year"],
                file_path=row["file_path"],
                file_hash=row["file_hash"],
                page_count=row["page_count"],
                language=row["language"],
            )
            for row in rows
        ]

    def get_pending_files(self) -> list[dict]:
        """Get files that need processing."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT file_path, file_hash, status FROM processing_manifest "
            "WHERE status IN ('pending', 'error') ORDER BY created_at"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_processing_stats(self) -> dict:
        """Get summary statistics of processing manifest."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT status, COUNT(*) as count FROM processing_manifest GROUP BY status"
        )
        stats = {row["status"]: row["count"] for row in cursor.fetchall()}
        cursor.execute("SELECT SUM(chunk_count) as total FROM processing_manifest")
        row = cursor.fetchone()
        stats["total_chunks"] = row["total"] or 0
        return stats

    def extract_metadata_from_text(
        self, text: str, file_path: str
    ) -> BookMetadata:
        """Extract title, author, ISBN, year from first pages of text.

        Uses regex heuristics on the first ~2000 characters.
        """
        sample = text[:2000]
        metadata = BookMetadata(file_path=file_path)

        # Title: first non-empty line or first markdown header
        title_match = re.search(r"^#\s+(.+)$", sample, re.MULTILINE)
        if title_match:
            metadata.title = title_match.group(1).strip()
        else:
            lines = [l.strip() for l in sample.split("\n") if l.strip()]
            if lines:
                metadata.title = lines[0][:200]

        # Author: look for "by Author" or "Author:" patterns
        author_match = re.search(
            r"(?:by|author[:\s])\s*([A-Z][a-zA-Z\s,.\-']+)",
            sample,
            re.IGNORECASE,
        )
        if author_match:
            metadata.author = author_match.group(1).strip().rstrip(",.")

        # ISBN: standard ISBN-10 or ISBN-13
        isbn_match = re.search(
            r"ISBN[:\s-]*([\d\-]{10,17})", sample, re.IGNORECASE
        )
        if isbn_match:
            metadata.isbn = isbn_match.group(1).replace("-", "")

        # Year: 4-digit year between 1900 and 2099
        year_match = re.search(r"\b(19|20)\d{2}\b", sample)
        if year_match:
            metadata.year = int(year_match.group(0))

        return metadata

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
