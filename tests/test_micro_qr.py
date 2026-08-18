"""Micro QR encoding, export, and API compatibility tests."""

from __future__ import annotations

import json
from io import BytesIO
from xml.etree import ElementTree

import pytest
import zxingcpp
from fastapi.testclient import TestClient
from PIL import Image

from qrcode_web.app import create_app
from qrcode_web.errors import RequestValidationError
from qrcode_web.rendering import make_code, render_jpg, render_png, render_svg
from qrcode_web.visuals import VisualOptions


def _visual() -> VisualOptions:
    """Return scanner-safe default visual settings."""
    return VisualOptions("#000000", "#FFFFFF", False, "quiet", 0, "")


def _state(**changes: object) -> dict[str, object]:
    """Return a valid Micro QR render state with optional changes."""
    state: dict[str, object] = {
        "symbol_type": "micro",
        "payload_type": "text",
        "payload": {"text": "HELLO"},
        "error_correction": "auto",
        "module_style": "square",
    }
    state.update(changes)
    return state


def test_micro_auto_uses_m1_and_boosts_without_growing() -> None:
    """Automatic correction permits M1 and boosts larger Micro symbols."""
    m1 = make_code("1", "micro", "auto")
    boosted = make_code("HELLO", "micro", "auto")
    explicit = make_code("HELLO", "micro", "L")

    assert (m1.version, m1.error, m1.designator) == ("M1", None, "M1")
    assert (boosted.version, boosted.error) == ("M2", "M")
    assert (explicit.version, explicit.error) == ("M2", "L")


def test_micro_capacity_failure_is_structured() -> None:
    """Content beyond M4 capacity becomes a correctable validation error."""
    with pytest.raises(RequestValidationError) as caught:
        make_code("x" * 16, "micro", "L")

    issue = caught.value.issues[0]
    assert (issue.path, issue.code) == ("payload", "capacity")
    assert "Micro QR Code" in issue.message


def test_micro_raster_and_svg_use_two_module_quiet_zone() -> None:
    """Micro exports use exact two-module quiet-zone geometry and decode."""
    code = make_code("1", "micro", "auto")
    modules = len(list(code.matrix_iter(border=2)))

    png = render_png(code, _visual(), scale=12)
    with Image.open(BytesIO(png)) as image:
        assert image.size == (modules * 12, modules * 12)
        result = zxingcpp.read_barcode(image)
        assert result is not None
        assert result.text == "1"

    jpg = render_jpg(code, _visual(), scale=12)
    with Image.open(BytesIO(jpg)) as image:
        result = zxingcpp.read_barcode(image)
        assert result is not None
        assert result.text == "1"

    root = ElementTree.fromstring(render_svg(code, _visual(), scale=12))
    assert root.get("viewBox") == f"0 0 {modules} {modules}"


@pytest.mark.parametrize(
    ("changes", "path"),
    [
        ({"error_correction": "H"}, "error_correction"),
        ({"module_style": "dot", "error_correction": "Q"}, "module_style"),
        (
            {
                "payload_type": "wifi",
                "payload": {
                    "security": "open",
                    "ssid": "a",
                    "password": "",
                    "hidden": False,
                },
            },
            "payload_type",
        ),
    ],
)
def test_micro_rejects_unsupported_combinations(
    monkeypatch: object, changes: dict[str, object], path: str
) -> None:
    """Micro requests reject correction, styling, and payload conflicts."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/preview",
            files={"request": (None, json.dumps(_state(**changes)))},
        )

    assert response.status_code == 422
    assert response.json()["issues"][0]["path"] == path


def test_micro_download_name_and_symbol_type_token_binding(
    monkeypatch: object,
) -> None:
    """Micro downloads are named distinctly and tokens bind the symbol family."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    micro_request = json.dumps(_state())
    standard_request = json.dumps(
        {
            "symbol_type": "qr",
            "payload_type": "text",
            "payload": {"text": "HELLO"},
            "error_correction": "M",
            "module_style": "square",
        }
    )
    with TestClient(create_app()) as client:
        preview = client.post("/api/preview", files={"request": (None, micro_request)})
        token = preview.headers["x-render-token"]
        download = client.post(
            "/api/download",
            files={
                "request": (None, micro_request),
                "render_token": (None, token),
            },
        )
        changed = client.post(
            "/api/download",
            files={
                "request": (None, standard_request),
                "render_token": (None, token),
            },
        )

    assert preview.status_code == 200
    assert download.status_code == 200
    assert "micro-qrcode-text.png" in download.headers["content-disposition"]
    assert changed.status_code == 409


@pytest.mark.parametrize(
    ("output_format", "media_type"),
    [
        ("png", "image/png"),
        ("jpg", "image/jpeg"),
        ("svg", "image/svg+xml"),
        ("pdf", "application/pdf"),
    ],
)
def test_micro_downloads_in_every_export_format(
    monkeypatch: object, output_format: str, media_type: str
) -> None:
    """Every supported export path preserves a valid Micro QR request."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    request = json.dumps(_state(output_format=output_format))
    with TestClient(create_app()) as client:
        preview = client.post("/api/preview", files={"request": (None, request)})
        download = client.post(
            "/api/download",
            files={
                "request": (None, request),
                "render_token": (None, preview.headers["x-render-token"]),
            },
        )

    assert preview.status_code == 200
    assert download.status_code == 200
    assert download.headers["content-type"] == media_type
