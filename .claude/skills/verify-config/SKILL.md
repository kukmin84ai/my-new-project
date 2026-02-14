---
name: verify-config
description: Verifies configuration module uses Pydantic BaseSettings with no hardcoded values. Use after modifying src/config.py or .env.example.
disable-model-invocation: true
argument-hint: "[optional: specific check name]"
---

# Configuration Verification

## Purpose

Ensures configuration correctness by verifying:

1. **Settings Class** — `src/config.py` defines a proper Pydantic `BaseSettings` class
2. **No Hardcoded Values** — Source files use configuration variables, not inline literals
3. **Environment Template** — `.env.example` documents all required `BIBLIO_*` variables
4. **GPU Detection** — `GPUDevice` enum and `detect_device()` function exist

## When to Run

- After modifying `src/config.py`
- After modifying `.env.example`
- After adding new configuration parameters
- Before creating PRs that touch configuration

## Related Files

| File | Purpose |
|------|---------|
| `src/config.py` | Pydantic BaseSettings configuration |
| `.env.example` | Environment variable template |

## Workflow

### Check 1: Settings class with BaseSettings

**File:** `src/config.py`

**Check:** File exists and defines a `Settings` class that inherits from `BaseSettings`.

```bash
grep -n "class Settings" src/config.py
grep -n "BaseSettings" src/config.py
```

**PASS:** Both `class Settings` and `BaseSettings` are found
**FAIL:** Either is missing
**Fix:** Define `class Settings(BaseSettings):` in `src/config.py`

### Check 2: get_settings() function exists

**File:** `src/config.py`

**Check:** A `get_settings()` function is defined for accessing the singleton settings instance.

```bash
grep -n "def get_settings" src/config.py
```

**PASS:** Function definition found
**FAIL:** No `get_settings` function
**Fix:** Add `def get_settings() -> Settings:` function that returns a cached Settings instance

### Check 3: detect_device() function exists

**File:** `src/config.py`

**Check:** A `detect_device()` function is defined for GPU auto-detection.

```bash
grep -n "def detect_device" src/config.py
```

**PASS:** Function definition found
**FAIL:** No `detect_device` function
**Fix:** Add `def detect_device() -> GPUDevice:` function

### Check 4: GPUDevice enum with all variants

**File:** `src/config.py`

**Check:** `GPUDevice` enum includes auto, cuda, mps, and cpu variants.

```bash
grep -n "class GPUDevice" src/config.py
grep -n "auto" src/config.py
grep -n "cuda" src/config.py
grep -n "mps" src/config.py
grep -n "cpu" src/config.py
```

**PASS:** `GPUDevice` enum exists with all four variants (auto, cuda, mps, cpu)
**FAIL:** Enum missing or incomplete
**Fix:** Define `class GPUDevice(str, Enum)` with `auto`, `cuda`, `mps`, `cpu` members

### Check 5: No hardcoded values in source files

**File:** `src/*.py`

**Check:** Common hardcoded values that should be configuration variables are absent from source code (excluding comments and docstrings).

```bash
grep -rn '"./chroma_db"' src/
grep -rn '"bibliotheca"' src/
grep -rn 'language="en"' src/
grep -rn 'max_triplets=2' src/
```

**PASS:** No matches found (all zero results)
**FAIL:** Hardcoded values found in source files
**Fix:** Replace hardcoded values with references to `Settings` fields via `get_settings()`

### Check 6: .env.example exists with BIBLIO_ variables

**File:** `.env.example`

**Check:** Environment template exists and contains `BIBLIO_` prefixed variables.

```bash
ls .env.example
grep -c "BIBLIO_" .env.example
```

**PASS:** File exists and contains one or more `BIBLIO_*` variables
**FAIL:** File missing or no `BIBLIO_` variables
**Fix:** Create `.env.example` with all required `BIBLIO_*` environment variables

## Output Format

```markdown
| # | Check | File | Status | Details |
|---|-------|------|--------|---------|
| 1 | Settings class | src/config.py | PASS/FAIL | BaseSettings inheritance |
| 2 | get_settings() | src/config.py | PASS/FAIL | Function presence |
| 3 | detect_device() | src/config.py | PASS/FAIL | Function presence |
| 4 | GPUDevice enum | src/config.py | PASS/FAIL | Enum completeness |
| 5 | No hardcoded values | src/*.py | PASS/FAIL | Matches found |
| 6 | .env.example | .env.example | PASS/FAIL | BIBLIO_ var count |
```

## Exceptions

The following are **NOT violations**:

1. **Hardcoded values in comments or docstrings** — Documentation examples like `# default: "./chroma_db"` are not violations
2. **Default values in Settings class fields** — `Field(default="bibliotheca")` in the Settings class itself is acceptable as it defines the configurable default
3. **Test files** — Hardcoded values in test fixtures are acceptable for deterministic testing
