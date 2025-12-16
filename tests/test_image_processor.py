"""Tests for image processing."""

import io

import pytest
from PIL import Image

from pp.core.image_processor import apply_color_transform, _remap_colors


class TestApplyColorTransform:
    """Tests for the apply_color_transform function."""

    def test_standard_inversion(self, sample_image: Image.Image):
        """Test standard black/white inversion."""
        result = apply_color_transform(
            sample_image,
            target_dark=(0, 0, 0),
            target_light=(255, 255, 255),
        )
        
        assert result.size == sample_image.size
        assert result.mode == "RGB"
        
        # Check that colors are inverted
        # Original pixel at (0,0) should be dark, inverted should be light
        original_pixel = sample_image.getpixel((0, 0))
        inverted_pixel = result.getpixel((0, 0))
        
        # After inversion, dark should become light
        assert sum(inverted_pixel) > sum(original_pixel)

    def test_custom_color_inversion(self, sample_image: Image.Image):
        """Test inversion with custom target colors."""
        result = apply_color_transform(
            sample_image,
            target_dark=(0, 0, 128),    # Navy
            target_light=(255, 255, 0),  # Yellow
        )
        
        assert result.size == sample_image.size
        
        # Check that result contains expected color range
        # All pixels should be between navy and yellow
        for x in range(0, result.width, 10):
            for y in range(0, result.height, 10):
                pixel = result.getpixel((x, y))
                # Blue channel should be in range [0, 128]
                assert 0 <= pixel[2] <= 130  # Allow some tolerance

    def test_rgba_preservation(self, sample_rgba_image: Image.Image):
        """Test that alpha channel is preserved."""
        result = apply_color_transform(
            sample_rgba_image,
            target_dark=(0, 0, 0),
            target_light=(255, 255, 255),
        )
        
        assert result.mode == "RGBA"
        
        # Check alpha channel is preserved
        original_alpha = sample_rgba_image.split()[3]
        result_alpha = result.split()[3]
        
        # Alpha values should match
        assert list(original_alpha.getdata()) == list(result_alpha.getdata())

    def test_grayscale_conversion(self):
        """Test that grayscale images are converted to RGB."""
        gray_img = Image.new("L", (50, 50), 128)
        
        result = apply_color_transform(
            gray_img,
            target_dark=(0, 0, 0),
            target_light=(255, 255, 255),
        )
        
        assert result.mode == "RGB"

    def test_palette_image_conversion(self):
        """Test that palette images are converted correctly.
        
        Palette images are converted to RGBA to handle potential transparency.
        """
        # Create a palette image
        palette_img = Image.new("P", (50, 50))
        
        result = apply_color_transform(
            palette_img,
            target_dark=(0, 0, 0),
            target_light=(255, 255, 255),
        )
        
        # Palette images are converted to RGBA to preserve any transparency
        assert result.mode == "RGBA"


class TestRemapColors:
    """Tests for the _remap_colors function."""

    def test_identity_remap(self):
        """Test remapping with black to white keeps same range."""
        img = Image.new("RGB", (10, 10), (128, 128, 128))
        
        result = _remap_colors(
            img,
            target_dark=(0, 0, 0),
            target_light=(255, 255, 255),
        )
        
        # Middle gray should stay roughly middle gray
        pixel = result.getpixel((5, 5))
        assert 120 <= pixel[0] <= 136  # Allow tolerance for rounding

    def test_color_remap(self):
        """Test remapping to a different color range."""
        # Create a white image
        img = Image.new("RGB", (10, 10), (255, 255, 255))
        
        result = _remap_colors(
            img,
            target_dark=(0, 0, 128),
            target_light=(255, 255, 0),
        )
        
        # White should map to target_light (yellow)
        pixel = result.getpixel((5, 5))
        assert pixel[0] == 255  # Red
        assert pixel[1] == 255  # Green
        assert pixel[2] == 0    # Blue

    def test_black_remap(self):
        """Test that black maps to target_dark."""
        img = Image.new("RGB", (10, 10), (0, 0, 0))
        
        result = _remap_colors(
            img,
            target_dark=(100, 50, 25),
            target_light=(200, 150, 125),
        )
        
        pixel = result.getpixel((5, 5))
        assert pixel == (100, 50, 25)
