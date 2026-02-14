#!/usr/bin/env python3
"""One-time metadata correction script.

Re-parses all book file_path values through the filename-based metadata parser,
updates SQLite records, then propagates corrected book_title/author to LanceDB.
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.metadata import extract_metadata_from_filename, _clean_text_metadata


def fix_sqlite(db_path: str) -> dict[str, dict]:
    """Re-parse filenames and update SQLite book metadata.

    Returns a mapping of file_path -> {old_title, new_title, old_author, new_author}
    for use in the LanceDB update step.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, author, year, file_path FROM books")
    rows = cursor.fetchall()

    changes: dict[str, dict] = {}

    for row in rows:
        file_path = row["file_path"]
        old_title = row["title"]
        old_author = row["author"]
        old_year = row["year"]

        # Parse filename
        meta = extract_metadata_from_filename(file_path)

        new_title = meta.title if meta.title else _clean_text_metadata(old_title)
        new_author = meta.author if meta.author else _clean_text_metadata(old_author)
        # Reject paragraph-length authors from OCR
        if len(new_author) > 80:
            new_author = ""
        new_year = meta.year if meta.year else old_year

        if new_title != old_title or new_author != old_author or new_year != old_year:
            cursor.execute(
                "UPDATE books SET title = ?, author = ?, year = ? WHERE id = ?",
                (new_title, new_author, new_year, row["id"]),
            )
            changes[file_path] = {
                "old_title": old_title,
                "new_title": new_title,
                "old_author": old_author,
                "new_author": new_author,
            }
            print(f"  [{row['id']}] {Path(file_path).name[:60]}")
            if old_title != new_title:
                print(f"       title: {old_title!r} -> {new_title!r}")
            if old_author != new_author:
                print(f"       author: {old_author!r} -> {new_author!r}")
            if old_year != new_year:
                print(f"       year: {old_year} -> {new_year}")

    conn.commit()
    conn.close()
    return changes


def fix_lancedb(lancedb_dir: str, changes: dict[str, dict]) -> int:
    """Update book_title and author in LanceDB documents table."""
    import lancedb

    db = lancedb.connect(lancedb_dir)
    if "documents" not in db.table_names():
        print("  No documents table found in LanceDB — skipping")
        return 0

    table = db.open_table("documents")
    updated = 0

    for file_path, change in changes.items():
        old_title = change["old_title"]
        new_title = change["new_title"]
        new_author = change["new_author"]

        # Find rows matching this source file
        try:
            # Update book_title and author for all chunks from this file
            rows = table.search().where(f"source_file = '{file_path}'").limit(10000).to_list()
            if not rows:
                continue

            # LanceDB update: delete and re-add with corrected metadata
            for row in rows:
                row["book_title"] = new_title
                row["author"] = new_author

            table.delete(f"source_file = '{file_path}'")
            table.add(rows)
            updated += len(rows)
            print(f"  Updated {len(rows)} chunks for: {Path(file_path).name[:50]}")
        except Exception as e:
            print(f"  Error updating {file_path}: {e}")

    return updated


def main():
    project_root = Path(__file__).resolve().parent.parent
    db_path = str(project_root / "bibliotheca_meta.db")
    lancedb_dir = str(project_root / "lancedb_data")

    print("=== Step 1: Fix SQLite metadata ===")
    changes = fix_sqlite(db_path)
    print(f"\nUpdated {len(changes)} books in SQLite\n")

    print("=== Step 2: Fix LanceDB chunk metadata ===")
    updated = fix_lancedb(lancedb_dir, changes)
    print(f"\nUpdated {updated} chunks in LanceDB\n")

    # Verify
    print("=== Verification ===")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT title, author, year, file_path FROM books ORDER BY id")
    for row in cursor.fetchall():
        print(f"  {row['title'][:50]:50s} | {row['author'][:30]:30s} | {row['year']} | {Path(row['file_path']).name[:30]}")
    conn.close()


if __name__ == "__main__":
    main()
