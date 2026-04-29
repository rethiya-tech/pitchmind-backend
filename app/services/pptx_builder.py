import io
import logging
from typing import Any

_log = logging.getLogger(__name__)

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from app.services.themes import Theme

# Slide dimensions — 16:9 widescreen (EMU)
SLIDE_W = 9144000   # 10 in
SLIDE_H = 5143500   # 5.625 in

# Layout constants (EMU) — mirrored exactly in SlidePreview.tsx
HEADER_H   = 685800   # top accent band height  (13.33% of H)
FOOTER_Y   = 5006700  # footer top              (97.34% of H)
FOOTER_H   = 136800   # footer height           ( 2.66% of H)
TITLE_X    = 457200   # title / content left margin
TITLE_Y    = 800000   # title top
TITLE_W    = 8229600  # title width
TITLE_H    = 1143000  # title height
DIVIDER_Y  = 1943400  # thin horizontal divider top
DIVIDER_W  = 1828800  # divider width (2 in)
DIVIDER_H  = 45720    # divider height (0.05 in)
BULLETS_Y  = 2057400  # bullets top
BULLETS_H  = 2743200  # bullets height


# ── helpers ───────────────────────────────────────────────────────────────────

def _rgb(hex_color: str) -> RGBColor:
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _hex_val(hex_color: str) -> str:
    return hex_color.lstrip("#").upper()


_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
_A = _NS["a"]
_P = _NS["p"]


def _set_background(slide: Any, hex_color: str) -> None:
    """Force-set slide background via direct XML — bypasses bgRef inheritance."""
    color_val = _hex_val(hex_color)
    cSld = slide._element.find(qn("p:cSld"))
    for old_bg in cSld.findall(qn("p:bg")):
        cSld.remove(old_bg)

    bg_elem = etree.fromstring(
        f'<p:bg xmlns:p="{_P}" xmlns:a="{_A}">'
        f'<p:bgPr>'
        f'<a:solidFill><a:srgbClr val="{color_val}"/></a:solidFill>'
        f'<a:effectLst/>'
        f'</p:bgPr>'
        f'</p:bg>'
    )
    spTree = cSld.find(qn("p:spTree"))
    idx = list(cSld).index(spTree) if spTree is not None else 0
    cSld.insert(idx, bg_elem)


def _add_solid_rect(slide: Any, x: int, y: int, w: int, h: int,
                    hex_color: str, shape_id: int) -> None:
    """Insert a coloured rectangle directly via XML for maximum viewer compat."""
    color_val = _hex_val(hex_color)
    sp_xml = (
        f'<p:sp xmlns:p="{_P}" xmlns:a="{_A}">'
        f'  <p:nvSpPr>'
        f'    <p:cNvPr id="{shape_id}" name="rect{shape_id}"/>'
        f'    <p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        f'    <p:nvPr/>'
        f'  </p:nvSpPr>'
        f'  <p:spPr>'
        f'    <a:xfrm>'
        f'      <a:off x="{x}" y="{y}"/>'
        f'      <a:ext cx="{w}" cy="{h}"/>'
        f'    </a:xfrm>'
        f'    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'    <a:solidFill><a:srgbClr val="{color_val}"/></a:solidFill>'
        f'    <a:ln><a:noFill/></a:ln>'
        f'  </p:spPr>'
        f'  <p:txBody>'
        f'    <a:bodyPr/><a:lstStyle/><a:p/>'
        f'  </p:txBody>'
        f'</p:sp>'
    )
    spTree = slide._element.find(qn("p:cSld")).find(qn("p:spTree"))
    spTree.append(etree.fromstring(sp_xml))


def _clear_textbox_border(tb: Any) -> None:
    """Remove all borders from a textbox — prevents accent-color bar artifacts."""
    spPr = tb._element.find(qn("p:spPr"))
    if spPr is not None:
        # Remove any existing ln elements (python-pptx may add defaults)
        for ln_elem in list(spPr.findall(qn("a:ln"))):
            spPr.remove(ln_elem)
        # Explicit zero-width no-fill line
        ln = etree.SubElement(spPr, qn("a:ln"), w="0")
        etree.SubElement(ln, qn("a:noFill"))


def _add_textbox(slide: Any, text: str, x: int, y: int, w: int, h: int,
                 size_pt: int, bold: bool, hex_color: str,
                 font: str = "Plus Jakarta Sans") -> None:
    tb = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
    _clear_textbox_border(tb)

    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    run = p.runs[0] if p.runs else p.add_run()
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = _rgb(hex_color)
    run.font.name = font


# ── main builder ──────────────────────────────────────────────────────────────

def _purge_spTree(element: Any, label: str) -> None:
    """Remove ALL non-placeholder shapes from a cSld element's spTree."""
    spTree = element.find(qn("p:cSld")).find(qn("p:spTree"))
    all_children = list(spTree)
    _log.warning("PPTX DEBUG %s spTree children: %s",
                 label, [c.tag.split("}")[-1] for c in all_children])
    for sp in list(spTree.findall(qn("p:sp"))):
        is_ph = False
        try:
            nvPr = sp.find(qn("p:nvSpPr")).find(qn("p:nvPr"))
            if nvPr is not None and nvPr.find(qn("p:ph")) is not None:
                is_ph = True
        except AttributeError:
            pass
        _log.warning("PPTX DEBUG %s sp is_ph=%s", label, is_ph)
        if not is_ph:
            spTree.remove(sp)
    for tag in (qn("p:pic"), qn("p:graphicFrame"), qn("p:cxnSp"), qn("p:grpSp")):
        for elem in list(spTree.findall(tag)):
            _log.warning("PPTX DEBUG %s removing %s", label, tag.split("}")[-1])
            spTree.remove(elem)


def _blank_layout(prs: Any) -> Any:
    """Return a clean Blank slide layout with master shapes also stripped."""
    _log.warning("PPTX DEBUG layouts: %s", [l.name for l in prs.slide_layouts])
    layout = None
    for l in prs.slide_layouts:
        if l.name.strip().lower() == "blank":
            layout = l
            break
    if layout is None:
        _log.warning("PPTX DEBUG no 'Blank' layout found, using index 6")
        layout = prs.slide_layouts[6]
    _log.warning("PPTX DEBUG using layout: '%s'", layout.name)
    _purge_spTree(layout._element, f"layout[{layout.name}]")
    _purge_spTree(layout.slide_master._element, "master")

    # Zero out the accent color in the master theme so viewers can't inherit
    # an accent-colored border on shapes that don't explicitly set their line.
    try:
        master = layout.slide_master
        theme_elem = master._element.find(
            ".//{http://schemas.openxmlformats.org/drawingml/2006/main}theme"
        )
        if theme_elem is None:
            theme_elem = master._element.find(
                ".//{http://schemas.openxmlformats.org/drawingml/2006/main}fmtScheme"
            )
        # Override every ln (line) style in the master's format scheme to noFill
        for ln in master._element.iter(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}ln"
        ):
            for child in list(ln):
                ln.remove(child)
            ln.set("w", "0")
            etree.SubElement(
                ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}noFill"
            )
    except Exception:
        pass  # Non-critical — explicit noFill on each shape is the primary fix

    return layout


def build_pptx(slides: list[Any], theme: Theme) -> bytes:
    prs = Presentation()
    prs.slide_width  = Emu(SLIDE_W)
    prs.slide_height = Emu(SLIDE_H)

    blank = _blank_layout(prs)  # layout cleaned once here

    for slide_idx, slide in enumerate(slides):
        sl = prs.slides.add_slide(blank)
        sl._element.set("showMasterSp", "0")

        # Fix empty grpSpPr — third-party viewers require an explicit xfrm on
        # the spTree's group so they know the child coordinate space matches the
        # slide dimensions.  Without it, viewers like Jumpshare/Doconut render
        # shapes in unexpected positions.
        cSld = sl._element.find(qn("p:cSld"))
        spTree = cSld.find(qn("p:spTree"))
        grpSpPr = spTree.find(qn("p:grpSpPr"))
        if grpSpPr is not None and grpSpPr.find(qn("a:xfrm")) is None:
            xfrm = etree.SubElement(grpSpPr, qn("a:xfrm"))
            etree.SubElement(xfrm, qn("a:off"), x="0", y="0")
            etree.SubElement(xfrm, qn("a:ext"), cx=str(SLIDE_W), cy=str(SLIDE_H))
            etree.SubElement(xfrm, qn("a:chOff"), x="0", y="0")
            etree.SubElement(xfrm, qn("a:chExt"), cx=str(SLIDE_W), cy=str(SLIDE_H))

        # Add all solid rects first so python-pptx's auto-ID counter starts
        # above our manually-assigned IDs and we never get duplicate shape IDs.
        sid = slide_idx * 20 + 10
        num_w = 457200  # 0.5 in — slide number chip width

        # 1. Background
        _set_background(sl, theme.bg)

        # 2–5. All coloured rectangles (header, slide-number bg, divider, footer)
        _add_solid_rect(sl, 0, 0, SLIDE_W, HEADER_H, theme.accent, sid)
        _add_solid_rect(sl, SLIDE_W - num_w, 0, num_w, HEADER_H, theme.accent, sid + 1)
        _add_solid_rect(sl, TITLE_X, DIVIDER_Y, DIVIDER_W, DIVIDER_H, theme.accent, sid + 2)
        _add_solid_rect(sl, 0, FOOTER_Y, SLIDE_W, FOOTER_H, theme.accent, sid + 3)

        # 6. Slide number text
        _add_textbox(
            sl, str(slide_idx + 1),
            SLIDE_W - num_w, 0, num_w, HEADER_H,
            size_pt=10, bold=True, hex_color="#FFFFFF",
        )

        # 7. Title
        _add_textbox(
            sl, slide.title or "",
            TITLE_X, TITLE_Y, TITLE_W, TITLE_H,
            size_pt=28, bold=True, hex_color=theme.text,
        )

        # 8. Bullet points
        bullets: list[str] = slide.bullets if slide.bullets else []
        if bullets:
            cb = sl.shapes.add_textbox(
                Emu(TITLE_X), Emu(BULLETS_Y), Emu(TITLE_W), Emu(BULLETS_H),
            )
            _clear_textbox_border(cb)
            ctf = cb.text_frame
            ctf.word_wrap = True
            for j, bullet in enumerate(bullets):
                cp = ctf.paragraphs[0] if j == 0 else ctf.add_paragraph()
                dot = cp.add_run()
                dot.text = "● "
                dot.font.size = Pt(9)
                dot.font.color.rgb = _rgb(theme.accent)
                dot.font.name = "Plus Jakarta Sans"

                txt = cp.add_run()
                txt.text = bullet
                txt.font.size = Pt(15)
                txt.font.color.rgb = _rgb(theme.text)
                txt.font.name = "Plus Jakarta Sans"

        # 9. Footer text
        _add_textbox(
            sl, "PitchMind",
            TITLE_X, FOOTER_Y, 2000000, FOOTER_H,
            size_pt=8, bold=False, hex_color="#FFFFFF",
        )

        # 8. Speaker notes
        if slide.speaker_notes:
            sl.notes_slide.notes_text_frame.text = slide.speaker_notes

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
