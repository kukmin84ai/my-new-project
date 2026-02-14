"""Tests for configuration module."""

from src.config import Settings, GPUDevice, setup_logging


def test_default_settings():
    s = Settings()
    assert s.ocr_languages == "ko,en"
    assert s.embedding_model == "BAAI/bge-m3"
    assert s.gpu_device == GPUDevice.AUTO


def test_chunk_size_defaults():
    s = Settings()
    assert s.chunk_size_search == 300
    assert s.chunk_size_parent == 900
    assert s.chunk_overlap == 50


def test_ocr_tier_defaults():
    s = Settings()
    assert s.ocr_tier1_enabled is True
    assert s.ocr_tier2_enabled is True
    assert s.ocr_tier3_enabled is False


def test_setup_logging():
    logger = setup_logging("DEBUG")
    assert logger.name == "bibliotheca"


def test_settings_extra_ignore():
    """Settings should ignore unknown env vars with BIBLIO_ prefix."""
    s = Settings(BIBLIO_UNKNOWN_KEY="value")
    assert not hasattr(s, "BIBLIO_UNKNOWN_KEY")
