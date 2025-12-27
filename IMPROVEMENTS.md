# PowerPoint Inverter - Improvement Plan

## Overview
This document outlines 10 improvements grouped by priority and theme. Each issue includes impact, effort, and implementation steps.

---

## Phase 1: High-Impact Quick Wins (Effort: Low-Medium)

### 1. Fix Code Duplication in inverter.py
**Impact:** High - Reduces maintenance burden and risk of divergence  
**Effort:** Low  
**Status:** Ready to implement

**Changes:**
- Extract common executor setup logic from `process_files()` and `process_files_streaming()` into a helper function
- Files modified: `src/pp/core/inverter.py`

**Steps:**
1. Create `_get_executor_and_config()` helper that returns:
   - Executor instance
   - Iterator over files
   - Payload configuration
   - Total file count
2. Replace duplicated setup in both functions with single call
3. Keep file yielding logic separate (streaming vs batch)

**Expected outcome:** ~40 lines removed, DRY principle applied

---

### 2. Add Input Validation to hex_to_rgb()
**Impact:** Medium - Prevents silent failures  
**Effort:** Low  
**Status:** Ready to implement

**Changes:**
- Files modified: `src/pp/models/config.py`
- Files modified: `tests/test_config.py`

**Steps:**
1. Add length and format validation to `hex_to_rgb()`
   - Must be 6 chars after stripping `#`
   - Must be valid hex digits
   - Raise `ValueError` with clear message on failure
2. Add test cases for:
   - Too short hex strings
   - Too long hex strings
   - Non-hex characters
   - Empty strings
3. Update docstring with exception information

**Expected outcome:** Fail fast with clear errors instead of cryptic parsing failures

---

### 3. Fix Logging Configuration
**Impact:** Medium - Better debugging and monitoring  
**Effort:** Low  
**Status:** Ready to implement

**Changes:**
- Files modified: `src/pp/__init__.py`
- Files modified: `src/pp/app.py`

**Steps:**
1. Move logging setup to package `__init__.py`:
   ```python
   import logging
   logging.basicConfig(level=logging.INFO)
   ```
2. In `app.py`, replace basic setup with:
   ```python
   import logging
   logger = logging.getLogger(__name__)
   ```
3. This applies configuration to entire package, not just one module

**Expected outcome:** Consistent logging across all modules

---

### 4. Make JPEG Quality Configurable
**Impact:** Low-Medium - Improves flexibility  
**Effort:** Low  
**Status:** Ready to implement

**Changes:**
- Files modified: `src/pp/core/image_processor.py`
- Files modified: `src/pp/models/config.py`
- Files modified: `tests/test_image_processor.py`

**Steps:**
1. Add `jpeg_quality: int = 85` to `InversionConfig` dataclass
2. Pass quality through `_process_file()` → `invert_image()` → `apply_color_transform()`
3. Update `_config_to_payload()` to include quality value
4. Add test validating different quality values produce different outputs

**Expected outcome:** Users can trade quality for speed via configuration

---

## Phase 2: Core Improvements (Effort: Medium)

### 5. Fix ProcessingResult Data Flow Inconsistency
**Impact:** Medium - Reduces confusion and bugs  
**Effort:** Medium  
**Status:** Requires design decision

**Changes:**
- Files modified: `src/pp/core/inverter.py`

**Problem:** `output_data` is only set in `_process_file()`, but `None` in `process_single_file()` and `process_presentation()`—inconsistent contract.

**Options:**
- **Option A (Recommended):** Remove `output_data` from `ProcessingResult` and only use it inside `_process_file()`; return results directly from `_create_output_zip_from_results()`
- **Option B:** Standardize all paths to populate `output_data`

**Steps:**
1. Choose option (A recommended for memory efficiency)
2. If Option A:
   - Create `_FileToZip = tuple[bytes, str]` type alias
   - `_process_file()` returns result without data
   - `process_files()` collects both results and file data separately
   - Pass file data directly to `_create_output_zip_from_results()`
3. Update docstrings to reflect contract

**Expected outcome:** Clear, consistent API contract; no stale fields

---

### 6. Remove Dead Code (file_handler.py and unused preview functions)
**Impact:** Medium - Reduces confusion and maintenance  
**Effort:** Medium  
**Status:** Requires verification

**Changes:**
- Files deleted or refactored: `src/pp/utils/file_handler.py`
- Files modified: `src/pp/utils/preview.py`
- Files modified: `src/pp/app.py`

**Steps:**
1. Audit `file_handler.py`:
   - `extract_pptx_files()` - UNUSED (inverter.py has `_extract_pptx_from_zip()`)
   - `create_output_zip()` - UNUSED (inverter.py has `_create_output_zip_from_results()`)
   - `get_output_filename()` - UNUSED (logic inline in inverter.py)
   - `validate_pptx()` - UNUSED
   
2. Decision: Delete file entirely—logic is already in inverter.py with better fit

3. Audit `preview.py` (407 lines):
   - `generate_color_preview()` - Used in app.py
   - `generate_slide_preview()` - Used in app.py
   - `generate_slide_preview_inverted()` - Used in app.py
   - `hex_to_tuple()` - Used in app.py
   - Other functions appear unused
   
4. Keep only functions used by app.py, comment/document others

**Expected outcome:** Cleaner codebase, easier to understand

---

### 7. Fix app.py Duplication (Date Calculation)
**Impact:** Low-Medium - Maintenance risk  
**Effort:** Low  
**Status:** Ready to implement

**Changes:**
- Files modified: `src/pp/app.py`

**Problem:** Date string calculation on lines 202-205 is identical to lines 279-282

**Steps:**
1. Extract to helper function:
   ```python
   def _get_final_folder_name(folder_name: str, include_date: bool) -> str:
       if not include_date:
           return folder_name
       date_str = datetime.now().strftime("%Y-%m-%d")
       return f"{folder_name} - {date_str}"
   ```
2. Use in both locations
3. Test with and without dates

**Expected outcome:** Single source of truth, easier to modify date format

---

## Phase 3: Major Features (Effort: High)

### 8. Add Configuration Validation (Color Contrast Check)
**Impact:** Medium - Improves UX  
**Effort:** Medium-High  
**Status:** Requires design

**Changes:**
- Files modified: `src/pp/models/config.py`
- Files modified: `src/pp/app.py`
- Files added: `src/pp/core/validation.py`

**Steps:**
1. Create `src/pp/core/validation.py` with color analysis functions:
   ```python
   def calculate_luminance(color: RGBColor) -> float:
       """Calculate relative luminance per WCAG 2.0"""
       # Standard formula using sRGB
   
   def calculate_contrast_ratio(fg: RGBColor, bg: RGBColor) -> float:
       """Calculate WCAG contrast ratio"""
   
   def validate_color_contrast(fg: RGBColor, bg: RGBColor) -> list[str]:
       """Return warnings if contrast too low"""
   ```

2. Add `validate()` method to `InversionConfig`:
   ```python
   def validate(self) -> list[str]:
       """Return list of warnings/issues with config"""
       return validate_color_contrast(self.foreground_color, self.background_color)
   ```

3. In app.py, after user picks colors, call validation and show warnings before processing

4. Add tests for luminance calculation and contrast ratios

**Expected outcome:** Warn users about low-contrast color combinations before processing

---

### 9. Create CLI Interface
**Impact:** High - Enables headless/batch processing  
**Effort:** High  
**Status:** Requires design

**Changes:**
- Files added: `src/pp/cli.py`
- Files modified: `pyproject.toml`
- Files added: `tests/test_cli.py`

**Steps:**
1. Create `src/pp/cli.py` using `argparse`:
   ```
   pp invert [input_files] --bg #000000 --fg #FFFFFF --suffix "(inverted)"
   pp invert *.pptx --bg #1a1a1a --fg #f0f0f0 --output ./output/
   ```

2. Argument structure:
   - `input`: Positional, one or more .pptx/.zip files (or directory)
   - `--bg/--background`: Background color (hex)
   - `--fg/--foreground`: Foreground color (hex)
   - `--suffix`: Output file suffix
   - `--output`: Output directory (default: current dir)
   - `--no-invert-images`: Skip image inversion
   - `--jpeg-quality`: JPEG quality 1-100
   - `--workers`: Override worker count (1-4)

3. Entry point in `pyproject.toml`:
   ```toml
   [project.scripts]
   pp = "pp.cli:main"
   ```

4. Add comprehensive tests for argument parsing and file handling

**Expected outcome:** Tool usable from command line and in automation scripts

---

### 10. Add Streamlit App Testing (High Priority)
**Impact:** High - Critical path untested  
**Effort:** High  
**Status:** Requires tool selection

**Changes:**
- Files added: `tests/test_app.py`
- Files modified: `pyproject.toml` (add `streamlit-testing-client` if using)

**Approach Options:**
- **Option A (Recommended):** Extract Streamlit UI logic into separate functions, test logic in unit tests
- **Option B:** Use `streamlit.testing.v1` (new in Streamlit 1.41+)
- **Option C:** Use `pytest-mock` to mock Streamlit functions

**Steps:**
1. Refactor app.py to separate concerns:
   - Keep Streamlit imports/decorators only where needed
   - Extract business logic (validation, caching, file processing) into testable functions
   - Example:
     ```python
     def validate_uploaded_files(files: list) -> tuple[bool, str]:
         """Returns (valid, error_message)"""
     
     def build_inversion_config_from_ui_inputs(...) -> InversionConfig:
         """Pure function, no Streamlit calls"""
     ```

2. Create test file `tests/test_app.py`:
   - Test config validation
   - Test cache key generation
   - Test file upload handling
   - Test progress callback behavior

3. Mark UI tests with `@pytest.mark.ui` for optional running

**Expected outcome:** 50%+ coverage on app.py logic, critical bugs caught early

---

## Implementation Roadmap

### Week 1 (Phase 1 - Quick Wins)
- [ ] Issue #1: Code duplication (1-2 hours)
- [ ] Issue #2: Input validation (1-2 hours)
- [ ] Issue #3: Logging (30 min)
- [ ] Issue #4: JPEG quality config (1 hour)

**Effort:** 4-6 hours, High ROI  
**PR:** Submit as single or split into 2-3 PRs

### Week 2 (Phase 2 - Core)
- [ ] Issue #5: ProcessingResult refactoring (2-3 hours)
- [ ] Issue #6: Dead code removal (1-2 hours)
- [ ] Issue #7: Date calculation fix (30 min)

**Effort:** 4-5 hours  
**PR:** 2-3 PRs (one per major change)

### Week 3-4 (Phase 3 - Features)
- [ ] Issue #8: Color validation (3-4 hours)
- [ ] Issue #9: CLI interface (4-6 hours)
- [ ] Issue #10: App testing (4-6 hours)

**Effort:** 12-16 hours  
**PR:** 3 separate PRs

---

## Testing Strategy

### After Phase 1
```bash
pytest tests/ --cov=src/pp --cov-report=html
# Target: 40%+ coverage
```

### After Phase 2
```bash
pytest tests/ --cov=src/pp --cov-report=html
# Target: 60%+ coverage
```

### After Phase 3
```bash
pytest tests/ --cov=src/pp --cov-report=html
# Target: 80%+ coverage
```

---

## File Changes Summary

| Phase | Issue | Files Modified | Files Added | Files Deleted |
|-------|-------|---|---|---|
| 1 | #1-4 | inverter.py, config.py, app.py, image_processor.py | test_config.py (new tests) | |
| 2 | #5-7 | inverter.py, app.py, preview.py | | file_handler.py |
| 3 | #8-10 | config.py, app.py, pyproject.toml | validation.py, cli.py, test_app.py, test_cli.py | |

---

## Risk Assessment

| Issue | Risk | Mitigation |
|-------|------|---|
| #1 Duplication | Low | Extract, run existing tests |
| #2 Validation | Low | Add validation tests, backward compatible |
| #5 ProcessingResult | Medium | Run full test suite, benchmark performance |
| #6 Dead code | Low | grep for imports before deletion |
| #9 CLI | Medium | Thorough argument testing, documentation |
| #10 App testing | High | Start with mock-based approach, don't refactor prematurely |

---

## Success Metrics

- [ ] All tests pass (33 → 50+ tests)
- [ ] Code coverage: 23% → 75%+
- [ ] No functional regressions (benchmarks unchanged or faster)
- [ ] Code duplication ratio decreases 10%+
- [ ] Dead code removal: 137 lines of unused code removed
- [ ] New CLI works with common use cases documented

