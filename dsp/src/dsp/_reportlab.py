# pyright: basic
"""A small typed layer over ReportLab for `dsp.report_pdf`.

ReportLab's annotations are missing, which strict type checking rejects; this module is the one
place that calls it directly, and every function states the types it takes and returns. It owns
the bundled fonts, the evidence-level glyphs (drawn as vector shapes, so they need no font) and
the deterministic document build (ReportLab's `invariant` mode: fixed dates and document id).
"""

import io
import threading
from collections.abc import Callable, Sequence
from importlib import resources
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable as _Flowable
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

Flowable = Any

PAGE_WIDTH = A4[0]
MARGIN = 18 * mm
CONTENT_WIDTH: float = PAGE_WIDTH - 2 * MARGIN

# Registered name -> file in dsp/fonts. IBM Plex (SIL OFL 1.1) as shipped by @fontsource, one
# file per unicode subset; the text layer picks the subset that has each character.
FONT_FILES: dict[str, str] = {
    "Sanket-Sans": "IBMPlexSans-latin-400.ttf",
    "Sanket-Sans-LatinExt": "IBMPlexSans-latin-ext-400.ttf",
    "Sanket-Sans-Greek": "IBMPlexSans-greek-400.ttf",
    "Sanket-Sans-Bold": "IBMPlexSans-latin-600.ttf",
    "Sanket-Sans-Bold-LatinExt": "IBMPlexSans-latin-ext-600.ttf",
    "Sanket-Sans-Bold-Greek": "IBMPlexSans-greek-600.ttf",
    "Sanket-Mono": "IBMPlexMono-latin-400.ttf",
}
# The fonts tried, in order, for each text style.
FONT_CHAINS: dict[str, tuple[str, ...]] = {
    "sans": ("Sanket-Sans", "Sanket-Sans-LatinExt", "Sanket-Sans-Greek"),
    "bold": ("Sanket-Sans-Bold", "Sanket-Sans-Bold-LatinExt", "Sanket-Sans-Bold-Greek"),
    "mono": ("Sanket-Mono", "Sanket-Sans", "Sanket-Sans-LatinExt", "Sanket-Sans-Greek"),
}

_lock = threading.Lock()
_registered = False


def register_fonts() -> None:
    """Register the bundled fonts with ReportLab (once per process)."""
    global _registered
    with _lock:
        if _registered:
            return
        for name, file in FONT_FILES.items():
            path = resources.files("dsp").joinpath("fonts", file)
            with resources.as_file(path) as real:
                font = TTFont(name, str(real))
            # Every subset file carries the same internal name, and ReportLab would treat them
            # as one font; the file's own name tells them apart.
            font.face.name = file.removesuffix(".ttf").encode("ascii")
            pdfmetrics.registerFont(font)
        _registered = True


def has_glyph(font: str, char: str) -> bool:
    register_fonts()
    loaded: Any = pdfmetrics.getFont(font)
    glyphs: dict[int, int] = loaded.face.charToGlyph
    return glyphs.get(ord(char), 0) != 0


def text_width(text: str, font: str, size: float) -> float:
    register_fonts()
    return float(stringWidth(text, font, size))


def paragraph(
    markup: str,
    *,
    font: str,
    size: float,
    leading: float | None = None,
    color: str = "#1f2328",
    left_indent: float = 0.0,
    space_before: float = 0.0,
    space_after: float = 0.0,
    keep_with_next: bool = False,
) -> Flowable:
    """A wrapping paragraph; `markup` is ReportLab's mini-HTML (text already escaped)."""
    register_fonts()
    style = ParagraphStyle(
        "p",
        fontName=font,
        fontSize=size,
        leading=leading if leading is not None else size * 1.3,
        textColor=HexColor(color),
        leftIndent=left_indent,
        spaceBefore=space_before,
        spaceAfter=space_after,
        keepWithNext=1 if keep_with_next else 0,
        splitLongWords=1,
    )
    return Paragraph(markup, style)


def spacer(height: float) -> Flowable:
    return Spacer(1, height)


def page_break() -> Flowable:
    return PageBreak()


def table(
    rows: Sequence[Sequence[Any]],
    col_widths: Sequence[float],
    *,
    header_rows: int = 1,
    header_color: str = "#e8ecf0",
    rule_color: str = "#c5ccd3",
) -> Flowable:
    """A table whose first rows repeat on every page it spans; cells are flowables."""
    style = TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, HexColor(rule_color)),
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), HexColor(header_color)),
        ]
    )
    return Table(
        [list(r) for r in rows],
        colWidths=list(col_widths),
        repeatRows=header_rows,
        style=style,
        splitByRow=1,
    )


class _LevelBadge(_Flowable):
    """An evidence level as a vector glyph and its word (never colour alone, PLAN §4)."""

    GLYPH = 10.0  # the glyph is drawn in a 10 x 10 box, scaled to `size`
    GAP = 2.5

    def __init__(self, level: str, color: str, font: str, size: float) -> None:
        super().__init__()
        self.level = level
        self.color = HexColor(color)
        self.font = font
        self.size = size
        self.box = size * 1.25
        self.width = self.box + self.GAP + text_width(level, font, size)
        self.height = self.box + 1

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        canvas: Canvas = self.canv
        canvas.saveState()
        canvas.translate(0, 0.5)
        canvas.scale(self.box / self.GLYPH, self.box / self.GLYPH)
        canvas.setStrokeColor(self.color)
        canvas.setFillColor(self.color)
        canvas.setLineCap(1)
        canvas.setLineJoin(1)
        _GLYPHS[self.level](canvas)
        canvas.restoreState()
        canvas.setFillColor(self.color)
        canvas.setFont(self.font, self.size)
        canvas.drawString(self.box + self.GAP, 0.5 + self.box * 0.2, self.level)


def _shield(c: Canvas) -> None:
    """VERIFIED: a filled shield with a white tick."""
    p = c.beginPath()
    p.moveTo(5, 10)
    p.lineTo(9, 8.6)
    p.lineTo(9, 5)
    p.curveTo(9, 2.5, 7, 1, 5, 0)
    p.curveTo(3, 1, 1, 2.5, 1, 5)
    p.lineTo(1, 8.6)
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    c.setStrokeColor(HexColor("#ffffff"))
    c.setLineWidth(1.3)
    c.lines([(3, 5, 4.5, 3.4), (4.5, 3.4, 7, 6.6)])


def _ruler(c: Canvas) -> None:
    """MEASURED: a ruler with ticks."""
    c.translate(5, 5)
    c.rotate(-45)
    c.setLineWidth(0.9)
    c.roundRect(-5.2, -2.2, 10.4, 4.4, 0.6, stroke=1, fill=0)
    c.lines([(x, 2.2, x, 0.4) for x in (-3.4, -1.1, 1.1, 3.4)])


def _sigma(c: Canvas) -> None:
    """ESTIMATED: the sum sign."""
    c.setLineWidth(1.4)
    p = c.beginPath()
    p.moveTo(8.5, 9)
    p.lineTo(1.5, 9)
    p.lineTo(5.2, 5)
    p.lineTo(1.5, 1)
    p.lineTo(8.5, 1)
    c.drawPath(p, stroke=1, fill=0)


def _dashed_circle(c: Canvas) -> None:
    """HYPOTHESIS: a dashed circle."""
    c.setLineWidth(1.2)
    c.setDash(1.7, 1.3)
    c.circle(5, 5, 4, stroke=1, fill=0)


def _slashed_circle(c: Canvas) -> None:
    """UNKNOWN: a circle with a slash."""
    c.setLineWidth(1.2)
    c.circle(5, 5, 4, stroke=1, fill=0)
    c.line(2.2, 2.2, 7.8, 7.8)


_GLYPHS: dict[str, Callable[[Canvas], None]] = {
    "VERIFIED": _shield,
    "MEASURED": _ruler,
    "ESTIMATED": _sigma,
    "HYPOTHESIS": _dashed_circle,
    "UNKNOWN": _slashed_circle,
}


def level_badge(level: str, color: str, font: str, size: float) -> Flowable:
    return _LevelBadge(level, color, font, size)


def _numbered_canvas(footer: str, font: str, size: float, color: str) -> type[Canvas]:
    """A canvas that writes `footer` (with 'page n of m') on every page, after the last page is
    known."""

    class NumberedCanvas(Canvas):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._saved_pages: list[dict[str, Any]] = []

        def showPage(self) -> None:
            self._saved_pages.append(dict(self.__dict__))
            self._startPage()  # type: ignore[attr-defined]

        def save(self) -> None:
            total = len(self._saved_pages)
            for state in self._saved_pages:
                self.__dict__.update(state)
                self.setFont(font, size)
                self.setFillColor(HexColor(color))
                self.drawString(
                    MARGIN, 10 * mm, f"{footer} · page {self.getPageNumber()} of {total}"
                )
                super().showPage()
            super().save()

    return NumberedCanvas


def build_pdf(
    story: Sequence[Flowable],
    *,
    footer: str,
    title: str,
    author: str,
    subject: str,
) -> bytes:
    """The PDF bytes for a story. Deterministic: ReportLab's invariant mode fixes the creation
    date and the document id, and nothing here reads the clock or a random source."""
    register_fonts()
    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=20 * mm,
        title=title,
        author=author,
        subject=subject,
        creator="Sanket",
        invariant=1,
    )
    doc.build(
        list(story),
        canvasmaker=_numbered_canvas(footer, "Sanket-Sans", 7.5, "#59636e"),
    )
    return out.getvalue()


__all__ = [
    "CONTENT_WIDTH",
    "FONT_CHAINS",
    "Flowable",
    "build_pdf",
    "has_glyph",
    "level_badge",
    "page_break",
    "paragraph",
    "register_fonts",
    "spacer",
    "table",
    "text_width",
]
