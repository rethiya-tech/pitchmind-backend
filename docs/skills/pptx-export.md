# PPTX Export Skill

## 6 Themes
```python
@dataclass
class Theme:
    id: str; name: str
    bg: str; text: str; accent: str
    font: str = "Plus Jakarta Sans"

THEMES = {
  "executive_modern": Theme("executive_modern","Executive Modern",
                            "#FFFFFF","#1A1A1A","#0F6E56"),
  "corporate_zenith": Theme("corporate_zenith","Corporate Zenith",
                            "#1A2A1A","#FFFFFF","#1D9E75"),
  "digital_frontier": Theme("digital_frontier","Digital Frontier",
                            "#0A1628","#FFFFFF","#5DCAA5"),
  "nordic_flow":      Theme("nordic_flow","Nordic Flow",
                            "#F5F4F0","#1A1A1A","#1D9E75"),
  "midnight_insight": Theme("midnight_insight","Midnight Insight",
                            "#1A1A1A","#FFFFFF","#C8850A"),
  "executive_gold":   Theme("executive_gold","Executive Gold",
                            "#0D0D0D","#FFFFFF","#C8850A"),
}
```

## PPTX builder
```python
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
import io

def hex_to_rgb(h: str) -> RGBColor:
    h = h.lstrip("#")
    return RGBColor(int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))

def build_pptx(slides: list, theme: Theme) -> bytes:
    prs = Presentation()
    prs.slide_width  = Emu(9144000)   # 10 inches (16:9)
    prs.slide_height = Emu(5143500)   # 5.63 inches
    for slide in slides:
        sl = prs.slides.add_slide(prs.slide_layouts[6])  # blank
        bg = sl.background.fill
        bg.solid()
        bg.fore_color.rgb = hex_to_rgb(theme.bg)
        bar = sl.shapes.add_shape(1,
            Emu(457200), Emu(914400), Emu(91440), Emu(3657600))
        bar.fill.solid()
        bar.fill.fore_color.rgb = hex_to_rgb(theme.accent)
        bar.line.fill.background()
        tb = sl.shapes.add_textbox(
            Emu(640080), Emu(914400), Emu(8229600), Emu(914400))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = slide.title or ""
        run = p.runs[0] if p.runs else p.add_run()
        run.font.size = Pt(28)
        run.font.bold = True
        run.font.color.rgb = hex_to_rgb(theme.text)
        if slide.bullets:
            cb = sl.shapes.add_textbox(
                Emu(640080), Emu(1981200), Emu(8229600), Emu(2743200))
            ctf = cb.text_frame
            ctf.word_wrap = True
            for i, bullet in enumerate(slide.bullets):
                cp = ctf.paragraphs[0] if i == 0 else ctf.add_paragraph()
                cp.text = f"• {bullet}"
                cr = cp.runs[0] if cp.runs else cp.add_run()
                cr.font.size = Pt(14)
                cr.font.color.rgb = hex_to_rgb(theme.text)
        if slide.speaker_notes:
            sl.notes_slide.notes_text_frame.text = slide.speaker_notes
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
```

## Export endpoint flow
1. Load all slides for conversion (is_deleted=False, ordered by position)
2. Get theme from conversion.theme
3. Call build_pptx(slides, theme) → bytes
4. Upload to GCS: key = pptx/{conversion_id}.pptx
5. Generate signed GET URL (1 hour expiry)
6. Return { download_url, expires_at }
