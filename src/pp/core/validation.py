"""Validation utilities for PowerPoint Inverter.

This module provides color validation and analysis functions to ensure
good readability of inverted presentations.
"""

import logging
from pptx.dml.color import RGBColor

logger = logging.getLogger(__name__)


def calculate_luminance(color: RGBColor) -> float:
    """Calculate relative luminance per WCAG 2.0 standard.
    
    Args:
        color: RGB color to analyze.
    
    Returns:
        Relative luminance value (0.0 to 1.0).
        
    Reference:
        https://www.w3.org/TR/WCAG20/#relativeluminancedef
    """
    # Convert RGB to sRGB normalized values (0.0 to 1.0)
    r, g, b = color[0] / 255.0, color[1] / 255.0, color[2] / 255.0
    
    # Apply gamma correction
    def gamma_correct(c: float) -> float:
        if c <= 0.03928:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4
    
    r = gamma_correct(r)
    g = gamma_correct(g)
    b = gamma_correct(b)
    
    # Calculate relative luminance
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def calculate_contrast_ratio(foreground: RGBColor, background: RGBColor) -> float:
    """Calculate WCAG contrast ratio between two colors.
    
    Args:
        foreground: Foreground (text) color.
        background: Background color.
    
    Returns:
        Contrast ratio (1.0 to 21.0).
        - 1.0 = no contrast (same color)
        - 4.5 = minimum for AA level (normal text)
        - 7.0 = AAA level (enhanced)
        - 21.0 = maximum (black on white or vice versa)
        
    Reference:
        https://www.w3.org/TR/WCAG20/#contrast-ratiodef
    """
    lum_fg = calculate_luminance(foreground)
    lum_bg = calculate_luminance(background)
    
    # Lighter color goes in numerator
    lighter = max(lum_fg, lum_bg)
    darker = min(lum_fg, lum_bg)
    
    # Avoid division by zero (though shouldn't happen in practice)
    if darker == 0:
        return 21.0
    
    return (lighter + 0.05) / (darker + 0.05)


def validate_color_contrast(
    foreground: RGBColor,
    background: RGBColor,
) -> list[str]:
    """Validate color contrast and return warnings if contrast is poor.
    
    Args:
        foreground: Foreground (text) color.
        background: Background color.
    
    Returns:
        List of warning messages. Empty if colors have acceptable contrast.
    """
    warnings = []
    contrast = calculate_contrast_ratio(foreground, background)
    
    # Check if colors are too similar (likely unintentional)
    if contrast < 1.5:
        warnings.append(
            f"Colors are very similar (contrast ratio: {contrast:.1f}). "
            "Text may be difficult to read. Consider using more contrasting colors."
        )
    # Check WCAG AA level (normal text)
    elif contrast < 4.5:
        warnings.append(
            f"Contrast ratio is {contrast:.1f}. WCAG AA recommends at least 4.5:1 "
            "for normal text. Consider using colors with more contrast."
        )
    # Check WCAG AAA level (enhanced)
    elif contrast < 7.0:
        # This is a suggestion, not a warning - AA level is met
        pass
    
    return warnings
