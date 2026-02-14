"""Agentic RAG query engine and tools for Bibliotheca AI.

Implements hybrid search pipeline:
1. Query analysis (type classification)
2. Parallel retrieval (dense + sparse via LanceDB)
3. Reranking
4. Parent chunk expansion
5. Response synthesis with source attribution
"""
import logging
import re
from dataclasses import dataclass, asdict
from typing import Optional

from src.config import get_settings
from src.database import VectorDatabase, EmbeddingEngine
from src.graph import KnowledgeGraph
from src.metadata import MetadataStore

logger = logging.getLogger("bibliotheca.agent_tools")

# Keywords used for heuristic query classification
_COMPARISON_KEYWORDS = [
    "compare", "comparison", "vs", "versus", "difference", "differ",
    "contrast", "similar", "unlike", "비교", "차이", "다른",
]
_CONCEPT_KEYWORDS = [
    "explain", "what is", "define", "definition", "concept", "theory",
    "의미", "개념", "설명", "정의",
]
_FACTUAL_KEYWORDS = [
    "who", "when", "where", "how many", "which year", "누가", "언제", "어디",
]


@dataclass
class SearchResult:
    text: str
    score: float
    source_file: str
    book_title: str = ""
    chapter: str = ""
    section: str = ""
    page_num: Optional[int] = None


@dataclass
class QueryResponse:
    answer: str
    sources: list[SearchResult]
    query_type: str = ""


class QueryEngine:
    """Hybrid search query engine with agentic RAG capabilities."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = VectorDatabase()
        self.embedder = EmbeddingEngine()
        self.graph = KnowledgeGraph()
        self.metadata_store = MetadataStore()
        logger.info("QueryEngine initialized")

    def query(self, query_text: str, top_k: int = 10, filters: Optional[dict] = None) -> QueryResponse:
        """Main query entry point with hybrid search."""
        query_type = self._classify_query(query_text)
        logger.info("Query: '%s' classified as: %s", query_text, query_type)

        # Get embedding
        query_embedding = self.embedder.embed_query(query_text)

        # Hybrid search
        results = self.db.hybrid_search(
            query_text, query_embedding, top_k=top_k, filters=filters,
        )

        # Convert to SearchResult objects
        search_results = [self._to_search_result(r) for r in results]

        # Parent chunk expansion: replace child results with parent text for richer context
        search_results = self._expand_parents(search_results, results)

        # Graph augmentation for concept queries
        if query_type in ("concept_explanation", "cross_book_comparison"):
            graph_results = self._graph_augment(query_text)
            search_results = self._merge_results(search_results, graph_results)

        return QueryResponse(
            answer="",  # Caller synthesizes with LLM
            sources=search_results[:top_k],
            query_type=query_type,
        )

    def _classify_query(self, query: str) -> str:
        """Classify query type using keyword heuristics.

        Returns one of: fact_lookup, concept_explanation, cross_book_comparison.
        """
        query_lower = query.lower()

        for kw in _COMPARISON_KEYWORDS:
            if kw in query_lower:
                return "cross_book_comparison"

        for kw in _CONCEPT_KEYWORDS:
            if kw in query_lower:
                return "concept_explanation"

        for kw in _FACTUAL_KEYWORDS:
            if kw in query_lower:
                return "fact_lookup"

        # Default to concept explanation for longer queries, fact lookup for short
        if len(query.split()) > 8:
            return "concept_explanation"
        return "fact_lookup"

    def _to_search_result(self, raw_result: dict) -> SearchResult:
        """Convert a raw LanceDB result dict to a SearchResult."""
        score = 1.0 - raw_result.get("_distance", 0.0)
        page_num_raw = raw_result.get("page_num")
        page_num = int(page_num_raw) if page_num_raw is not None and page_num_raw != 0 else None

        return SearchResult(
            text=raw_result.get("text", ""),
            score=score,
            source_file=raw_result.get("source_file", ""),
            book_title=raw_result.get("book_title", ""),
            chapter=raw_result.get("chapter", ""),
            section=raw_result.get("section", ""),
            page_num=page_num,
        )

    def _expand_parents(self, search_results: list[SearchResult], raw_results: list[dict]) -> list[SearchResult]:
        """Expand child chunks to their parent chunks for richer context.

        If a result has a parent_id and is not itself a parent, fetch the parent
        text and prepend it for context.
        """
        expanded: list[SearchResult] = []
        seen_parents: dict[str, Optional[dict]] = {}

        for sr, raw in zip(search_results, raw_results):
            parent_id = raw.get("parent_id", "")
            is_parent = raw.get("is_parent", False)

            if parent_id and not is_parent:
                if parent_id not in seen_parents:
                    seen_parents[parent_id] = self.db.get_parent(parent_id)
                parent = seen_parents[parent_id]
                if parent:
                    sr = SearchResult(
                        text=parent.get("text", "") + "\n---\n" + sr.text,
                        score=sr.score,
                        source_file=sr.source_file,
                        book_title=sr.book_title,
                        chapter=sr.chapter,
                        section=sr.section,
                        page_num=sr.page_num,
                    )
            expanded.append(sr)
        return expanded

    def _graph_augment(self, query: str) -> list[SearchResult]:
        """Extract key terms from query and retrieve graph context."""
        graph_results: list[SearchResult] = []

        # Extract candidate entity names (capitalized phrases or quoted terms)
        terms = re.findall(r'"([^"]+)"', query)
        if not terms:
            # Fall back to capitalized multi-word phrases
            terms = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query)
        if not terms:
            # Fall back to longest words (likely nouns/concepts)
            words = [w for w in query.split() if len(w) > 4]
            terms = words[:3]

        for term in terms[:5]:
            entity = self.graph.search_entity(term)
            if entity is None:
                continue

            rels = self.graph.get_relationships(entity.name)
            if not rels:
                continue

            # Build a textual summary of graph context
            rel_lines = []
            for r in rels[:10]:
                rel_lines.append(f"  {r.source} --[{r.relationship_type}]--> {r.target}")

            graph_text = (
                f"Knowledge Graph — {entity.name} ({entity.entity_type})\n"
                f"Description: {entity.description}\n"
                f"Relationships:\n" + "\n".join(rel_lines)
            )

            graph_results.append(
                SearchResult(
                    text=graph_text,
                    score=0.5,  # Lower base score for graph results
                    source_file=entity.source_book,
                    book_title=entity.source_book,
                )
            )

        return graph_results

    def _merge_results(
        self,
        vector_results: list[SearchResult],
        graph_results: list[SearchResult],
    ) -> list[SearchResult]:
        """Merge vector search results with graph-augmented results.

        Graph results are interleaved after the top vector results to ensure
        diversity without overpowering relevance-ranked results.
        """
        if not graph_results:
            return vector_results

        merged: list[SearchResult] = []
        # Insert top vector results first, then alternate graph results
        vi, gi = 0, 0
        while vi < len(vector_results) or gi < len(graph_results):
            # Add 3 vector results for every 1 graph result
            for _ in range(3):
                if vi < len(vector_results):
                    merged.append(vector_results[vi])
                    vi += 1
            if gi < len(graph_results):
                merged.append(graph_results[gi])
                gi += 1

        return merged


# -----------------------------------------------------------------
# Agentic RAG Tool Functions
# Standalone functions for use in tool-calling agents
# -----------------------------------------------------------------

def search_vector(query: str, filters: Optional[dict] = None, top_k: int = 10) -> list[dict]:
    """Semantic search + metadata filter.

    Returns a list of dicts with text, score, source_file, book_title, etc.
    """
    settings = get_settings()
    embedder = EmbeddingEngine(settings)
    db = VectorDatabase(settings)

    embedding = embedder.embed_query(query)
    results = db.search(embedding, top_k=top_k, filters=filters)

    return [
        {
            "text": r.get("text", ""),
            "score": 1.0 - r.get("_distance", 0.0),
            "source_file": r.get("source_file", ""),
            "book_title": r.get("book_title", ""),
            "chapter": r.get("chapter", ""),
            "section": r.get("section", ""),
            "page_num": r.get("page_num"),
        }
        for r in results
    ]


def search_graph(entity: str, relationship_type: Optional[str] = None) -> dict:
    """Knowledge graph traversal.

    Looks up an entity by name and returns its properties and relationships.
    """
    graph = KnowledgeGraph()
    entity_obj = graph.search_entity(entity)
    if not entity_obj:
        return {"error": f"Entity '{entity}' not found"}

    rels = graph.get_relationships(entity_obj.name, relationship_type)
    return {
        "entity": asdict(entity_obj),
        "relationships": [asdict(r) for r in rels],
    }


def search_graph_neighborhood(entity: str, depth: int = 1) -> dict:
    """Get entity neighborhood from the knowledge graph.

    Returns entities and relationships within the specified depth.
    """
    graph = KnowledgeGraph()
    entity_obj = graph.search_entity(entity)
    if not entity_obj:
        return {"error": f"Entity '{entity}' not found"}

    neighborhood = graph.get_neighbors(entity_obj.name, depth=depth)
    return {
        "entities": [asdict(e) for e in neighborhood["entities"]],
        "relationships": [asdict(r) for r in neighborhood["relationships"]],
    }


def get_book_toc(title: str) -> dict:
    """Get book table of contents / structure.

    Searches for distinct chapter/section combinations from chunks belonging
    to the given book title.
    """
    settings = get_settings()
    db = VectorDatabase(settings)
    embedder = EmbeddingEngine(settings)

    # Search for the book by title using a simple embedding query
    query_embedding = embedder.embed_query(title)
    results = db.search(query_embedding, top_k=200, filters={"book_title": title})

    if not results:
        # Try broader search without filter
        results = db.search(query_embedding, top_k=50)
        results = [r for r in results if title.lower() in r.get("book_title", "").lower()]

    # Build TOC from distinct chapter/section pairs
    toc: dict[str, list[str]] = {}
    for r in results:
        chapter = r.get("chapter", "")
        section = r.get("section", "")
        if chapter:
            if chapter not in toc:
                toc[chapter] = []
            if section and section not in toc[chapter]:
                toc[chapter].append(section)

    return {
        "book_title": title,
        "chapters": [
            {"chapter": ch, "sections": sorted(secs)}
            for ch, secs in sorted(toc.items())
        ],
        "total_chunks": len(results),
    }


def get_section(book_title: str, section_path: str) -> list[dict]:
    """Retrieve specific section from a book.

    Args:
        book_title: Title of the book.
        section_path: Chapter or section name to retrieve.

    Returns:
        List of chunk dicts ordered by page number.
    """
    settings = get_settings()
    db = VectorDatabase(settings)
    embedder = EmbeddingEngine(settings)

    # Use section_path as search query for semantic matching
    query_embedding = embedder.embed_query(f"{book_title} {section_path}")
    results = db.search(query_embedding, top_k=50, filters={"book_title": book_title})

    # Filter to matching chapter/section
    section_lower = section_path.lower()
    matching = [
        r for r in results
        if section_lower in r.get("chapter", "").lower()
        or section_lower in r.get("section", "").lower()
    ]

    # If no exact match, return all results from the search
    if not matching:
        matching = results[:20]

    # Sort by page number
    matching.sort(key=lambda r: r.get("page_num", 0))

    return [
        {
            "text": r.get("text", ""),
            "chapter": r.get("chapter", ""),
            "section": r.get("section", ""),
            "page_num": r.get("page_num"),
            "source_file": r.get("source_file", ""),
        }
        for r in matching
    ]


def search_by_metadata(
    author: str = "",
    year: Optional[int] = None,
    topic: str = "",
) -> list[dict]:
    """Metadata-based filtering across the library.

    Searches the metadata store for books matching the given criteria,
    then returns matching chunk summaries.
    """
    store = MetadataStore()
    all_books = store.get_all_books()

    matching_books = []
    for book in all_books:
        if author and author.lower() not in getattr(book, "author", "").lower():
            continue
        if year and getattr(book, "year", None) != year:
            continue
        if topic and topic.lower() not in getattr(book, "title", "").lower():
            # Also check tags/subject if available
            tags = getattr(book, "tags", []) or []
            if not any(topic.lower() in t.lower() for t in tags):
                continue
        matching_books.append(book)

    results = []
    for book in matching_books:
        results.append({
            "title": getattr(book, "title", ""),
            "author": getattr(book, "author", ""),
            "year": getattr(book, "year", None),
            "source_file": getattr(book, "source_file", ""),
            "language": getattr(book, "language", ""),
        })

    return results


def list_all_books() -> list[dict]:
    """List all books in the library."""
    store = MetadataStore()
    all_books = store.get_all_books()
    return [
        {
            "title": getattr(b, "title", ""),
            "author": getattr(b, "author", ""),
            "source_file": getattr(b, "source_file", ""),
        }
        for b in all_books
    ]


def graph_stats() -> dict:
    """Return knowledge graph statistics."""
    graph = KnowledgeGraph()
    return graph.get_stats()
