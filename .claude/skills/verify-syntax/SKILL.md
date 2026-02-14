---
name: verify-syntax
description: Verifies all Python source files parse correctly and required project files exist. Use after modifying any src/ files.
disable-model-invocation: true
argument-hint: "[optional: specific file to check]"
---

# Syntax Verification

## Purpose

Ensures codebase integrity by verifying:

1. **Parse Validity** — All Python files in `src/` are valid Python syntax
2. **File Completeness** — All expected source modules exist
3. **Package Structure** — `__init__.py` present for proper package imports
4. **Dependency Manifest** — `requirements.txt` is parseable and well-formed

## When to Run

- After modifying any Python file in `src/`
- After adding new modules to the project
- Before creating PRs
- After resolving merge conflicts

## Related Files

| File | Purpose |
|------|---------|
| `src/__init__.py` | Package init |
| `src/config.py` | Configuration module |
| `src/processors.py` | OCR pipeline |
| `src/database.py` | Vector database |
| `src/chunking.py` | Semantic chunking |
| `src/metadata.py` | Metadata store |
| `src/graph.py` | Knowledge graph |
| `src/agent_tools.py` | Query engine and tools |
| `src/ingest.py` | Orchestration pipeline |
| `src/backup.py` | Backup/export/import |
| `requirements.txt` | Python dependencies |

## Workflow

### Check 1: All expected source files exist

**File:** `src/`

**Check:** Verify every expected module is present.

```bash
for f in src/__init__.py src/config.py src/processors.py src/database.py src/chunking.py src/metadata.py src/graph.py src/agent_tools.py src/ingest.py src/backup.py; do
  ls "$f" 2>/dev/null || echo "MISSING: $f"
done
```

**PASS:** All files exist (no "MISSING" output)
**FAIL:** One or more files are missing
**Fix:** Create the missing module file(s)

### Check 2: All Python files parse without syntax errors

**File:** `src/*.py`

**Check:** Each file can be parsed by Python's `ast` module.

```bash
for f in src/*.py; do
  python -c "import ast; ast.parse(open('$f').read())" 2>&1 || echo "SYNTAX ERROR: $f"
done
```

**PASS:** All files parse successfully (exit code 0 for each)
**FAIL:** Any file raises `SyntaxError`
**Fix:** Open the reported file and fix the syntax error at the indicated line

### Check 3: No concatenated import statements

**File:** `src/*.py`

**Check:** Detect `importFOO` style typos where a space is missing between `import` and the module name.

```bash
grep -rn "^import[A-Z]" src/
grep -rn "^from [a-zA-Z.]* import[A-Z]" src/
```

**PASS:** No matches found
**FAIL:** Lines matching `importFOO` pattern found
**Fix:** Add a space between `import` and the module name

### Check 4: `__init__.py` exists in `src/`

**File:** `src/__init__.py`

**Check:** Package init file is present.

```bash
ls src/__init__.py
```

**PASS:** File exists
**FAIL:** File does not exist
**Fix:** Create `src/__init__.py` (can be empty or contain package-level imports)

### Check 5: `requirements.txt` is parseable

**File:** `requirements.txt`

**Check:** Each non-empty, non-comment line matches a valid pip requirement format.

```bash
grep -n "^[^#]" requirements.txt | grep -v "^[0-9]*:$" | grep -vE "^[0-9]*:[a-zA-Z0-9_-]+((\[.*\])?([><=!~]+[0-9a-zA-Z.*]+)?(,\s*[><=!~]+[0-9a-zA-Z.*]+)*)?$"
```

**PASS:** No invalid lines found
**FAIL:** Lines that don't match requirement format
**Fix:** Fix the formatting of the reported lines in `requirements.txt`

## Output Format

```markdown
| # | Check | File | Status | Details |
|---|-------|------|--------|---------|
| 1 | Expected files exist | src/ | PASS/FAIL | List missing files |
| 2 | Python syntax valid | src/*.py | PASS/FAIL | Files with errors |
| 3 | No import typos | src/*.py | PASS/FAIL | Lines with issues |
| 4 | __init__.py exists | src/__init__.py | PASS/FAIL | - |
| 5 | requirements.txt valid | requirements.txt | PASS/FAIL | Invalid lines |
```

## Exceptions

The following are **NOT violations**:

1. **Comments containing import-like text** — Comments or docstrings with `importFoo` are not code and not violations
2. **String literals** — Import-like patterns inside string literals (e.g., error messages) are not violations
3. **Empty `__init__.py`** — An empty init file is valid; it only needs to exist
4. **Extra `.py` files in `src/`** — Files beyond the expected list are not violations (only missing expected files are)
