"""Resource-control and privacy integration tests."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import Callable
from typing import Any

import anyio.to_process
import pytest
from fastapi.testclient import TestClient

from qrcode_web.app import MAX_REQUEST_BYTES, create_app
from qrcode_web.render_jobs import (
    RenderBusyError,
    RenderJobs,
    RenderTimeoutError,
)


def _request(payload: str = "https://example.com") -> str:
    """Return a valid serialized render request."""
    return json.dumps(
        {
            "payload_type": "url",
            "payload": {"url": payload},
            "error_correction": "M",
            "output_format": "png",
        }
    )


class _FailingJobs:
    """Render-job test double that raises one configured exception."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def run(
        self,
        _: Callable[..., object],
        *args: Any,
        timeout: float,
    ) -> bytes:
        """Raise the configured failure without inspecting private input."""
        del args, timeout
        raise self.error


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (RenderBusyError(), 503, "render_busy"),
        (RenderTimeoutError(), 504, "render_timeout"),
        (RuntimeError("private diagnostic"), 500, "internal_error"),
    ],
)
def test_render_operational_errors_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status: int,
    code: str,
) -> None:
    """Busy, timeout, and unexpected failures expose only stable codes."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)
    app = create_app()
    app.state.render_jobs = _FailingJobs(error)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/preview", files={"request": (None, _request())})
    assert response.status_code == status
    assert response.json() == {"error": code}
    assert response.headers["cache-control"] == "no-store"
    assert len(response.headers["x-request-id"]) == 32
    assert "private diagnostic" not in response.text


def test_request_and_json_size_limits_return_413(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both total request bodies and the JSON form part are independently bounded."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)
    with TestClient(create_app()) as client:
        total = client.post(
            "/api/preview",
            content=b"x" * (MAX_REQUEST_BYTES + 1),
            headers={"Content-Type": "application/octet-stream"},
        )
        settings = client.post(
            "/api/preview",
            files={"request": (None, "x" * (16 * 1024 + 1))},
        )
    assert total.status_code == 413
    assert total.json() == {"error": "request_too_large"}
    assert settings.status_code == 413
    assert settings.json() == {"error": "request_too_large"}


def test_chunked_oversized_request_is_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Streaming bodies are counted when Content-Length is unavailable."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)

    def chunks() -> Any:
        yield b"x" * (MAX_REQUEST_BYTES // 2)
        yield b"x" * (MAX_REQUEST_BYTES // 2 + 2)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/preview",
            content=chunks(),
            headers={"Content-Type": "application/octet-stream"},
        )
    assert response.status_code == 413
    assert response.json() == {"error": "request_too_large"}


def test_security_headers_cover_success_and_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Security headers are present without trusting proxy-supplied identity."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)
    with TestClient(create_app()) as client:
        responses = [
            client.get("/health"),
            client.post("/api/preview", content=b"bad multipart"),
        ]
    for response in responses:
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert responses[1].headers["cache-control"] == "no-store"


def test_logs_exclude_request_secrets_and_headers(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Operational logs contain metadata but no submitted private material."""
    monkeypatch.setenv("QR_RENDER_TOKEN_SECRET", "a" * 32)
    caplog.set_level(logging.INFO, logger="qrcode_web.requests")
    app = create_app()
    app.state.render_jobs = _FailingJobs(RuntimeError("STACK_SECRET"))
    request = json.dumps(
        {
            "payload_type": "url",
            "payload": {"url": "https://PAYLOAD_SECRET.example"},
            "error_correction": "H",
            "output_format": "png",
        }
    )
    logo = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNg"
        "YAAAAAMAASsJTYQAAAAASUVORK5CYII="
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/preview",
            files={
                "request": (None, request),
                "logo": (
                    "FILENAME_SECRET.png",
                    logo,
                    "image/png",
                ),
            },
            headers={"Authorization": "Bearer HEADER_SECRET"},
        )
    logs = caplog.text
    assert response.status_code == 500
    assert "request_id=" in logs
    assert "route=/api/preview" in logs
    for secret in (
        "PAYLOAD_SECRET",
        "FILENAME_SECRET",
        "LOGO_SECRET",
        "HEADER_SECRET",
        "STACK_SECRET",
    ):
        assert secret not in logs
        assert secret not in response.text


def test_render_gate_rejects_seventh_admitted_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two active plus four queued jobs exhaust admission capacity."""

    async def scenario() -> None:
        release = asyncio.Event()
        ready = asyncio.Event()
        entered = 0
        active = 0
        maximum_active = 0

        async def blocked(*_: object, **kwargs: object) -> bytes:
            nonlocal active, entered, maximum_active
            limiter = kwargs["limiter"]
            async with limiter:  # type: ignore[attr-defined]
                entered += 1
                active += 1
                maximum_active = max(maximum_active, active)
                if entered == 2:
                    ready.set()
                await release.wait()
                active -= 1
                return b"ok"

        monkeypatch.setattr(anyio.to_process, "run_sync", blocked)
        jobs = RenderJobs(active=2, queued=4)
        tasks = [asyncio.create_task(jobs.run(bytes, timeout=1)) for _ in range(6)]
        await ready.wait()
        await asyncio.sleep(0)
        with pytest.raises(RenderBusyError):
            await jobs.run(bytes, timeout=1)
        release.set()
        assert await asyncio.gather(*tasks) == [b"ok"] * 6
        assert maximum_active == 2

    asyncio.run(scenario())


def test_render_timeout_cancels_worker_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A route deadline becomes a stable render-timeout exception."""

    async def scenario() -> None:
        async def stalled(*_: object, **__: object) -> bytes:
            await asyncio.sleep(1)
            return b"late"

        monkeypatch.setattr(anyio.to_process, "run_sync", stalled)
        jobs = RenderJobs()
        with pytest.raises(RenderTimeoutError):
            await jobs.run(bytes, timeout=0.01)

    asyncio.run(scenario())
