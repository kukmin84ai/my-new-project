"""LanceDB vector database for Bibliotheca AI.

Provides:
- VectorDatabase: LanceDB-based vector store with hybrid search support
"""

import logging
from pathlib import Path
from typing import Optional

import lancedb
import pyarrow as pa

from src.config import Settings, get_settings

logger = logging.getLogger("bibliotheca.database")


# Default vector dimension (BGE-M3 / Voyage / Jina = 1024)
DEFAULT_VECTOR_DIM = 1024


def get_document_schema(vector_dim: int = DEFAULT_VECTOR_DIM) -> pa.Schema:
    """Build LanceDB document schema with configurable vector dimension.

    Different embedding providers produce different dimensions:
    - BGE-M3 (local): 1024
    - Voyage-3: 1024
    - Jina-v3: 1024
    - OpenAI text-embedding-3-small: 1536
    - OpenAI text-embedding-3-large: 3072
    """
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), vector_dim)),
            pa.field("parent_id", pa.string()),
            pa.field("source_file", pa.string()),
            pa.field("page_num", pa.int32()),
            pa.field("chapter", pa.string()),
            pa.field("section", pa.string()),
            pa.field("language", pa.string()),
            pa.field("ocr_confidence", pa.float32()),
            pa.field("book_title", pa.string()),
            pa.field("author", pa.string()),
            pa.field("is_parent", pa.bool_()),
            pa.field("context_prefix", pa.string()),
            pa.field("subject", pa.string()),
            pa.field("embedding_model", pa.string()),
        ]
    )


# Default schema for backwards compatibility
DOCUMENT_SCHEMA = get_document_schema()


class VectorDatabase:
    """LanceDB-based vector store with hybrid search."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        subject: str = "default",
        vector_dim: int = DEFAULT_VECTOR_DIM,
    ):
        self.settings = settings or get_settings()
        self.subject = self._validate_subject(subject)
        self.vector_dim = vector_dim
        self.db_path = str(self.settings.lancedb_dir)
        Path(self.db_path).mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(self.db_path)
        self._table = None
        logger.info("VectorDatabase connected at %s (subject=%s)", self.db_path, self.subject)

    @staticmethod
    def _validate_subject(subject: str) -> str:
        """Validate subject name is a safe identifier for table naming."""
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', subject):
            raise ValueError(
                f"Invalid subject name '{subject}': "
                "must contain only letters, digits, underscores, and hyphens"
            )
        return subject

    def _get_table_name(self) -> str:
        """Return table name for the current subject."""
        if self.subject == "default":
            return "documents"
        return f"{self.subject}_documents"

    def create_table(self, name: str = None) -> None:
        """Create the documents table if it doesn't exist."""
        name = name or self._get_table_name()
        existing = self.db.table_names()
        if name in existing:
            self._table = self.db.open_table(name)
            logger.info("Opened existing table: %s", name)
        else:
            schema = get_document_schema(self.vector_dim)
            self._table = self.db.create_table(name, schema=schema)
            logger.info("Created new table: %s (vector_dim=%d)", name, self.vector_dim)

    def _ensure_table(self) -> None:
        """Ensure table is initialized."""
        if self._table is None:
            self.create_table()

    def add_documents(self, documents: list[dict]) -> None:
        """Add documents to the vector store.

        Each dict should contain keys matching DOCUMENT_SCHEMA fields.
        Required: id, text, vector. Others default to empty/zero.
        """
        self._ensure_table()

        # Fill in defaults for missing fields
        rows = []
        for doc in documents:
            row = {
                "id": doc["id"],
                "text": doc["text"],
                "vector": doc["vector"],
                "parent_id": doc.get("parent_id", ""),
                "source_file": doc.get("source_file", ""),
                "page_num": doc.get("page_num", 0),
                "chapter": doc.get("chapter", ""),
                "section": doc.get("section", ""),
                "language": doc.get("language", ""),
                "ocr_confidence": doc.get("ocr_confidence", 0.0),
                "book_title": doc.get("book_title", ""),
                "author": doc.get("author", ""),
                "is_parent": doc.get("is_parent", False),
                "context_prefix": doc.get("context_prefix", ""),
                "subject": doc.get("subject", ""),
                "embedding_model": doc.get("embedding_model", ""),
            }
            rows.append(row)

        self._table.add(rows)
        logger.info("Added %d documents to vector store", len(rows))

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """Dense vector similarity search.

        Args:
            query_embedding: Query vector.
            top_k: Number of results to return.
            filters: Optional filter dict, e.g. {"language": "ko"}.

        Returns:
            List of matching document dicts with _distance score.
        """
        self._ensure_table()

        query = self._table.search(query_embedding).limit(top_k)

        if filters:
            filter_clauses = []
            for key, value in filters.items():
                if isinstance(value, str):
                    filter_clauses.append(f"{key} = '{value}'")
                else:
                    filter_clauses.append(f"{key} = {value}")
            if filter_clauses:
                query = query.where(" AND ".join(filter_clauses))

        results = query.to_list()
        logger.debug("Search returned %d results", len(results))
        return results

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """Hybrid search combining dense vector and full-text search.

        LanceDB supports FTS natively. This combines both signals.
        """
        self._ensure_table()

        # Try to create FTS index if not exists (idempotent in LanceDB)
        try:
            self._table.create_fts_index("text", replace=True)
        except Exception:
            logger.debug("FTS index already exists or creation failed")

        search_query = (
            self._table.search(query_type="hybrid")
            .vector(query_embedding)
            .text(query)
            .limit(top_k)
        )

        if filters:
            filter_clauses = []
            for key, value in filters.items():
                if isinstance(value, str):
                    filter_clauses.append(f"{key} = '{value}'")
                else:
                    filter_clauses.append(f"{key} = {value}")
            if filter_clauses:
                search_query = search_query.where(" AND ".join(filter_clauses))

        results = search_query.to_list()
        logger.debug("Hybrid search returned %d results", len(results))
        return results

    def get_by_id(self, doc_id: str) -> Optional[dict]:
        """Retrieve a single document by ID."""
        self._ensure_table()
        results = self._table.search().where(f"id = '{doc_id}'").limit(1).to_list()
        return results[0] if results else None

    def get_parent(self, parent_id: str) -> Optional[dict]:
        """Retrieve a parent chunk by its ID."""
        return self.get_by_id(parent_id)

    def delete_by_source(self, source_file: str) -> None:
        """Delete all documents from a given source file."""
        self._ensure_table()
        self._table.delete(f"source_file = '{source_file}'")
        logger.info("Deleted documents from source: %s", source_file)

    def count(self) -> int:
        """Return total number of documents in the table."""
        self._ensure_table()
        return self._table.count_rows()

    def create_index(self) -> None:
        """Create ANN index for large-scale search (100k+ chunks)."""
        self._ensure_table()
        try:
            self._table.create_index(
                metric="cosine",
                num_partitions=256,
                num_sub_vectors=96,
                index_type="IVF_PQ",
            )
            logger.info("Created ANN index on table %s", self._get_table_name())
        except Exception:
            logger.warning("ANN index creation failed (may already exist)", exc_info=True)

    @classmethod
    def list_subject_tables(cls, settings: Optional[Settings] = None) -> list[str]:
        """List all subject-based document tables in the database."""
        settings = settings or get_settings()
        db = lancedb.connect(str(settings.lancedb_dir))
        tables = db.table_names()
        subjects = []
        for t in tables:
            if t == "documents":
                subjects.append("default")
            elif t.endswith("_documents"):
                subjects.append(t.removesuffix("_documents"))
        return subjects
