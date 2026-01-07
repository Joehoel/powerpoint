"""Entry point for PowerPoint Inverter."""

import streamlit as st

pptx_inverter = st.Page(
    "pages/pptx_inverter.py",
    title="PowerPoint Inverter",
    icon=":material/swap_horiz:",
    default=True,
)
image_converter = st.Page(
    "pages/image_converter.py", title="Image Converter", icon=":material/image:"
)

pg = st.navigation([pptx_inverter, image_converter])
st.set_page_config(
    page_title="PowerPoint Inverter", page_icon=":material/swap_horiz:", layout="wide"
)
pg.run()
