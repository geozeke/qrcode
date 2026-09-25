"""Payload normalization for supported QR code content types."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from qrcode_web.errors import RequestValidationError, ValidationIssue

_DECIMAL_COORDINATE = re.compile(r"-?\d+(?:\.\d+)?")
_COORDINATE_PRECISION = Decimal("0.000001")
_VCARD_FIELD_BYTES = 255
_VCARD_MAX_BYTES = 858


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
    if not isinstance(value, str) or not _DECIMAL_COORDINATE.fullmatch(value):
        raise _invalid(path, "coordinate", "Enter a decimal coordinate.")
    try:
        coordinate = Decimal(value)
        coordinate = coordinate.quantize(_COORDINATE_PRECISION, rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise _invalid(path, "coordinate", "Enter a decimal coordinate.") from error
    if coordinate < lower or coordinate > upper:
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


def _vcard_field(payload: dict[str, Any], name: str) -> str:
    """Validate and trim one vCard text field.

    Parameters
    ----------
    payload : dict[str, Any]
        Candidate vCard fields.
    name : str
        Field name to read.

    Returns
    -------
    str
        Trimmed field value.
    """
    value = payload.get(name, "")
    path = f"payload.{name}"
    if not isinstance(value, str):
        raise _invalid(path, "type", "Enter valid contact details.")
    value = value.strip()
    if len(value.encode("utf-8")) > _VCARD_FIELD_BYTES:
        raise _invalid(
            path,
            "length",
            f"Contact fields must be at most {_VCARD_FIELD_BYTES} UTF-8 bytes.",
        )
    if any(
        (ord(character) < 32 and character not in "\r\n") or ord(character) == 127
        for character in value
    ):
        raise _invalid(path, "characters", "Contact fields cannot contain controls.")
    return value


def _escape_vcard(value: str) -> str:
    """Escape an RFC 2426 text value."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return (
        normalized.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _fold_vcard_line(line: str) -> list[str]:
    """Fold one content line without splitting a UTF-8 character."""
    result: list[str] = []
    current = ""
    limit = 75
    for character in line:
        if len((current + character).encode("utf-8")) > limit:
            result.append(current)
            current = f" {character}"
            limit = 75
        else:
            current += character
    result.append(current)
    return result


def _valid_email(value: str) -> bool:
    """Return whether a contact email has a safe basic address shape."""
    if (
        value.count("@") != 1
        or any(character.isspace() for character in value)
        or any(character in "\\,;" for character in value)
    ):
        return False
    local, domain = value.rsplit("@", 1)
    return bool(
        local and domain and not local.startswith(".") and not domain.startswith(".")
    )


def normalize_vcard(payload: dict[str, Any]) -> str:
    """Normalize contact fields into one canonical vCard 3.0 value.

    Parameters
    ----------
    payload : dict[str, Any]
        Supported contact and work-address fields.

    Returns
    -------
    str
        Canonical RFC 2426 vCard text.
    """
    field_names = (
        "given_name",
        "family_name",
        "personal_phone",
        "email",
        "company",
        "work_title",
        "work_phone",
        "fax",
        "street",
        "city",
        "state",
        "postal_code",
        "country",
        "website_url",
    )
    fields = {name: _vcard_field(payload, name) for name in field_names}
    given_name = fields["given_name"]
    family_name = fields["family_name"]
    if not given_name and not family_name:
        raise _invalid(
            "payload.given_name", "required", "Enter a given or family name."
        )
    if fields["email"] and not _valid_email(fields["email"]):
        raise _invalid("payload.email", "email", "Enter a valid email address.")
    if fields["website_url"]:
        try:
            fields["website_url"] = normalize_url(fields["website_url"])
        except RequestValidationError as error:
            issue = error.issues[0]
            raise _invalid("payload.website_url", issue.code, issue.message) from error

    display_name = " ".join(value for value in (given_name, family_name) if value)
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_escape_vcard(family_name)};{_escape_vcard(given_name)};;;",
        f"FN:{_escape_vcard(display_name)}",
    ]
    properties = (
        ("ORG", "company"),
        ("TITLE", "work_title"),
        ("TEL;TYPE=CELL,VOICE", "personal_phone"),
        ("TEL;TYPE=WORK,VOICE", "work_phone"),
        ("TEL;TYPE=WORK,FAX", "fax"),
        ("EMAIL;TYPE=INTERNET", "email"),
    )
    lines.extend(
        f"{property_name}:{_escape_vcard(fields[field_name])}"
        for property_name, field_name in properties
        if fields[field_name]
    )
    address_names = ("street", "city", "state", "postal_code", "country")
    if any(fields[name] for name in address_names):
        address = ";".join(
            [
                "",
                "",
                _escape_vcard(fields["street"]),
                _escape_vcard(fields["city"]),
                _escape_vcard(fields["state"]),
                _escape_vcard(fields["postal_code"]),
                _escape_vcard(fields["country"]),
            ]
        )
        lines.append(f"ADR;TYPE=WORK:{address}")
    if fields["website_url"]:
        lines.append(f"URL:{fields['website_url']}")
    lines.append("END:VCARD")
    result = (
        "\r\n".join(
            physical_line for line in lines for physical_line in _fold_vcard_line(line)
        )
        + "\r\n"
    )
    if len(result.encode("utf-8")) > _VCARD_MAX_BYTES:
        raise _invalid(
            "payload",
            "length",
            f"Contact details must fit within {_VCARD_MAX_BYTES} UTF-8 bytes.",
        )
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
    if payload_type == "vcard":
        return normalize_vcard(payload)
    raise _invalid("payload_type", "unsupported", "Choose a supported payload type.")
