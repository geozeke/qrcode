"""Logo validation, token binding, placement, and export tests."""

from __future__ import annotations

import base64
import json
from io import BytesIO
from xml.etree import ElementTree

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from qrcode_web.app import create_app


def _logo(color: str = "#D7195B", image_format: str = "PNG") -> bytes:
    """Create a small in-memory logo fixture."""
    output = BytesIO()
    image = Image.new("RGBA", (64, 32), color)
    if image_format == "JPEG":
        image.convert("RGB").save(output, format="JPEG", quality=90)
    else:
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("private", "must be stripped")
        image.save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


def _state(output_format: str = "png") -> str:
    """Return valid square/H render state for a logo request."""
    return json.dumps(
        {
            "payload_type": "url",
            "payload": {"url": "example.com"},
            "error_correction": "H",
            "module_style": "square",
            "output_format": output_format,
        }
    )


def _files(request: str, logo: bytes, token: str | None = None) -> dict[str, object]:
    """Build multipart fields for a logo request."""
    fields: dict[str, object] = {
        "request": (None, request),
        "logo": ("ignored-name.png", logo, "application/octet-stream"),
    }
    if token is not None:
        fields["render_token"] = (None, token)
    return fields


def test_logo_preview_and_matching_download(monkeypatch: object) -> None:
    """A sanitized logo can be previewed and downloaded with the same bytes."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    request = _state()
    logo = _logo()
    with TestClient(create_app()) as client:
        preview = client.post("/api/preview", files=_files(request, logo))
        assert preview.status_code == 200
        token = preview.headers["x-render-token"]
        download = client.post("/api/download", files=_files(request, logo, token))
    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"
    with Image.open(BytesIO(download.content)) as image:
        assert image.convert("RGB").getpixel((169, 169)) == (255, 255, 255)


def test_jpeg_logo_is_detected_from_image_data(monkeypatch: object) -> None:
    """JPEG logo data is accepted regardless of multipart MIME declaration."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/preview", files=_files(_state(), _logo(image_format="JPEG"))
        )
    assert response.status_code == 200


def test_logo_bytes_are_bound_to_render_token(monkeypatch: object) -> None:
    """Changing logo bytes after preview invalidates the render token."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    request = _state()
    with TestClient(create_app()) as client:
        preview = client.post("/api/preview", files=_files(request, _logo()))
        response = client.post(
            "/api/download",
            files=_files(request, _logo("#146B3A"), preview.headers["x-render-token"]),
        )
    assert response.status_code == 409


def test_logo_requires_square_modules_and_h_correction(monkeypatch: object) -> None:
    """Logo requests reject dot modules and correction levels below H."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    states = (
        {
            "payload_type": "url",
            "payload": {"url": "example.com"},
            "error_correction": "Q",
        },
        {
            "payload_type": "url",
            "payload": {"url": "example.com"},
            "error_correction": "H",
            "module_style": "dot",
        },
    )
    with TestClient(create_app()) as client:
        for state in states:
            response = client.post(
                "/api/preview", files=_files(json.dumps(state), _logo())
            )
            assert response.status_code == 415


def test_logo_rejects_bad_format_size_and_unsafe_center(monkeypatch: object) -> None:
    """Invalid, oversized, and function-overlapping logos are rejected safely."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    unsafe_state = json.dumps(
        {
            "payload_type": "text",
            "payload": {"text": "x"},
            "error_correction": "H",
        }
    )
    with TestClient(create_app()) as client:
        invalid = client.post("/api/preview", files=_files(_state(), b"not an image"))
        oversized = client.post(
            "/api/preview", files=_files(_state(), b"x" * (5 * 1024 * 1024 + 1))
        )
        unsafe = client.post("/api/preview", files=_files(unsafe_state, _logo()))
    assert invalid.status_code == 415
    assert oversized.status_code == 413
    assert unsafe.status_code == 415


def test_svg_embeds_sanitized_logo_without_source_metadata(monkeypatch: object) -> None:
    """SVG embeds a clean PNG data URI and opaque white backing."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)  # type: ignore[attr-defined]
    request = _state("svg")
    logo = _logo()
    with TestClient(create_app()) as client:
        preview = client.post("/api/preview", files=_files(request, logo))
        response = client.post(
            "/api/download",
            files=_files(request, logo, preview.headers["x-render-token"]),
        )
    root = ElementTree.fromstring(response.content)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    embedded = root.find("svg:image", namespace)
    assert embedded is not None
    encoded = embedded.get("href", "").partition(",")[2]
    with Image.open(BytesIO(base64.b64decode(encoded))) as clean:
        assert clean.format == "PNG"
        assert "private" not in clean.info
    assert any(
        rectangle.get("fill") == "#FFFFFF"
        for rectangle in root.findall("svg:rect", namespace)
    )
