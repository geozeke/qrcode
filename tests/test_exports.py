"""Geometry, format, physical-layout, and decode tests for exports."""

from __future__ import annotations

import json
from io import BytesIO
from xml.etree import ElementTree

import pytest
import segno
import zxingcpp
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from qrcode_web.app import create_app
from qrcode_web.errors import RequestValidationError
from qrcode_web.exports import PdfOptions
from qrcode_web.rendering import render_jpg, render_pdf, render_png, render_svg
from qrcode_web.visuals import VisualOptions


def _visual(transparent: bool = False) -> VisualOptions:
    """Return safe quiet-zone-only visual settings."""
    return VisualOptions("#000000", "#FFFFFF", transparent, "quiet", 0, "")


def _code(version: int) -> segno.QRCode:
    """Create a deterministic QR code at an exact standard version."""
    return segno.make(
        "export",
        version=version,
        error="M",
        micro=False,
        boost_error=False,
    )


def test_png_scale_presets_dimensions_dpi_and_decode() -> None:
    """Raster scale presets use exact integer modules and decode at v1/v20."""
    for version in (1, 20):
        code = _code(version)
        modules = len(list(code.matrix_iter(border=4)))
        for scale in (8, 12, 24):
            data = render_png(code, _visual(), scale=scale)
            with Image.open(BytesIO(data)) as image:
                assert image.size == (modules * scale, modules * scale)
                assert image.mode == "RGB"
                assert image.info["dpi"][0] == pytest.approx(300, abs=1)
                result = zxingcpp.read_barcode(image)
                assert result is not None
                assert result.text == "export"


def test_jpg_is_opaque_rgb_and_decodes() -> None:
    """JPEG output is opaque RGB, carries 300-DPI metadata, and decodes."""
    data = render_jpg(_code(1), _visual(), scale=8)
    with Image.open(BytesIO(data)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.info["dpi"][0] == 300
        assert all(component[1:3] == (1, 1) for component in image.layer)
        result = zxingcpp.read_barcode(image)
        assert result is not None
        assert result.text == "export"


def test_transparent_png_and_module_based_svg_geometry() -> None:
    """Transparent PNG uses alpha and SVG uses a module-coordinate viewBox."""
    code = _code(1)
    modules = len(list(code.matrix_iter(border=4)))
    png = render_png(code, _visual(transparent=True), scale=8)
    with Image.open(BytesIO(png)) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
    svg = render_svg(code, _visual(), scale=24)
    root = ElementTree.fromstring(svg)
    assert root.get("viewBox") == f"0 0 {modules} {modules}"
    assert root.get("width") == str(modules * 24)
    assert root.get("height") == str(modules * 24)


def test_pdf_is_vector_and_respects_page_layout_and_caption() -> None:
    """PDF output uses vector QR operators and configured page geometry."""
    options = PdfOptions("letter", "landscape", 20, 100, "Export caption")
    data = render_pdf(_code(1), _visual(), options=options)
    reader = PdfReader(BytesIO(data))
    page = reader.pages[0]
    assert float(page.mediabox.width) == pytest.approx(792, abs=1)
    assert float(page.mediabox.height) == pytest.approx(612, abs=1)
    assert "Export caption" in page.extract_text()
    assert not list(page.images)
    content = page.get_contents().get_data()
    assert b" re" in content
    assert b" Do" not in content


def test_pdf_rejects_submillimeter_modules_and_nonfitting_layout() -> None:
    """Physical PDF output rejects unsafe module size and page overflow."""
    with pytest.raises(RequestValidationError, match="Request validation failed"):
        render_pdf(
            _code(20),
            _visual(),
            options=PdfOptions("a4", "portrait", 12, 100, ""),
        )
    framed = VisualOptions("#000000", "#FFFFFF", False, "solid", 4, "")
    with pytest.raises(RequestValidationError, match="Request validation failed"):
        render_pdf(
            _code(1),
            framed,
            options=PdfOptions("a4", "portrait", 12, 150, ""),
        )


def test_export_settings_are_bound_to_preview_token(monkeypatch: object) -> None:
    """Changing output scale after preview invalidates the download token."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    state = {
        "payload_type": "url",
        "payload": {"url": "example.com"},
        "digital_scale": "compact",
    }
    with TestClient(create_app()) as client:
        preview_request = json.dumps(state)
        preview = client.post(
            "/api/preview", files={"request": (None, preview_request)}
        )
        state["digital_scale"] = "large"
        response = client.post(
            "/api/download",
            files={
                "request": (None, json.dumps(state)),
                "render_token": (None, preview.headers["x-render-token"]),
            },
        )
    assert response.status_code == 409


def test_preview_rejects_unsafe_pdf_physical_size(monkeypatch: object) -> None:
    """Preview does not issue a token for submillimeter PDF modules."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    state = {
        "payload_type": "text",
        "payload": {"text": "x" * 700},
        "error_correction": "L",
        "output_format": "pdf",
        "pdf": {"symbol_size_mm": 50},
    }
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/preview", files={"request": (None, json.dumps(state))}
        )
    assert response.status_code == 422
    assert response.json()["issues"][0]["path"] == "pdf.symbol_size_mm"


def test_opaque_formats_reject_transparency(monkeypatch: object) -> None:
    """JPG and PDF requests cannot enable transparent QR backgrounds."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    with TestClient(create_app()) as client:
        for output_format in ("jpg", "pdf"):
            state = {
                "payload_type": "url",
                "payload": {"url": "example.com"},
                "output_format": output_format,
                "visual": {"transparent": True},
            }
            response = client.post(
                "/api/preview", files={"request": (None, json.dumps(state))}
            )
            assert response.status_code == 422
            assert response.json()["issues"][0]["path"] == "visual.transparent"
