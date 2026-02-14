---
name: verify-ocr-quality
description: Verifies 3-tier OCR pipeline structure with language auto-detection and multi-format support. Use after modifying src/processors.py.
disable-model-invocation: true
argument-hint: "[optional: specific check name]"
---

# OCR Pipeline Verification

## Purpose

Ensures OCR pipeline quality by verifying:

1. **Pipeline Structure** — `DocumentProcessor` class with 3-tier fallback (Marker, Docling, LlamaParse)
2. **Language Detection** — Auto-detection via `langdetect`, no hardcoded language
3. **Format Support** — EPUB handling via `ebooklib`
4. **Local-First** — LlamaParse is conditional/opt-in, not the default processor

## When to Run

- After modifying `src/processors.py`
- After changing OCR-related dependencies
- Before PRs that touch document processing

## Related Files

| File | Purpose |
|------|---------|
| `src/processors.py` | 3-tier OCR pipeline implementation |
| `src/config.py` | OCR-related configuration (languages, device) |

## Workflow

### Check 1: DocumentProcessor class exists

**File:** `src/processors.py`

**Check:** File exists and defines the `DocumentProcessor` class.

```bash
ls src/processors.py
grep -n "class DocumentProcessor" src/processors.py
```

**PASS:** File exists and class is defined
**FAIL:** File or class missing
**Fix:** Create `src/processors.py` with `class DocumentProcessor:`

### Check 2: Required methods present

**File:** `src/processors.py`

**Check:** All required processing methods are defined.

```bash
grep -n "def process_file" src/processors.py
grep -n "def _process_with_marker" src/processors.py
grep -n "def _process_with_docling" src/processors.py
grep -n "def _process_with_llamaparse" src/processors.py
```

**PASS:** All four methods found
**FAIL:** One or more methods missing
**Fix:** Add the missing method(s) to `DocumentProcessor`

### Check 3: ProcessedDocument dataclass defined

**File:** `src/processors.py`

**Check:** `ProcessedDocument` dataclass is defined with required fields.

```bash
grep -n "class ProcessedDocument" src/processors.py
grep -n "dataclass\|BaseModel" src/processors.py
```

**PASS:** `ProcessedDocument` class defined as a dataclass or Pydantic model
**FAIL:** Class not found
**Fix:** Define `@dataclass class ProcessedDocument:` with fields for content, metadata, and quality metrics

### Check 4: Language auto-detection

**File:** `src/processors.py`

**Check:** `langdetect` is imported for automatic language detection.

```bash
grep -n "langdetect" src/processors.py
```

**PASS:** `langdetect` import or usage found
**FAIL:** No reference to `langdetect`
**Fix:** Add `from langdetect import detect` and use it for language auto-detection

### Check 5: No hardcoded language

**File:** `src/processors.py`

**Check:** No `language="en"` hardcoding exists.

```bash
grep -n 'language="en"' src/processors.py
grep -n "language='en'" src/processors.py
```

**PASS:** No matches found
**FAIL:** Hardcoded English language setting found
**Fix:** Use `langdetect` for auto-detection or reference `Settings` for language config

### Check 6: EPUB support via ebooklib

**File:** `src/processors.py`

**Check:** `ebooklib` is referenced for EPUB handling.

```bash
grep -n "ebooklib" src/processors.py
```

**PASS:** `ebooklib` import or usage found
**FAIL:** No EPUB handling
**Fix:** Add `import ebooklib` for EPUB format support

### Check 7: Local OCR engines referenced

**File:** `src/processors.py`

**Check:** Marker and Docling are referenced as local OCR options.

```bash
grep -in "marker" src/processors.py
grep -in "docling" src/processors.py
```

**PASS:** Both Marker and Docling are referenced
**FAIL:** One or both local OCR engines missing
**Fix:** Implement `_process_with_marker` and `_process_with_docling` methods using local OCR

### Check 8: LlamaParse is conditional

**File:** `src/processors.py`

**Check:** LlamaParse is not the default/first-choice processor; it should be opt-in or a fallback.

```bash
grep -n "llamaparse\|LlamaParse\|llama_parse" src/processors.py
```

**PASS:** LlamaParse references exist but are conditional (behind a config flag or as last-resort fallback)
**FAIL:** LlamaParse used as default processor
**Fix:** Make LlamaParse conditional on `BIBLIO_LLAMAPARSE_API_KEY` being set or config flag

## Output Format

```markdown
| # | Check | File | Status | Details |
|---|-------|------|--------|---------|
| 1 | DocumentProcessor class | src/processors.py | PASS/FAIL | - |
| 2 | Required methods | src/processors.py | PASS/FAIL | Missing methods |
| 3 | ProcessedDocument dataclass | src/processors.py | PASS/FAIL | - |
| 4 | langdetect import | src/processors.py | PASS/FAIL | - |
| 5 | No hardcoded language | src/processors.py | PASS/FAIL | Matches found |
| 6 | ebooklib EPUB support | src/processors.py | PASS/FAIL | - |
| 7 | Local OCR engines | src/processors.py | PASS/FAIL | Missing engines |
| 8 | LlamaParse conditional | src/processors.py | PASS/FAIL | Usage pattern |
```

## Exceptions

The following are **NOT violations**:

1. **LlamaParse in import guards** — `try: import llama_parse` with fallback is acceptable (conditional import)
2. **Language string in config defaults** — `language="en"` inside `Settings` field defaults is not hardcoding in processor logic
3. **OCR engine names in comments** — Mentions of Marker, Docling, or LlamaParse in comments/docstrings are informational, not code
