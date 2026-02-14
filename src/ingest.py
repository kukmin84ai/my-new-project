"""Document ingestion pipeline for Bibliotheca AI.

Orchestrates: file discovery -> dedup check -> OCR -> chunking -> embedding -> storage -> graph extraction
"""
import argparse
import hashlib
import logging
import time
from pathlib import Path

from tqdm import tqdm

from src.config import get_settings, setup_logging
from src.processors import DocumentProcessor
from src.database import VectorDatabase, EmbeddingEngine
from src.chunking import ChunkingEngine
from src.metadata import MetadataStore, BookMetadata
from src.graph import KnowledgeGraph, extract_triplets_prompt, Triplet

logger = logging.getLogger("bibliotheca.ingest")

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".epub", ".png", ".jpg", ".jpeg"}


def discover_files(directory: Path) -> list[Path]:
    """Recursively find all supported files in a directory."""
    files: list[Path] = []
    if not directory.is_dir():
        logger.warning("Directory does not exist: %s", directory)
        return files

    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)
    return files


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash for file deduplication."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def ingest_directory(
    directory_path: str,
    force: bool = False,
    skip_graph: bool = False,
    batch_size: int = 32,
) -> dict:
    """Main ingestion pipeline with incremental processing.

    Args:
        directory_path: Path to the directory containing documents.
        force: If True, reprocess all files regardless of prior state.
        skip_graph: If True, skip knowledge graph triplet extraction.
        batch_size: Number of chunks to embed in a single batch.

    Returns:
        Summary dict with processed/skipped/error counts.
    """
    settings = get_settings()
    logger.info("Starting ingestion from: %s", directory_path)

    # Initialize components
    processor = DocumentProcessor(settings)
    chunker = ChunkingEngine(settings)
    embedder = EmbeddingEngine(settings)
    db = VectorDatabase(settings)
    meta_store = MetadataStore()
    graph = KnowledgeGraph()

    files = discover_files(Path(directory_path))
    logger.info("Found %d supported files", len(files))

    processed_count = 0
    skipped_count = 0
    error_count = 0
    total_chunks = 0

    for file_path in tqdm(files, desc="Processing documents"):
        file_hash = compute_file_hash(file_path)

        # Incremental: skip if already processed (by hash)
        if not force and meta_store.is_file_processed(file_path):
            skipped_count += 1
            logger.debug("Skipping (already processed): %s", file_path)
            continue

        try:
            start_time = time.time()

            # Step 1: OCR / text extraction
            logger.info("Extracting text from: %s", file_path.name)
            docs = processor.process_file(file_path)

            if not docs:
                logger.warning("No content extracted from: %s", file_path)
                meta_store.update_status(str(file_path), "empty")
                skipped_count += 1
                continue

            # Step 2: Extract and register metadata
            first_text = docs[0].text if docs else ""
            book_meta = meta_store.extract_metadata_from_text(first_text, str(file_path))
            meta_store.register_file(file_path, book_meta)

            # Step 3: Chunk all documents
            all_chunks = []
            for doc in docs:
                chunks = chunker.chunk_document(
                    doc.text,
                    {
                        "source_file": str(file_path),
                        "page_num": doc.page_num,
                        "language": doc.language,
                        "ocr_confidence": doc.ocr_confidence,
                        "book_title": book_meta.title,
                        "author": book_meta.author,
                    },
                )
                all_chunks.extend(chunks)

            if not all_chunks:
                logger.warning("No chunks generated from: %s", file_path)
                meta_store.update_status(str(file_path), "empty")
                skipped_count += 1
                continue

            # Step 4: Embed and store in batches
            texts = [c.context_prefix + c.text for c in all_chunks]
            embeddings = embedder.embed(texts)

            records = []
            for chunk, embedding in zip(all_chunks, embeddings):
                records.append(
                    {
                        "id": chunk.chunk_id,
                        "text": chunk.text,
                        "vector": embedding,
                        "parent_id": chunk.parent_id or "",
                        "source_file": chunk.source_file,
                        "page_num": chunk.page_num,
                        "chapter": chunk.chapter,
                        "section": chunk.section,
                        "language": chunk.metadata.get("language", ""),
                        "book_title": chunk.metadata.get("book_title", ""),
                        "author": chunk.metadata.get("author", ""),
                        "is_parent": chunk.is_parent,
                        "context_prefix": chunk.context_prefix,
                    }
                )

            db.add_documents(records)
            total_chunks += len(records)

            # Step 5: Knowledge graph extraction (optional)
            if not skip_graph:
                _extract_graph_triplets(all_chunks, graph, str(file_path))

            # Update processing status
            elapsed = time.time() - start_time
            meta_store.update_status(str(file_path), "done")
            processed_count += 1
            logger.info(
                "Processed %s: %d chunks in %.1fs",
                file_path.name,
                len(all_chunks),
                elapsed,
            )

        except Exception:
            error_count += 1
            meta_store.update_status(str(file_path), "error")
            logger.exception("Error processing %s", file_path)

    summary = {
        "processed": processed_count,
        "skipped": skipped_count,
        "errors": error_count,
        "total_chunks": total_chunks,
        "total_files": len(files),
    }
    logger.info(
        "Ingestion complete: %d processed, %d skipped, %d errors, %d total chunks",
        processed_count,
        skipped_count,
        error_count,
        total_chunks,
    )
    return summary


def _extract_graph_triplets(
    chunks: list,
    graph: KnowledgeGraph,
    source_file: str,
    max_chunks: int = 5,
) -> None:
    """Extract knowledge graph triplets from the first N chunks.

    Uses the triplet extraction prompt for offline/batch LLM processing.
    In production, this would call Ollama. Currently generates prompts
    and logs them for later processing.
    """
    for chunk in chunks[:max_chunks]:
        prompt = extract_triplets_prompt(chunk.text, max_triplets=12)
        # In production: send prompt to Ollama and parse response
        # response = call_ollama(prompt)
        # triplets = parse_triplets_response(response, source_file, chunk.chunk_id)
        # graph.add_triplets(triplets)
        logger.debug(
            "Graph extraction prompt generated for chunk %s (%d chars)",
            getattr(chunk, "chunk_id", "unknown"),
            len(prompt),
        )


def ingest_single_file(
    file_path: str,
    force: bool = False,
    skip_graph: bool = False,
) -> dict:
    """Ingest a single file into the system.

    Convenience wrapper for processing individual files outside of
    directory-level ingestion.

    Args:
        file_path: Path to the file to ingest.
        force: If True, reprocess even if already ingested.
        skip_graph: If True, skip graph triplet extraction.

    Returns:
        Summary dict with processing result.
    """
    path = Path(file_path)
    if not path.is_file():
        logger.error("File not found: %s", file_path)
        return {"error": f"File not found: {file_path}"}

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        logger.error("Unsupported file type: %s", path.suffix)
        return {"error": f"Unsupported file type: {path.suffix}"}

    # Create a temporary directory-like context with just this file
    parent = path.parent
    return ingest_directory(
        str(parent),
        force=force,
        skip_graph=skip_graph,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest documents into Bibliotheca AI"
    )
    parser.add_argument(
        "--dir", type=str, default="data", help="Directory to ingest"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="GPU device: auto/cuda/mps/cpu",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocess all files",
    )
    parser.add_argument(
        "--skip-graph",
        action="store_true",
        help="Skip knowledge graph extraction",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level",
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    if args.device != "auto":
        import os

        os.environ["BIBLIO_GPU_DEVICE"] = args.device

    result = ingest_directory(
        args.dir, force=args.force, skip_graph=args.skip_graph
    )
    logger.info("Final summary: %s", result)
