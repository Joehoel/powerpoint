"""Spike 7 act C input: a deck whose colors are set through python-pptx's own
theme-color API, so the JS resolver is validated against an independent writer."""
from pathlib import Path

from pptx import Presentation
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.util import Inches, Pt

prs = Presentation()  # default template = Office theme (accent1 4472C4)
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(2))
tf = box.text_frame

p1 = tf.paragraphs[0]
r1 = p1.add_run()
r1.text = "accent1"
r1.font.size = Pt(24)
r1.font.color.theme_color = MSO_THEME_COLOR.ACCENT_1

r2 = p1.add_run()
r2.text = " lighter40"
r2.font.size = Pt(24)
r2.font.color.theme_color = MSO_THEME_COLOR.ACCENT_1
r2.font.color.brightness = 0.4  # -> lumMod 60000 + lumOff 40000

out = Path(__file__).parent / "out" / "spike7-themed.pptx"
prs.save(out)
print(f"generated {out.relative_to(Path.cwd())}")
