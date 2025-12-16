"""Configuration models for PowerPoint Inverter."""

from dataclasses import dataclass, field
from typing import Self

from pptx.dml.color import RGBColor


@dataclass
class InversionConfig:
    """Configuration for color inversion settings.

    Attributes:
        foreground_color: The color to use for text (default: white).
        background_color: The color to use for slide backgrounds (default: black).
        file_suffix: Suffix to append to inverted file names.
        folder_name: Name of the output folder/zip file.
        invert_images: Whether to invert image colors.
    """

    foreground_color: RGBColor = field(default_factory=lambda: RGBColor(255, 255, 255))
    background_color: RGBColor = field(default_factory=lambda: RGBColor(0, 0, 0))
    file_suffix: str = "(inverted)"
    folder_name: str = "Inverted Presentations"
    invert_images: bool = True

    @classmethod
    def from_hex(
        cls,
        fg_hex: str,
        bg_hex: str,
        file_suffix: str = "(inverted)",
        folder_name: str = "Inverted Presentations",
        invert_images: bool = True,
    ) -> Self:
        """Create config from hex color strings (e.g., from st.color_picker).

        Args:
            fg_hex: Foreground/text color as hex string (e.g., "#FFFFFF").
            bg_hex: Background color as hex string (e.g., "#000000").
            file_suffix: Suffix for output filenames.
            folder_name: Name of output folder.
            invert_images: Whether to invert image colors.

        Returns:
            InversionConfig instance with parsed colors.
        """
        return cls(
            foreground_color=hex_to_rgb(fg_hex),
            background_color=hex_to_rgb(bg_hex),
            file_suffix=file_suffix,
            folder_name=folder_name,
            invert_images=invert_images,
        )


def hex_to_rgb(hex_color: str) -> RGBColor:
    """Convert a hex color string to RGBColor.

    Args:
        hex_color: Color as hex string, with or without '#' prefix.

    Returns:
        RGBColor instance.

    Examples:
        >>> hex_to_rgb("#FF0000")
        RGBColor(0xFF, 0x00, 0x00)
        >>> hex_to_rgb("00FF00")
        RGBColor(0x00, 0xFF, 0x00)
    """
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return RGBColor(r, g, b)


def rgb_to_hex(color: RGBColor) -> str:
    """Convert RGBColor to hex string.

    Args:
        color: RGBColor instance.

    Returns:
        Hex color string with '#' prefix.
    """
    # RGBColor string representation is like "RRGGBB"
    return f"#{str(color)}"
