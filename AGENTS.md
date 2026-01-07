# AGENTS.md - PowerPoint Inverter

This file provides guidance for AI coding agents working in this repository.

## Project Overview

PowerPoint Inverter (`pp`) is a Python application that inverts colors in PowerPoint presentations. It provides both a Streamlit web UI and a CLI interface.

- **Language**: Python 3.11+
- **Package Manager**: uv (Astral)
- **Framework**: Streamlit (web UI), python-pptx (PPTX manipulation)
- **Build System**: Hatchling

## Build Commands

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras

# Run the Streamlit web app
uv run streamlit run main.py --server.address=0.0.0.0 --server.port=8501

# Run CLI
uv run pp-cli <input.pptx> [options]

# Run benchmarks
uv run python bench.py --repeat 2
```

## Test Commands

```bash
# Run all tests
uv run pytest

# Run single test file
uv run pytest tests/test_validation.py

# Run specific test class
uv run pytest tests/test_validation.py::TestCalculateLuminance

# Run single test by name
uv run pytest tests/test_validation.py::TestCalculateLuminance::test_white

# Run tests matching pattern
uv run pytest -k "test_white"

# Run with coverage
uv run pytest --cov

# Run with verbose output
uv run pytest -v
```

## Lint/Format Commands

```bash
# Check linting
uv run ruff check .

# Auto-fix linting issues
uv run ruff check . --fix

# Format code
uv run ruff format .

# Check formatting without changes
uv run ruff format . --check
```

## Project Structure

```
pp/
├── main.py                    # Streamlit entry point
├── bench.py                   # Benchmarking script
├── pyproject.toml             # Project config, dependencies
├── src/pp/                    # Main package
│   ├── __init__.py            # Package init, version, logging
│   ├── app.py                 # Streamlit application
│   ├── cli.py                 # Command-line interface
│   ├── core/                  # Core processing logic
│   │   ├── inverter.py        # Main orchestration, batch processing
│   │   ├── slide_processor.py # Single slide processing
│   │   ├── image_processor.py # Image color transformation
│   │   └── validation.py      # Color contrast validation
│   ├── models/                # Data models
│   │   └── config.py          # InversionConfig dataclass
│   └── utils/                 # Utility functions
│       └── preview.py         # Preview generation
└── tests/                     # Test suite
    ├── conftest.py            # Shared fixtures
    ├── fixtures/              # Test PPTX files
    └── test_*.py              # Test modules
```

## Code Style Guidelines

### Imports

- Use `from __future__ import annotations` when needed for forward references
- Use `TYPE_CHECKING` guards for type-only imports to avoid circular dependencies:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from pptx.presentation import Presentation as PresentationType
  ```
- Order imports: stdlib, third-party, local (ruff handles this)
- Prefer explicit imports over wildcards

### Type Hints

- Use type annotations for all function parameters and return values
- Use `Self` from `typing` for methods returning the class instance
- Use `|` for union types (Python 3.10+ style): `config: InversionConfig | ConfigPayload`
- Use `list[str]` not `List[str]` (lowercase generics)

### Docstrings

Use Google-style docstrings:
```python
def process_file(file_data: bytes, filename: str) -> ProcessingResult:
    """Process a single PPTX file.

    Args:
        file_data: Raw bytes of the PPTX file.
        filename: Original filename.

    Returns:
        ProcessingResult with output bytes.

    Raises:
        ValueError: If file_data is invalid.
    """
```

### Naming Conventions

- **Functions/methods**: `snake_case` (e.g., `process_slide_safe`)
- **Classes**: `PascalCase` (e.g., `ProcessingResult`)
- **Constants**: `UPPER_SNAKE_CASE`
- **Private functions**: prefix with underscore (e.g., `_set_background_color`)
- **Type aliases**: `PascalCase` (e.g., `ConfigPayload`, `ProgressCallback`)

### Dataclasses

Use dataclasses for configuration and result types:
```python
@dataclass
class ProcessingResult:
    """Result of processing a single file."""
    filename: str
    success: bool
    output_data: bytes | None = None
    warnings: list[str] = field(default_factory=list)
```

### Error Handling

- Use try/except with logging for recoverable errors
- Return warning lists instead of raising exceptions for non-fatal issues
- Use `logger.exception()` to capture stack traces:
  ```python
  try:
      # processing
  except Exception as e:
      logger.exception(f"Failed to process {filename}: {e}")
      return ProcessingResult(filename=filename, success=False, warnings=[str(e)])
  ```

### Logging

- Create module-level loggers: `logger = logging.getLogger(__name__)`
- Use appropriate log levels: `debug`, `info`, `warning`, `exception`

## Testing Guidelines

### Test Organization

- Use class-based test organization: `class TestCalculateLuminance:`
- Name test methods descriptively: `test_white`, `test_poor_contrast_warning`
- Add docstrings explaining what each test validates

### Fixtures

Use fixtures from `conftest.py`:
- `sample_presentation` - Presentation object with text and images
- `sample_presentation_bytes` - Same as bytes
- `default_config` - Default InversionConfig
- `custom_config` - Config with custom colors
- `sample_image` - PIL Image for testing

### Test Patterns

```python
class TestValidateColorContrast:
    """Tests for color contrast validation."""

    def test_good_contrast(self):
        """Test colors with good contrast return no warnings."""
        black = RGBColor(0, 0, 0)
        white = RGBColor(255, 255, 255)
        warnings = validate_color_contrast(black, white)
        assert len(warnings) == 0

    def test_poor_contrast_warning(self):
        """Test colors with poor contrast produce warnings."""
        light_gray = RGBColor(200, 200, 200)
        white = RGBColor(255, 255, 255)
        warnings = validate_color_contrast(light_gray, white)
        assert len(warnings) > 0
        assert "contrast ratio" in warnings[0].lower()
```

### Mocking

Use `unittest.mock.patch` for external dependencies:
```python
from unittest.mock import patch

def test_with_mock():
    with patch("pp.core.inverter.Presentation") as mock_prs:
        # test code
```

## Environment Variables

- `PP_FORCE_THREADS=1` - Force thread-based executor instead of process-based (reduces memory)

## Docker

Build and run with Docker:
```bash
docker build -t pp .
docker run -p 8501:8501 pp
```
