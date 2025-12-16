"""Main orchestration for PowerPoint Inverter.

This module handles parallel processing of presentations and files.
"""

import io
import logging
import os
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Callable

from pptx import Presentation

from pp.core.slide_processor import process_slide_safe
from pp.models.config import InversionConfig

if TYPE_CHECKING:
    from streamlit.runtime.uploaded_file_manager import UploadedFile

logger = logging.getLogger(__name__)

# Number of parallel workers for slide processing
MAX_SLIDE_WORKERS = 4


@dataclass
class ProcessingResult:
    """Result of processing a single file."""

    filename: str
    success: bool
    output_path: Path | None
    warnings: list[str]


@dataclass
class BatchResult:
    """Result of processing multiple files."""

    results: list[ProcessingResult]
    output_zip: bytes
    total_files: int
    successful_files: int

    @property
    def all_warnings(self) -> list[str]:
        """Get all warnings from all files."""
        warnings = []
        for result in self.results:
            if result.warnings:
                for warning in result.warnings:
                    warnings.append(f"{result.filename}: {warning}")
        return warnings


ProgressCallback = Callable[[int, int, str], None]


def process_presentation(
    prs: Presentation,
    config: InversionConfig,
    progress_callback: ProgressCallback | None = None,
    filename: str = "presentation",
) -> list[str]:
    """Process all slides in a presentation with parallel slide processing.

    Args:
        prs: The Presentation object to process.
        config: Inversion configuration.
        progress_callback: Optional callback(current, total, status) for progress.
        filename: Name of the file being processed (for logging).

    Returns:
        List of warning messages.
    """
    all_warnings: list[str] = []
    total_slides = len(prs.slides)

    if total_slides == 0:
        return ["Presentation has no slides"]

    # Note: python-pptx is not thread-safe for modifying the same presentation
    # from multiple threads. We process slides sequentially but could parallelize
    # if we split into separate presentations or use a thread-safe wrapper.
    # For now, sequential processing is safer and still fast.

    for idx, slide in enumerate(prs.slides):
        success, warnings = process_slide_safe(slide, config)

        if warnings:
            for warning in warnings:
                all_warnings.append(f"Slide {idx + 1}: {warning}")

        if progress_callback:
            progress_callback(idx + 1, total_slides, f"Processing slide {idx + 1}/{total_slides}")

    return all_warnings


def process_single_file(
    file_data: bytes,
    filename: str,
    config: InversionConfig,
    output_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> ProcessingResult:
    """Process a single PPTX file.

    Args:
        file_data: Raw bytes of the PPTX file.
        filename: Original filename.
        config: Inversion configuration.
        output_dir: Directory to save output file.
        progress_callback: Optional progress callback.

    Returns:
        ProcessingResult with success status and any warnings.
    """
    try:
        # Load presentation from bytes
        with io.BytesIO(file_data) as file_stream:
            prs = Presentation(file_stream)

            # Process the presentation
            warnings = process_presentation(prs, config, progress_callback, filename)

            # Generate output filename
            name_without_ext = os.path.splitext(filename)[0]
            output_filename = f"{name_without_ext} {config.file_suffix}.pptx"
            output_path = output_dir / output_filename

            # Save the modified presentation
            prs.save(str(output_path))

            return ProcessingResult(
                filename=filename,
                success=True,
                output_path=output_path,
                warnings=warnings,
            )

    except Exception as e:
        logger.exception(f"Failed to process {filename}: {e}")
        return ProcessingResult(
            filename=filename,
            success=False,
            output_path=None,
            warnings=[f"Processing failed: {e}"],
        )


def process_files(
    uploaded_files: list["UploadedFile"],
    config: InversionConfig,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> BatchResult:
    """Process multiple uploaded files (PPTX or ZIP).

    Args:
        uploaded_files: List of Streamlit UploadedFile objects.
        config: Inversion configuration.
        progress_callback: Optional callback(current_file, total_files, filename).

    Returns:
        BatchResult with output ZIP and processing statistics.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        results: list[ProcessingResult] = []

        # Collect all PPTX files to process
        files_to_process: list[tuple[bytes, str]] = []

        for uploaded_file in uploaded_files:
            if uploaded_file.name.endswith(".pptx"):
                files_to_process.append((uploaded_file.read(), uploaded_file.name))
                uploaded_file.seek(0)  # Reset for potential re-read

            elif uploaded_file.name.endswith(".zip"):
                # Extract PPTX files from ZIP
                extracted = _extract_pptx_from_zip(uploaded_file)
                files_to_process.extend(extracted)

        total_files = len(files_to_process)

        if total_files == 0:
            return BatchResult(
                results=[],
                output_zip=b"",
                total_files=0,
                successful_files=0,
            )

        # Process files with parallel execution
        with ThreadPoolExecutor(max_workers=MAX_SLIDE_WORKERS) as executor:
            future_to_file = {
                executor.submit(
                    process_single_file,
                    file_data,
                    filename,
                    config,
                    output_dir,
                    None,  # Per-slide progress not used in parallel mode
                ): filename
                for file_data, filename in files_to_process
            }

            completed = 0
            for future in as_completed(future_to_file):
                filename = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.exception(f"Future failed for {filename}: {e}")
                    results.append(
                        ProcessingResult(
                            filename=filename,
                            success=False,
                            output_path=None,
                            warnings=[f"Unexpected error: {e}"],
                        )
                    )

                completed += 1
                if progress_callback:
                    progress_callback(completed, total_files, filename)

        # Create output ZIP
        output_zip = _create_output_zip(results, config.folder_name)

        successful = sum(1 for r in results if r.success)

        return BatchResult(
            results=results,
            output_zip=output_zip,
            total_files=total_files,
            successful_files=successful,
        )


def _extract_pptx_from_zip(zip_file: IO[bytes]) -> list[tuple[bytes, str]]:
    """Extract PPTX files from a ZIP archive.

    Args:
        zip_file: File-like object containing ZIP data.

    Returns:
        List of (file_data, filename) tuples.
    """
    files = []
    try:
        with zipfile.ZipFile(zip_file, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".pptx") and not name.startswith("__MACOSX"):
                    data = zf.read(name)
                    # Use just the filename, not the full path
                    filename = os.path.basename(name)
                    if filename:  # Skip if it was a directory
                        files.append((data, filename))
    except zipfile.BadZipFile as e:
        logger.warning(f"Invalid ZIP file: {e}")
    return files


def _create_output_zip(results: list[ProcessingResult], folder_name: str) -> bytes:
    """Create a ZIP file containing all successful output files.

    Args:
        results: List of processing results.
        folder_name: Name prefix for the ZIP file.

    Returns:
        ZIP file as bytes.
    """
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for result in results:
            if result.success and result.output_path and result.output_path.exists():
                zf.write(result.output_path, result.output_path.name)

    output.seek(0)
    return output.read()
