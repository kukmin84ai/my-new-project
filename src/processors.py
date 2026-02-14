"""3-tier OCR and document processing pipeline for Bibliotheca AI.

Tier 1: Marker (Surya OCR) - primary local GPU-accelerated OCR
Tier 2: Docling (IBM) - complex tables/math handling
Tier 3: LlamaParse - cloud fallback (opt-in)
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.config import Settings, get_settings, detect_device

logger = logging.getLogger("bibliotheca.processors")


@dataclass
class ProcessedDocument:
    """Result of processing a single document or page."""

    text: str
    source_file: str
    page_num: Optional[int] = None
    language: str = "unknown"
    ocr_confidence: float = 0.0
    ocr_tier_used: str = "none"
    processing_time: float = 0.0
    metadata: dict = field(default_factory=dict)


class DocumentProcessor:
    """3-tier document processing pipeline with automatic fallback."""

    SUPPORTED_OCR_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
    TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
    EPUB_EXTENSIONS = {".epub"}

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.device = detect_device(self.settings.gpu_device)
        self._marker_model = None
        self._docling_converter = None
        logger.info("DocumentProcessor initialized with device: %s", self.device)

    def process_file(self, file_path: Path) -> list[ProcessedDocument]:
        """Process a single file through the appropriate OCR tier.

        Routing logic:
        - PDF/images -> Tier 1 (Marker) -> Tier 2 (Docling) -> Tier 3 (LlamaParse)
        - EPUB -> ebooklib extraction
        - TXT/MD -> direct read
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix in self.EPUB_EXTENSIONS:
            return self._process_epub(file_path)
        if suffix in self.TEXT_EXTENSIONS:
            return self._process_text_file(file_path)
        if suffix in self.SUPPORTED_OCR_EXTENSIONS:
            return self._process_with_ocr_pipeline(file_path)

        logger.warning("Unsupported file type: %s, attempting text read", suffix)
        return self._process_text_file(file_path)

    def _process_with_ocr_pipeline(self, file_path: Path) -> list[ProcessedDocument]:
        """Run through OCR tiers with automatic fallback."""
        # Tier 1: Marker
        if self.settings.ocr_tier1_enabled:
            try:
                results = self._process_with_marker(file_path)
                if results and any(doc.text.strip() for doc in results):
                    return results
                logger.warning("Marker produced empty output, falling through to Tier 2")
            except Exception:
                logger.exception("Tier 1 (Marker) failed for %s", file_path)

        # Tier 2: Docling
        if self.settings.ocr_tier2_enabled:
            try:
                results = self._process_with_docling(file_path)
                if results and any(doc.text.strip() for doc in results):
                    return results
                logger.warning("Docling produced empty output, falling through to Tier 3")
            except Exception:
                logger.exception("Tier 2 (Docling) failed for %s", file_path)

        # Tier 3: LlamaParse (opt-in cloud fallback)
        if self.settings.ocr_tier3_enabled:
            try:
                results = self._process_with_llamaparse(file_path)
                if results and any(doc.text.strip() for doc in results):
                    return results
            except Exception:
                logger.exception("Tier 3 (LlamaParse) failed for %s", file_path)

        logger.error("All OCR tiers failed for %s", file_path)
        return [
            ProcessedDocument(
                text="",
                source_file=str(file_path),
                ocr_tier_used="none",
                metadata={"error": "All OCR tiers failed"},
            )
        ]

    def _process_with_marker(self, file_path: Path) -> list[ProcessedDocument]:
        """Tier 1: Marker (Surya OCR) - primary local OCR.

        Features: GPU-accelerated, math formula re-detection, multi-column layout.
        """
        start = time.perf_counter()
        logger.info("Tier 1 (Marker) processing: %s", file_path)

        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        if self._marker_model is None:
            self._marker_model = create_model_dict()

        converter = PdfConverter(
            artifact_dict=self._marker_model,
        )
        result = converter(str(file_path))
        rendered = result.document

        elapsed = time.perf_counter() - start
        documents: list[ProcessedDocument] = []

        # Marker returns a full document; split by pages if available
        full_text = rendered.render_as_text()
        lang = self._detect_language(full_text)

        pages = full_text.split("\n\n---\n\n") if "\n\n---\n\n" in full_text else [full_text]
        for idx, page_text in enumerate(pages):
            if not page_text.strip():
                continue
            documents.append(
                ProcessedDocument(
                    text=page_text,
                    source_file=str(file_path),
                    page_num=idx + 1,
                    language=lang,
                    ocr_confidence=0.85,  # Marker doesn't expose per-page confidence
                    ocr_tier_used="marker",
                    processing_time=elapsed / max(len(pages), 1),
                    metadata={"ocr_engine": "marker-surya", "device": self.device},
                )
            )

        logger.info(
            "Marker completed: %d pages in %.2fs", len(documents), elapsed
        )
        return documents

    def _process_with_docling(self, file_path: Path) -> list[ProcessedDocument]:
        """Tier 2: Docling (IBM) - complex tables and math.

        Best for: structured tables, mathematical formulas, complex layouts.
        """
        start = time.perf_counter()
        logger.info("Tier 2 (Docling) processing: %s", file_path)

        from docling.document_converter import DocumentConverter

        if self._docling_converter is None:
            self._docling_converter = DocumentConverter()

        result = self._docling_converter.convert(str(file_path))
        doc = result.document

        elapsed = time.perf_counter() - start
        documents: list[ProcessedDocument] = []

        full_text = doc.export_to_markdown()
        lang = self._detect_language(full_text)

        # Split by page markers if present, otherwise treat as single document
        pages = full_text.split("\n\n---\n\n") if "\n\n---\n\n" in full_text else [full_text]
        for idx, page_text in enumerate(pages):
            if not page_text.strip():
                continue
            documents.append(
                ProcessedDocument(
                    text=page_text,
                    source_file=str(file_path),
                    page_num=idx + 1,
                    language=lang,
                    ocr_confidence=0.80,
                    ocr_tier_used="docling",
                    processing_time=elapsed / max(len(pages), 1),
                    metadata={"ocr_engine": "docling-ibm", "device": self.device},
                )
            )

        logger.info(
            "Docling completed: %d pages in %.2fs", len(documents), elapsed
        )
        return documents

    def _process_with_llamaparse(self, file_path: Path) -> list[ProcessedDocument]:
        """Tier 3: LlamaParse - cloud fallback (opt-in).

        Requires BIBLIO_LLAMA_CLOUD_API_KEY and BIBLIO_OCR_TIER3_ENABLED=true.
        """
        start = time.perf_counter()
        logger.info("Tier 3 (LlamaParse) processing: %s", file_path)

        if not self.settings.llama_cloud_api_key:
            raise ValueError("LlamaParse requires BIBLIO_LLAMA_CLOUD_API_KEY")

        from llama_parse import LlamaParse

        languages = [
            lang.strip() for lang in self.settings.ocr_languages.split(",")
        ]
        parser = LlamaParse(
            api_key=self.settings.llama_cloud_api_key,
            result_type="markdown",
            language=languages[0] if languages else "en",
            parsing_instruction=(
                "You are parsing a scholarly book. Extract all text, "
                "including captions from images. For complex images or "
                "charts, provide a detailed description. Preserve "
                "mathematical formulas and table structures."
            ),
        )

        parsed_docs = parser.load_data(str(file_path))

        elapsed = time.perf_counter() - start
        documents: list[ProcessedDocument] = []

        for idx, doc in enumerate(parsed_docs):
            text = doc.text if hasattr(doc, "text") else str(doc)
            lang = self._detect_language(text)
            documents.append(
                ProcessedDocument(
                    text=text,
                    source_file=str(file_path),
                    page_num=idx + 1,
                    language=lang,
                    ocr_confidence=0.90,
                    ocr_tier_used="llamaparse",
                    processing_time=elapsed / max(len(parsed_docs), 1),
                    metadata={"ocr_engine": "llamaparse-cloud"},
                )
            )

        logger.info(
            "LlamaParse completed: %d pages in %.2fs", len(documents), elapsed
        )
        return documents

    def _process_text_file(self, file_path: Path) -> list[ProcessedDocument]:
        """Handle plain text and markdown files via direct read."""
        start = time.perf_counter()
        logger.info("Processing text file: %s", file_path)

        text = file_path.read_text(encoding="utf-8", errors="replace")
        elapsed = time.perf_counter() - start
        lang = self._detect_language(text)

        return [
            ProcessedDocument(
                text=text,
                source_file=str(file_path),
                page_num=None,
                language=lang,
                ocr_confidence=1.0,
                ocr_tier_used="text-read",
                processing_time=elapsed,
                metadata={"ocr_engine": "direct-read"},
            )
        ]

    def _process_epub(self, file_path: Path) -> list[ProcessedDocument]:
        """Extract text from EPUB using ebooklib."""
        start = time.perf_counter()
        logger.info("Processing EPUB: %s", file_path)

        import ebooklib
        from ebooklib import epub

        book = epub.read_epub(str(file_path))
        documents: list[ProcessedDocument] = []

        chapter_num = 0
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            content = item.get_content()
            # Strip HTML tags for plain text extraction
            text = self._strip_html(content.decode("utf-8", errors="replace"))
            if not text.strip():
                continue

            chapter_num += 1
            lang = self._detect_language(text)
            documents.append(
                ProcessedDocument(
                    text=text,
                    source_file=str(file_path),
                    page_num=chapter_num,
                    language=lang,
                    ocr_confidence=1.0,
                    ocr_tier_used="epub-extract",
                    processing_time=0.0,
                    metadata={
                        "ocr_engine": "ebooklib",
                        "epub_item": item.get_name(),
                    },
                )
            )

        elapsed = time.perf_counter() - start
        for doc in documents:
            doc.processing_time = elapsed / max(len(documents), 1)

        logger.info(
            "EPUB completed: %d chapters in %.2fs", len(documents), elapsed
        )
        return documents

    def _detect_language(self, text: str) -> str:
        """Auto-detect language using langdetect."""
        if not text or len(text.strip()) < 20:
            return "unknown"
        try:
            from langdetect import detect

            return detect(text[:2000])
        except Exception:
            logger.debug("Language detection failed, returning 'unknown'")
            return "unknown"

    @staticmethod
    def _strip_html(html: str) -> str:
        """Remove HTML tags from string, keeping text content."""
        import re

        # Remove script and style elements
        clean = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL)
        # Remove tags
        clean = re.sub(r"<[^>]+>", " ", clean)
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
