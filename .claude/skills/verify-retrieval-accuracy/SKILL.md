---
name: verify-retrieval-accuracy
description: Verifies query engine structure with agentic RAG tools and source attribution. Use after modifying src/agent_tools.py.
disable-model-invocation: true
argument-hint: "[optional: specific check name]"
---

# Retrieval & Query Engine Verification

## Purpose

Ensures retrieval accuracy by verifying:

1. **Query Engine** — `QueryEngine` class with query classification and result merging
2. **Agentic Tools** — Tool functions for vector search, graph search, TOC, sections, and metadata
3. **Data Models** — `SearchResult` and `QueryResponse` dataclasses with proper fields
4. **Source Attribution** — Results include book title, chapter, and page information

## When to Run

- After modifying `src/agent_tools.py`
- After changing search or query logic
- Before PRs that touch retrieval functionality

## Related Files

| File | Purpose |
|------|---------|
| `src/agent_tools.py` | Query engine and agentic RAG tools |
| `src/database.py` | Vector search backend |
| `src/graph.py` | Knowledge graph search backend |

## Workflow

### Check 1: QueryEngine class exists

**File:** `src/agent_tools.py`

**Check:** File exists and defines the `QueryEngine` class.

```bash
ls src/agent_tools.py
grep -n "class QueryEngine" src/agent_tools.py
```

**PASS:** File exists and class is defined
**FAIL:** File or class missing
**Fix:** Create `src/agent_tools.py` with `class QueryEngine:`

### Check 2: Required QueryEngine methods

**File:** `src/agent_tools.py`

**Check:** QueryEngine has query, classify, graph augment, and merge methods.

```bash
grep -n "def query" src/agent_tools.py
grep -n "def _classify_query" src/agent_tools.py
grep -n "def _graph_augment" src/agent_tools.py
grep -n "def _merge_results" src/agent_tools.py
```

**PASS:** All four methods found
**FAIL:** One or more methods missing
**Fix:** Add the missing method(s) to `QueryEngine`

### Check 3: Tool functions defined

**File:** `src/agent_tools.py`

**Check:** All required agentic RAG tool functions are defined.

```bash
grep -n "def search_vector\|def search_vectors" src/agent_tools.py
grep -n "def search_graph" src/agent_tools.py
grep -n "def get_book_toc" src/agent_tools.py
grep -n "def get_section" src/agent_tools.py
grep -n "def search_by_metadata" src/agent_tools.py
```

**PASS:** All five tool functions found
**FAIL:** One or more tool functions missing
**Fix:** Define the missing tool function(s)

### Check 4: SearchResult dataclass

**File:** `src/agent_tools.py`

**Check:** `SearchResult` dataclass is defined.

```bash
grep -n "class SearchResult" src/agent_tools.py
```

**PASS:** Class found
**FAIL:** Class missing
**Fix:** Define `@dataclass class SearchResult:` with fields for content, score, and source metadata

### Check 5: QueryResponse dataclass

**File:** `src/agent_tools.py`

**Check:** `QueryResponse` dataclass is defined.

```bash
grep -n "class QueryResponse" src/agent_tools.py
```

**PASS:** Class found
**FAIL:** Class missing
**Fix:** Define `@dataclass class QueryResponse:` with fields for results, query type, and metadata

### Check 6: Source attribution fields

**File:** `src/agent_tools.py`

**Check:** Source attribution fields are present in data models for traceability.

```bash
grep -n "book_title\|book_name" src/agent_tools.py
grep -n "chapter" src/agent_tools.py
grep -n "page_num\|page_number\|page" src/agent_tools.py
```

**PASS:** All three attribution fields (book title, chapter, page) are referenced
**FAIL:** Missing source attribution fields
**Fix:** Add `book_title`, `chapter`, and `page_num` fields to `SearchResult`

## Output Format

```markdown
| # | Check | File | Status | Details |
|---|-------|------|--------|---------|
| 1 | QueryEngine class | src/agent_tools.py | PASS/FAIL | - |
| 2 | Required methods | src/agent_tools.py | PASS/FAIL | Missing methods |
| 3 | Tool functions | src/agent_tools.py | PASS/FAIL | Missing functions |
| 4 | SearchResult dataclass | src/agent_tools.py | PASS/FAIL | - |
| 5 | QueryResponse dataclass | src/agent_tools.py | PASS/FAIL | - |
| 6 | Source attribution | src/agent_tools.py | PASS/FAIL | Missing fields |
```

## Exceptions

The following are **NOT violations**:

1. **Alternative field names** — `book_name` instead of `book_title`, or `page_number` instead of `page_num` are acceptable variants
2. **Tool functions as methods** — Tool functions defined as methods of a class (e.g., `QueryEngine.search_vector`) rather than standalone functions are acceptable
3. **Dataclass alternatives** — Using Pydantic `BaseModel` instead of `@dataclass` for `SearchResult` and `QueryResponse` is acceptable
