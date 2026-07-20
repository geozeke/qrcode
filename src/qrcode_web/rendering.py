"""QR encoding and initial raster/vector export functions."""

from __future__ import annotations

import base64
from io import BytesIO
from textwrap import wrap
from typing import cast
from xml.etree.ElementTree import Element, SubElement, tostring

import segno
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape, letter
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from segno import consts

from qrcode_web.errors import RequestValidationError, ValidationIssue
from qrcode_web.exports import PdfOptions
from qrcode_web.logos import PreparedLogo, logo_placement
from qrcode_web.visuals import VisualOptions


def make_qr(content: str, error_correction: str = "M") -> segno.QRCode:
    """Encode content as a standard QR Code within the v20 limit.

    Parameters
    ----------
    content : str
        Normalized payload content.
    error_correction : str, default="M"
        QR error-correction level.

    Returns
    -------
    segno.QRCode
        Encoded standard Model 2 QR Code.

    Raises
    ------
    RequestValidationError
        If the content cannot fit in version 1 through 20.
    """
    try:
        code = segno.make(
            content, error=error_correction, micro=False, boost_error=False
        )
    except ValueError as error:
        raise RequestValidationError(
            [
                ValidationIssue(
                    "payload", "capacity", "This payload is too large for a QR Code."
                )
            ]
        ) from error
    if not isinstance(code.version, int) or code.version > 20:
        raise RequestValidationError(
            [
                ValidationIssue(
                    "payload",
                    "version",
                    "This payload requires QR version 21 or higher.",
                )
            ]
        )
    return code


def render_png(
    code: segno.QRCode,
    visual: VisualOptions,
    scale: int = 12,
    module_style: str = "square",
    logo: PreparedLogo | None = None,
) -> bytes:
    """Render a scanner-safe PNG preview.

    Parameters
    ----------
    code : segno.QRCode
        QR code to render.
    scale : int, default=12
        Integer pixels per module.

    Returns
    -------
    bytes
        PNG image bytes with a four-module quiet zone.
    """
    image = _render_raster(code, visual, scale, module_style, logo)
    output = BytesIO()
    image.save(output, format="PNG", dpi=(300, 300))
    return output.getvalue()


def _render_raster(
    code: segno.QRCode,
    visual: VisualOptions,
    scale: int,
    module_style: str,
    logo: PreparedLogo | None,
) -> Image.Image:
    """Render QR modules and external border geometry to a PIL image."""
    matrix = list(code.matrix_iter(scale=1, border=4, verbose=True))
    qr_size = len(matrix) * scale
    has_border = visual.border_type != "quiet"
    gap = 2 * scale if has_border else 0
    frame = visual.border_width * scale if has_border else 0
    offset = gap + frame
    caption_height = 4 * scale if visual.border_type == "label" else 0
    width = qr_size + 2 * offset
    height = qr_size + 2 * offset + caption_height
    mode = "RGBA" if visual.transparent else "RGB"
    background = (0, 0, 0, 0) if visual.transparent else visual.background
    image = Image.new(mode, (width, height), background)
    draw = ImageDraw.Draw(image)
    _draw_raster_frame(draw, visual, scale, width, height, caption_height)
    for row_index, row in enumerate(matrix):
        for column_index, module_type in enumerate(row):
            if not module_type >> 8:
                continue
            x0 = offset + column_index * scale
            y0 = offset + row_index * scale
            x1, y1 = x0 + scale - 1, y0 + scale - 1
            if module_style == "dot" and module_type == consts.TYPE_DATA_DARK:
                draw.ellipse((x0, y0, x1, y1), fill=visual.foreground)
            else:
                draw.rectangle((x0, y0, x1, y1), fill=visual.foreground)
    if logo is not None:
        _place_raster_logo(image, code, logo, scale, offset)
    return image


def _place_raster_logo(
    image: Image.Image,
    code: segno.QRCode,
    logo: PreparedLogo,
    scale: int,
    qr_offset: int,
) -> None:
    """Composite a sanitized logo over an opaque white module-aligned backing."""
    placement = logo_placement(code)
    symbol_origin = qr_offset + 4 * scale
    backing_xy = symbol_origin + placement.backing_start * scale
    backing_size = placement.backing_modules * scale
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (
            backing_xy,
            backing_xy,
            backing_xy + backing_size - 1,
            backing_xy + backing_size - 1,
        ),
        fill="#FFFFFF",
    )
    logo_size = placement.logo_modules * scale
    with Image.open(BytesIO(logo.png)) as source:
        clean = source.convert("RGBA")
        clean.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
    logo_x = backing_xy + (backing_size - clean.width) // 2
    logo_y = backing_xy + (backing_size - clean.height) // 2
    if image.mode == "RGBA":
        image.alpha_composite(clean, (logo_x, logo_y))
    else:
        image.paste(clean.convert("RGB"), (logo_x, logo_y), clean)


def _draw_raster_frame(
    draw: ImageDraw.ImageDraw,
    visual: VisualOptions,
    scale: int,
    width: int,
    height: int,
    caption_height: int,
) -> None:
    """Draw an external raster frame without entering the fixed gap."""
    if visual.border_type in {"quiet", "padding"}:
        return
    frame = visual.border_width * scale
    bounds = (0, 0, width - 1, height - 1)
    if visual.border_type == "rounded":
        radius = min(2 * frame, 8 * scale)
        draw.rounded_rectangle(
            bounds, radius=radius, outline=visual.foreground, width=frame
        )
    else:
        draw.rectangle(bounds, outline=visual.foreground, width=frame)
    if visual.border_type != "label":
        return
    divider_y = height - caption_height - frame
    draw.line(
        (frame, divider_y, width - frame - 1, divider_y),
        fill=visual.foreground,
        width=frame,
    )
    font = ImageFont.load_default(size=max(10, scale * 2))
    lines = wrap(visual.border_caption, width=max(1, width // (scale * 2)))[:2]
    line_height = max(10, scale * 2)
    start_y = divider_y + (caption_height - len(lines) * line_height) / 2
    for index, line in enumerate(lines):
        draw.text(
            (width / 2, start_y + index * line_height),
            line,
            fill=visual.foreground,
            font=font,
            anchor="ma",
        )


def render_svg(
    code: segno.QRCode,
    visual: VisualOptions,
    scale: int = 12,
    module_style: str = "square",
    logo: PreparedLogo | None = None,
) -> bytes:
    """Render a self-contained SVG QR image.

    Parameters
    ----------
    code : segno.QRCode
        QR code to render.
    scale : int, default=12
        Integer module scale used for SVG geometry.

    Returns
    -------
    bytes
        SVG image bytes with a four-module quiet zone.
    """
    return _render_svg_geometry(code, visual, scale, module_style, logo)


def _render_svg_geometry(
    code: segno.QRCode,
    visual: VisualOptions,
    scale: int,
    module_style: str,
    logo: PreparedLogo | None,
) -> bytes:
    """Render classified QR modules and external frame as SVG geometry."""
    pixel_scale = scale
    scale = 1
    matrix = list(code.matrix_iter(scale=1, border=4, verbose=True))
    qr_size = len(matrix) * scale
    has_border = visual.border_type != "quiet"
    gap = 2 * scale if has_border else 0
    frame = visual.border_width * scale if has_border else 0
    offset = gap + frame
    caption_height = 4 * scale if visual.border_type == "label" else 0
    width = qr_size + 2 * offset
    height = qr_size + 2 * offset + caption_height
    root = Element(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        width=str(width * pixel_scale),
        height=str(height * pixel_scale),
        viewBox=f"0 0 {width} {height}",
    )
    if not visual.transparent:
        SubElement(
            root,
            "rect",
            x="0",
            y="0",
            width=str(width),
            height=str(height),
            fill=visual.background,
        )
    _draw_svg_frame(root, visual, scale, width, height, caption_height)
    for row_index, row in enumerate(matrix):
        for column_index, module_type in enumerate(row):
            if not module_type >> 8:
                continue
            x = offset + column_index * scale
            y = offset + row_index * scale
            if module_style == "dot" and module_type == consts.TYPE_DATA_DARK:
                SubElement(
                    root,
                    "circle",
                    cx=str(x + scale / 2),
                    cy=str(y + scale / 2),
                    r=str(scale / 2),
                    fill=visual.foreground,
                )
            else:
                SubElement(
                    root,
                    "rect",
                    x=str(x),
                    y=str(y),
                    width=str(scale),
                    height=str(scale),
                    fill=visual.foreground,
                )
    if logo is not None:
        _add_svg_logo(root, code, logo, scale, offset)
    return cast(bytes, tostring(root, encoding="utf-8", xml_declaration=True))


def _add_svg_logo(
    root: Element,
    code: segno.QRCode,
    logo: PreparedLogo,
    scale: int,
    qr_offset: int,
) -> None:
    """Embed a sanitized logo and opaque white backing in an SVG document."""
    placement = logo_placement(code)
    symbol_origin = qr_offset + 4 * scale
    backing_xy = symbol_origin + placement.backing_start * scale
    backing_size = placement.backing_modules * scale
    logo_size = placement.logo_modules * scale
    SubElement(
        root,
        "rect",
        x=str(backing_xy),
        y=str(backing_xy),
        width=str(backing_size),
        height=str(backing_size),
        fill="#FFFFFF",
    )
    encoded = base64.b64encode(logo.png).decode("ascii")
    SubElement(
        root,
        "image",
        x=str(backing_xy + scale),
        y=str(backing_xy + scale),
        width=str(logo_size),
        height=str(logo_size),
        href=f"data:image/png;base64,{encoded}",
        preserveAspectRatio="xMidYMid meet",
    )


def _draw_svg_frame(
    root: Element,
    visual: VisualOptions,
    scale: int,
    width: int,
    height: int,
    caption_height: int,
) -> None:
    """Add external SVG frame and optional escaped caption geometry."""
    if visual.border_type in {"quiet", "padding"}:
        return
    frame = visual.border_width * scale
    attributes = {
        "x": str(frame / 2),
        "y": str(frame / 2),
        "width": str(width - frame),
        "height": str(height - frame),
        "fill": "none",
        "stroke": visual.foreground,
        "stroke-width": str(frame),
    }
    if visual.border_type == "rounded":
        radius = min(2 * frame, 8 * scale)
        attributes.update({"rx": str(radius), "ry": str(radius)})
    SubElement(root, "rect", attributes)
    if visual.border_type != "label":
        return
    divider_y = height - caption_height - frame
    SubElement(
        root,
        "line",
        {
            "x1": str(frame),
            "y1": str(divider_y),
            "x2": str(width - frame),
            "y2": str(divider_y),
            "stroke": visual.foreground,
            "stroke-width": str(frame),
        },
    )
    text = SubElement(
        root,
        "text",
        {
            "x": str(width / 2),
            "y": str(divider_y + caption_height / 2),
            "fill": visual.foreground,
            "font-family": "sans-serif",
            "font-size": str(scale * 2),
            "text-anchor": "middle",
            "dominant-baseline": "middle",
        },
    )
    text.text = visual.border_caption


def render_jpg(
    code: segno.QRCode,
    visual: VisualOptions,
    scale: int = 12,
    module_style: str = "square",
    logo: PreparedLogo | None = None,
) -> bytes:
    """Render an opaque high-quality JPEG QR export.

    Parameters
    ----------
    code : segno.QRCode
        QR code to render.
    scale : int, default=12
        Integer pixels per module.

    Returns
    -------
    bytes
        JPEG image bytes with no chroma subsampling.
    """
    png = render_png(code, visual, scale=scale, module_style=module_style, logo=logo)
    output = BytesIO()
    with Image.open(BytesIO(png)) as image:
        image.convert("RGB").save(
            output, format="JPEG", quality=95, subsampling=0, dpi=(300, 300)
        )
    return output.getvalue()


def render_pdf(
    code: segno.QRCode,
    visual: VisualOptions,
    module_style: str = "square",
    logo: PreparedLogo | None = None,
    options: PdfOptions | None = None,
) -> bytes:
    """Render a single-page vector PDF with validated physical geometry.

    Parameters
    ----------
    code : segno.QRCode
        QR code to render.

    Returns
    -------
    bytes
        A4 PDF bytes.
    """
    if options is None:
        options = PdfOptions("a4", "portrait", 12, 100, "")
    page_size = A4 if options.page_size == "a4" else letter
    if options.orientation == "landscape":
        page_size = landscape(page_size)
    matrix = [list(row) for row in code.matrix_iter(border=4, verbose=True)]
    module_count = len(matrix)
    symbol_size = options.symbol_size_mm * mm
    module_size = symbol_size / module_count
    if module_size < mm:
        raise RequestValidationError(
            [
                ValidationIssue(
                    "pdf.symbol_size_mm",
                    "module_size",
                    "PDF output requires at least one millimeter per module.",
                )
            ]
        )
    has_border = visual.border_type != "quiet"
    gap = 2 * module_size if has_border else 0
    frame = visual.border_width * module_size if has_border else 0
    offset = gap + frame
    border_caption_height = 4 * module_size if visual.border_type == "label" else 0
    visual_width = symbol_size + 2 * offset
    visual_height = symbol_size + 2 * offset + border_caption_height
    page_caption_height = 12 + 4 * mm if options.caption else 0
    margin = options.margin_mm * mm
    usable_width = page_size[0] - 2 * margin
    usable_height = page_size[1] - 2 * margin
    if (
        options.caption
        and pdfmetrics.stringWidth(options.caption, "Helvetica", 12) > usable_width
    ):
        raise RequestValidationError(
            [
                ValidationIssue(
                    "pdf.caption",
                    "fit",
                    "The PDF caption does not fit within the selected margins.",
                )
            ]
        )
    if (
        visual.border_type == "label"
        and pdfmetrics.stringWidth(visual.border_caption, "Helvetica", 9)
        > visual_width - 2 * frame
    ):
        raise RequestValidationError(
            [
                ValidationIssue(
                    "visual.border_caption",
                    "fit",
                    "The border caption does not fit the selected PDF size.",
                )
            ]
        )
    if (
        visual_width > usable_width
        or visual_height + page_caption_height > usable_height
    ):
        raise RequestValidationError(
            [
                ValidationIssue(
                    "pdf.symbol_size_mm",
                    "fit",
                    "The selected QR size, frame, and captions do not fit the page.",
                )
            ]
        )
    output = BytesIO()
    page = canvas.Canvas(output, pagesize=page_size)
    group_height = visual_height + page_caption_height
    x = (page_size[0] - visual_width) / 2
    group_y = (page_size[1] - group_height) / 2
    visual_y = group_y + page_caption_height
    _draw_pdf_background_and_frame(
        page,
        visual,
        x,
        visual_y,
        visual_width,
        visual_height,
        frame,
        border_caption_height,
        module_size,
    )
    qr_x = x + offset
    qr_y = visual_y + offset + border_caption_height
    page.setFillColor(HexColor(visual.foreground))
    for row_index, row in enumerate(matrix):
        for column_index, module_type in enumerate(row):
            if not module_type >> 8:
                continue
            module_x = qr_x + column_index * module_size
            module_y = qr_y + symbol_size - (row_index + 1) * module_size
            if module_style == "dot" and module_type == consts.TYPE_DATA_DARK:
                page.circle(
                    module_x + module_size / 2,
                    module_y + module_size / 2,
                    module_size / 2,
                    stroke=0,
                    fill=1,
                )
            else:
                page.rect(
                    module_x, module_y, module_size, module_size, stroke=0, fill=1
                )
    if logo is not None:
        _draw_pdf_logo(page, code, logo, qr_x, qr_y, module_size)
    if options.caption:
        page.setFillColor(HexColor(visual.foreground))
        page.setFont("Helvetica", 12)
        page.drawCentredString(page_size[0] / 2, group_y, options.caption)
    page.showPage()
    page.save()
    return output.getvalue()


def _draw_pdf_background_and_frame(
    page: canvas.Canvas,
    visual: VisualOptions,
    x: float,
    y: float,
    width: float,
    height: float,
    frame: float,
    caption_height: float,
    module_size: float,
) -> None:
    """Draw opaque PDF background, frame, and optional border caption."""
    page.setFillColor(HexColor(visual.background))
    page.rect(x, y, width, height, stroke=0, fill=1)
    if visual.border_type in {"quiet", "padding"}:
        return
    page.setStrokeColor(HexColor(visual.foreground))
    page.setLineWidth(frame)
    inset = frame / 2
    if visual.border_type == "rounded":
        radius = min(2 * frame, 8 * module_size)
        page.roundRect(
            x + inset,
            y + inset,
            width - frame,
            height - frame,
            radius,
            stroke=1,
            fill=0,
        )
    else:
        page.rect(
            x + inset,
            y + inset,
            width - frame,
            height - frame,
            stroke=1,
            fill=0,
        )
    if visual.border_type != "label":
        return
    divider_y = y + frame + caption_height
    page.line(x + frame, divider_y, x + width - frame, divider_y)
    page.setFillColor(HexColor(visual.foreground))
    page.setFont("Helvetica", 9)
    page.drawCentredString(
        x + width / 2,
        y + frame + caption_height / 2,
        visual.border_caption,
    )


def _draw_pdf_logo(
    page: canvas.Canvas,
    code: segno.QRCode,
    logo: PreparedLogo,
    qr_x: float,
    qr_y: float,
    module_size: float,
) -> None:
    """Draw an opaque logo backing and sanitized logo in vector PDF layout."""
    placement = logo_placement(code)
    symbol_x = qr_x + 4 * module_size
    symbol_y = qr_y + 4 * module_size
    backing_x = symbol_x + placement.backing_start * module_size
    backing_y = symbol_y + placement.backing_start * module_size
    backing_size = placement.backing_modules * module_size
    page.setFillColor(HexColor("#FFFFFF"))
    page.rect(backing_x, backing_y, backing_size, backing_size, stroke=0, fill=1)
    box_size = placement.logo_modules * module_size
    aspect = logo.width / logo.height
    if aspect >= 1:
        image_width, image_height = box_size, box_size / aspect
    else:
        image_width, image_height = box_size * aspect, box_size
    image_x = backing_x + (backing_size - image_width) / 2
    image_y = backing_y + (backing_size - image_height) / 2
    page.drawImage(
        ImageReader(BytesIO(logo.png)),
        image_x,
        image_y,
        width=image_width,
        height=image_height,
        mask="auto",
    )
