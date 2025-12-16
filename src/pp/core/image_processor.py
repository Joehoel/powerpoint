"""Image processing for PowerPoint Inverter.

This module handles memory-efficient image color transformation.
"""

import io
import logging
from typing import TYPE_CHECKING

from PIL import Image, ImageChops
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE

if TYPE_CHECKING:
    from pptx.shapes.picture import Picture
    from pptx.slide import Slide

logger = logging.getLogger(__name__)

# JPEG quality for output images (85 is visually near-lossless and faster)
JPEG_QUALITY = 85


def apply_color_transform(
    img: Image.Image,
    target_dark: tuple[int, int, int],
    target_light: tuple[int, int, int],
) -> Image.Image:
    """Apply color transform using Pillow LUTs (no numpy).

    Inverts then remaps dark/light ranges to target colors.
    Alpha is preserved and processed separately.
    """

    def build_lut(dark: int, light: int) -> list[int]:
        if dark == 0 and light == 255:
            return [255 - c for c in range(256)]
        scale = light - dark
        return [max(0, min(255, int(dark + (255 - c) * scale / 255))) for c in range(256)]

    # Normalize image to RGB, track alpha separately
    alpha = None
    base = img
    if img.mode == "RGBA":
        r, g, b, alpha = img.split()
        base = Image.merge("RGB", (r, g, b))
    elif img.mode == "RGB" and "transparency" in img.info:
        transparency = img.info.get("transparency")
        rgba = img.convert("RGBA")
        r, g, b, a = rgba.split()
        if isinstance(transparency, tuple) and len(transparency) == 3:
            tr, tg, tb = transparency
            mask_r = r.point(lambda v: 255 if v == tr else 0)
            mask_g = g.point(lambda v: 255 if v == tg else 0)
            mask_b = b.point(lambda v: 255 if v == tb else 0)
            mask = ImageChops.multiply(mask_r, ImageChops.multiply(mask_g, mask_b))
            alpha = mask.point(lambda v: 0 if v else 255)
        else:
            alpha = a
        base = Image.merge("RGB", (r, g, b))
    elif img.mode == "P":
        rgba = img.convert("RGBA")
        r, g, b, alpha = rgba.split()
        base = Image.merge("RGB", (r, g, b))
    elif img.mode != "RGB":
        base = img.convert("RGB")

    # Build LUTs per channel
    lut_r = build_lut(target_dark[0], target_light[0])
    lut_g = build_lut(target_dark[1], target_light[1])
    lut_b = build_lut(target_dark[2], target_light[2])
    full_lut = lut_r + lut_g + lut_b

    transformed = base.point(full_lut)

    if alpha is not None:
        transformed.putalpha(alpha)
        return transformed.convert("RGBA")

    return transformed

def invert_image(
    slide: "Slide",
    shape: "Picture",
    background_color: RGBColor,
    foreground_color: RGBColor,
) -> str | None:
    """Invert colors of a picture shape on a slide.

    This function extracts the image, applies color transformation,
    and replaces the original with the transformed version.

    Uses JPEG for faster encoding when no transparency is needed.

    Args:
        slide: The slide containing the picture.
        shape: The picture shape to invert.
        background_color: Target color for originally light areas.
        foreground_color: Target color for originally dark areas.

    Returns:
        Warning message if processing failed, None on success.
    """
    try:
        # Extract image data
        image_blob = shape.image.blob

        # Process image with context manager for memory efficiency
        with io.BytesIO(image_blob) as image_stream:
            with Image.open(image_stream) as img:
                # Apply color transformation
                # Note: For inversion, light areas become dark (background)
                # and dark areas become light (foreground)
                transformed = apply_color_transform(
                    img,
                    target_dark=(background_color[0], background_color[1], background_color[2]),
                    target_light=(foreground_color[0], foreground_color[1], foreground_color[2]),
                )

                # Save to bytes - use JPEG for RGB (faster), PNG for RGBA (transparency)
                output_stream = io.BytesIO()
                if transformed.mode == "RGBA":
                    transformed.save(output_stream, format="PNG", optimize=False)
                else:
                    # JPEG is much faster to encode than PNG
                    transformed.save(
                        output_stream,
                        format="JPEG",
                        quality=JPEG_QUALITY,
                        optimize=False,
                    )
                output_stream.seek(0)

                # Store position and size before removing
                left = shape.left
                top = shape.top
                width = shape.width
                height = shape.height

                # Remove original shape
                shape_element = shape._element
                shape_element.getparent().remove(shape_element)

                # Add new image at same position
                slide.shapes.add_picture(output_stream, left, top, width, height)

        return None

    except Exception as e:
        logger.warning(f"Failed to process image: {e}")
        return f"Image processing failed: {e}"


def is_picture_shape(shape) -> bool:
    """Check if a shape is a picture that can be inverted.

    Args:
        shape: A pptx shape object.

    Returns:
        True if shape is a processable picture.
    """
    return shape.shape_type == MSO_SHAPE_TYPE.PICTURE
