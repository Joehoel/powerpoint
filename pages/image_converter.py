"""Streamlit page for image color conversion."""

import io
import zipfile
from pathlib import Path

import streamlit as st

from pp.core.image_processor import convert_image_colors
from pp.utils.preview import hex_to_tuple


def _get_output_filename(original_name: str, new_ext: str) -> str:
    """Get output filename with new extension."""
    stem = Path(original_name).stem
    return f"{stem}_converted.{new_ext}"


st.title("Image Converter")
st.write(
    "Convert image colors with custom mapping. "
    "Default converts black-on-white to white-on-black."
)

# Initialize session state
if "converted_images" not in st.session_state:
    st.session_state.converted_images = None

# Sidebar configuration
with st.sidebar:
    st.header("Color Options")

    col1, col2 = st.columns(2)
    with col1:
        bg_color = st.color_picker(
            "Background",
            value="#000000",
            help="Color for image backgrounds",
        )
    with col2:
        fg_color = st.color_picker(
            "Text",
            value="#FFFFFF",
            help="Color for text content",
        )

    st.divider()

    # Quick preset buttons
    st.subheader("Presets")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Invert", use_container_width=True, help="White on black"):
            st.session_state.fg_color = "#FFFFFF"
            st.session_state.bg_color = "#000000"
            st.rerun()
    with col2:
        if st.button("Original", use_container_width=True, help="Black on white"):
            st.session_state.fg_color = "#000000"
            st.session_state.bg_color = "#FFFFFF"
            st.rerun()

    # Apply session state overrides if set
    if "fg_color" in st.session_state:
        fg_color = st.session_state.pop("fg_color")
    if "bg_color" in st.session_state:
        bg_color = st.session_state.pop("bg_color")

    st.divider()
    st.header("Output Options")

    jpeg_quality = st.slider(
        "JPEG Quality",
        min_value=50,
        max_value=100,
        value=100,
        help="Quality setting for JPEG output (higher = better quality, larger file)",
    )

# Main content area
uploaded_files = st.file_uploader(
    "Upload images",
    type=["png", "jpg", "jpeg", "gif", "bmp", "webp"],
    accept_multiple_files=True,
    help="Select one or more image files to convert",
)

if uploaded_files:
    st.success(f"Uploaded {len(uploaded_files)} image(s)")

    # Convert colors to tuples
    fg_rgb = hex_to_tuple(fg_color)
    bg_rgb = hex_to_tuple(bg_color)

    # Preview section
    st.subheader("Preview")

    # Show first image preview
    first_file = uploaded_files[0]
    first_bytes = first_file.getvalue()

    preview_cols = st.columns(2)

    with preview_cols[0]:
        st.write("**Original**")
        st.image(first_bytes, use_container_width=True)

    with preview_cols[1]:
        st.write("**Converted**")
        try:
            converted_bytes, _ = convert_image_colors(
                first_bytes,
                background_color=bg_rgb,
                foreground_color=fg_rgb,
                jpeg_quality=jpeg_quality,
            )
            st.image(converted_bytes, use_container_width=True)
        except Exception as e:
            st.error(f"Preview failed: {e}")

    st.divider()

    # Process button
    if st.button("Convert All Images", type="primary", use_container_width=True):
        converted_results = []

        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, file in enumerate(uploaded_files):
            status_text.text(f"Converting: {file.name} ({i + 1}/{len(uploaded_files)})")
            progress_bar.progress((i + 1) / len(uploaded_files))

            try:
                file_bytes = file.getvalue()
                converted_bytes, ext = convert_image_colors(
                    file_bytes,
                    background_color=bg_rgb,
                    foreground_color=fg_rgb,
                    jpeg_quality=jpeg_quality,
                )
                output_name = _get_output_filename(file.name, ext)
                converted_results.append(
                    {
                        "name": output_name,
                        "data": converted_bytes,
                        "success": True,
                        "original_name": file.name,
                    }
                )
            except Exception as e:
                converted_results.append(
                    {
                        "name": file.name,
                        "data": None,
                        "success": False,
                        "error": str(e),
                        "original_name": file.name,
                    }
                )

        progress_bar.progress(1.0)
        successful = sum(1 for r in converted_results if r["success"])
        status_text.text(
            f"Complete! Converted {successful}/{len(uploaded_files)} images"
        )

        st.session_state.converted_images = converted_results

    # Show download section if we have results
    if st.session_state.converted_images:
        results = st.session_state.converted_images
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]

        st.markdown("### Download")

        if failed_results:
            st.warning(f"{len(failed_results)} image(s) failed to convert")
            with st.expander("Show errors"):
                for r in failed_results:
                    st.write(
                        f"- **{r['original_name']}**: {r.get('error', 'Unknown error')}"
                    )

        if successful_results:
            if len(successful_results) == 1:
                # Single file download
                result = successful_results[0]
                st.download_button(
                    label=f"Download {result['name']}",
                    data=result["data"],
                    file_name=result["name"],
                    mime="application/octet-stream",
                    type="primary",
                    use_container_width=True,
                )
            else:
                # Multiple files - create ZIP
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for result in successful_results:
                        zf.writestr(result["name"], result["data"])
                zip_buffer.seek(0)

                st.download_button(
                    label=f"Download All ({len(successful_results)} images)",
                    data=zip_buffer.getvalue(),
                    file_name="converted_images.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                )

            # Show gallery of converted images
            st.markdown("### Converted Images")
            cols = st.columns(min(4, len(successful_results)))
            for i, result in enumerate(successful_results):
                with cols[i % len(cols)]:
                    st.image(
                        result["data"], caption=result["name"], use_container_width=True
                    )

else:
    # Show instructions when no files uploaded
    st.info(
        "Upload one or more images to convert their colors. "
        "Supports PNG, JPG, GIF, BMP, and WebP formats."
    )
