"""Tests for image processing."""

import io

import pytest
from PIL import Image

from pp.core.image_processor import apply_color_transform


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

    def test_color_remap_white_to_yellow(self):
        """Test remapping white to a custom light color."""
        # Create a white image
        img = Image.new("RGB", (10, 10), (255, 255, 255))
        
        result = apply_color_transform(
            img,
            target_dark=(0, 0, 128),
            target_light=(255, 255, 0),
        )
        
        # White inverted is black, then remapped to target_dark (navy)
        pixel = result.getpixel((5, 5))
        assert pixel[0] == 0    # Red
        assert pixel[1] == 0    # Green
        assert pixel[2] == 128  # Blue

    def test_color_remap_black_to_navy(self):
        """Test that black maps correctly after inversion."""
        img = Image.new("RGB", (10, 10), (0, 0, 0))
        
        result = apply_color_transform(
            img,
            target_dark=(100, 50, 25),
            target_light=(200, 150, 125),
        )
        
        # Black inverted is white (255,255,255), then remapped to target_light
        pixel = result.getpixel((5, 5))
        assert pixel == (200, 150, 125)
