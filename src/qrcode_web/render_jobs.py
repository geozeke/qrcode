"""Bounded, disposable worker-process execution for QR rendering."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

import anyio
import anyio.to_process

from qrcode_web.exports import ExportOptions
from qrcode_web.logos import PreparedLogo
from qrcode_web.rendering import make_qr, render_jpg, render_pdf, render_png, render_svg
from qrcode_web.visuals import VisualOptions

_T = TypeVar("_T")


class RenderBusyError(RuntimeError):
    """Raised when all active and queued render capacity is occupied."""


class RenderTimeoutError(RuntimeError):
    """Raised when a render exceeds its route-specific deadline."""


def render_preview_job(
    content: str,
    error_correction: str,
    module_style: str,
    export: ExportOptions,
    visual: VisualOptions,
    logo: PreparedLogo | None,
) -> bytes:
    """Render and validate a preview in an isolated worker process."""
    code = make_qr(content, error_correction)
    if export.output_format == "pdf":
        render_pdf(
            code,
            visual,
            module_style=module_style,
            logo=logo,
            options=export.pdf,
        )
    return render_png(
        code,
        visual,
        scale=export.digital_scale,
        module_style=module_style,
        logo=logo,
    )


def render_download_job(
    content: str,
    error_correction: str,
    module_style: str,
    export: ExportOptions,
    visual: VisualOptions,
    logo: PreparedLogo | None,
) -> tuple[bytes, str]:
    """Render one validated download in an isolated worker process."""
    code = make_qr(content, error_correction)
    if export.output_format == "png":
        return (
            render_png(
                code,
                visual,
                scale=export.digital_scale,
                module_style=module_style,
                logo=logo,
            ),
            "image/png",
        )
    if export.output_format == "jpg":
        return (
            render_jpg(
                code,
                visual,
                scale=export.digital_scale,
                module_style=module_style,
                logo=logo,
            ),
            "image/jpeg",
        )
    if export.output_format == "svg":
        return (
            render_svg(
                code,
                visual,
                scale=export.digital_scale,
                module_style=module_style,
                logo=logo,
            ),
            "image/svg+xml",
        )
    return (
        render_pdf(
            code,
            visual,
            module_style=module_style,
            logo=logo,
            options=export.pdf,
        ),
        "application/pdf",
    )


class RenderJobs:
    """Admit six jobs while limiting worker execution to two processes."""

    def __init__(self, *, active: int = 2, queued: int = 4) -> None:
        self._limiter = anyio.CapacityLimiter(active)
        self._capacity = active + queued
        self._admitted = 0
        self._lock = asyncio.Lock()

    async def run(
        self,
        function: Callable[..., _T],
        *args: Any,
        timeout: float,
    ) -> _T:
        """Run an admitted job or raise a stable busy/timeout exception."""
        async with self._lock:
            if self._admitted >= self._capacity:
                raise RenderBusyError
            self._admitted += 1
        try:
            try:
                with anyio.fail_after(timeout):
                    return await anyio.to_process.run_sync(
                        function,
                        *args,
                        cancellable=True,
                        limiter=self._limiter,
                    )
            except TimeoutError as error:
                raise RenderTimeoutError from error
        finally:
            async with self._lock:
                self._admitted -= 1
