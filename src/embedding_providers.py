"""Cross-platform embedding provider abstraction for Bibliotheca AI.

Provides a unified interface for local (sentence-transformers) and API-based
(OpenAI, Voyage, Jina) embedding models. The appropriate provider is selected
based on the EmbeddingProvider setting.

Usage:
    from src.embedding_providers import create_embedder
    embedder = create_embedder(settings)
    vectors = embedder.embed(["text1", "text2"])
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

import requests

from src.config import EmbeddingProvider, Settings, get_settings, detect_device

logger = logging.getLogger("bibliotheca.embedding")


class BaseEmbedder(ABC):
    """Abstract base class for all embedding providers."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning list of vectors."""
        ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        ...


class LocalEmbedder(BaseEmbedder):
    """Local embedding via sentence-transformers with GPU auto-detection.

    Wraps the original EmbeddingEngine logic from database.py.
    Supports BGE-M3 and any sentence-transformers model.
    """

    def __init__(self, settings: Optional[Settings] = None):
        from sentence_transformers import SentenceTransformer

        self.settings = settings or get_settings()
        self.device = detect_device(self.settings.gpu_device)
        logger.info(
            "Loading local embedding model %s on %s",
            self.settings.embedding_model,
            self.device,
        )
        self.model = SentenceTransformer(
            self.settings.embedding_model, device=self.device
        )
        self.batch_size = self.settings.embedding_batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=len(texts) > self.batch_size,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        embedding = self.model.encode(query, normalize_embeddings=True)
        return embedding.tolist()

    @property
    def dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI API embedding provider.

    Models: text-embedding-3-small (1536d), text-embedding-3-large (3072d).
    """

    # Default dimensions per model
    MODEL_DIMS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        if not self.settings.embedding_api_key:
            raise ValueError("embedding_api_key required for OpenAI provider")
        self._api_key = self.settings.embedding_api_key
        self._model = self.settings.embedding_model or "text-embedding-3-small"
        self._dim = self.MODEL_DIMS.get(self._model, 1536)
        logger.info("OpenAI embedder initialized: model=%s, dim=%d", self._model, self._dim)

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        resp = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"input": texts, "model": self._model},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        # Sort by index to preserve input order
        data.sort(key=lambda x: x["index"])
        return [item["embedding"] for item in data]

    def embed(self, texts: list[str]) -> list[list[float]]:
        # OpenAI API supports up to 2048 inputs per call; batch if needed
        all_embeddings: list[list[float]] = []
        batch_size = 2048
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            all_embeddings.extend(self._call_api(batch))
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        return self._call_api([query])[0]

    @property
    def dimension(self) -> int:
        return self._dim


class VoyageEmbedder(BaseEmbedder):
    """Voyage AI embedding provider.

    Model: voyage-3 (1024d, compatible with default LanceDB schema).
    """

    MODEL_DIMS = {
        "voyage-3": 1024,
        "voyage-3-lite": 512,
        "voyage-large-2": 1536,
    }

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        if not self.settings.embedding_api_key:
            raise ValueError("embedding_api_key required for Voyage provider")
        self._api_key = self.settings.embedding_api_key
        self._model = self.settings.embedding_model or "voyage-3"
        self._dim = self.MODEL_DIMS.get(self._model, 1024)
        logger.info("Voyage embedder initialized: model=%s, dim=%d", self._model, self._dim)

    def _call_api(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        resp = requests.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": texts,
                "model": self._model,
                "input_type": input_type,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        data.sort(key=lambda x: x["index"])
        return [item["embedding"] for item in data]

    def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        batch_size = 128  # Voyage API batch limit
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            all_embeddings.extend(self._call_api(batch, input_type="document"))
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        return self._call_api([query], input_type="query")[0]

    @property
    def dimension(self) -> int:
        return self._dim


class JinaEmbedder(BaseEmbedder):
    """Jina AI embedding provider.

    Model: jina-embeddings-v3 (1024d, compatible with default LanceDB schema).
    """

    MODEL_DIMS = {
        "jina-embeddings-v3": 1024,
        "jina-embeddings-v2-base-en": 768,
    }

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        if not self.settings.embedding_api_key:
            raise ValueError("embedding_api_key required for Jina provider")
        self._api_key = self.settings.embedding_api_key
        self._model = self.settings.embedding_model or "jina-embeddings-v3"
        self._dim = self.MODEL_DIMS.get(self._model, 1024)
        logger.info("Jina embedder initialized: model=%s, dim=%d", self._model, self._dim)

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        resp = requests.post(
            "https://api.jina.ai/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"input": texts, "model": self._model},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        data.sort(key=lambda x: x["index"])
        return [item["embedding"] for item in data]

    def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        batch_size = 2048
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            all_embeddings.extend(self._call_api(batch))
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        return self._call_api([query])[0]

    @property
    def dimension(self) -> int:
        return self._dim


_PROVIDERS: dict[EmbeddingProvider, type[BaseEmbedder]] = {
    EmbeddingProvider.LOCAL: LocalEmbedder,
    EmbeddingProvider.OPENAI: OpenAIEmbedder,
    EmbeddingProvider.VOYAGE: VoyageEmbedder,
    EmbeddingProvider.JINA: JinaEmbedder,
}


def create_embedder(settings: Optional[Settings] = None) -> BaseEmbedder:
    """Create an embedding provider based on settings.

    Uses ``settings.embedding_provider`` to select the implementation.
    Defaults to ``LocalEmbedder`` (sentence-transformers on GPU).
    """
    settings = settings or get_settings()
    provider_cls = _PROVIDERS.get(settings.embedding_provider)
    if provider_cls is None:
        raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
    return provider_cls(settings)
