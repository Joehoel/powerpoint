"""File handling utilities for PowerPoint Inverter.

This module provides utilities for extracting and packaging PPTX files.
"""

import io
import logging
import os
import zipfile
from pathlib import Path
from typing import IO

logger = logging.getLogger(__name__)


def extract_pptx_files(source: IO[bytes], source_name: str) -> list[tuple[bytes, str]]:
    """Extract PPTX files from a source (either a PPTX or ZIP file).

    Args:
        source: File-like object containing PPTX or ZIP data.
        source_name: Name of the source file (used to determine type).

    Returns:
        List of (file_data, filename) tuples.
    """
    if source_name.endswith(".pptx"):
        data = source.read()
        source.seek(0)
        return [(data, source_name)]

    elif source_name.endswith(".zip"):
        return _extract_from_zip(source)

    else:
        logger.warning(f"Unsupported file type: {source_name}")
        return []


def _extract_from_zip(zip_source: IO[bytes]) -> list[tuple[bytes, str]]:
    """Extract PPTX files from a ZIP archive.

    Args:
        zip_source: File-like object containing ZIP data.

    Returns:
        List of (file_data, filename) tuples.
    """
    files: list[tuple[bytes, str]] = []

    try:
        with zipfile.ZipFile(zip_source, "r") as zf:
            for name in zf.namelist():
                # Skip Mac OS metadata and non-PPTX files
                if name.startswith("__MACOSX") or name.startswith("._"):
                    continue

                if name.lower().endswith(".pptx"):
                    try:
                        data = zf.read(name)
                        # Use just the filename, not the full path
                        filename = os.path.basename(name)
                        if filename:  # Skip if it was a directory
                            files.append((data, filename))
                    except Exception as e:
                        logger.warning(f"Failed to extract {name}: {e}")

    except zipfile.BadZipFile as e:
        logger.warning(f"Invalid ZIP file: {e}")

    return files


def create_output_zip(
    files: list[tuple[bytes, str]],
    folder_name: str | None = None,
) -> bytes:
    """Create a ZIP file from a list of files.

    Args:
        files: List of (file_data, filename) tuples.
        folder_name: Optional folder name to put files under in the ZIP.

    Returns:
        ZIP file as bytes.
    """
    output = io.BytesIO()

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_data, filename in files:
            if folder_name:
                arcname = f"{folder_name}/{filename}"
            else:
                arcname = filename

            zf.writestr(arcname, file_data)

    output.seek(0)
    return output.read()


def get_output_filename(original_name: str, suffix: str) -> str:
    """Generate output filename with suffix.

    Args:
        original_name: Original filename.
        suffix: Suffix to add before extension.

    Returns:
        New filename with suffix.

    Example:
        >>> get_output_filename("presentation.pptx", "(inverted)")
        "presentation (inverted).pptx"
    """
    name, ext = os.path.splitext(original_name)
    return f"{name} {suffix}{ext}"


def validate_pptx(data: bytes) -> bool:
    """Check if data is a valid PPTX file.

    Args:
        data: Raw file bytes.

    Returns:
        True if data appears to be a valid PPTX file.
    """
    # PPTX is a ZIP file with specific contents
    try:
        with io.BytesIO(data) as f:
            with zipfile.ZipFile(f, "r") as zf:
                # Check for required PPTX components
                names = zf.namelist()
                required = ["[Content_Types].xml"]
                return all(req in names for req in required)
    except (zipfile.BadZipFile, Exception):
        return False
