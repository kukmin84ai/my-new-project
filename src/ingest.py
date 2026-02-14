"""Document ingestion pipeline for Bibliotheca AI.

Orchestrates: file discovery -> dedup check -> OCR -> chunking -> embedding -> storage -> graph extraction

Supports multicore parallelization:
- Phase 1: Parallel OCR across worker processes (CPU-bound)
- Phase 2: Serial embedding on GPU + LanceDB storage (GPU-bound)
"""
import argparse
import hashlib
import logging
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

from src.config import get_settings, setup_logging
from src.processors import DocumentProcessor
from src.database import VectorDatabase
from src.embedding_providers import create_embedder
from src.chunking import ChunkingEngine
from src.metadata import MetadataStore, BookMetadata
from src.web_lookup import WebMetadataLookup
from src.graph import KnowledgeGraph, extract_triplets_prompt, Triplet

logger = logging.getLogger("bibliotheca.ingest")

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".epub", ".png", ".jpg", ".jpeg"}

# Max chunks to embed in a single call to avoid OOM on large documents
MAX_EMBED_BATCH = 2048


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


def _ocr_worker(file_path_str: str) -> dict:
    """Worker function: OCR a single file in a separate process.

    Returns serialized document dicts for IPC (avoids pickling complex objects).
    Each worker creates its own DocumentProcessor to avoid shared state.
    """
    from src.config import get_settings
    from src.processors import DocumentProcessor

    settings = get_settings()
    processor = DocumentProcessor(settings)
    file_path = Path(file_path_str)

    start = time.time()
    try:
        docs = processor.process_file(file_path)
        elapsed = time.time() - start

        # Serialize ProcessedDocument objects to plain dicts for IPC
        serialized_docs = [
            {
                "text": d.text,
                "source_file": d.source_file,
                "page_num": d.page_num,
                "language": d.language,
                "ocr_confidence": d.ocr_confidence,
                "ocr_tier_used": d.ocr_tier_used,
                "processing_time": d.processing_time,
                "metadata": d.metadata,
            }
            for d in docs
        ]

        return {
            "file_path": file_path_str,
            "status": "ok",
            "documents": serialized_docs,
            "elapsed": elapsed,
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "file_path": file_path_str,
            "status": "error",
            "documents": [],
            "elapsed": elapsed,
            "error": str(e),
        }


def ingest_directory(
    directory_path: str,
    subject: str = "default",
    force: bool = False,
    skip_graph: bool = False,
    batch_size: int = 32,
    workers: int = 0,
) -> dict:
    """Main ingestion pipeline with multicore parallelization.

    Architecture:
    - Phase 1: Parallel OCR across worker processes (CPU-bound bottleneck)
    - Phase 2: Serial embedding on GPU + LanceDB storage (GPU/IO-bound)

    Args:
        directory_path: Path to the directory containing documents.
        subject: Subject category for domain separation (e.g., "emc", "physics").
        force: If True, reprocess all files regardless of prior state.
        skip_graph: If True, skip knowledge graph triplet extraction.
        batch_size: Number of chunks to embed in a single batch.
        workers: Number of parallel OCR workers (0 = auto-detect).

    Returns:
        Summary dict with processed/skipped/error counts.
    """
    settings = get_settings()
    logger.info("Starting ingestion from: %s", directory_path)

    # Auto-detect worker count: leave 2 cores for main process + OS
    if workers <= 0:
        cpu_count = multiprocessing.cpu_count()
        workers = max(1, min(cpu_count - 2, 8))
    logger.info("Using %d OCR worker processes", workers)

    # Initialize components (main process only — GPU + SQLite not fork-safe)
    meta_store = MetadataStore()
    web_lookup = WebMetadataLookup(settings)
    chunker = ChunkingEngine(settings)
    embedder = create_embedder(settings)
    db = VectorDatabase(settings, subject=subject, vector_dim=embedder.dimension)
    graph = KnowledgeGraph(subject=subject)

    files = discover_files(Path(directory_path))
    logger.info("Found %d supported files", len(files))

    # Filter already-processed files
    files_to_process = []
    skipped_count = 0
    for file_path in files:
        if not force and meta_store.is_file_processed(file_path):
            skipped_count += 1
            logger.debug("Skipping (already processed): %s", file_path)
        else:
            files_to_process.append(file_path)

    logger.info(
        "%d files to process, %d skipped (already done)",
        len(files_to_process),
        skipped_count,
    )

    if not files_to_process:
        return {
            "processed": 0,
            "skipped": skipped_count,
            "errors": 0,
            "total_chunks": 0,
            "total_files": len(files),
        }

    # Sort by file size (largest first) for better load balancing
    files_to_process.sort(key=lambda p: p.stat().st_size, reverse=True)

    processed_count = 0
    error_count = 0
    total_chunks = 0

    # ── Phase 1: Parallel OCR ──────────────────────────────────────
    logger.info("Phase 1: Parallel OCR with %d workers...", workers)
    ocr_results: dict[str, dict] = {}

    if workers == 1:
        # Single-worker mode: run in main process (useful for debugging)
        for file_path in tqdm(files_to_process, desc="OCR Processing"):
            result = _ocr_worker(str(file_path))
            if result["status"] == "ok" and result["documents"]:
                ocr_results[str(file_path)] = result
                logger.info(
                    "OCR done: %s (%d pages, %.1fs)",
                    file_path.name,
                    len(result["documents"]),
                    result["elapsed"],
                )
            else:
                error_count += 1
                meta_store.update_status(
                    str(file_path), "error",
                    error_message=result.get("error", "OCR produced no output"),
                )
                logger.error("OCR failed: %s — %s", file_path.name, result.get("error"))
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_file = {
                executor.submit(_ocr_worker, str(fp)): fp
                for fp in files_to_process
            }

            for future in tqdm(
                as_completed(future_to_file),
                total=len(future_to_file),
                desc="OCR Processing",
            ):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    if result["status"] == "ok" and result["documents"]:
                        ocr_results[str(file_path)] = result
                        logger.info(
                            "OCR done: %s (%d pages, %.1fs)",
                            file_path.name,
                            len(result["documents"]),
                            result["elapsed"],
                        )
                    else:
                        error_count += 1
                        meta_store.update_status(
                            str(file_path), "error",
                            error_message=result.get("error", "OCR produced no output"),
                        )
                        logger.error(
                            "OCR failed: %s — %s",
                            file_path.name,
                            result.get("error"),
                        )
                except Exception:
                    error_count += 1
                    meta_store.update_status(str(file_path), "error")
                    logger.exception("OCR worker crashed: %s", file_path)

    logger.info(
        "Phase 1 complete: %d files OCR'd, %d errors",
        len(ocr_results),
        error_count,
    )

    # ── Phase 2: Serial Embedding + Storage ────────────────────────
    logger.info("Phase 2: Embedding + storage (GPU-accelerated)...")

    for file_path_str, ocr_result in tqdm(
        ocr_results.items(), desc="Embedding & Storage"
    ):
        file_path = Path(file_path_str)
        try:
            # Clear MPS GPU cache between files to prevent memory fragmentation
            _clear_gpu_cache()

            start_time = time.time()

            # Step 2a: Extract and register metadata
            first_text = ocr_result["documents"][0]["text"] if ocr_result["documents"] else ""
            book_meta = meta_store.extract_metadata_from_text(first_text, file_path_str)

            # Step 2a-1: Web metadata enrichment
            if web_lookup.enabled:
                try:
                    web_meta = web_lookup.lookup(book_meta)
                    if web_meta and web_meta.confidence > 0.5:
                        book_meta = web_lookup.merge_into(book_meta, web_meta)
                        logger.info(
                            "Enriched metadata from %s (confidence=%.2f)",
                            web_meta.source_api, web_meta.confidence,
                        )
                except Exception:
                    logger.debug("Web lookup failed for %s, continuing", file_path.name, exc_info=True)

            book_meta.subject = subject
            meta_store.register_file(file_path, book_meta)

            # Step 2b: Chunk all documents
            all_chunks = []
            for doc_dict in ocr_result["documents"]:
                chunks = chunker.chunk_document(
                    doc_dict["text"],
                    {
                        "source_file": file_path_str,
                        "page_num": doc_dict["page_num"],
                        "language": doc_dict["language"],
                        "ocr_confidence": doc_dict["ocr_confidence"],
                        "book_title": book_meta.title,
                        "author": book_meta.author,
                    },
                )
                all_chunks.extend(chunks)

            if not all_chunks:
                logger.warning("No chunks generated from: %s", file_path)
                meta_store.update_status(file_path_str, "empty")
                continue

            # Step 2c: Embed in batches with OOM retry
            texts = [c.context_prefix + c.text for c in all_chunks]
            all_embeddings = _embed_with_retry(embedder, texts, file_path.name)

            # Step 2d: Store in LanceDB (filter out NaN vectors)
            import math
            records = []
            nan_count = 0
            for chunk, embedding in zip(all_chunks, all_embeddings):
                if any(math.isnan(v) for v in embedding):
                    nan_count += 1
                    continue
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
                        "ocr_confidence": chunk.metadata.get("ocr_confidence", 0.0),
                        "book_title": chunk.metadata.get("book_title", "") or book_meta.title,
                        "author": chunk.metadata.get("author", "") or book_meta.author,
                        "is_parent": chunk.is_parent,
                        "context_prefix": chunk.context_prefix,
                        "subject": subject,
                        "embedding_model": settings.embedding_model,
                    }
                )
            if nan_count:
                logger.warning("Dropped %d chunks with NaN vectors from %s", nan_count, file_path.name)

            db.add_documents(records)
            total_chunks += len(records)

            # Step 2e: Knowledge graph extraction (optional)
            if not skip_graph:
                _extract_graph_triplets(all_chunks, graph, file_path_str)

            # Update processing status
            elapsed = time.time() - start_time
            meta_store.update_status(file_path_str, "done", chunk_count=len(all_chunks))
            processed_count += 1
            logger.info(
                "Stored %s: %d chunks in %.1fs",
                file_path.name,
                len(all_chunks),
                elapsed,
            )

        except Exception:
            error_count += 1
            meta_store.update_status(file_path_str, "error")
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


def _clear_gpu_cache() -> None:
    """Clear MPS/CUDA GPU cache to prevent memory fragmentation between files."""
    try:
        import torch
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
            torch.mps.synchronize()
            logger.debug("MPS cache cleared")
        elif torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug("CUDA cache cleared")
        import gc
        gc.collect()
    except Exception:
        pass


def _embed_with_retry(
    embedder,
    texts: list[str],
    file_name: str,
    initial_batch_size: int = MAX_EMBED_BATCH,
) -> list[list[float]]:
    """Embed texts with automatic batch size reduction on OOM.

    If MPS OOM occurs, clears cache, halves the batch size, and retries.
    Falls back to CPU as last resort.
    """
    batch_size = initial_batch_size
    all_embeddings: list[list[float]] = []

    while batch_size >= 64:
        all_embeddings = []
        try:
            for batch_start in range(0, len(texts), batch_size):
                batch_end = min(batch_start + batch_size, len(texts))
                batch_texts = texts[batch_start:batch_end]
                logger.info(
                    "Embedding batch %d-%d/%d for %s (batch_size=%d)",
                    batch_start + 1,
                    batch_end,
                    len(texts),
                    file_name,
                    batch_size,
                )
                batch_embeddings = embedder.embed(batch_texts)
                all_embeddings.extend(batch_embeddings)
            return all_embeddings
        except RuntimeError as e:
            if "out of memory" in str(e) or "Invalid buffer size" in str(e):
                logger.warning(
                    "OOM with batch_size=%d for %s, halving and retrying...",
                    batch_size,
                    file_name,
                )
                _clear_gpu_cache()
                batch_size //= 2
            else:
                raise

    # Final fallback: CPU embedding with small batches (only for LocalEmbedder)
    logger.warning("Falling back to CPU embedding for %s", file_name)
    _clear_gpu_cache()

    from src.embedding_providers import LocalEmbedder
    if not isinstance(embedder, LocalEmbedder):
        # API-based embedders don't have GPU fallback — re-raise
        raise RuntimeError(f"Embedding failed for {file_name} after batch reduction")

    original_device = embedder.model.device
    embedder.model.to("cpu")
    original_batch_size = embedder.batch_size
    embedder.batch_size = 8

    try:
        all_embeddings = []
        for batch_start in range(0, len(texts), 256):
            batch_end = min(batch_start + 256, len(texts))
            batch_texts = texts[batch_start:batch_end]
            logger.info(
                "CPU embedding %d-%d/%d for %s",
                batch_start + 1,
                batch_end,
                len(texts),
                file_name,
            )
            batch_embeddings = embedder.embed(batch_texts)
            all_embeddings.extend(batch_embeddings)
        return all_embeddings
    finally:
        # Restore GPU device
        embedder.model.to(str(original_device))
        embedder.batch_size = original_batch_size
        _clear_gpu_cache()


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
        logger.debug(
            "Graph extraction prompt generated for chunk %s (%d chars)",
            getattr(chunk, "chunk_id", "unknown"),
            len(prompt),
        )


def ingest_single_file(
    file_path: str,
    subject: str = "default",
    force: bool = False,
    skip_graph: bool = False,
) -> dict:
    """Ingest a single file into the system.

    Convenience wrapper for processing individual files outside of
    directory-level ingestion.

    Args:
        file_path: Path to the file to ingest.
        subject: Subject category for domain separation.
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
        subject=subject,
        force=force,
        skip_graph=skip_graph,
        workers=1,
    )


if __name__ == "__main__":
    # Use spawn method for macOS compatibility (fork can cause issues with GPU)
    multiprocessing.set_start_method("spawn", force=True)

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
        "--subject",
        type=str,
        default="default",
        help="Subject category (e.g., emc, physics, medical)",
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
        "--workers",
        type=int,
        default=0,
        help="Number of parallel OCR workers (0 = auto-detect, default: 0)",
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
        os.environ["BIBLIO_GPU_DEVICE"] = args.device

    result = ingest_directory(
        args.dir,
        subject=args.subject,
        force=args.force,
        skip_graph=args.skip_graph,
        workers=args.workers,
    )
    logger.info("Final summary: %s", result)
