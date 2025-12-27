"""Tests for CLI module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pp.cli import expand_file_patterns, parse_args, MockUploadedFile


class TestMockUploadedFile:
    """Tests for MockUploadedFile."""

    def test_initialization(self, tmp_path):
        """Test mock file initialization."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        mock = MockUploadedFile(test_file)
        assert mock.name == "test.txt"
        assert mock.path == test_file

    def test_read(self, tmp_path):
        """Test reading file content."""
        test_file = tmp_path / "test.txt"
        content = "Test content"
        test_file.write_text(content)
        
        mock = MockUploadedFile(test_file)
        assert mock.read() == content.encode()

    def test_seek(self, tmp_path):
        """Test seek operation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test")
        
        mock = MockUploadedFile(test_file)
        mock.seek(0)
        assert mock.read() == b"Test"


class TestParseArgs:
    """Tests for argument parsing."""

    def test_minimal_args(self):
        """Test parsing with minimal arguments."""
        with patch("sys.argv", ["pp-cli", "test.pptx"]):
            args = parse_args()
            assert args.files == ["test.pptx"]
            assert args.background == "#000000"
            assert args.foreground == "#FFFFFF"

    def test_multiple_files(self):
        """Test parsing multiple files."""
        with patch("sys.argv", ["pp-cli", "file1.pptx", "file2.pptx"]):
            args = parse_args()
            assert args.files == ["file1.pptx", "file2.pptx"]

    def test_custom_colors(self):
        """Test parsing custom colors."""
        with patch("sys.argv", [
            "pp-cli", "test.pptx",
            "--bg", "#1a1a1a",
            "--fg", "#f0f0f0",
        ]):
            args = parse_args()
            assert args.background == "#1a1a1a"
            assert args.foreground == "#f0f0f0"

    def test_output_directory(self):
        """Test parsing output directory."""
        with patch("sys.argv", ["pp-cli", "test.pptx", "--output", "/tmp/out"]):
            args = parse_args()
            assert args.output == Path("/tmp/out")

    def test_jpeg_quality(self):
        """Test parsing JPEG quality."""
        with patch("sys.argv", ["pp-cli", "test.pptx", "--jpeg-quality", "95"]):
            args = parse_args()
            assert args.jpeg_quality == 95

    def test_no_invert_images(self):
        """Test no-invert-images flag."""
        with patch("sys.argv", ["pp-cli", "test.pptx", "--no-invert-images"]):
            args = parse_args()
            assert args.no_invert_images is True

    def test_verbose_flag(self):
        """Test verbose flag."""
        with patch("sys.argv", ["pp-cli", "test.pptx", "-v"]):
            args = parse_args()
            assert args.verbose is True

    def test_suffix_option(self):
        """Test custom suffix."""
        with patch("sys.argv", ["pp-cli", "test.pptx", "--suffix", "(dark)"]):
            args = parse_args()
            assert args.suffix == "(dark)"


class TestExpandFilePatterns:
    """Tests for file pattern expansion."""

    def test_single_file(self, tmp_path):
        """Test expanding single file."""
        test_file = tmp_path / "test.pptx"
        test_file.touch()
        
        result = expand_file_patterns([str(test_file)])
        assert len(result) == 1
        assert result[0].name == "test.pptx"

    def test_multiple_files(self, tmp_path):
        """Test expanding multiple files."""
        file1 = tmp_path / "test1.pptx"
        file2 = tmp_path / "test2.pptx"
        file1.touch()
        file2.touch()
        
        result = expand_file_patterns([str(file1), str(file2)])
        assert len(result) == 2

    def test_glob_pattern(self, tmp_path):
        """Test glob pattern expansion."""
        (tmp_path / "test1.pptx").touch()
        (tmp_path / "test2.pptx").touch()
        (tmp_path / "test3.txt").touch()  # Should be ignored
        
        # Change to tmp_path for glob to work
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = expand_file_patterns(["*.pptx"])
            assert len(result) == 2
            assert all(p.suffix == ".pptx" for p in result)
        finally:
            os.chdir(old_cwd)

    def test_no_files_found(self):
        """Test error when no files found."""
        with pytest.raises(SystemExit):
            expand_file_patterns(["nonexistent.pptx"])

    def test_wrong_file_type(self, tmp_path):
        """Test error for non-PPTX file."""
        test_file = tmp_path / "test.txt"
        test_file.touch()
        
        # Change to tmp_path so glob works correctly
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(SystemExit):
                expand_file_patterns(["test.txt"])
        finally:
            os.chdir(old_cwd)

    def test_duplicate_removal(self, tmp_path):
        """Test that duplicate files are removed."""
        test_file = tmp_path / "test.pptx"
        test_file.touch()
        
        # Pass same file twice
        result = expand_file_patterns([str(test_file), str(test_file)])
        assert len(result) == 1


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_cli_help(self):
        """Test that help is available."""
        with patch("sys.argv", ["pp-cli", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_args()
            # Exit code 0 for --help
            assert exc_info.value.code == 0

    def test_invalid_jpeg_quality(self):
        """Test invalid JPEG quality."""
        with patch("sys.argv", ["pp-cli", "test.pptx", "--jpeg-quality", "150"]):
            with pytest.raises(SystemExit):
                parse_args()

    def test_foreground_background_flags(self):
        """Test both short and long color flags."""
        with patch("sys.argv", [
            "pp-cli", "test.pptx",
            "--background", "#000000",
            "--foreground", "#FFFFFF",
        ]):
            args = parse_args()
            assert args.background == "#000000"
            assert args.foreground == "#FFFFFF"
