"""Advanced chunking strategies for scholarly documents.

Implements:
- Structure-aware pre-chunking (respects section/paragraph boundaries)
- Semantic chunking using cosine similarity between consecutive sentences
- Parent-Child hierarchy: search chunks linked to parent chunks
- Contextual Retrieval prefix generation
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

from src.config import Settings, get_settings

logger = logging.getLogger("bibliotheca.chunking")


@dataclass
class Chunk:
    """A text chunk with hierarchy and metadata."""

    text: str
    chunk_id: str = ""
    parent_id: Optional[str] = None
    source_file: str = ""
    page_num: Optional[int] = None
    chapter: str = ""
    section: str = ""
    is_parent: bool = False
    context_prefix: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.chunk_id:
            self.chunk_id = str(uuid.uuid4())


class ChunkingEngine:
    """Structure-aware, semantic chunking with parent-child hierarchy."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.child_size = self.settings.chunk_size_search
        self.parent_size = self.settings.chunk_size_parent
        self.overlap = self.settings.chunk_overlap
        self.semantic_threshold = self.settings.semantic_threshold
        self._embedding_model = None

    def chunk_document(self, text: str, metadata: dict) -> list[Chunk]:
        """Main entry: structure-aware -> semantic -> parent-child.

        Args:
            text: Full document text (may contain markdown headers).
            metadata: Dict with source_file, page_num, book_title, author, etc.

        Returns:
            List of Chunk objects (both parent and child chunks).
        """
        if not text.strip():
            return []

        source_file = metadata.get("source_file", "")
        page_num = metadata.get("page_num")

        # Step 1: Split by structure (markdown headers, section boundaries)
        sections = self._split_by_structure(text)

        # Step 2: For each section, apply semantic splitting then parent-child
        all_chunks: list[Chunk] = []

        for section_info in sections:
            section_text = section_info["text"]
            chapter = section_info.get("chapter", "")
            section = section_info.get("section", "")

            if not section_text.strip():
                continue

            # Semantic split within the section
            sub_segments = self._semantic_split(section_text)

            # Create parent-child hierarchy from sub-segments
            pc_chunks = self._create_parent_child(
                sub_segments,
                source_file=source_file,
                page_num=page_num,
                chapter=chapter,
                section=section,
            )

            # Generate context prefixes
            for chunk in pc_chunks:
                chunk.context_prefix = self._generate_context_prefix(
                    chunk, metadata
                )

            all_chunks.extend(pc_chunks)

        logger.info(
            "Chunked document into %d chunks (%d parents, %d children)",
            len(all_chunks),
            sum(1 for c in all_chunks if c.is_parent),
            sum(1 for c in all_chunks if not c.is_parent),
        )
        return all_chunks

    def _split_by_structure(self, text: str) -> list[dict]:
        """Split by markdown headers/section boundaries.

        Returns list of dicts with 'text', 'chapter', 'section' keys.
        """
        # Match markdown headers: # Chapter, ## Section, ### Subsection
        header_pattern = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

        sections: list[dict] = []
        current_chapter = ""
        current_section = ""
        last_end = 0

        for match in header_pattern.finditer(text):
            # Capture text before this header (if any)
            pre_text = text[last_end : match.start()].strip()
            if pre_text:
                sections.append(
                    {
                        "text": pre_text,
                        "chapter": current_chapter,
                        "section": current_section,
                    }
                )

            level = len(match.group(1))
            title = match.group(2).strip()

            if level == 1:
                current_chapter = title
                current_section = ""
            elif level >= 2:
                current_section = title

            last_end = match.end()

        # Capture remaining text after last header
        remaining = text[last_end:].strip()
        if remaining:
            sections.append(
                {
                    "text": remaining,
                    "chapter": current_chapter,
                    "section": current_section,
                }
            )

        # If no headers found, return the whole text as one section
        if not sections:
            sections.append({"text": text, "chapter": "", "section": ""})

        return sections

    def _semantic_split(self, section_text: str) -> list[str]:
        """Split by cosine similarity drops between consecutive sentences.

        Falls back to token-based splitting if embedding model is unavailable.
        """
        # Split into sentences
        sentences = self._split_sentences(section_text)
        if len(sentences) <= 1:
            return sentences if sentences else [section_text]

        # Try semantic splitting with embeddings
        try:
            embeddings = self._get_sentence_embeddings(sentences)
            if embeddings is not None:
                return self._merge_by_similarity(sentences, embeddings)
        except Exception:
            logger.debug("Semantic splitting unavailable, using token-based fallback")

        # Fallback: token-based splitting
        return self._token_split(section_text)

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences using regex."""
        # Split on sentence-ending punctuation followed by whitespace
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _get_sentence_embeddings(self, sentences: list[str]) -> Optional[list]:
        """Get embeddings for sentences using the embedding model."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedding_model = SentenceTransformer(
                    self.settings.embedding_model
                )
            except Exception:
                return None

        return self._embedding_model.encode(sentences, normalize_embeddings=True)

    def _merge_by_similarity(
        self, sentences: list[str], embeddings: list
    ) -> list[str]:
        """Merge consecutive sentences whose similarity exceeds threshold."""
        import numpy as np

        segments: list[str] = []
        current_segment: list[str] = [sentences[0]]

        for i in range(1, len(sentences)):
            sim = float(np.dot(embeddings[i - 1], embeddings[i]))
            if sim >= self.semantic_threshold:
                current_segment.append(sentences[i])
            else:
                segments.append(" ".join(current_segment))
                current_segment = [sentences[i]]

        if current_segment:
            segments.append(" ".join(current_segment))

        return segments

    def _token_split(self, text: str) -> list[str]:
        """Simple word-count-based splitting as fallback."""
        words = text.split()
        if len(words) <= self.child_size:
            return [text]

        segments: list[str] = []
        start = 0
        while start < len(words):
            end = min(start + self.child_size, len(words))
            segment = " ".join(words[start:end])
            segments.append(segment)
            start = end - self.overlap if end < len(words) else end

        return segments

    def _create_parent_child(
        self,
        segments: list[str],
        source_file: str = "",
        page_num: Optional[int] = None,
        chapter: str = "",
        section: str = "",
    ) -> list[Chunk]:
        """Create parent-child hierarchy from text segments.

        Parent chunks: ~800-1000 tokens for providing broader context.
        Child chunks: ~200-400 tokens for precise retrieval.
        """
        all_chunks: list[Chunk] = []

        # Group segments into parent-sized blocks
        parent_groups: list[list[str]] = []
        current_group: list[str] = []
        current_word_count = 0

        for segment in segments:
            seg_words = len(segment.split())
            if current_word_count + seg_words > self.parent_size and current_group:
                parent_groups.append(current_group)
                current_group = []
                current_word_count = 0
            current_group.append(segment)
            current_word_count += seg_words

        if current_group:
            parent_groups.append(current_group)

        # Create parent and child chunks
        for group in parent_groups:
            parent_text = " ".join(group)
            parent_id = str(uuid.uuid4())

            # Parent chunk
            parent_chunk = Chunk(
                text=parent_text,
                chunk_id=parent_id,
                parent_id=None,
                source_file=source_file,
                page_num=page_num,
                chapter=chapter,
                section=section,
                is_parent=True,
            )
            all_chunks.append(parent_chunk)

            # Child chunks from each segment in the group
            for segment in group:
                # If a segment is still larger than child_size, split further
                child_texts = self._ensure_child_size(segment)
                for ct in child_texts:
                    child_chunk = Chunk(
                        text=ct,
                        chunk_id=str(uuid.uuid4()),
                        parent_id=parent_id,
                        source_file=source_file,
                        page_num=page_num,
                        chapter=chapter,
                        section=section,
                        is_parent=False,
                    )
                    all_chunks.append(child_chunk)

        return all_chunks

    def _ensure_child_size(self, text: str) -> list[str]:
        """Split text further if it exceeds child chunk size."""
        words = text.split()
        if len(words) <= self.child_size:
            return [text]

        parts: list[str] = []
        start = 0
        while start < len(words):
            end = min(start + self.child_size, len(words))
            parts.append(" ".join(words[start:end]))
            start = end - self.overlap if end < len(words) else end
        return parts

    def _generate_context_prefix(self, chunk: Chunk, book_metadata: dict) -> str:
        """Generate Anthropic-style contextual retrieval prefix.

        Creates a short context string that situates the chunk within
        the broader document for improved retrieval accuracy.
        """
        parts: list[str] = []

        book_title = book_metadata.get("book_title", "")
        author = book_metadata.get("author", "")

        if book_title:
            parts.append(f"From '{book_title}'")
            if author:
                parts.append(f"by {author}")

        if chunk.chapter:
            parts.append(f"in chapter '{chunk.chapter}'")

        if chunk.section:
            parts.append(f"section '{chunk.section}'")

        if chunk.page_num is not None:
            parts.append(f"(page {chunk.page_num})")

        if not parts:
            return ""

        return " ".join(parts) + ". "
