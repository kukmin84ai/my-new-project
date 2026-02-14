"""Backup, cache management, and export/import for Bibliotheca AI.

Provides:
- LanceDB directory backup to timestamped directories
- OCR result cache management
- Export/import for portability between machines
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import Settings, get_settings

logger = logging.getLogger("bibliotheca.backup")


class BackupManager:
    """Manages backups, cache, and data portability."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.lancedb_dir = Path(self.settings.lancedb_dir)
        self.ocr_cache_dir = Path(self.settings.ocr_cache_dir)
        self.sqlite_db_path = Path(self.settings.sqlite_db_path)

    def backup_lancedb(self, backup_root: Optional[Path] = None) -> Path:
        """Create a timestamped backup of the LanceDB directory.

        Args:
            backup_root: Directory to store backups. Defaults to ./backups/.

        Returns:
            Path to the created backup directory.
        """
        if backup_root is None:
            backup_root = Path("./backups")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = backup_root / f"lancedb_backup_{timestamp}"

        if not self.lancedb_dir.exists():
            raise FileNotFoundError(
                f"LanceDB directory not found: {self.lancedb_dir}"
            )

        backup_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.lancedb_dir, backup_dir)

        logger.info("LanceDB backed up to %s", backup_dir)
        return backup_dir

    def backup_sqlite(self, backup_root: Optional[Path] = None) -> Path:
        """Create a timestamped backup of the SQLite metadata database.

        Returns:
            Path to the backup file.
        """
        if backup_root is None:
            backup_root = Path("./backups")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = backup_root / f"bibliotheca_meta_{timestamp}.db"

        if not self.sqlite_db_path.exists():
            raise FileNotFoundError(
                f"SQLite database not found: {self.sqlite_db_path}"
            )

        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.sqlite_db_path, backup_path)

        logger.info("SQLite DB backed up to %s", backup_path)
        return backup_path

    def backup_all(self, backup_root: Optional[Path] = None) -> dict[str, Path]:
        """Backup both LanceDB and SQLite database.

        Returns:
            Dict mapping component name to backup path.
        """
        if backup_root is None:
            backup_root = Path("./backups")

        results: dict[str, Path] = {}

        try:
            results["lancedb"] = self.backup_lancedb(backup_root)
        except FileNotFoundError:
            logger.warning("LanceDB directory not found, skipping backup")

        try:
            results["sqlite"] = self.backup_sqlite(backup_root)
        except FileNotFoundError:
            logger.warning("SQLite database not found, skipping backup")

        return results

    def clear_ocr_cache(self) -> int:
        """Remove all files from the OCR cache directory.

        Returns:
            Number of files removed.
        """
        if not self.ocr_cache_dir.exists():
            logger.info("OCR cache directory does not exist, nothing to clear")
            return 0

        count = 0
        for item in self.ocr_cache_dir.iterdir():
            if item.is_file():
                item.unlink()
                count += 1
            elif item.is_dir():
                shutil.rmtree(item)
                count += 1

        logger.info("Cleared %d items from OCR cache", count)
        return count

    def get_cache_size(self) -> int:
        """Return total size of OCR cache in bytes."""
        if not self.ocr_cache_dir.exists():
            return 0

        total = 0
        for item in self.ocr_cache_dir.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total

    def export_data(self, export_path: Path) -> Path:
        """Export all data (LanceDB + SQLite + cache) to a directory for portability.

        Creates a self-contained directory with all data needed to
        reconstruct the knowledge base on another machine.

        Returns:
            Path to the export directory.
        """
        export_path = Path(export_path)
        export_path.mkdir(parents=True, exist_ok=True)

        # Export LanceDB
        if self.lancedb_dir.exists():
            lance_dest = export_path / "lancedb_data"
            if lance_dest.exists():
                shutil.rmtree(lance_dest)
            shutil.copytree(self.lancedb_dir, lance_dest)
            logger.info("Exported LanceDB to %s", lance_dest)

        # Export SQLite
        if self.sqlite_db_path.exists():
            sqlite_dest = export_path / "bibliotheca_meta.db"
            shutil.copy2(self.sqlite_db_path, sqlite_dest)
            logger.info("Exported SQLite to %s", sqlite_dest)

        # Export OCR cache
        if self.ocr_cache_dir.exists():
            cache_dest = export_path / "ocr_cache"
            if cache_dest.exists():
                shutil.rmtree(cache_dest)
            shutil.copytree(self.ocr_cache_dir, cache_dest)
            logger.info("Exported OCR cache to %s", cache_dest)

        # Write manifest
        manifest = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "components": {
                "lancedb": self.lancedb_dir.exists(),
                "sqlite": self.sqlite_db_path.exists(),
                "ocr_cache": self.ocr_cache_dir.exists(),
            },
        }
        manifest_path = export_path / "export_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        logger.info("Data exported to %s", export_path)
        return export_path

    def import_data(self, import_path: Path) -> dict[str, bool]:
        """Import data from a previously exported directory.

        Args:
            import_path: Path to the export directory.

        Returns:
            Dict mapping component name to import success.
        """
        import_path = Path(import_path)
        if not import_path.exists():
            raise FileNotFoundError(f"Import path not found: {import_path}")

        results: dict[str, bool] = {}

        # Import LanceDB
        lance_src = import_path / "lancedb_data"
        if lance_src.exists():
            if self.lancedb_dir.exists():
                shutil.rmtree(self.lancedb_dir)
            shutil.copytree(lance_src, self.lancedb_dir)
            results["lancedb"] = True
            logger.info("Imported LanceDB from %s", lance_src)
        else:
            results["lancedb"] = False

        # Import SQLite
        sqlite_src = import_path / "bibliotheca_meta.db"
        if sqlite_src.exists():
            shutil.copy2(sqlite_src, self.sqlite_db_path)
            results["sqlite"] = True
            logger.info("Imported SQLite from %s", sqlite_src)
        else:
            results["sqlite"] = False

        # Import OCR cache
        cache_src = import_path / "ocr_cache"
        if cache_src.exists():
            if self.ocr_cache_dir.exists():
                shutil.rmtree(self.ocr_cache_dir)
            shutil.copytree(cache_src, self.ocr_cache_dir)
            results["ocr_cache"] = True
            logger.info("Imported OCR cache from %s", cache_src)
        else:
            results["ocr_cache"] = False

        logger.info("Data import completed: %s", results)
        return results

    def list_backups(self, backup_root: Optional[Path] = None) -> list[dict]:
        """List all available backups.

        Returns:
            List of dicts with backup info (path, type, timestamp, size_bytes).
        """
        if backup_root is None:
            backup_root = Path("./backups")

        if not backup_root.exists():
            return []

        backups: list[dict] = []
        for item in sorted(backup_root.iterdir()):
            if item.name.startswith("lancedb_backup_"):
                size = sum(
                    f.stat().st_size for f in item.rglob("*") if f.is_file()
                )
                backups.append(
                    {
                        "path": str(item),
                        "type": "lancedb",
                        "name": item.name,
                        "size_bytes": size,
                    }
                )
            elif item.name.startswith("bibliotheca_meta_") and item.suffix == ".db":
                backups.append(
                    {
                        "path": str(item),
                        "type": "sqlite",
                        "name": item.name,
                        "size_bytes": item.stat().st_size,
                    }
                )

        return backups
