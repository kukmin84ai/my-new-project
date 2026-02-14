"""Bibliotheca AI configuration management using Pydantic BaseSettings."""

import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class GPUDevice(str, Enum):
    AUTO = "auto"
    CUDA = "cuda"
    MPS = "mps"
    CPU = "cpu"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="BIBLIO_", extra="ignore"
    )

    # OCR Settings
    ocr_languages: str = "ko,en"
    ocr_tier1_enabled: bool = True  # Marker
    ocr_tier2_enabled: bool = True  # Docling
    ocr_tier3_enabled: bool = False  # LlamaParse (opt-in)
    llama_cloud_api_key: Optional[str] = None

    # Chunking
    chunk_size_search: int = 300  # child chunks for retrieval (200-400 tokens)
    chunk_size_parent: int = 900  # parent chunks for context (800-1000 tokens)
    chunk_overlap: int = 50
    semantic_threshold: float = 0.75  # cosine similarity threshold for semantic splitting

    # Embedding
    embedding_model: str = "BAAI/bge-m3"
    embedding_batch_size: int = 32

    # Database Paths
    data_dir: Path = Path("data")
    lancedb_dir: Path = Path("./lancedb_data")
    sqlite_db_path: Path = Path("./bibliotheca_meta.db")
    ocr_cache_dir: Path = Path("./ocr_cache")
    graph_store_dir: Path = Path("./graph_store")

    # GPU
    gpu_device: GPUDevice = GPUDevice.AUTO

    # LLM (for contextual retrieval)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:13b"

    # Logging
    log_level: str = "INFO"


def detect_device(preferred: GPUDevice = GPUDevice.AUTO) -> str:
    """Auto-detect best available compute device."""
    import torch

    if preferred != GPUDevice.AUTO:
        return preferred.value
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def get_settings() -> Settings:
    """Return a Settings instance populated from environment and .env file."""
    return Settings()


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("bibliotheca")
