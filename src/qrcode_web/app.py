"""FastAPI application factory and static-site hosting."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError as FastAPIValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint

from qrcode_web.errors import RequestValidationError, ValidationIssue
from qrcode_web.exports import ExportOptions, parse_export_options
from qrcode_web.logos import (
    MAX_LOGO_BYTES,
    LogoTooLargeError,
    LogoValidationError,
    PreparedLogo,
    prepare_logo,
)
from qrcode_web.payloads import normalize_payload
from qrcode_web.render_jobs import (
    RenderBusyError,
    RenderJobs,
    RenderTimeoutError,
    render_download_job,
    render_preview_job,
)
from qrcode_web.tokens import issue_token, request_fingerprint, verify_token
from qrcode_web.visuals import VisualOptions, parse_visual_options

MAX_REQUEST_BYTES = 5 * 1024 * 1024
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; "
        "style-src 'self'; script-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    ),
}
_request_logger = logging.getLogger("qrcode_web.requests")


def _require_render_secret() -> None:
    """Validate the render-token secret required for application startup.

    Raises
    ------
    RuntimeError
        If the configured secret is absent or too short.
    """
    secret = os.environ.get("QR_RENDER_TOKEN_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        message = "QR_RENDER_TOKEN_SECRET must contain at least 32 bytes."
        raise RuntimeError(message)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate process configuration before accepting requests.

    Parameters
    ----------
    _ : FastAPI
        Application instance supplied by FastAPI.

    Yields
    ------
    None
        Control to the running application.
    """
    _require_render_secret()
    yield


def create_app() -> FastAPI:
    """Create the QR Code Generator ASGI application.

    Returns
    -------
    FastAPI
        Configured application with health and static-site routes.
    """
    app = FastAPI(
        title="QR Code Generator", docs_url=None, redoc_url=None, lifespan=_lifespan
    )
    app.state.render_jobs = RenderJobs(active=2, queued=4)

    def error_response(status: int, code: str) -> JSONResponse:
        """Create a sanitized, stable operational-error response."""
        return JSONResponse(
            {"error": code},
            status_code=status,
            headers={"Cache-Control": "no-store", "X-Error-Code": code},
        )

    @app.exception_handler(FastAPIValidationError)
    async def malformed_request(_: Request, __: FastAPIValidationError) -> JSONResponse:
        """Hide multipart parser and framework validation details."""
        return error_response(400, "malformed_request")

    @app.middleware("http")
    async def request_controls(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Bound API bodies and add privacy-safe operational logging."""
        started = time.perf_counter()
        request_id = uuid.uuid4().hex
        path = request.url.path
        route = path if path in {"/health", "/api/preview", "/api/download"} else "spa"
        response: Response
        error_code = "none"
        try:
            if path in {"/api/preview", "/api/download"}:
                raw_length = request.headers.get("content-length")
                try:
                    if raw_length is not None and int(raw_length) > MAX_REQUEST_BYTES:
                        response = error_response(413, "request_too_large")
                    else:
                        body = bytearray()
                        async for chunk in request.stream():
                            body.extend(chunk)
                            if len(body) > MAX_REQUEST_BYTES:
                                break
                        if len(body) > MAX_REQUEST_BYTES:
                            response = error_response(413, "request_too_large")
                        else:
                            request._body = bytes(body)  # noqa: SLF001
                            response = await call_next(request)
                except (TypeError, ValueError):
                    response = error_response(400, "malformed_request")
            else:
                response = await call_next(request)
        except Exception:
            response = error_response(500, "internal_error")
        for name, value in _SECURITY_HEADERS.items():
            response.headers[name] = value
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif route == "spa" and response.status_code == 200:
            response.headers["Cache-Control"] = "no-cache"
        if response.status_code >= 400:
            response.headers["X-Request-ID"] = request_id
            error_code = response.headers.get(
                "X-Error-Code", f"http_{response.status_code}"
            )
        duration_ms = (time.perf_counter() - started) * 1000
        response_size = response.headers.get("content-length", "unknown")
        _request_logger.info(
            "timestamp=%s request_id=%s route=%s status=%d "
            "duration_ms=%.3f response_size=%s error_code=%s",
            datetime.now(UTC).isoformat(),
            request_id,
            route,
            response.status_code,
            duration_ms,
            response_size,
            error_code,
        )
        return response

    @app.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        """Return a minimal Docker health-check response.

        Returns
        -------
        JSONResponse
            Stateless service-health confirmation.
        """
        return JSONResponse({"status": "ok"}, headers={"Cache-Control": "no-store"})

    def validation_response(error: RequestValidationError) -> JSONResponse:
        """Translate internal validation errors into the API error shape.

        Parameters
        ----------
        error : RequestValidationError
            Structured validation failure.

        Returns
        -------
        JSONResponse
            Sanitized validation error response.
        """
        if any(issue.code == "size" for issue in error.issues):
            return error_response(413, "request_too_large")
        issues = [
            {"path": issue.path, "code": issue.code, "message": issue.message}
            for issue in error.issues
        ]
        return JSONResponse({"error": "validation", "issues": issues}, status_code=422)

    def logo_error_response(error: LogoValidationError) -> JSONResponse:
        """Return a sanitized unsupported-logo response."""
        issue = {
            "path": "logo",
            "code": "logo",
            "message": str(error),
        }
        return JSONResponse({"error": "validation", "issues": [issue]}, status_code=415)

    async def read_logo(upload: UploadFile | None) -> PreparedLogo | None:
        """Read and sanitize one bounded multipart logo upload."""
        if upload is None:
            return None
        data = await upload.read(MAX_LOGO_BYTES + 1)
        return prepare_logo(data)

    def validate_logo_options(
        logo: PreparedLogo | None, normalized: dict[str, object]
    ) -> None:
        """Enforce logo-specific QR correction and style constraints."""
        if logo is None:
            return
        if normalized["module_style"] != "square":
            raise LogoValidationError("Logos require square QR modules.")
        if normalized["error_correction"] != "H":
            raise LogoValidationError("Logos require H error correction.")

    def parse_render_request(
        raw_request: str,
    ) -> tuple[dict[str, object], str, ExportOptions, VisualOptions]:
        """Parse and normalize the multipart render-state JSON field.

        Parameters
        ----------
        raw_request : str
            Raw JSON supplied by the browser.

        Returns
        -------
        tuple[dict[str, object], str, ExportOptions, VisualOptions]
            Token state, content, export settings, and visual settings.

        Raises
        ------
        RequestValidationError
            If request JSON or fields are invalid.
        """
        if len(raw_request.encode("utf-8")) > 16 * 1024:
            raise RequestValidationError(
                [ValidationIssue("request", "size", "Request settings are too large.")]
            )
        try:
            request = json.loads(raw_request)
        except json.JSONDecodeError as error:
            raise RequestValidationError(
                [
                    ValidationIssue(
                        "request", "json", "Request settings must be valid JSON."
                    )
                ]
            ) from error
        if not isinstance(request, dict):
            raise RequestValidationError(
                [
                    ValidationIssue(
                        "request", "type", "Request settings must be an object."
                    )
                ]
            )
        payload_type = request.get("payload_type")
        payload = request.get("payload")
        error_correction = request.get("error_correction", "M")
        module_style = request.get("module_style", "square")
        if not isinstance(payload_type, str) or not isinstance(payload, dict):
            raise RequestValidationError(
                [ValidationIssue("payload", "required", "Enter QR code content.")]
            )
        if error_correction not in {"L", "M", "Q", "H"}:
            raise RequestValidationError(
                [
                    ValidationIssue(
                        "error_correction", "choice", "Choose a valid correction level."
                    )
                ]
            )
        if module_style not in {"square", "dot"}:
            raise RequestValidationError(
                [
                    ValidationIssue(
                        "module_style", "choice", "Choose a supported module style."
                    )
                ]
            )
        if module_style == "dot" and error_correction not in {"Q", "H"}:
            raise RequestValidationError(
                [
                    ValidationIssue(
                        "error_correction",
                        "dot_style",
                        "Dot modules require Q or H error correction.",
                    )
                ]
            )
        content = normalize_payload(payload_type, payload)
        export = parse_export_options(request)
        visual = parse_visual_options(request.get("visual"), export.output_format)
        normalized = {
            "payload_type": payload_type,
            "content": content,
            "error_correction": error_correction,
            "module_style": module_style,
            "export": {
                "output_format": export.output_format,
                "digital_scale": export.digital_scale_name,
                "pdf": {
                    "page_size": export.pdf.page_size,
                    "orientation": export.pdf.orientation,
                    "margin_mm": export.pdf.margin_mm,
                    "symbol_size_mm": export.pdf.symbol_size_mm,
                    "caption": export.pdf.caption,
                },
            },
            "visual": {
                "foreground": visual.foreground,
                "background": visual.background,
                "transparent": visual.transparent,
                "border_type": visual.border_type,
                "border_width": visual.border_width,
                "border_caption": visual.border_caption,
            },
        }
        return normalized, content, export, visual

    @app.post("/api/preview", include_in_schema=False)
    async def preview(
        request: Annotated[str, Form()],
        logo: Annotated[UploadFile | None, File()] = None,
    ) -> Response:
        """Validate state and return a non-cacheable PNG preview.

        Parameters
        ----------
        request : str
            JSON render state in a multipart form field.

        Returns
        -------
        Response
            PNG preview with a short-lived render token header.
        """
        try:
            normalized, content, export, visual = parse_render_request(request)
            prepared_logo = await read_logo(logo)
            validate_logo_options(prepared_logo, normalized)
            normalized["logo_sha256"] = (
                prepared_logo.sha256 if prepared_logo is not None else None
            )
            image = await app.state.render_jobs.run(
                render_preview_job,
                content,
                str(normalized["error_correction"]),
                str(normalized["module_style"]),
                export,
                visual,
                prepared_logo,
                timeout=5,
            )
        except RequestValidationError as error:
            return validation_response(error)
        except LogoTooLargeError:
            return error_response(413, "request_too_large")
        except LogoValidationError as error:
            return logo_error_response(error)
        except RenderBusyError:
            return error_response(503, "render_busy")
        except RenderTimeoutError:
            return error_response(504, "render_timeout")
        fingerprint = request_fingerprint(normalized)
        return Response(
            image,
            media_type="image/png",
            headers={
                "Cache-Control": "no-store",
                "X-Render-Token": issue_token(fingerprint),
            },
        )

    @app.post("/api/download", include_in_schema=False)
    async def download(
        request: Annotated[str, Form()],
        render_token: Annotated[str, Form()],
        logo: Annotated[UploadFile | None, File()] = None,
    ) -> Response:
        """Return an export only for the state shown in a current preview.

        Parameters
        ----------
        request : str
            JSON render state in a multipart form field.
        render_token : str
            Short-lived preview token.

        Returns
        -------
        Response
            Generated download response.
        """
        try:
            normalized, content, export, visual = parse_render_request(request)
            prepared_logo = await read_logo(logo)
            validate_logo_options(prepared_logo, normalized)
            normalized["logo_sha256"] = (
                prepared_logo.sha256 if prepared_logo is not None else None
            )
        except RequestValidationError as error:
            return validation_response(error)
        except LogoTooLargeError:
            return error_response(413, "request_too_large")
        except LogoValidationError as error:
            return logo_error_response(error)
        if not verify_token(render_token, request_fingerprint(normalized)):
            raise HTTPException(
                status_code=409, detail="Preview state does not match this download."
            )
        try:
            data, media_type = await app.state.render_jobs.run(
                render_download_job,
                content,
                str(normalized["error_correction"]),
                str(normalized["module_style"]),
                export,
                visual,
                prepared_logo,
                timeout=15,
            )
        except RequestValidationError as error:
            return validation_response(error)
        except LogoValidationError as error:
            return logo_error_response(error)
        except RenderBusyError:
            return error_response(503, "render_busy")
        except RenderTimeoutError:
            return error_response(504, "render_timeout")
        filename = f"qrcode-{normalized['payload_type']}.{export.output_format}"
        return Response(
            data,
            media_type=media_type,
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    configured_web_root = os.environ.get("QR_WEB_ROOT")
    web_root = (
        Path(configured_web_root)
        if configured_web_root
        else Path(__file__).resolve().parents[2] / "web"
    )
    if web_root.is_dir():
        assets_path = web_root / "assets"
        if assets_path.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str) -> FileResponse:
            """Serve the static SPA entry point for non-API GET routes.

            Parameters
            ----------
            path : str
                Requested browser path.

            Returns
            -------
            FileResponse
                The SPA entry document or a static file below the web root.
            """
            candidate = (web_root / path).resolve()
            if path and candidate.is_file() and web_root in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(
                web_root / "index.html",
                headers={"Cache-Control": "no-cache"},
            )

    return app
