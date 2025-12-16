"""Preview generation for PowerPoint Inverter.

This module provides utilities for generating slide previews.
Note: Full slide rendering requires external tools. This module provides
simplified previews based on slide content.
"""

import io
import logging
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE

if TYPE_CHECKING:
    from pptx.slide import Slide

logger = logging.getLogger(__name__)

# Default preview dimensions (4:3 aspect ratio)
DEFAULT_PREVIEW_WIDTH = 400
DEFAULT_PREVIEW_HEIGHT = 300


def generate_slide_preview(
    slide: "Slide",
    width: int = DEFAULT_PREVIEW_WIDTH,
    height: int = DEFAULT_PREVIEW_HEIGHT,
    background_color: tuple[int, int, int] = (255, 255, 255),
    text_color: tuple[int, int, int] = (0, 0, 0),
) -> bytes:
    """Generate a simplified preview image of a slide.

    This creates a visual representation showing:
    - Background color
    - Text content (first few lines)
    - Placeholder for images

    Args:
        slide: The slide to preview.
        width: Preview image width in pixels.
        height: Preview image height in pixels.
        background_color: RGB tuple for background.
        text_color: RGB tuple for text.

    Returns:
        PNG image as bytes.
    """
    # Create base image with background
    img = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(img)

    # Try to use a basic font, fall back to default
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except (OSError, IOError):
        font = ImageFont.load_default()
        title_font = font

    # Collect text content from slide
    texts: list[tuple[str, bool]] = []  # (text, is_title)
    image_count = 0

    for shape in slide.shapes:
        if shape.has_text_frame:
            text = shape.text_frame.text.strip()  # type: ignore[union-attr]
            if text:
                # Check if it's likely a title (usually first text, larger)
                is_title = len(texts) == 0 and len(text) < 100
                texts.append((text, is_title))

        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            image_count += 1

    # Draw text content
    y_position = 20
    margin = 20

    for text, is_title in texts[:5]:  # Limit to first 5 text blocks
        current_font = title_font if is_title else font

        # Truncate long text
        if len(text) > 50:
            text = text[:47] + "..."

        # Word wrap
        words = text.split()
        lines: list[str] = []
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=current_font)
            if bbox[2] < width - 2 * margin:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        # Draw lines
        for line in lines[:3]:  # Max 3 lines per text block
            if y_position > height - 40:
                break
            draw.text((margin, y_position), line, fill=text_color, font=current_font)
            y_position += 22 if is_title else 18

        y_position += 10  # Gap between text blocks

    # Show image indicator if slide has images
    if image_count > 0:
        indicator_text = f"[{image_count} image{'s' if image_count > 1 else ''}]"
        bbox = draw.textbbox((0, 0), indicator_text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(
            (width - text_width - margin, height - 30),
            indicator_text,
            fill=(*text_color[:2], min(text_color[2] + 100, 255)),  # Slightly lighter
            font=font,
        )

    # Add border
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(200, 200, 200))

    # Convert to bytes
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output.read()


def generate_color_preview(
    background_color: tuple[int, int, int],
    foreground_color: tuple[int, int, int],
    width: int = 200,
    height: int = 100,
) -> bytes:
    """Generate a preview showing the color scheme.

    Creates an image with the background color and sample text
    in the foreground color.

    Args:
        background_color: RGB tuple for background.
        foreground_color: RGB tuple for text.
        width: Preview width in pixels.
        height: Preview height in pixels.

    Returns:
        PNG image as bytes.
    """
    img = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(img)

    # Try to get a font
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # Draw sample text
    sample_text = "Sample Text"
    bbox = draw.textbbox((0, 0), sample_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (width - text_width) // 2
    y = (height - text_height) // 2

    draw.text((x, y), sample_text, fill=foreground_color, font=font)

    # Add border
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(128, 128, 128))

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output.read()


def rgb_color_to_tuple(color: RGBColor) -> tuple[int, int, int]:
    """Convert RGBColor to tuple.

    Args:
        color: pptx RGBColor instance.

    Returns:
        Tuple of (red, green, blue) integers.
    """
    return (color[0], color[1], color[2])


def hex_to_tuple(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple.

    Args:
        hex_color: Color as hex string (e.g., "#FF0000").

    Returns:
        Tuple of (red, green, blue) integers.
    """
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )
