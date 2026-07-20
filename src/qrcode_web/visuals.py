"""Scanner-safe QR visual-option validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from qrcode_web.errors import RequestValidationError, ValidationIssue

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True, slots=True)
class VisualOptions:
    """Validated QR visual settings."""

    foreground: str
    background: str
    transparent: bool
    border_type: str
    border_width: int
    border_caption: str


def _luminance(color: str) -> float:
    """Return WCAG relative luminance for a six-digit hex color."""
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear: list[float] = []
    for channel in channels:
        if channel <= 0.04045:
            linear.append(channel / 12.92)
        else:
            linear.append(((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _issue(path: str, code: str, message: str) -> RequestValidationError:
    """Create one structured visual-validation error."""
    return RequestValidationError([ValidationIssue(path, code, message)])


def parse_visual_options(value: Any, output_format: str) -> VisualOptions:
    """Validate QR colors and allowed background transparency."""
    settings = value if isinstance(value, dict) else {}
    foreground = settings.get("foreground", "#000000")
    background = settings.get("background", "#FFFFFF")
    transparent = settings.get("transparent", False)
    border_type = settings.get("border_type", "quiet")
    border_width = settings.get("border_width", 2)
    border_caption = settings.get("border_caption", "")
    if not isinstance(foreground, str) or not _HEX_COLOR.fullmatch(foreground):
        raise _issue(
            "visual.foreground", "color", "Enter a six-digit foreground color."
        )
    if not isinstance(background, str) or not _HEX_COLOR.fullmatch(background):
        raise _issue(
            "visual.background", "color", "Enter a six-digit background color."
        )
    if not isinstance(transparent, bool):
        raise _issue(
            "visual.transparent", "type", "Choose a valid transparency setting."
        )
    if border_type not in {"quiet", "solid", "rounded", "label", "padding"}:
        raise _issue("visual.border_type", "choice", "Choose a supported border type.")
    if border_width not in {1, 2, 4}:
        raise _issue(
            "visual.border_width",
            "choice",
            "Choose a border width of 1, 2, or 4 modules.",
        )
    if not isinstance(border_caption, str):
        raise _issue(
            "visual.border_caption", "type", "Enter a plain-text border caption."
        )
    border_caption = border_caption.strip()
    if border_type == "label" and not 1 <= len(border_caption) <= 80:
        raise _issue(
            "visual.border_caption",
            "length",
            "Border captions must be 1 to 80 characters.",
        )
    if border_type != "label" and border_caption:
        raise _issue(
            "visual.border_caption",
            "unused",
            "Choose a label frame to use a border caption.",
        )
    foreground = foreground.upper()
    background = background.upper()
    if transparent:
        if output_format not in {"png", "svg"}:
            raise _issue(
                "visual.transparent",
                "format",
                "Transparency is available only for PNG and SVG.",
            )
        if _luminance(foreground) > 0.15:
            raise _issue(
                "visual.foreground",
                "contrast",
                "Transparent exports require a dark foreground color.",
            )
    else:
        lighter = max(_luminance(foreground), _luminance(background))
        darker = min(_luminance(foreground), _luminance(background))
        if (lighter + 0.05) / (darker + 0.05) < 7:
            raise _issue(
                "visual",
                "contrast",
                "Foreground and background contrast must be at least 7:1.",
            )
    if border_type == "quiet":
        border_width = 0
    return VisualOptions(
        foreground,
        background,
        transparent,
        border_type,
        border_width,
        border_caption,
    )
