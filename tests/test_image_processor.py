"""Tests for image processing."""

import io

from PIL import Image

from pp.core.image_processor import apply_color_transform, convert_image_colors


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
            target_dark=(0, 0, 128),  # Navy
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
        assert pixel[0] == 0  # Red
        assert pixel[1] == 0  # Green
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


class TestConvertImageColors:
    """Tests for the convert_image_colors function."""

    def test_png_format_preserved(self):
        """Test that PNG format is preserved in output."""
        img = Image.new("RGB", (50, 50), (255, 255, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        result_bytes, ext = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
        )

        assert ext == "png"
        # Verify it's valid PNG
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.format == "PNG"

    def test_jpeg_format_preserved(self):
        """Test that JPEG format is preserved in output."""
        img = Image.new("RGB", (50, 50), (255, 255, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        result_bytes, ext = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
        )

        assert ext == "jpg"
        # Verify it's valid JPEG
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.format == "JPEG"

    def test_gif_format_preserved(self):
        """Test that GIF format is preserved in output."""
        img = Image.new("RGB", (50, 50), (255, 255, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="GIF")
        img_bytes.seek(0)

        result_bytes, ext = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
        )

        assert ext == "gif"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.format == "GIF"

    def test_webp_format_preserved(self):
        """Test that WebP format is preserved in output."""
        img = Image.new("RGB", (50, 50), (255, 255, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="WEBP")
        img_bytes.seek(0)

        result_bytes, ext = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
        )

        assert ext == "webp"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.format == "WEBP"

    def test_bmp_format_preserved(self):
        """Test that BMP format is preserved in output."""
        img = Image.new("RGB", (50, 50), (255, 255, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="BMP")
        img_bytes.seek(0)

        result_bytes, ext = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
        )

        assert ext == "bmp"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.format == "BMP"

    def test_color_inversion_white_to_black(self):
        """Test that white image becomes black background."""
        img = Image.new("RGB", (10, 10), (255, 255, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        result_bytes, _ = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
        )

        result_img = Image.open(io.BytesIO(result_bytes))
        pixel = result_img.getpixel((5, 5))
        # White (light) should become background color (black)
        assert pixel == (0, 0, 0)

    def test_color_inversion_black_to_white(self):
        """Test that black image becomes white foreground."""
        img = Image.new("RGB", (10, 10), (0, 0, 0))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        result_bytes, _ = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
        )

        result_img = Image.open(io.BytesIO(result_bytes))
        pixel = result_img.getpixel((5, 5))
        # Black (dark) should become foreground color (white)
        assert pixel == (255, 255, 255)

    def test_custom_colors(self):
        """Test inversion with custom background and foreground colors."""
        img = Image.new("RGB", (10, 10), (255, 255, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        result_bytes, _ = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 128),  # Navy
            foreground_color=(255, 255, 0),  # Yellow
        )

        result_img = Image.open(io.BytesIO(result_bytes))
        pixel = result_img.getpixel((5, 5))
        # White (light) should become background color (navy)
        assert pixel == (0, 0, 128)

    def test_rgba_transparency_preserved_png(self):
        """Test that RGBA transparency is preserved for PNG output."""
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        result_bytes, ext = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
        )

        assert ext == "png"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.mode == "RGBA"
        # Check alpha is preserved
        pixel = result_img.getpixel((5, 5))
        assert pixel[3] == 128

    def test_jpeg_quality_parameter(self):
        """Test that JPEG quality parameter affects output size."""
        # Create a gradient image (more complex than solid color)
        img = Image.new("RGB", (100, 100))
        pixels = img.load()
        for x in range(100):
            for y in range(100):
                pixels[x, y] = (x * 2, y * 2, (x + y))  # type: ignore[index]

        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=100)
        img_bytes.seek(0)
        input_bytes = img_bytes.getvalue()

        result_low, _ = convert_image_colors(
            input_bytes,
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
            jpeg_quality=10,
        )

        result_high, _ = convert_image_colors(
            input_bytes,
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
            jpeg_quality=100,
        )

        # Higher quality should produce larger file
        assert len(result_high) > len(result_low)

    def test_force_output_format(self):
        """Test forcing a specific output format."""
        img = Image.new("RGB", (50, 50), (255, 255, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        result_bytes, ext = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
            output_format="JPEG",
        )

        assert ext == "jpg"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.format == "JPEG"

    def test_rgba_to_jpeg_conversion(self):
        """Test that RGBA images are properly converted when output is JPEG."""
        img = Image.new("RGBA", (50, 50), (255, 0, 0, 128))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        result_bytes, ext = convert_image_colors(
            img_bytes.getvalue(),
            background_color=(0, 0, 0),
            foreground_color=(255, 255, 255),
            output_format="JPEG",
        )

        assert ext == "jpg"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.format == "JPEG"
        assert result_img.mode == "RGB"  # JPEG doesn't support alpha
