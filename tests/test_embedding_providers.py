"""Tests for embedding provider abstraction layer."""

import pytest
from unittest.mock import patch, MagicMock

from src.config import Settings, EmbeddingProvider
from src.embedding_providers import (
    BaseEmbedder,
    LocalEmbedder,
    OpenAIEmbedder,
    VoyageEmbedder,
    JinaEmbedder,
    create_embedder,
    _PROVIDERS,
)


# ---------------------------------------------------------------------------
# BaseEmbedder / provider registry
# ---------------------------------------------------------------------------


def test_base_embedder_is_abstract():
    """BaseEmbedder cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseEmbedder()


def test_provider_registry_has_all_enum_values():
    """Every EmbeddingProvider enum value has a matching class in _PROVIDERS."""
    for provider in EmbeddingProvider:
        assert provider in _PROVIDERS


def test_create_embedder_unknown_provider():
    """create_embedder raises ValueError for an unknown provider string."""
    settings = Settings(embedding_provider="local")
    # Monkey-patch the provider to a value not in the registry
    with patch.object(settings, "embedding_provider", new="nonexistent"):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            create_embedder(settings)


# ---------------------------------------------------------------------------
# LocalEmbedder
# ---------------------------------------------------------------------------


@patch("src.embedding_providers.detect_device", return_value="cpu")
@patch("src.embedding_providers.SentenceTransformer", create=True)
def test_local_embedder_init(mock_st_class, mock_device):
    """LocalEmbedder loads model on the detected device."""
    # We patch the import inside LocalEmbedder.__init__
    mock_model = MagicMock()
    with patch(
        "sentence_transformers.SentenceTransformer", return_value=mock_model
    ):
        settings = Settings(embedding_model="BAAI/bge-m3")
        embedder = LocalEmbedder(settings)
        assert embedder.device == "cpu"
        assert embedder.batch_size == settings.embedding_batch_size


@patch("src.embedding_providers.detect_device", return_value="cpu")
def test_local_embedder_embed(mock_device):
    """LocalEmbedder.embed delegates to model.encode."""
    import numpy as np

    mock_model = MagicMock()
    fake_vectors = np.array([[0.1, 0.2], [0.3, 0.4]])
    mock_model.encode.return_value = fake_vectors

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        settings = Settings(embedding_model="BAAI/bge-m3")
        embedder = LocalEmbedder(settings)

    result = embedder.embed(["hello", "world"])
    assert result == fake_vectors.tolist()
    mock_model.encode.assert_called_once()


@patch("src.embedding_providers.detect_device", return_value="cpu")
def test_local_embedder_embed_query(mock_device):
    """LocalEmbedder.embed_query returns a single vector."""
    import numpy as np

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([0.5, 0.6])

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        settings = Settings(embedding_model="BAAI/bge-m3")
        embedder = LocalEmbedder(settings)

    result = embedder.embed_query("test query")
    assert result == [0.5, 0.6]


@patch("src.embedding_providers.detect_device", return_value="cpu")
def test_local_embedder_dimension(mock_device):
    """LocalEmbedder.dimension delegates to model."""
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = 1024

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        settings = Settings(embedding_model="BAAI/bge-m3")
        embedder = LocalEmbedder(settings)

    assert embedder.dimension == 1024


# ---------------------------------------------------------------------------
# OpenAIEmbedder
# ---------------------------------------------------------------------------


def test_openai_embedder_requires_api_key():
    """OpenAIEmbedder raises ValueError without api key."""
    settings = Settings(embedding_provider="openai", embedding_api_key=None)
    with pytest.raises(ValueError, match="embedding_api_key required"):
        OpenAIEmbedder(settings)


def test_openai_embedder_dimension_lookup():
    """OpenAIEmbedder resolves dimension from MODEL_DIMS."""
    settings = Settings(
        embedding_provider="openai",
        embedding_api_key="sk-test",
        embedding_model="text-embedding-3-large",
    )
    embedder = OpenAIEmbedder(settings)
    assert embedder.dimension == 3072


def test_openai_embedder_default_model():
    """OpenAIEmbedder defaults to text-embedding-3-small."""
    settings = Settings(
        embedding_provider="openai",
        embedding_api_key="sk-test",
        embedding_model="",
    )
    embedder = OpenAIEmbedder(settings)
    assert embedder._model == "text-embedding-3-small"
    assert embedder.dimension == 1536


@patch("src.embedding_providers.requests.post")
def test_openai_embedder_embed(mock_post):
    """OpenAIEmbedder.embed calls the OpenAI API and returns sorted vectors."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"index": 1, "embedding": [0.3, 0.4]},
            {"index": 0, "embedding": [0.1, 0.2]},
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    settings = Settings(
        embedding_provider="openai",
        embedding_api_key="sk-test",
        embedding_model="text-embedding-3-small",
    )
    embedder = OpenAIEmbedder(settings)
    result = embedder.embed(["hello", "world"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    mock_post.assert_called_once()


@patch("src.embedding_providers.requests.post")
def test_openai_embedder_embed_query(mock_post):
    """OpenAIEmbedder.embed_query returns a single vector."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"index": 0, "embedding": [0.1, 0.2]}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    settings = Settings(
        embedding_provider="openai",
        embedding_api_key="sk-test",
    )
    embedder = OpenAIEmbedder(settings)
    result = embedder.embed_query("test")
    assert result == [0.1, 0.2]


# ---------------------------------------------------------------------------
# VoyageEmbedder
# ---------------------------------------------------------------------------


def test_voyage_embedder_requires_api_key():
    settings = Settings(embedding_provider="voyage", embedding_api_key=None)
    with pytest.raises(ValueError, match="embedding_api_key required"):
        VoyageEmbedder(settings)


def test_voyage_embedder_default_model():
    settings = Settings(
        embedding_provider="voyage",
        embedding_api_key="voy-test",
        embedding_model="",
    )
    embedder = VoyageEmbedder(settings)
    assert embedder._model == "voyage-3"
    assert embedder.dimension == 1024


@patch("src.embedding_providers.requests.post")
def test_voyage_embedder_uses_input_type(mock_post):
    """Voyage API calls include input_type parameter."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"index": 0, "embedding": [0.1]}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    settings = Settings(
        embedding_provider="voyage",
        embedding_api_key="voy-test",
    )
    embedder = VoyageEmbedder(settings)

    # embed() uses input_type="document"
    embedder.embed(["hello"])
    call_json = mock_post.call_args[1]["json"]
    assert call_json["input_type"] == "document"

    # embed_query() uses input_type="query"
    embedder.embed_query("query text")
    call_json = mock_post.call_args[1]["json"]
    assert call_json["input_type"] == "query"


# ---------------------------------------------------------------------------
# JinaEmbedder
# ---------------------------------------------------------------------------


def test_jina_embedder_requires_api_key():
    settings = Settings(embedding_provider="jina", embedding_api_key=None)
    with pytest.raises(ValueError, match="embedding_api_key required"):
        JinaEmbedder(settings)


def test_jina_embedder_default_model():
    settings = Settings(
        embedding_provider="jina",
        embedding_api_key="jina-test",
        embedding_model="",
    )
    embedder = JinaEmbedder(settings)
    assert embedder._model == "jina-embeddings-v3"
    assert embedder.dimension == 1024


@patch("src.embedding_providers.requests.post")
def test_jina_embedder_embed(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"index": 0, "embedding": [0.5, 0.6]},
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    settings = Settings(
        embedding_provider="jina",
        embedding_api_key="jina-test",
    )
    embedder = JinaEmbedder(settings)
    result = embedder.embed(["text"])
    assert result == [[0.5, 0.6]]


# ---------------------------------------------------------------------------
# create_embedder factory
# ---------------------------------------------------------------------------


@patch("src.embedding_providers.detect_device", return_value="cpu")
def test_create_embedder_local(mock_device):
    """create_embedder returns LocalEmbedder for LOCAL provider."""
    mock_model = MagicMock()
    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        settings = Settings(embedding_provider="local")
        embedder = create_embedder(settings)
        assert isinstance(embedder, LocalEmbedder)


def test_create_embedder_openai():
    """create_embedder returns OpenAIEmbedder for OPENAI provider."""
    settings = Settings(
        embedding_provider="openai",
        embedding_api_key="sk-test",
    )
    embedder = create_embedder(settings)
    assert isinstance(embedder, OpenAIEmbedder)


def test_create_embedder_voyage():
    settings = Settings(
        embedding_provider="voyage",
        embedding_api_key="voy-test",
    )
    embedder = create_embedder(settings)
    assert isinstance(embedder, VoyageEmbedder)


def test_create_embedder_jina():
    settings = Settings(
        embedding_provider="jina",
        embedding_api_key="jina-test",
    )
    embedder = create_embedder(settings)
    assert isinstance(embedder, JinaEmbedder)
