---
name: verify-incremental-ingest
description: Verifies incremental processing with file hash dedup and force-reprocess support. Use after modifying src/metadata.py or src/ingest.py.
disable-model-invocation: true
argument-hint: "[optional: specific check name]"
---

# Incremental Ingest Verification

## Purpose

Ensures incremental processing integrity by verifying:

1. **Metadata Store** — `MetadataStore` class with SQLite-backed file manifest
2. **File Hashing** — SHA-256 based deduplication via `compute_file_hash`
3. **Skip Logic** — `is_file_processed` check before processing
4. **Force Reprocess** — `--force` flag support for full reprocessing

## When to Run

- After modifying `src/metadata.py`
- After modifying `src/ingest.py`
- After changing file processing or deduplication logic
- Before PRs that touch the ingest pipeline

## Related Files

| File | Purpose |
|------|---------|
| `src/metadata.py` | MetadataStore class with SQLite manifest |
| `src/ingest.py` | Orchestration pipeline with incremental processing |

## Workflow

### Check 1: MetadataStore class exists

**File:** `src/metadata.py`

**Check:** File exists and defines the `MetadataStore` class.

```bash
ls src/metadata.py
grep -n "class MetadataStore" src/metadata.py
```

**PASS:** File exists and class is defined
**FAIL:** File or class missing
**Fix:** Create `src/metadata.py` with `class MetadataStore:`

### Check 2: compute_file_hash method

**File:** `src/metadata.py`

**Check:** A `compute_file_hash` method or function exists for SHA-256 hashing.

```bash
grep -n "def compute_file_hash\|def _compute_file_hash\|def file_hash" src/metadata.py
grep -n "sha256\|SHA256\|hashlib" src/metadata.py
```

**PASS:** Hash computation method found with SHA-256 reference
**FAIL:** No file hashing capability
**Fix:** Add `def compute_file_hash(self, file_path) -> str:` using `hashlib.sha256`

### Check 3: is_file_processed method

**File:** `src/metadata.py`

**Check:** A method to check if a file has already been processed exists.

```bash
grep -n "def is_file_processed\|def is_processed\|def file_exists" src/metadata.py
```

**PASS:** File-processed check method found
**FAIL:** No method to check processed status
**Fix:** Add `def is_file_processed(self, file_path) -> bool:` that checks the SQLite manifest

### Check 4: SQLite usage for manifest

**File:** `src/metadata.py`

**Check:** SQLite is used as the backing store for the metadata manifest.

```bash
grep -n "sqlite3\|sqlite\|SQLite" src/metadata.py
```

**PASS:** SQLite reference found
**FAIL:** No SQLite usage
**Fix:** Use `import sqlite3` for the metadata manifest storage

### Check 5: Ingest pipeline checks is_file_processed

**File:** `src/ingest.py`

**Check:** The ingest pipeline calls `is_file_processed` before processing each file.

```bash
grep -n "is_file_processed\|is_processed\|file_exists" src/ingest.py
```

**PASS:** Processed-file check found in ingest pipeline
**FAIL:** No skip-if-processed logic
**Fix:** Add `if metadata_store.is_file_processed(file_path): continue` before processing

### Check 6: Force reprocess flag

**File:** `src/ingest.py`

**Check:** A `--force` flag or `force` parameter exists for reprocessing all files.

```bash
grep -n "force\|--force\|force_reprocess\|reprocess" src/ingest.py
```

**PASS:** Force reprocess option found
**FAIL:** No force reprocess capability
**Fix:** Add `--force` CLI argument or `force: bool = False` parameter that skips the `is_file_processed` check

## Output Format

```markdown
| # | Check | File | Status | Details |
|---|-------|------|--------|---------|
| 1 | MetadataStore class | src/metadata.py | PASS/FAIL | - |
| 2 | compute_file_hash | src/metadata.py | PASS/FAIL | SHA-256 usage |
| 3 | is_file_processed | src/metadata.py | PASS/FAIL | - |
| 4 | SQLite manifest | src/metadata.py | PASS/FAIL | - |
| 5 | Skip-if-processed | src/ingest.py | PASS/FAIL | - |
| 6 | Force reprocess flag | src/ingest.py | PASS/FAIL | - |
```

## Exceptions

The following are **NOT violations**:

1. **Alternative method names** — `is_processed`, `check_processed`, or `file_exists` are acceptable alternatives to `is_file_processed`
2. **Force flag variants** — `--force`, `--reprocess`, `force=True`, or `reprocess_all` are all acceptable implementations of force reprocessing
3. **Hash algorithm in comments** — Mentioning SHA-256 or other algorithms in comments is informational, not a code issue
