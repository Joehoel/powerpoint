"""Image processing for PowerPoint Inverter.

This module handles memory-efficient image color transformation.
"""

import io
import logging
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image, ImageOps
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE

if TYPE_CHECKING:
    from pptx.shapes.picture import Picture
    from pptx.slide import Slide

logger = logging.getLogger(__name__)

# JPEG quality for output images (92 is visually lossless)
JPEG_QUALITY = 92


def apply_color_transform(
    img: Image.Image,
    target_dark: tuple[int, int, int],
    target_light: tuple[int, int, int],
) -> Image.Image:
    """Apply color transformation to map dark colors to target_dark and light to target_light.

    This creates a more sophisticated inversion that maps the image's color range
    to the specified target colors rather than simple RGB inversion.

    Optimized version using in-place numpy operations for memory efficiency.

    Args:
        img: PIL Image to transform.
        target_dark: RGB tuple for dark colors (e.g., background color).
        target_light: RGB tuple for light colors (e.g., foreground color).

    Returns:
        Transformed PIL Image (RGBA if transparency present, RGB otherwise).
    """
    alpha = None
    has_alpha = False

    # Handle different image modes and transparency types
    if img.mode == "RGBA":
        has_alpha = True
        arr = np.array(img, dtype=np.uint8)
        alpha = arr[:, :, 3].copy()
        arr = arr[:, :, :3]
    elif img.mode == "RGB" and "transparency" in img.info:
        transparency_color = img.info["transparency"]
        arr = np.array(img, dtype=np.uint8)
        # Create alpha from transparency color
        matches = np.all(arr == transparency_color, axis=2)
        alpha = np.where(matches, 0, 255).astype(np.uint8)
        has_alpha = True
    elif img.mode == "P":
        rgba = img.convert("RGBA")
        arr = np.array(rgba, dtype=np.uint8)
        alpha = arr[:, :, 3].copy()
        arr = arr[:, :, :3]
        has_alpha = True
    elif img.mode != "RGB":
        arr = np.array(img.convert("RGB"), dtype=np.uint8)
    else:
        arr = np.array(img, dtype=np.uint8)

    # Invert in-place: 255 - arr
    arr = np.subtract(255, arr, dtype=np.uint8)

    # If target colors are not standard black/white, remap colors
    if target_dark != (0, 0, 0) or target_light != (255, 255, 255):
        # Convert to float32 for interpolation, process in-place
        arr_float = arr.astype(np.float32)
        arr_float *= (1.0 / 255.0)  # Normalize to 0-1

        # Compute color range once
        dark = np.array(target_dark, dtype=np.float32) / 255.0
        light = np.array(target_light, dtype=np.float32) / 255.0
        color_range = light - dark

        # Interpolate: dark + arr * (light - dark)
        arr_float *= color_range
        arr_float += dark

        # Convert back to uint8
        arr_float *= 255.0
        arr = arr_float.astype(np.uint8)

    # Create result image
    if has_alpha and alpha is not None:
        # Combine RGB with alpha
        result_arr = np.dstack((arr, alpha))
        return Image.fromarray(result_arr, mode="RGBA")
    else:
        return Image.fromarray(arr, mode="RGB")


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
