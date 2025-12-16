"""Tests for configuration models."""

import pytest
from pptx.dml.color import RGBColor

from pp.models.config import InversionConfig, hex_to_rgb, rgb_to_hex


class TestHexToRgb:
    """Tests for hex_to_rgb function."""

    def test_hex_with_hash(self):
        """Test conversion with # prefix."""
        result = hex_to_rgb("#FF0000")
        assert result == RGBColor(255, 0, 0)

    def test_hex_without_hash(self):
        """Test conversion without # prefix."""
        result = hex_to_rgb("00FF00")
        assert result == RGBColor(0, 255, 0)

    def test_hex_lowercase(self):
        """Test lowercase hex values."""
        result = hex_to_rgb("#ffffff")
        assert result == RGBColor(255, 255, 255)

    def test_hex_black(self):
        """Test black color."""
        result = hex_to_rgb("#000000")
        assert result == RGBColor(0, 0, 0)

    def test_hex_mixed_case(self):
        """Test mixed case hex values."""
        result = hex_to_rgb("#AbCdEf")
        assert result == RGBColor(171, 205, 239)


class TestRgbToHex:
    """Tests for rgb_to_hex function."""

    def test_white(self):
        """Test white color conversion."""
        result = rgb_to_hex(RGBColor(255, 255, 255))
        assert result.lower() == "#ffffff"

    def test_black(self):
        """Test black color conversion."""
        result = rgb_to_hex(RGBColor(0, 0, 0))
        assert result.lower() == "#000000"

    def test_red(self):
        """Test red color conversion."""
        result = rgb_to_hex(RGBColor(255, 0, 0))
        assert result.lower() == "#ff0000"


class TestInversionConfig:
    """Tests for InversionConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = InversionConfig()
        assert config.foreground_color == RGBColor(255, 255, 255)
        assert config.background_color == RGBColor(0, 0, 0)
        assert config.file_suffix == "(inverted)"
        assert config.folder_name == "Inverted Presentations"
        assert config.invert_images is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = InversionConfig(
            foreground_color=RGBColor(255, 255, 0),
            background_color=RGBColor(0, 0, 128),
            file_suffix="(custom)",
            folder_name="Custom",
            invert_images=False,
        )
        assert config.foreground_color == RGBColor(255, 255, 0)
        assert config.background_color == RGBColor(0, 0, 128)
        assert config.file_suffix == "(custom)"
        assert config.folder_name == "Custom"
        assert config.invert_images is False

    def test_from_hex(self):
        """Test creating config from hex color strings."""
        config = InversionConfig.from_hex(
            fg_hex="#FFFF00",
            bg_hex="#000080",
            file_suffix="(test)",
            folder_name="Test Output",
        )
        assert config.foreground_color == RGBColor(255, 255, 0)
        assert config.background_color == RGBColor(0, 0, 128)
        assert config.file_suffix == "(test)"
        assert config.folder_name == "Test Output"

    def test_from_hex_without_hash(self):
        """Test from_hex with colors without # prefix."""
        config = InversionConfig.from_hex(
            fg_hex="FFFFFF",
            bg_hex="000000",
        )
        assert config.foreground_color == RGBColor(255, 255, 255)
        assert config.background_color == RGBColor(0, 0, 0)
