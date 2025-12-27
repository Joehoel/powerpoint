"""Tests for color validation module."""

from pptx.dml.color import RGBColor

from pp.core.validation import (
    calculate_contrast_ratio,
    calculate_luminance,
    validate_color_contrast,
)
from pp.models.config import InversionConfig


class TestCalculateLuminance:
    """Tests for luminance calculation."""

    def test_white(self):
        """Test luminance of white."""
        white = RGBColor(255, 255, 255)
        lum = calculate_luminance(white)
        assert abs(lum - 1.0) < 0.01

    def test_black(self):
        """Test luminance of black."""
        black = RGBColor(0, 0, 0)
        lum = calculate_luminance(black)
        assert abs(lum - 0.0) < 0.01

    def test_red(self):
        """Test luminance of red."""
        red = RGBColor(255, 0, 0)
        lum = calculate_luminance(red)
        # Red has low luminance
        assert 0.0 < lum < 0.3

    def test_green(self):
        """Test luminance of green."""
        green = RGBColor(0, 255, 0)
        lum = calculate_luminance(green)
        # Green has higher luminance than red
        assert 0.5 < lum < 0.8

    def test_blue(self):
        """Test luminance of blue."""
        blue = RGBColor(0, 0, 255)
        lum = calculate_luminance(blue)
        # Blue has low luminance
        assert 0.0 < lum < 0.2


class TestCalculateContrastRatio:
    """Tests for WCAG contrast ratio calculation."""

    def test_black_on_white(self):
        """Test maximum contrast (black on white)."""
        white = RGBColor(255, 255, 255)
        black = RGBColor(0, 0, 0)
        contrast = calculate_contrast_ratio(black, white)
        assert abs(contrast - 21.0) < 0.5

    def test_white_on_black(self):
        """Test maximum contrast (white on black, reversed order)."""
        white = RGBColor(255, 255, 255)
        black = RGBColor(0, 0, 0)
        # Should be same regardless of order
        contrast = calculate_contrast_ratio(white, black)
        assert abs(contrast - 21.0) < 0.5

    def test_same_colors(self):
        """Test contrast of identical colors."""
        red = RGBColor(255, 0, 0)
        contrast = calculate_contrast_ratio(red, red)
        assert abs(contrast - 1.0) < 0.01

    def test_wcag_aa_compliant(self):
        """Test colors that meet WCAG AA standard."""
        # Good dark text on light background
        dark = RGBColor(33, 33, 33)
        light = RGBColor(255, 255, 255)
        contrast = calculate_contrast_ratio(dark, light)
        assert contrast >= 4.5

    def test_wcag_aaa_compliant(self):
        """Test colors that meet WCAG AAA standard."""
        # Excellent contrast
        black = RGBColor(0, 0, 0)
        white = RGBColor(255, 255, 255)
        contrast = calculate_contrast_ratio(black, white)
        assert contrast >= 7.0

    def test_low_contrast_colors(self):
        """Test colors with poor contrast."""
        light_gray = RGBColor(200, 200, 200)
        light_white = RGBColor(255, 255, 255)
        contrast = calculate_contrast_ratio(light_gray, light_white)
        # Should be low
        assert contrast < 2.0


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

    def test_very_similar_colors_warning(self):
        """Test nearly identical colors produce warnings."""
        color1 = RGBColor(100, 100, 100)
        color2 = RGBColor(101, 101, 101)
        warnings = validate_color_contrast(color1, color2)
        assert len(warnings) > 0
        assert "similar" in warnings[0].lower()

    def test_aa_level_achieved(self):
        """Test colors that meet AA but not AAA level."""
        dark = RGBColor(33, 33, 33)
        white = RGBColor(255, 255, 255)
        warnings = validate_color_contrast(dark, white)
        # AA level is acceptable, no warning
        assert len(warnings) == 0


class TestInversionConfigValidate:
    """Tests for InversionConfig.validate() method."""

    def test_validate_good_colors(self):
        """Test validation with good contrast colors."""
        config = InversionConfig(
            foreground_color=RGBColor(255, 255, 255),
            background_color=RGBColor(0, 0, 0),
        )
        warnings = config.validate()
        assert len(warnings) == 0

    def test_validate_poor_colors(self):
        """Test validation with poor contrast colors."""
        config = InversionConfig(
            foreground_color=RGBColor(200, 200, 200),
            background_color=RGBColor(255, 255, 255),
        )
        warnings = config.validate()
        assert len(warnings) > 0

    def test_validate_from_hex(self):
        """Test validation with colors from hex."""
        config = InversionConfig.from_hex(
            fg_hex="#FFFFFF",
            bg_hex="#000000",
        )
        warnings = config.validate()
        assert len(warnings) == 0

    def test_validate_from_hex_poor(self):
        """Test validation with poor hex colors."""
        config = InversionConfig.from_hex(
            fg_hex="#C8C8C8",  # Light gray
            bg_hex="#FFFFFF",  # White
        )
        warnings = config.validate()
        assert len(warnings) > 0
