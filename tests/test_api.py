"""Integration tests for the internal preview and download API."""

from __future__ import annotations

import json
from io import BytesIO
from xml.etree import ElementTree

from fastapi.testclient import TestClient
from PIL import Image

from qrcode_web.app import create_app


def _request(output_format: str = "png") -> str:
    """Build a valid browser render-state JSON value.

    Parameters
    ----------
    output_format : str, default="png"
        Requested download format.

    Returns
    -------
    str
        Serialized render state.
    """
    return json.dumps(
        {
            "payload_type": "url",
            "payload": {"url": "example.com/docs"},
            "error_correction": "M",
            "output_format": output_format,
        }
    )


def test_preview_and_matching_png_download(monkeypatch: object) -> None:
    """Preview returns a token that permits the matching PNG download.

    Parameters
    ----------
    monkeypatch : object
        Pytest environment patch fixture.
    """
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    with TestClient(create_app()) as client:
        preview = client.post("/api/preview", files={"request": (None, _request())})
        assert preview.status_code == 200
        assert preview.headers["content-type"] == "image/png"
        assert preview.headers["cache-control"] == "no-store"
        token = preview.headers["x-render-token"]

        download = client.post(
            "/api/download",
            files={"request": (None, _request()), "render_token": (None, token)},
        )
        assert download.status_code == 200
        assert download.headers["content-type"] == "image/png"
        assert "qrcode-url.png" in download.headers["content-disposition"]


def test_download_rejects_changed_preview_state(monkeypatch: object) -> None:
    """A preview token cannot authorize a modified request.

    Parameters
    ----------
    monkeypatch : object
        Pytest environment patch fixture.
    """
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    with TestClient(create_app()) as client:
        preview = client.post("/api/preview", files={"request": (None, _request())})
        token = preview.headers["x-render-token"]
        changed = json.dumps(
            {
                "payload_type": "url",
                "payload": {"url": "example.com/changed"},
                "error_correction": "M",
                "output_format": "png",
            }
        )
        download = client.post(
            "/api/download",
            files={"request": (None, changed), "render_token": (None, token)},
        )
        assert download.status_code == 409


def test_preview_reports_structured_validation_error(monkeypatch: object) -> None:
    """Malformed payload input is returned as a safe 422 response.

    Parameters
    ----------
    monkeypatch : object
        Pytest environment patch fixture.
    """
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    invalid = json.dumps(
        {"payload_type": "url", "payload": {"url": "ftp://example.com"}}
    )
    with TestClient(create_app()) as client:
        response = client.post("/api/preview", files={"request": (None, invalid)})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation"
    assert body["issues"][0]["path"] == "payload.url"


def test_dot_modules_require_high_error_correction(monkeypatch: object) -> None:
    """Dot-module requests reject low and medium correction levels."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    request = json.dumps(
        {
            "payload_type": "url",
            "payload": {"url": "example.com"},
            "error_correction": "M",
            "module_style": "dot",
        }
    )
    with TestClient(create_app()) as client:
        response = client.post("/api/preview", files={"request": (None, request)})
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "dot_style"


def test_dot_modules_render_with_quartile_correction(monkeypatch: object) -> None:
    """Dot-module previews render successfully with Q correction."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    request = json.dumps(
        {
            "payload_type": "url",
            "payload": {"url": "example.com"},
            "error_correction": "Q",
            "module_style": "dot",
        }
    )
    with TestClient(create_app()) as client:
        response = client.post("/api/preview", files={"request": (None, request)})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_dot_modules_download_as_jpg_and_pdf(monkeypatch: object) -> None:
    """Dot-module downloads use the selected raster-backed export path."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    with TestClient(create_app()) as client:
        formats = (("jpg", "image/jpeg"), ("pdf", "application/pdf"))
        for output_format, media_type in formats:
            request = json.dumps(
                {
                    "payload_type": "url",
                    "payload": {"url": "example.com"},
                    "error_correction": "Q",
                    "module_style": "dot",
                    "output_format": output_format,
                }
            )
            preview = client.post("/api/preview", files={"request": (None, request)})
            response = client.post(
                "/api/download",
                files={
                    "request": (None, request),
                    "render_token": (None, preview.headers["x-render-token"]),
                },
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith(media_type)


def test_dot_modules_download_as_vector_svg(monkeypatch: object) -> None:
    """Dot-style SVG output contains both circle and rectangle geometry."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    request = json.dumps(
        {
            "payload_type": "url",
            "payload": {"url": "example.com"},
            "error_correction": "Q",
            "module_style": "dot",
            "output_format": "svg",
        }
    )
    with TestClient(create_app()) as client:
        preview = client.post("/api/preview", files={"request": (None, request)})
        response = client.post(
            "/api/download",
            files={
                "request": (None, request),
                "render_token": (None, preview.headers["x-render-token"]),
            },
        )
    assert response.status_code == 200
    assert b"<circle" in response.content
    assert b"<rect" in response.content


def _preview(client: TestClient, state: dict[str, object]) -> object:
    """Submit a preview request for test render state."""
    request = json.dumps(state)
    return client.post("/api/preview", files={"request": (None, request)})


def test_solid_frame_preserves_external_gap(monkeypatch: object) -> None:
    """A two-module frame grows each raster side by frame plus fixed gap."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    base = {
        "payload_type": "url",
        "payload": {"url": "example.com"},
        "error_correction": "M",
    }
    framed = {
        **base,
        "visual": {"border_type": "solid", "border_width": 2},
    }
    with TestClient(create_app()) as client:
        plain_response = _preview(client, base)
        framed_response = _preview(client, framed)
    with Image.open(BytesIO(plain_response.content)) as plain_image:
        plain_size = plain_image.width
    with Image.open(BytesIO(framed_response.content)) as framed_image:
        framed_size = framed_image.width
    assert framed_size - plain_size == 2 * (2 + 2) * 12


def test_transparent_padding_has_clear_outer_pixels(monkeypatch: object) -> None:
    """Transparent padding adds clear space outside the fixed clear gap."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    state = {
        "payload_type": "url",
        "payload": {"url": "example.com"},
        "visual": {
            "transparent": True,
            "border_type": "padding",
            "border_width": 4,
        },
    }
    with TestClient(create_app()) as client:
        response = _preview(client, state)
    assert response.status_code == 200
    with Image.open(BytesIO(response.content)) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0


def test_rounded_and_label_frames_use_safe_svg_geometry(monkeypatch: object) -> None:
    """SVG frames expose rounded geometry and escaped caption text."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    for border_type, caption in (("rounded", ""), ("label", "Scan <safe> & go")):
        state = {
            "payload_type": "url",
            "payload": {"url": "example.com"},
            "output_format": "svg",
            "visual": {
                "border_type": border_type,
                "border_width": 2,
                "border_caption": caption,
            },
        }
        request = json.dumps(state)
        with TestClient(create_app()) as client:
            preview = _preview(client, state)
            response = client.post(
                "/api/download",
                files={
                    "request": (None, request),
                    "render_token": (None, preview.headers["x-render-token"]),
                },
            )
        assert response.status_code == 200
        root = ElementTree.fromstring(response.content)
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        if border_type == "rounded":
            rectangles = root.findall("svg:rect", namespace)
            assert any(element.get("rx") for element in rectangles)
        else:
            text = root.find("svg:text", namespace)
            assert text is not None
            assert text.text == caption


def test_border_validation_rejects_invalid_width(monkeypatch: object) -> None:
    """Only one, two, and four-module external border widths are valid."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    state = {
        "payload_type": "url",
        "payload": {"url": "example.com"},
        "visual": {"border_type": "solid", "border_width": 3},
    }
    with TestClient(create_app()) as client:
        response = _preview(client, state)
    assert response.status_code == 422
    assert response.json()["issues"][0]["path"] == "visual.border_width"


def test_every_border_type_and_width_renders(monkeypatch: object) -> None:
    """Every configured external border type and width renders successfully."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    border_types = ("solid", "rounded", "label", "padding")
    with TestClient(create_app()) as client:
        for border_type in border_types:
            for border_width in (1, 2, 4):
                visual = {
                    "border_type": border_type,
                    "border_width": border_width,
                    "border_caption": "Scan me" if border_type == "label" else "",
                }
                state = {
                    "payload_type": "url",
                    "payload": {"url": "example.com"},
                    "visual": visual,
                }
                response = _preview(client, state)
                assert response.status_code == 200
                assert response.headers["content-type"] == "image/png"
