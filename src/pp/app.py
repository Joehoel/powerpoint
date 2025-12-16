"""Streamlit application for PowerPoint Inverter."""

import hashlib
import io
import logging
from datetime import datetime

import streamlit as st
from pptx import Presentation

from pp.core.inverter import process_files
from pp.models.config import InversionConfig
from pp.utils.preview import (
    generate_color_preview,
    generate_slide_preview,
    generate_slide_preview_inverted,
    hex_to_tuple,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@st.cache_data(show_spinner=False)
def _cached_color_preview(bg_hex: str, fg_hex: str):
    return generate_color_preview(
        background_color=hex_to_tuple(bg_hex),
        foreground_color=hex_to_tuple(fg_hex),
    )


def _hash_file(name: str, data: bytes) -> str:
    h = hashlib.sha256()
    h.update(name.encode())
    h.update(data)
    return h.hexdigest()


def main():

    """Main Streamlit application entry point."""
    st.set_page_config(
        page_title="PowerPoint Inverter",
        page_icon="🔄",
        layout="wide",
    )

    st.title("PowerPoint Inverter")
    st.write(
        "Invert colors in your PowerPoint presentations. "
        "Upload .pptx files or a .zip archive containing presentations."
    )

    # Initialize session state
    if "processed_result" not in st.session_state:
        st.session_state.processed_result = None
    if "preview_generated" not in st.session_state:
        st.session_state.preview_generated = False

    # Sidebar configuration
    with st.sidebar:
        st.header("Color Options")

        col1, col2 = st.columns(2)
        with col1:
            bg_color = st.color_picker(
                "Background",
                value="#000000",
                help="Color for slide backgrounds",
            )
        with col2:
            fg_color = st.color_picker(
                "Text",
                value="#FFFFFF",
                help="Color for text content",
            )

        # Show color preview
        st.subheader("Color Preview")
        color_preview = _cached_color_preview(bg_color, fg_color)
        st.image(color_preview, use_container_width=True)

        st.divider()
        st.header("Output Options")

        file_suffix = st.text_input(
            "File Suffix",
            value="(inverted)",
            help="Text added to output filenames",
        )

        folder_name = st.text_input(
            "Folder Name",
            value="Inverted Presentations",
            help="Name of the output ZIP file",
        )

        include_date = st.checkbox("Include date in folder name", value=True)

        invert_images = st.checkbox(
            "Invert image colors",
            value=True,
            help="Apply color inversion to images in slides",
        )

    # Main content area
    uploaded_files = st.file_uploader(
        "Upload PowerPoint files",
        type=["pptx", "zip"],
        accept_multiple_files=True,
        help="Select .pptx files or a .zip archive containing presentations",
    )

    if uploaded_files:
        st.success(f"Uploaded {len(uploaded_files)} file(s)")

        # File preview section
        file_blobs = [(f.name, f.getvalue()) for f in uploaded_files]
        with st.expander("Uploaded Files", expanded=False):
            for name, data in file_blobs:
                file_size = len(data) / 1024  # KB
                st.write(f"- **{name}** ({file_size:.1f} KB)")

        # Preview section
        st.subheader("Preview")

        preview_cols = st.columns(2)

        with preview_cols[0]:
            st.write("**Original**")
            # Show preview of first slide from first PPTX
            first_pptx = None
            prs = None
            for f in uploaded_files:
                if f.name.endswith(".pptx"):
                    first_pptx = f
                    break

            if first_pptx:
                try:
                    with st.spinner("Loading preview..."):
                        first_pptx.seek(0)
                        prs = Presentation(io.BytesIO(first_pptx.read()))
                        first_pptx.seek(0)

                        if prs.slides:
                            original_preview = generate_slide_preview(
                                prs.slides[0],
                                background_color=(255, 255, 255),
                                text_color=(0, 0, 0),
                            )
                            st.image(original_preview, width=320)
                        else:
                            st.info("No slides in presentation")
                except Exception as e:
                    st.warning(f"Could not generate preview: {e}")

        with preview_cols[1]:
            st.write("**After Inversion**")
            # Show what the inverted slide would look like with actual color transform
            if first_pptx and prs:
                try:
                    with st.spinner("Loading preview..."):
                        inverted_preview = generate_slide_preview_inverted(
                            prs.slides[0],
                            background_color=hex_to_tuple(bg_color),
                            foreground_color=hex_to_tuple(fg_color),
                        )
                        st.image(inverted_preview, width=320)
                except Exception as e:
                    st.warning(f"Could not generate preview: {e}")

        st.divider()

        # Process button
        if st.button("Invert Presentations", type="primary", use_container_width=True):
            # Build configuration
            final_folder_name = folder_name
            if include_date:
                date_str = datetime.now().strftime("%Y-%m-%d")
                final_folder_name = f"{folder_name} - {date_str}"

            config = InversionConfig.from_hex(
                fg_hex=fg_color,
                bg_hex=bg_color,
                file_suffix=file_suffix,
                folder_name=final_folder_name,
                invert_images=invert_images,
            )

            # Build cache key for manual reuse
            file_hashes = tuple((name, _hash_file(name, data)) for name, data in file_blobs)
            cache_key = (fg_color, bg_color, file_suffix, final_folder_name, invert_images, file_hashes)

            progress_bar = st.progress(0)
            status_text = st.empty()
            warnings_container = st.container()

            cached_entry = st.session_state.get("last_result")
            if cached_entry and cached_entry.get("key") == cache_key:
                result = cached_entry["result"]
                progress_bar.progress(1.0)
                status_text.text(
                    f"Complete! (cached) Processed {result.successful_files}/{result.total_files} files"
                )
            else:
                def update_progress(current: int, total: int, filename: str):
                    progress = current / total if total > 0 else 1.0
                    progress_bar.progress(progress)
                    status_text.text(f"Processing: {filename} ({current}/{total})")

                with st.spinner("Processing presentations..."):
                    # Reset file pointers before processing
                    for f in uploaded_files:
                        f.seek(0)
                    result = process_files(
                        uploaded_files,
                        config,
                        progress_callback=update_progress,
                    )

                progress_bar.progress(1.0)
                status_text.text(
                    f"Complete! Processed {result.successful_files}/{result.total_files} files"
                )

                st.session_state.last_result = {"key": cache_key, "result": result}

            # Show warnings
            if result.all_warnings:
                with warnings_container:
                    st.warning(f"Completed with {len(result.all_warnings)} warning(s)")
                    with st.expander("Show warnings"):
                        for warning in result.all_warnings:
                            st.write(f"- {warning}")

            # Store result in session state
            st.session_state.processed_result = result

        # Show download button if we have results
        if st.session_state.processed_result is not None:
            result = st.session_state.processed_result

            if result.output_zip:
                # Generate filename with date
                final_folder_name = folder_name
                if include_date:
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    final_folder_name = f"{folder_name} - {date_str}"

                st.download_button(
                    label=f"Download ({result.successful_files} files)",
                    data=result.output_zip,
                    file_name=f"{final_folder_name}.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                )

                # Show processing summary
                with st.expander("Processing Summary"):
                    for r in result.results:
                        status = "Success" if r.success else "Failed"
                        icon = "✅" if r.success else "❌"
                        st.write(f"{icon} **{r.filename}**: {status}")
                        if r.warnings:
                            for w in r.warnings:
                                st.write(f"   - ⚠️ {w}")
            else:
                st.error("No files were successfully processed")

    else:
        # Show instructions when no files uploaded
        st.info(
            "👆 Upload PowerPoint files to get started. "
            "You can upload multiple .pptx files or a .zip archive."
        )

        # Feature highlights
        st.subheader("Features")
        cols = st.columns(3)

        with cols[0]:
            st.markdown("**Custom Colors**")
            st.write("Choose your own foreground and background colors")

        with cols[1]:
            st.markdown("**Batch Processing**")
            st.write("Process multiple files at once with ZIP support")

        with cols[2]:
            st.markdown("**Fast & Parallel**")
            st.write("Optimized processing for large batches")


if __name__ == "__main__":
    main()
