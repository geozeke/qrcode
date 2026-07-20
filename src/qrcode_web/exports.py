"""Validation and normalization for download-format settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qrcode_web.errors import RequestValidationError, ValidationIssue

DIGITAL_SCALES = {"compact": 8, "standard": 12, "large": 24}


@dataclass(frozen=True, slots=True)
class PdfOptions:
    """Validated single-page PDF layout settings."""

    page_size: str
    orientation: str
    margin_mm: int
    symbol_size_mm: int
    caption: str


@dataclass(frozen=True, slots=True)
class ExportOptions:
    """Validated output settings for one render request."""

    output_format: str
    digital_scale: int
    digital_scale_name: str
    pdf: PdfOptions


def _issue(path: str, code: str, message: str) -> RequestValidationError:
    """Create one structured export validation failure."""
    return RequestValidationError([ValidationIssue(path, code, message)])


def parse_export_options(request: dict[str, Any]) -> ExportOptions:
    """Validate output format, digital scale, and PDF layout settings."""
    output_format = request.get("output_format", "png")
    scale_name = request.get("digital_scale", "standard")
    if not isinstance(output_format, str) or output_format not in {
        "png",
        "jpg",
        "svg",
        "pdf",
    }:
        raise _issue("output_format", "choice", "Choose a supported file format.")
    if not isinstance(scale_name, str) or scale_name not in DIGITAL_SCALES:
        raise _issue("digital_scale", "choice", "Choose Compact, Standard, or Large.")
    raw_pdf = request.get("pdf", {})
    if not isinstance(raw_pdf, dict):
        raise _issue("pdf", "type", "PDF settings must be an object.")
    page_size = raw_pdf.get("page_size", "a4")
    orientation = raw_pdf.get("orientation", "portrait")
    margin_mm = raw_pdf.get("margin_mm", 12)
    symbol_size_mm = raw_pdf.get("symbol_size_mm", 100)
    caption = raw_pdf.get("caption", "")
    if not isinstance(page_size, str) or page_size not in {"a4", "letter"}:
        raise _issue("pdf.page_size", "choice", "Choose A4 or US Letter.")
    if not isinstance(orientation, str) or orientation not in {
        "portrait",
        "landscape",
    }:
        raise _issue("pdf.orientation", "choice", "Choose portrait or landscape.")
    if margin_mm not in {12, 20, 25}:
        raise _issue("pdf.margin_mm", "choice", "Choose a supported PDF margin.")
    if symbol_size_mm not in {50, 75, 100, 125, 150}:
        raise _issue(
            "pdf.symbol_size_mm", "choice", "Choose a supported QR symbol size."
        )
    if not isinstance(caption, str):
        raise _issue("pdf.caption", "type", "Enter a plain-text PDF caption.")
    caption = caption.strip()
    if len(caption) > 120:
        raise _issue(
            "pdf.caption", "length", "PDF captions must be at most 120 characters."
        )
    pdf = PdfOptions(page_size, orientation, margin_mm, symbol_size_mm, caption)
    return ExportOptions(
        output_format,
        DIGITAL_SCALES[str(scale_name)],
        str(scale_name),
        pdf,
    )
