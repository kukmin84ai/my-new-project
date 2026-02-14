---
name: verify-gpu-acceleration
description: Verifies GPU auto-detection and device-aware processing across all modules. Use after modifying device or GPU-related code.
disable-model-invocation: true
argument-hint: "[optional: specific check name]"
---

# GPU Acceleration Verification

## Purpose

Ensures proper GPU utilization by verifying:

1. **Device Enum** — `GPUDevice` enum with auto/cuda/mps/cpu variants
2. **Auto-Detection** — `detect_device()` checks CUDA and MPS availability
3. **Device Propagation** — Embedding and OCR modules accept and use device configuration
4. **No Hardcoded Devices** — Device strings come from config, not inline literals

## When to Run

- After modifying `src/config.py` device-related code
- After modifying `src/database.py` embedding initialization
- After modifying `src/processors.py` OCR device settings
- Before PRs that touch GPU/device logic

## Related Files

| File | Purpose |
|------|---------|
| `src/config.py` | GPUDevice enum and detect_device() function |
| `src/database.py` | Embedding model device placement |
| `src/processors.py` | OCR pipeline device configuration |

## Workflow

### Check 1: GPUDevice enum with all variants

**File:** `src/config.py`

**Check:** `GPUDevice` enum includes auto, cuda, mps, and cpu.

```bash
grep -n "class GPUDevice" src/config.py
grep -n '"auto"\|auto\s*=' src/config.py
grep -n '"cuda"\|cuda\s*=' src/config.py
grep -n '"mps"\|mps\s*=' src/config.py
grep -n '"cpu"\|cpu\s*=' src/config.py
```

**PASS:** Enum exists with all four variants
**FAIL:** Enum missing or incomplete
**Fix:** Define `class GPUDevice(str, Enum)` with `auto = "auto"`, `cuda = "cuda"`, `mps = "mps"`, `cpu = "cpu"`

### Check 2: detect_device() checks CUDA availability

**File:** `src/config.py`

**Check:** `detect_device()` function checks `torch.cuda.is_available()`.

```bash
grep -n "torch.cuda.is_available" src/config.py
```

**PASS:** CUDA availability check found
**FAIL:** No CUDA check
**Fix:** Add `if torch.cuda.is_available(): return GPUDevice.cuda` in `detect_device()`

### Check 3: detect_device() checks MPS availability

**File:** `src/config.py`

**Check:** `detect_device()` function checks `torch.backends.mps.is_available()`.

```bash
grep -n "torch.backends.mps.is_available" src/config.py
```

**PASS:** MPS availability check found
**FAIL:** No MPS check
**Fix:** Add `if torch.backends.mps.is_available(): return GPUDevice.mps` in `detect_device()`

### Check 4: Database module uses device parameter

**File:** `src/database.py`

**Check:** Embedding initialization uses a device parameter from config.

```bash
grep -n "device" src/database.py
grep -n "detect_device\|get_settings\|config" src/database.py
```

**PASS:** Device parameter is used in embedding setup
**FAIL:** No device handling in database module
**Fix:** Pass `detect_device()` result or `settings.device` when initializing `SentenceTransformer`

### Check 5: Processors module uses device parameter

**File:** `src/processors.py`

**Check:** OCR pipeline uses a device parameter from config.

```bash
grep -n "device" src/processors.py
grep -n "detect_device\|get_settings\|config" src/processors.py
```

**PASS:** Device parameter is used in OCR processing
**FAIL:** No device handling in processors module
**Fix:** Use `detect_device()` or `settings.device` for OCR engine device configuration

### Check 6: No hardcoded device strings in src/

**File:** `src/*.py`

**Check:** No hardcoded device strings like `"cuda"`, `"mps"`, or `"cpu"` used directly for model placement (should come from config).

```bash
grep -rn 'device\s*=\s*"cuda"' src/
grep -rn 'device\s*=\s*"mps"' src/
grep -rn 'device\s*=\s*"cpu"' src/
grep -rn "\.to(\"cuda\")\|\.to(\"cpu\")\|\.to(\"mps\")" src/
```

**PASS:** No hardcoded device assignments found
**FAIL:** Hardcoded device strings found outside config.py
**Fix:** Replace hardcoded device strings with `detect_device()` or `settings.device`

## Output Format

```markdown
| # | Check | File | Status | Details |
|---|-------|------|--------|---------|
| 1 | GPUDevice enum | src/config.py | PASS/FAIL | Missing variants |
| 2 | CUDA check | src/config.py | PASS/FAIL | - |
| 3 | MPS check | src/config.py | PASS/FAIL | - |
| 4 | DB device param | src/database.py | PASS/FAIL | - |
| 5 | OCR device param | src/processors.py | PASS/FAIL | - |
| 6 | No hardcoded devices | src/*.py | PASS/FAIL | Lines found |
```

## Exceptions

The following are **NOT violations**:

1. **Device strings in GPUDevice enum definition** — `cuda = "cuda"` inside the enum class in `src/config.py` is the definition, not hardcoding
2. **Device strings in detect_device()** — Returning `GPUDevice.cuda` or comparing against device strings within `detect_device()` is expected
3. **Device in comments or docstrings** — References like `# Use "cuda" for NVIDIA GPUs` are documentation, not code
4. **Device in string formatting** — Logging statements like `logger.info(f"Using device: {device}")` are acceptable
