---
name: verify-embedding-coverage
description: Verifies BGE-M3 embedding with LanceDB vector store and no legacy dependencies. Use after modifying src/database.py.
disable-model-invocation: true
argument-hint: "[optional: specific check name]"
---

# Embedding & Vector DB Verification

## Purpose

Ensures embedding and vector database correctness by verifying:

1. **Embedding Engine** — BGE-M3 model via sentence-transformers with GPU support
2. **Vector Store** — LanceDB used (not ChromaDB)
3. **No Legacy Dependencies** — No chromadb or neo4j imports
4. **Hybrid Search** — Vector + keyword hybrid search capability

## When to Run

- After modifying `src/database.py`
- After changing embedding-related dependencies
- Before PRs that touch vector search

## Related Files

| File | Purpose |
|------|---------|
| `src/database.py` | EmbeddingEngine and VectorDatabase classes |
| `src/config.py` | Embedding model and device configuration |

## Workflow

### Check 1: Required classes exist

**File:** `src/database.py`

**Check:** Both `EmbeddingEngine` and `VectorDatabase` classes are defined.

```bash
ls src/database.py
grep -n "class EmbeddingEngine" src/database.py
grep -n "class VectorDatabase" src/database.py
```

**PASS:** Both classes found
**FAIL:** One or both classes missing
**Fix:** Define the missing class(es) in `src/database.py`

### Check 2: BGE-M3 embedding model referenced

**File:** `src/database.py`

**Check:** The BGE-M3 model identifier is referenced.

```bash
grep -n "bge-m3\|BGE-M3\|BAAI/bge-m3" src/database.py
```

**PASS:** BGE-M3 model reference found
**FAIL:** No BGE-M3 reference
**Fix:** Use `BAAI/bge-m3` as the embedding model in `EmbeddingEngine`

### Check 3: sentence-transformers imported

**File:** `src/database.py`

**Check:** The `sentence-transformers` library is used for embedding.

```bash
grep -n "sentence_transformers\|SentenceTransformer" src/database.py
```

**PASS:** Import or usage found
**FAIL:** No sentence-transformers reference
**Fix:** Add `from sentence_transformers import SentenceTransformer`

### Check 4: LanceDB imported (not ChromaDB)

**File:** `src/database.py`

**Check:** `lancedb` is the vector database, not `chromadb`.

```bash
grep -n "lancedb" src/database.py
```

**PASS:** `lancedb` import found
**FAIL:** No `lancedb` reference
**Fix:** Add `import lancedb` and use LanceDB for vector storage

### Check 5: No chromadb imports in database module

**File:** `src/database.py`

**Check:** ChromaDB is fully removed from the database module.

```bash
grep -n "chromadb" src/database.py
```

**PASS:** No matches found (zero results)
**FAIL:** `chromadb` reference still present
**Fix:** Remove all `chromadb` imports and references; replace with `lancedb`

### Check 6: No neo4j imports anywhere in src/

**File:** `src/*.py`

**Check:** Neo4j is not used anywhere in the source (replaced by file-based graph).

```bash
grep -rn "neo4j" src/
```

**PASS:** No matches found (zero results)
**FAIL:** `neo4j` references found in source files
**Fix:** Remove all `neo4j` imports and references; use file-based knowledge graph instead

### Check 7: GPU device detection used

**File:** `src/database.py`

**Check:** Embedding uses `detect_device` for GPU auto-detection.

```bash
grep -n "detect_device\|device" src/database.py
```

**PASS:** `detect_device` or device parameter usage found
**FAIL:** No device handling
**Fix:** Import and use `detect_device()` from `src/config.py` for embedding model device placement

### Check 8: hybrid_search method exists

**File:** `src/database.py`

**Check:** A `hybrid_search` method is defined for combined vector + keyword search.

```bash
grep -n "def hybrid_search\|def hybrid_query" src/database.py
```

**PASS:** Hybrid search method found
**FAIL:** No hybrid search capability
**Fix:** Add `def hybrid_search(self, query, ...)` method to `VectorDatabase`

## Output Format

```markdown
| # | Check | File | Status | Details |
|---|-------|------|--------|---------|
| 1 | Required classes | src/database.py | PASS/FAIL | Missing classes |
| 2 | BGE-M3 model | src/database.py | PASS/FAIL | - |
| 3 | sentence-transformers | src/database.py | PASS/FAIL | - |
| 4 | LanceDB import | src/database.py | PASS/FAIL | - |
| 5 | No chromadb | src/database.py | PASS/FAIL | Lines found |
| 6 | No neo4j | src/*.py | PASS/FAIL | Lines found |
| 7 | GPU device detection | src/database.py | PASS/FAIL | - |
| 8 | hybrid_search method | src/database.py | PASS/FAIL | - |
```

## Exceptions

The following are **NOT violations**:

1. **ChromaDB/Neo4j in comments** — References in comments explaining migration (e.g., `# Replaced chromadb with lancedb`) are not violations
2. **Generic `device` parameter** — A `device` parameter in function signatures is acceptable even without explicitly calling `detect_device` if the caller passes it
3. **BGE-M3 model name in config** — The model name may be defined in `src/config.py` Settings rather than hardcoded in `src/database.py`; check config if not found in database module
