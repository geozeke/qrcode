"""Payload normalization for first-release QR code types."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from qrcode_web.errors import RequestValidationError, ValidationIssue


def _invalid(path: str, code: str, message: str) -> RequestValidationError:
    """Create a one-issue request validation exception.

    Parameters
    ----------
    path : str
        Request field path.
    code : str
        Stable failure code.
    message : str
        User-safe explanation.

    Returns
    -------
    RequestValidationError
        Exception containing the supplied issue.
    """
    return RequestValidationError([ValidationIssue(path, code, message)])


def normalize_url(value: Any) -> str:
    """Normalize an HTTP(S) URL payload.

    Parameters
    ----------
    value : Any
        Candidate URL value.

    Returns
    -------
    str
        Normalized URL with an explicit scheme.

    Raises
    ------
    RequestValidationError
        If the value is not a valid HTTP(S) URL.
    """
    if not isinstance(value, str):
        raise _invalid("payload.url", "type", "Enter a URL.")
    url = value.strip()
    if not url:
        raise _invalid("payload.url", "required", "Enter a URL.")
    if any(character.isspace() or ord(character) < 32 for character in url):
        raise _invalid("payload.url", "characters", "URLs cannot contain whitespace.")
    if "://" not in url:
        url = f"https://{url}"
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise _invalid("payload.url", "url", "Enter a valid HTTP or HTTPS URL.")
    return urlunsplit(parts)


def _coordinate(value: Any, path: str, lower: Decimal, upper: Decimal) -> str:
    """Validate and normalize one WGS84 decimal coordinate.

    Parameters
    ----------
    value : Any
        Candidate coordinate value.
    path : str
        Request field path.
    lower : Decimal
        Minimum inclusive value.
    upper : Decimal
        Maximum inclusive value.

    Returns
    -------
    str
        Plain decimal coordinate with at most six fractional digits.
    """
    if not isinstance(value, str) or not value or "e" in value.lower() or "," in value:
        raise _invalid(path, "coordinate", "Enter a decimal coordinate.")
    try:
        coordinate = Decimal(value)
    except InvalidOperation as error:
        raise _invalid(path, "coordinate", "Enter a decimal coordinate.") from error
    exponent = coordinate.as_tuple().exponent
    fractional_digits = -exponent if isinstance(exponent, int) else 7
    if coordinate < lower or coordinate > upper or fractional_digits > 6:
        raise _invalid(path, "range", "Enter a coordinate in the supported range.")
    if not coordinate:
        return "0"
    return format(coordinate.normalize(), "f")


def normalize_geo(payload: dict[str, Any]) -> str:
    """Normalize a geographic QR payload to the canonical geo URI.

    Parameters
    ----------
    payload : dict[str, Any]
        Payload fields containing latitude and longitude.

    Returns
    -------
    str
        Canonical `geo:latitude,longitude` URI.
    """
    latitude = _coordinate(
        payload.get("latitude"), "payload.latitude", Decimal("-90"), Decimal("90")
    )
    longitude = _coordinate(
        payload.get("longitude"), "payload.longitude", Decimal("-180"), Decimal("180")
    )
    return f"geo:{latitude},{longitude}"


def normalize_text(value: Any) -> str:
    """Validate a UTF-8 plain-text payload without altering it.

    Parameters
    ----------
    value : Any
        Candidate text value.

    Returns
    -------
    str
        Original text value.
    """
    if not isinstance(value, str):
        raise _invalid("payload.text", "type", "Enter text.")
    size = len(value.encode("utf-8"))
    if not 1 <= size <= 1000:
        raise _invalid("payload.text", "length", "Text must be 1 to 1,000 UTF-8 bytes.")
    return value


def _escape_wifi(value: str) -> str:
    """Escape special characters in a WIFI payload field.

    Parameters
    ----------
    value : str
        Unescaped field value.

    Returns
    -------
    str
        WIFI-compatible escaped field value.
    """
    special_characters = '\\;,": '
    return "".join(
        f"\\{character}" if character in special_characters else character
        for character in value
    )


def _printable_ascii(value: str) -> bool:
    """Report whether a string contains printable ASCII characters only.

    Parameters
    ----------
    value : str
        Candidate value.

    Returns
    -------
    bool
        Whether all characters are printable ASCII.
    """
    return all(" " <= character <= "~" for character in value)


def normalize_wifi(payload: dict[str, Any]) -> str:
    """Normalize a scanner-compatible WIFI QR payload.

    Parameters
    ----------
    payload : dict[str, Any]
        WiFi fields: security, SSID, password, and optional hidden state.

    Returns
    -------
    str
        Canonical `WIFI:` payload.
    """
    security = payload.get("security")
    ssid = payload.get("ssid")
    password = payload.get("password", "")
    hidden = payload.get("hidden", False)
    if security not in {"open", "wpa", "wep"}:
        raise _invalid(
            "payload.security", "choice", "Choose a supported WiFi security type."
        )
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode("utf-8")) <= 32:
        raise _invalid("payload.ssid", "length", "SSID must be 1 to 32 UTF-8 bytes.")
    if any(ord(character) < 32 or ord(character) == 127 for character in ssid):
        raise _invalid(
            "payload.ssid", "characters", "SSID cannot contain control characters."
        )
    if not isinstance(password, str) or not isinstance(hidden, bool):
        raise _invalid("payload", "type", "Enter valid WiFi settings.")
    if security == "open" and password:
        raise _invalid(
            "payload.password", "open", "Open networks cannot have a password."
        )
    if security == "wpa" and (
        not 8 <= len(password) <= 63 or not _printable_ascii(password)
    ):
        raise _invalid(
            "payload.password",
            "wpa",
            "WPA passwords must be 8 to 63 printable ASCII characters.",
        )
    is_wep_length = len(password) in {5, 13} and _printable_ascii(password)
    is_wep_hex = len(password) in {10, 26} and all(
        character in "0123456789abcdefABCDEF" for character in password
    )
    if security == "wep" and not (is_wep_length or is_wep_hex):
        raise _invalid("payload.password", "wep", "Enter a valid WEP password.")
    network_type = {"open": "nopass", "wpa": "WPA", "wep": "WEP"}[security]
    result = f"WIFI:T:{network_type};S:{_escape_wifi(ssid)};"
    if security != "open":
        result += f"P:{_escape_wifi(password)};"
    if hidden:
        result += "H:true;"
    return result


def normalize_payload(payload_type: str, payload: dict[str, Any]) -> str:
    """Normalize one supported QR payload type.

    Parameters
    ----------
    payload_type : str
        Selected payload type.
    payload : dict[str, Any]
        Type-specific input fields.

    Returns
    -------
    str
        QR-encoded content.

    Raises
    ------
    RequestValidationError
        If the payload type or fields are unsupported.
    """
    if payload_type == "url":
        return normalize_url(payload.get("url"))
    if payload_type == "geo":
        return normalize_geo(payload)
    if payload_type == "text":
        return normalize_text(payload.get("text"))
    if payload_type == "wifi":
        return normalize_wifi(payload)
    raise _invalid("payload_type", "unsupported", "Choose a supported payload type.")
