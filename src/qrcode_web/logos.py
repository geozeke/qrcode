"""Temporary logo decoding, sanitization, and placement validation."""

from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from io import BytesIO

import segno
from PIL import Image, UnidentifiedImageError
from segno import consts

MAX_LOGO_BYTES = 5 * 1024 * 1024
MAX_LOGO_PIXELS = 4_000_000
MAX_LOGO_DIMENSION = 4096


class LogoValidationError(ValueError):
    """A safe, user-correctable logo validation failure."""


class LogoTooLargeError(LogoValidationError):
    """Raised when a logo exceeds the configured upload limit."""


@dataclass(frozen=True, slots=True)
class PreparedLogo:
    """Sanitized in-memory logo data."""

    png: bytes
    sha256: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class LogoPlacement:
    """Whole-module placement within the QR symbol, excluding quiet zone."""

    backing_start: int
    backing_modules: int
    logo_modules: int


def prepare_logo(data: bytes) -> PreparedLogo:
    """Decode and re-encode one bounded PNG or JPEG without metadata."""
    if not data:
        raise LogoValidationError("Choose a PNG or JPEG logo.")
    if len(data) > MAX_LOGO_BYTES:
        raise LogoTooLargeError("Logo files must be no larger than 5 MiB.")
    Image.MAX_IMAGE_PIXELS = MAX_LOGO_PIXELS
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {"PNG", "JPEG"}:
                    raise LogoValidationError("Logo files must be PNG or JPEG images.")
                if getattr(source, "n_frames", 1) != 1:
                    raise LogoValidationError(
                        "Animated or multi-frame logos are not supported."
                    )
                width, height = source.size
                if (
                    width > MAX_LOGO_DIMENSION
                    or height > MAX_LOGO_DIMENSION
                    or width * height > MAX_LOGO_PIXELS
                ):
                    raise LogoValidationError(
                        "Logos must be at most 4096 pixels per side and 4 megapixels."
                    )
                source.load()
                clean = source.convert("RGBA")
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise LogoValidationError(
            "Logo data is not a valid PNG or JPEG image."
        ) from error
    output = BytesIO()
    clean.save(output, format="PNG", optimize=False)
    png = output.getvalue()
    return PreparedLogo(png, hashlib.sha256(data).hexdigest(), width, height)


def logo_placement(code: segno.QRCode) -> LogoPlacement:
    """Return a centered safe logo placement or reject the QR version."""
    matrix = [list(row) for row in code.matrix_iter(scale=1, border=0, verbose=True)]
    symbol_modules = len(matrix)
    logo_modules = int(symbol_modules * 0.15)
    if logo_modules % 2 == 0:
        logo_modules -= 1
    if logo_modules < 1:
        raise LogoValidationError("This QR code is too small for a logo.")
    backing_modules = logo_modules + 2
    backing_start = (symbol_modules - backing_modules) // 2
    data_types = {consts.TYPE_DATA_LIGHT, consts.TYPE_DATA_DARK}
    for row in matrix[backing_start : backing_start + backing_modules]:
        modules = row[backing_start : backing_start + backing_modules]
        if any(module_type not in data_types for module_type in modules):
            raise LogoValidationError(
                "A centered logo would overlap a functional QR module."
            )
    return LogoPlacement(backing_start, backing_modules, logo_modules)
