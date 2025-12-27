"""Command-line interface for PowerPoint Inverter.

This module provides a CLI for batch processing PowerPoint presentations
without requiring the Streamlit UI.
"""

import argparse
import logging
import sys
from pathlib import Path

from pp.models.config import InversionConfig

logger = logging.getLogger(__name__)


class MockUploadedFile:
    """Mock object that mimics Streamlit's UploadedFile for CLI use."""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self._data = path.read_bytes()
        self._pos = 0

    def read(self) -> bytes:
        self._pos = 0
        return self._data

    def seek(self, pos: int) -> None:
        self._pos = pos


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.
    
    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Invert colors in PowerPoint presentations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pp-cli *.pptx --bg '#1a1a1a' --fg '#f0f0f0'
  pp-cli presentation.pptx --bg '#000000' --fg '#FFFFFF' --output ./inverted/
  pp-cli *.pptx --no-invert-images --jpeg-quality 80
        """,
    )

    parser.add_argument(
        "files",
        nargs="+",
        help="Path(s) to PPTX files or glob pattern (e.g., *.pptx)",
    )

    parser.add_argument(
        "--bg",
        "--background",
        dest="background",
        default="#000000",
        help="Background color in hex format (default: #000000)",
    )

    parser.add_argument(
        "--fg",
        "--foreground",
        dest="foreground",
        default="#FFFFFF",
        help="Foreground (text) color in hex format (default: #FFFFFF)",
    )

    parser.add_argument(
        "--suffix",
        default="(inverted)",
        help="Suffix to append to output filenames (default: (inverted))",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd(),
        help="Output directory for inverted files (default: current directory)",
    )

    parser.add_argument(
        "--no-invert-images",
        action="store_true",
        help="Skip image color inversion",
    )

    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=85,
        choices=range(1, 101),
        help="JPEG quality 1-100 (default: 85)",
        metavar="QUALITY",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    return parser.parse_args()


def expand_file_patterns(patterns: list[str]) -> list[Path]:
    """Expand glob patterns to actual file paths.
    
    Args:
        patterns: List of file paths or glob patterns.
    
    Returns:
        List of resolved PPTX file paths.
    
    Raises:
        SystemExit: If no valid PPTX files are found.
    """
    files = []
    
    for pattern in patterns:
        path = Path(pattern)
        
        # Check if it's a direct file reference
        if path.is_file() and path.suffix.lower() == ".pptx":
            files.append(path)
        else:
            # Try as glob pattern
            matches = list(Path.cwd().glob(pattern))
            pptx_matches = [p for p in matches if p.suffix.lower() == ".pptx"]
            
            if pptx_matches:
                files.extend(pptx_matches)
            elif path.is_file():
                # File exists but wrong extension
                logger.error(f"File {path} is not a PPTX file")
                sys.exit(1)
    
    if not files:
        logger.error("No PPTX files found matching the given patterns")
        sys.exit(1)
    
    return sorted(set(files))  # Remove duplicates and sort


def main() -> int:
    """Main CLI entry point.
    
    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )
    
    # Find input files
    input_files = expand_file_patterns(args.files)
    logger.info(f"Found {len(input_files)} file(s) to process")
    
    # Create output directory
    output_dir = args.output.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    
    # Validate colors
    try:
        config = InversionConfig.from_hex(
            fg_hex=args.foreground,
            bg_hex=args.background,
            file_suffix=args.suffix,
            folder_name=str(output_dir),
            invert_images=not args.no_invert_images,
            jpeg_quality=args.jpeg_quality,
        )
    except ValueError as e:
        logger.error(f"Invalid color: {e}")
        return 1
    
    # Check color contrast
    warnings = config.validate()
    if warnings:
        for warning in warnings:
            logger.warning(f"Color: {warning}")
    
    # Create mock uploaded files
    mock_files = [MockUploadedFile(f) for f in input_files]
    
    # Process files
    def progress_callback(current: int, total: int, filename: str) -> None:
        logger.info(f"[{current}/{total}] Processing: {filename}")
    
    try:
        # Use the internal processor
        from pp.core.inverter import process_files as process_files_internal
        result = process_files_internal(mock_files, config, progress_callback)
        
        # Save output files
        if result.results:
            success_count = sum(1 for r in result.results if r.success)
            
            # Write each file to output directory
            import zipfile
            import io
            
            # Extract files from the zip
            with zipfile.ZipFile(io.BytesIO(result.output_zip), "r") as zf:
                for file_info in zf.filelist:
                    # Get just the filename without folder structure
                    filename = Path(file_info.filename).name
                    output_path = output_dir / filename
                    output_path.write_bytes(zf.read(file_info.filename))
            
            logger.info(f"Successfully processed {success_count}/{result.total_files} files")
            
            # Log warnings if any
            if result.all_warnings:
                logger.warning(f"Completed with {len(result.all_warnings)} warning(s):")
                for warning in result.all_warnings:
                    logger.warning(f"  - {warning}")
            
            return 0
        else:
            logger.error("No files were processed")
            return 1
    
    except Exception as e:
        logger.exception(f"Processing failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
