"""Tests for chunking module."""

from src.chunking import ChunkingEngine, Chunk


def test_structure_split():
    engine = ChunkingEngine()
    text = "# Chapter 1\nContent here.\n## Section 1.1\nMore content."
    chunks = engine.chunk_document(text, {"source_file": "test.pdf"})
    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)


def test_empty_text():
    engine = ChunkingEngine()
    chunks = engine.chunk_document("", {"source_file": "test.pdf"})
    assert chunks == []


def test_plain_text_no_headers():
    engine = ChunkingEngine()
    text = "This is a simple paragraph without any headers or structure."
    chunks = engine.chunk_document(text, {"source_file": "test.pdf"})
    assert len(chunks) > 0
    # Should have at least one parent and one child
    parents = [c for c in chunks if c.is_parent]
    children = [c for c in chunks if not c.is_parent]
    assert len(parents) >= 1
    assert len(children) >= 1


def test_parent_child_linking():
    engine = ChunkingEngine()
    text = "# Chapter 1\n" + "Some content. " * 50
    chunks = engine.chunk_document(text, {"source_file": "test.pdf"})

    parents = [c for c in chunks if c.is_parent]
    children = [c for c in chunks if not c.is_parent]

    # Every child should reference an existing parent
    parent_ids = {p.chunk_id for p in parents}
    for child in children:
        assert child.parent_id in parent_ids


def test_context_prefix_generation():
    engine = ChunkingEngine()
    text = "# Introduction\nThis is the introduction of the book."
    metadata = {
        "source_file": "test.pdf",
        "book_title": "Test Book",
        "author": "Jane Doe",
    }
    chunks = engine.chunk_document(text, metadata)
    # At least one chunk should have a context prefix with book info
    prefixed = [c for c in chunks if c.context_prefix]
    assert len(prefixed) > 0
    assert "Test Book" in prefixed[0].context_prefix


def test_chunk_ids_unique():
    engine = ChunkingEngine()
    text = "# A\nParagraph one.\n## B\nParagraph two.\n# C\nParagraph three."
    chunks = engine.chunk_document(text, {"source_file": "test.pdf"})
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "Chunk IDs must be unique"
