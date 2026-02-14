"""LanceDB vector database and BGE-M3 embedding for Bibliotheca AI.

Provides:
- EmbeddingEngine: BGE-M3 embedding with auto GPU detection and batching
- VectorDatabase: LanceDB-based vector store with hybrid search support
"""

import logging
from pathlib import Path
from typing import Optional

import lancedb
import pyarrow as pa
from sentence_transformers import SentenceTransformer

from src.config import Settings, get_settings, detect_device

logger = logging.getLogger("bibliotheca.database")


class EmbeddingEngine:
    """BGE-M3 embedding with auto GPU detection."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.device = detect_device(self.settings.gpu_device)
        logger.info(
            "Loading embedding model %s on %s",
            self.settings.embedding_model,
            self.device,
        )
        self.model = SentenceTransformer(
            self.settings.embedding_model, device=self.device
        )
        self.batch_size = self.settings.embedding_batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning list of vectors."""
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=len(texts) > self.batch_size,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        embedding = self.model.encode(
            query, normalize_embeddings=True
        )
        return embedding.tolist()

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self.model.get_sentence_embedding_dimension()


# LanceDB document schema
DOCUMENT_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 1024)),
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
    ]
)


class VectorDatabase:
    """LanceDB-based vector store with hybrid search."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.db_path = str(self.settings.lancedb_dir)
        Path(self.db_path).mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(self.db_path)
        self._table = None
        logger.info("VectorDatabase connected at %s", self.db_path)

    def create_table(self, name: str = "documents") -> None:
        """Create the documents table if it doesn't exist."""
        existing = self.db.table_names()
        if name in existing:
            self._table = self.db.open_table(name)
            logger.info("Opened existing table: %s", name)
        else:
            # Create with empty data matching schema
            self._table = self.db.create_table(name, schema=DOCUMENT_SCHEMA)
            logger.info("Created new table: %s", name)

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
            self._table.search(query_embedding, query_type="hybrid")
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
