"""Tests for multi-subject domain separation across metadata, database, and graph.

Verifies that the subject/tags fields in BookMetadata, subject-based table
routing in VectorDatabase, and subject-scoped KnowledgeGraph all work correctly.
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.config import Settings
from src.metadata import BookMetadata, MetadataStore
from src.graph import KnowledgeGraph, Entity, Relationship, Triplet


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_env(tmp_path):
    """Override env vars so stores use tmp_path, restoring after test."""
    overrides = {
        "BIBLIO_LANCEDB_DIR": str(tmp_path / "lancedb"),
        "BIBLIO_SQLITE_DB_PATH": str(tmp_path / "test_meta.db"),
        "BIBLIO_GRAPH_STORE_DIR": str(tmp_path / "graph"),
        "BIBLIO_DATA_DIR": str(tmp_path / "data"),
    }
    originals: dict[str, str | None] = {}
    for key, value in overrides.items():
        originals[key] = os.environ.get(key)
        os.environ[key] = value
    yield tmp_path
    for key, orig in originals.items():
        if orig is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = orig


@pytest.fixture()
def metadata_store(tmp_env):
    """Create a MetadataStore backed by the temp database."""
    db_path = str(tmp_env / "test_meta.db")
    store = MetadataStore(db_path=db_path)
    yield store
    store.close()


@pytest.fixture()
def sample_file(tmp_env):
    """Create a dummy PDF-like file so compute_file_hash can read it."""
    f = tmp_env / "data" / "sample.pdf"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"fake pdf content")
    return f


@pytest.fixture()
def sample_file_2(tmp_env):
    """A second dummy file with different content."""
    f = tmp_env / "data" / "sample2.pdf"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"another fake pdf content")
    return f


# ---------------------------------------------------------------------------
# BookMetadata dataclass
# ---------------------------------------------------------------------------


class TestBookMetadataFields:
    """Verify subject/tags fields on the BookMetadata dataclass."""

    def test_default_values(self):
        meta = BookMetadata()
        assert meta.subject == ""
        assert meta.tags == ""

    def test_explicit_values(self):
        meta = BookMetadata(subject="emc", tags="shielding,grounding")
        assert meta.subject == "emc"
        assert meta.tags == "shielding,grounding"

    def test_all_fields_preserved(self):
        meta = BookMetadata(
            title="EMC Handbook",
            author="Henry Ott",
            isbn="1234567890",
            subject="emc",
            tags="shielding",
        )
        assert meta.title == "EMC Handbook"
        assert meta.author == "Henry Ott"
        assert meta.isbn == "1234567890"
        assert meta.subject == "emc"
        assert meta.tags == "shielding"


# ---------------------------------------------------------------------------
# MetadataStore: subject/tags in SQLite
# ---------------------------------------------------------------------------


class TestMetadataStoreSubject:
    """MetadataStore persists and queries subject/tags."""

    def test_register_and_retrieve_subject(self, metadata_store, sample_file):
        meta = BookMetadata(
            title="EMC for Engineers",
            subject="emc",
            tags="shielding,filtering",
        )
        metadata_store.register_file(sample_file, meta)

        books = metadata_store.get_all_books()
        assert len(books) == 1
        assert books[0].subject == "emc"
        assert books[0].tags == "shielding,filtering"

    def test_get_books_by_subject(self, metadata_store, sample_file, sample_file_2):
        meta_emc = BookMetadata(title="EMC Book", subject="emc", tags="shielding")
        meta_phys = BookMetadata(title="Physics Book", subject="physics", tags="optics")

        metadata_store.register_file(sample_file, meta_emc)
        metadata_store.register_file(sample_file_2, meta_phys)

        emc_books = metadata_store.get_books_by_subject("emc")
        assert len(emc_books) == 1
        assert emc_books[0].title == "EMC Book"
        assert emc_books[0].subject == "emc"

        phys_books = metadata_store.get_books_by_subject("physics")
        assert len(phys_books) == 1
        assert phys_books[0].title == "Physics Book"

    def test_get_books_by_subject_empty(self, metadata_store, sample_file):
        meta = BookMetadata(title="EMC Book", subject="emc")
        metadata_store.register_file(sample_file, meta)

        result = metadata_store.get_books_by_subject("medical")
        assert result == []

    def test_upsert_updates_subject(self, metadata_store, sample_file):
        meta1 = BookMetadata(title="Book", subject="emc")
        metadata_store.register_file(sample_file, meta1)

        meta2 = BookMetadata(title="Book", subject="physics")
        metadata_store.register_file(sample_file, meta2)

        books = metadata_store.get_all_books()
        assert len(books) == 1
        assert books[0].subject == "physics"

    def test_migration_adds_subject_columns(self, tmp_env):
        """Simulate a legacy DB without subject/tags columns, verify migration."""
        db_path = str(tmp_env / "legacy.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL DEFAULT '',
                isbn TEXT NOT NULL DEFAULT '',
                doi TEXT NOT NULL DEFAULT '',
                issn TEXT NOT NULL DEFAULT '',
                publisher TEXT NOT NULL DEFAULT '',
                year INTEGER,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                page_count INTEGER DEFAULT 0,
                language TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE processing_manifest (
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
            )
            """
        )
        conn.commit()
        conn.close()

        # Opening MetadataStore on this DB should run the migration
        store = MetadataStore(db_path=db_path)

        # Verify subject and tags columns exist
        cursor = store.conn.cursor()
        cursor.execute("PRAGMA table_info(books)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "subject" in columns
        assert "tags" in columns
        store.close()


# ---------------------------------------------------------------------------
# KnowledgeGraph: subject-scoped stores
# ---------------------------------------------------------------------------


class TestKnowledgeGraphSubjectSeparation:
    """KnowledgeGraph isolates data by subject subdirectory."""

    def test_separate_subjects_have_separate_files(self, tmp_env):
        graph_dir = tmp_env / "graph"

        g_emc = KnowledgeGraph(store_dir=graph_dir, subject="emc")
        g_phys = KnowledgeGraph(store_dir=graph_dir, subject="physics")

        assert g_emc.store_dir == graph_dir / "emc"
        assert g_phys.store_dir == graph_dir / "physics"
        assert g_emc.store_dir != g_phys.store_dir

    def test_entities_isolated_between_subjects(self, tmp_env):
        graph_dir = tmp_env / "graph"

        g_emc = KnowledgeGraph(store_dir=graph_dir, subject="emc")
        g_emc.add_entity(Entity(name="Shielding", entity_type="Concept"))

        g_phys = KnowledgeGraph(store_dir=graph_dir, subject="physics")
        g_phys.add_entity(Entity(name="Quantum", entity_type="Concept"))

        # Each graph only sees its own entities
        assert "Shielding" in g_emc.entities
        assert "Quantum" not in g_emc.entities
        assert "Quantum" in g_phys.entities
        assert "Shielding" not in g_phys.entities

    def test_relationships_isolated_between_subjects(self, tmp_env):
        graph_dir = tmp_env / "graph"

        g_emc = KnowledgeGraph(store_dir=graph_dir, subject="emc")
        g_emc.add_entity(Entity(name="A", entity_type="Concept"))
        g_emc.add_entity(Entity(name="B", entity_type="Concept"))
        g_emc.add_relationship(
            Relationship(source="A", target="B", relationship_type="RELATED_TO")
        )

        g_phys = KnowledgeGraph(store_dir=graph_dir, subject="physics")
        assert len(g_phys.relationships) == 0
        assert len(g_emc.relationships) == 1

    def test_triplets_scoped_to_subject(self, tmp_env):
        graph_dir = tmp_env / "graph"
        g = KnowledgeGraph(store_dir=graph_dir, subject="medical")
        g.add_triplets([
            Triplet(
                subject="MRI",
                predicate="EXTENDS",
                object="NMR",
                source_file="medical_imaging.pdf",
            )
        ])
        assert "MRI" in g.entities
        assert "NMR" in g.entities
        assert len(g.relationships) == 1

        # Other subject does not see the data
        g_other = KnowledgeGraph(store_dir=graph_dir, subject="emc")
        assert len(g_other.entities) == 0

    def test_clear_only_affects_own_subject(self, tmp_env):
        graph_dir = tmp_env / "graph"

        g_emc = KnowledgeGraph(store_dir=graph_dir, subject="emc")
        g_emc.add_entity(Entity(name="EMC_Entity", entity_type="Concept"))

        g_phys = KnowledgeGraph(store_dir=graph_dir, subject="physics")
        g_phys.add_entity(Entity(name="Phys_Entity", entity_type="Concept"))

        g_emc.clear()
        assert len(g_emc.entities) == 0

        # Reload physics to verify it's untouched
        g_phys_reload = KnowledgeGraph(store_dir=graph_dir, subject="physics")
        assert "Phys_Entity" in g_phys_reload.entities

    def test_default_subject_uses_default_dir(self, tmp_env):
        graph_dir = tmp_env / "graph"
        g = KnowledgeGraph(store_dir=graph_dir, subject="default")
        assert g.store_dir == graph_dir / "default"

    def test_stats_scoped_to_subject(self, tmp_env):
        graph_dir = tmp_env / "graph"

        g1 = KnowledgeGraph(store_dir=graph_dir, subject="emc")
        g1.add_entity(Entity(name="E1", entity_type="Concept"))
        g1.add_entity(Entity(name="E2", entity_type="Person"))

        g2 = KnowledgeGraph(store_dir=graph_dir, subject="physics")
        g2.add_entity(Entity(name="P1", entity_type="Theory"))

        stats1 = g1.get_stats()
        assert stats1["entity_count"] == 2

        stats2 = g2.get_stats()
        assert stats2["entity_count"] == 1


# ---------------------------------------------------------------------------
# VectorDatabase: subject-based table naming
# ---------------------------------------------------------------------------


class TestVectorDatabaseTableNaming:
    """VectorDatabase routes to separate tables per subject.

    These tests verify the table-naming logic without requiring
    a full LanceDB instance with vector data.
    """

    def test_default_subject_table_name(self, tmp_env):
        from src.database import VectorDatabase

        db = VectorDatabase(subject="default")
        assert db._get_table_name() == "documents"

    def test_custom_subject_table_name(self, tmp_env):
        from src.database import VectorDatabase

        db = VectorDatabase(subject="emc")
        assert db._get_table_name() == "emc_documents"

    def test_different_subjects_different_tables(self, tmp_env):
        from src.database import VectorDatabase

        db_emc = VectorDatabase(subject="emc")
        db_phys = VectorDatabase(subject="physics")
        assert db_emc._get_table_name() != db_phys._get_table_name()

    def test_subject_stored_on_instance(self, tmp_env):
        from src.database import VectorDatabase

        db = VectorDatabase(subject="medical")
        assert db.subject == "medical"

    def test_invalid_subject_raises(self, tmp_env):
        from src.database import VectorDatabase

        with pytest.raises(ValueError, match="Invalid subject name"):
            VectorDatabase(subject="bad subject; DROP TABLE")

    def test_subject_with_hyphens_and_underscores(self, tmp_env):
        from src.database import VectorDatabase

        db = VectorDatabase(subject="emc-testing_2024")
        assert db._get_table_name() == "emc-testing_2024_documents"
