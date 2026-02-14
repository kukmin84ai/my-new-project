"""MCP server for Bibliotheca AI knowledge base.

Exposes the scholarly book search tools via the Model Context Protocol,
allowing Claude CLI to query the EMC engineering book library.

Run: python -m src.mcp_server
"""
import json
import logging
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Ensure src package is importable when run as module
from src.agent_tools import (
    search_vector,
    search_graph,
    get_book_toc,
    get_section,
    search_by_metadata,
    list_all_books,
    graph_stats,
)

logger = logging.getLogger("bibliotheca.mcp")

mcp = FastMCP("bibliotheca")


def _fmt_json(data) -> str:
    """Format data as pretty-printed JSON string."""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def search_books(query: str, top_k: int = 5) -> str:
    """Search the EMC engineering book library semantically.

    Args:
        query: Natural language search query (e.g. "electromagnetic shielding techniques")
        top_k: Number of results to return (default 5)

    Returns:
        Formatted search results with text excerpts and source attribution.
    """
    results = search_vector(query, top_k=top_k)
    if not results:
        return "No results found."

    parts = []
    for i, r in enumerate(results, 1):
        source = r.get("book_title") or r.get("source_file", "Unknown")
        chapter = r.get("chapter", "")
        section = r.get("section", "")
        page = r.get("page_num")
        score = r.get("score", 0)

        location = ""
        if chapter:
            location += f" > {chapter}"
        if section:
            location += f" > {section}"
        if page:
            location += f" (p.{page})"

        parts.append(
            f"### Result {i} [score: {score:.3f}]\n"
            f"**Source**: {source}{location}\n\n"
            f"{r.get('text', '')}\n"
        )

    return "\n---\n".join(parts)


@mcp.tool()
def search_knowledge_graph(entity_name: str, relationship_type: Optional[str] = None) -> str:
    """Search the knowledge graph for entities and their relationships.

    Args:
        entity_name: Name of the entity to look up (e.g. "EMI shielding", "Henry Ott")
        relationship_type: Optional filter for relationship type

    Returns:
        Entity details and its relationships in the knowledge graph.
    """
    result = search_graph(entity_name, relationship_type)
    if "error" in result:
        return result["error"]
    return _fmt_json(result)


@mcp.tool()
def get_table_of_contents(book_title: str) -> str:
    """Get the table of contents for a specific book.

    Args:
        book_title: Title of the book (partial match supported)

    Returns:
        Chapter and section structure of the book.
    """
    result = get_book_toc(book_title)
    if not result.get("chapters"):
        return f"No table of contents found for '{book_title}'."
    return _fmt_json(result)


@mcp.tool()
def get_book_section(book_title: str, section_path: str) -> str:
    """Retrieve a specific section or chapter from a book.

    Args:
        book_title: Title of the book
        section_path: Chapter or section name to retrieve

    Returns:
        Text content of the matching section, ordered by page number.
    """
    results = get_section(book_title, section_path)
    if not results:
        return f"No content found for section '{section_path}' in '{book_title}'."

    parts = []
    for r in results:
        chapter = r.get("chapter", "")
        section = r.get("section", "")
        page = r.get("page_num")

        header = ""
        if chapter:
            header += chapter
        if section:
            header += f" > {section}"
        if page:
            header += f" (p.{page})"

        parts.append(f"**{header}**\n{r.get('text', '')}")

    return "\n\n---\n\n".join(parts)


@mcp.tool()
def find_books_by_metadata(author: str = "", year: Optional[int] = None, topic: str = "") -> str:
    """Search for books by author, publication year, or topic.

    Args:
        author: Author name to search for (partial match)
        year: Publication year
        topic: Topic keyword to search in title and tags

    Returns:
        List of matching books with metadata.
    """
    results = search_by_metadata(author=author, year=year, topic=topic)
    if not results:
        return "No matching books found."
    return _fmt_json(results)


@mcp.tool()
def list_library() -> str:
    """List all books in the Bibliotheca AI library.

    Returns:
        Complete list of all ingested books with title, author, and source file.
    """
    results = list_all_books()
    if not results:
        return "No books found in the library."
    return _fmt_json(results)


@mcp.tool()
def get_graph_stats() -> str:
    """Get knowledge graph statistics.

    Returns:
        Statistics about entities and relationships in the knowledge graph.
    """
    return _fmt_json(graph_stats())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    mcp.run()
