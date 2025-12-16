"""Main orchestration for PowerPoint Inverter.

This module handles processing of presentations and files.
Sequential processing is used to minimize memory usage on resource-constrained
environments like small VPS instances.
"""

import io
import logging
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Callable, Iterator

from pptx import Presentation

from pp.core.slide_processor import process_slide_safe
from pp.models.config import InversionConfig

if TYPE_CHECKING:
    from pptx.presentation import Presentation as PresentationType
    from streamlit.runtime.uploaded_file_manager import UploadedFile

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a single file."""

    filename: str
    success: bool
    output_data: bytes | None  # Store bytes directly instead of path
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


def _process_file(
    file_data: bytes,
    filename: str,
    config: InversionConfig,
) -> ProcessingResult:
    """Process a single PPTX file.

    Args:
        file_data: Raw bytes of the PPTX file.
        filename: Original filename.
        config: Inversion configuration.

    Returns:
        ProcessingResult with output bytes.
    """
    try:
        # Load presentation from bytes
        with io.BytesIO(file_data) as file_stream:
            prs = Presentation(file_stream)

            # Process all slides
            all_warnings: list[str] = []
            for idx, slide in enumerate(prs.slides):
                success, warnings = process_slide_safe(slide, config)
                if warnings:
                    for warning in warnings:
                        all_warnings.append(f"Slide {idx + 1}: {warning}")

            # Generate output filename
            name_without_ext = os.path.splitext(filename)[0]
            output_filename = f"{name_without_ext} {config.file_suffix}.pptx"

            # Save to bytes
            output_stream = io.BytesIO()
            prs.save(output_stream)
            output_data = output_stream.getvalue()

            return ProcessingResult(
                filename=output_filename,
                success=True,
                output_data=output_data,
                warnings=all_warnings,
            )

    except Exception as e:
        logger.exception(f"Failed to process {filename}: {e}")
        return ProcessingResult(
            filename=filename,
            success=False,
            output_data=None,
            warnings=[f"Processing failed: {e}"],
        )


def process_presentation(
    prs: "PresentationType",
    config: InversionConfig,
    progress_callback: ProgressCallback | None = None,
    filename: str = "presentation",
) -> list[str]:
    """Process all slides in a presentation.

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
    """Process a single PPTX file and save to disk.

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
                output_data=None,
                warnings=warnings,
            )

    except Exception as e:
        logger.exception(f"Failed to process {filename}: {e}")
        return ProcessingResult(
            filename=filename,
            success=False,
            output_data=None,
            warnings=[f"Processing failed: {e}"],
        )


def process_files_streaming(
    uploaded_files: list["UploadedFile"],
    config: InversionConfig,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> Iterator[ProcessingResult]:
    """Process multiple uploaded files with streaming results.

    Yields results as each file completes, allowing for progressive updates.
    Uses sequential processing to minimize memory usage.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects.
        config: Inversion configuration.
        progress_callback: Optional callback(current_file, total_files, filename).

    Yields:
        ProcessingResult for each completed file.
    """
    # Collect all PPTX files to process
    files_to_process: list[tuple[bytes, str]] = []

    for uploaded_file in uploaded_files:
        if uploaded_file.name.endswith(".pptx"):
            files_to_process.append((uploaded_file.read(), uploaded_file.name))
            uploaded_file.seek(0)

        elif uploaded_file.name.endswith(".zip"):
            extracted = _extract_pptx_from_zip(uploaded_file)
            files_to_process.extend(extracted)

    total_files = len(files_to_process)

    if total_files == 0:
        return

    logger.info(f"Processing {total_files} files sequentially")

    for idx, (file_data, filename) in enumerate(files_to_process):
        result = _process_file(file_data, filename, config)
        yield result

        if progress_callback:
            progress_callback(idx + 1, total_files, filename)


def process_files(
    uploaded_files: list["UploadedFile"],
    config: InversionConfig,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> BatchResult:
    """Process multiple uploaded files (PPTX or ZIP).

    Uses sequential processing to minimize memory usage on resource-constrained
    environments. The image processing optimizations (JPEG encoding, optimized
    numpy operations) provide the main performance improvements.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects.
        config: Inversion configuration.
        progress_callback: Optional callback(current_file, total_files, filename).

    Returns:
        BatchResult with output ZIP and processing statistics.
    """
    # Collect all PPTX files to process
    files_to_process: list[tuple[bytes, str]] = []

    for uploaded_file in uploaded_files:
        if uploaded_file.name.endswith(".pptx"):
            files_to_process.append((uploaded_file.read(), uploaded_file.name))
            uploaded_file.seek(0)

        elif uploaded_file.name.endswith(".zip"):
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

    results: list[ProcessingResult] = []
    logger.info(f"Processing {total_files} files sequentially")

    # Process files sequentially to minimize memory usage
    for idx, (file_data, filename) in enumerate(files_to_process):
        result = _process_file(file_data, filename, config)
        results.append(result)

        if progress_callback:
            progress_callback(idx + 1, total_files, filename)

    # Create output ZIP from in-memory results
    output_zip = _create_output_zip_from_results(results)

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


def _create_output_zip_from_results(results: list[ProcessingResult]) -> bytes:
    """Create a ZIP file from in-memory processing results.

    Args:
        results: List of processing results with output_data bytes.

    Returns:
        ZIP file as bytes.
    """
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for result in results:
            if result.success and result.output_data:
                zf.writestr(result.filename, result.output_data)

    output.seek(0)
    return output.read()
