"""Payload normalization tests."""

from __future__ import annotations

import pytest

from qrcode_web.errors import RequestValidationError
from qrcode_web.payloads import normalize_geo, normalize_vcard


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected"),
    [
        ("40.71281234567890", "-74.00601250000000", "geo:40.712812,-74.006013"),
        ("1.9999999", "-0.0000005", "geo:2,-0.000001"),
        ("0.0000004", "-0.0000004", "geo:0,0"),
        ("90.0000004", "-180.0000004", "geo:90,-180"),
    ],
)
def test_geo_coordinates_round_to_six_places(
    latitude: str, longitude: str, expected: str
) -> None:
    """High-precision coordinates use half-away-from-zero rounding."""
    assert normalize_geo({"latitude": latitude, "longitude": longitude}) == expected


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        ("90.0000005", "0"),
        ("0", "-180.0000005"),
        ("nan", "0"),
        ("1e1", "0"),
        (" 1", "0"),
    ],
)
def test_geo_coordinates_reject_invalid_or_out_of_range_values(
    latitude: str, longitude: str
) -> None:
    """Malformed coordinates and values outside rounded bounds are rejected."""
    with pytest.raises(RequestValidationError):
        normalize_geo({"latitude": latitude, "longitude": longitude})


def test_vcard_serializes_supported_fields_and_omits_blanks() -> None:
    """Contact fields produce a deterministic scanner-compatible vCard."""
    result = normalize_vcard(
        {
            "given_name": "Ada",
            "family_name": "Lovelace",
            "personal_phone": "+44 20 7946 0958",
            "email": "ada@example.com",
            "company": "Analytical Engines, Ltd.",
            "work_title": "Mathematician",
            "work_phone": "",
            "fax": "+44 20 7000 0000",
            "street": "1 Engine; Way",
            "city": "London",
            "state": "",
            "postal_code": "SW1A 1AA",
            "country": "United Kingdom",
            "website_url": "example.com/ada",
        }
    )

    assert result == (
        "BEGIN:VCARD\r\n"
        "VERSION:3.0\r\n"
        "N:Lovelace;Ada;;;\r\n"
        "FN:Ada Lovelace\r\n"
        "ORG:Analytical Engines\\, Ltd.\r\n"
        "TITLE:Mathematician\r\n"
        "TEL;TYPE=CELL,VOICE:+44 20 7946 0958\r\n"
        "TEL;TYPE=WORK,FAX:+44 20 7000 0000\r\n"
        "EMAIL;TYPE=INTERNET:ada@example.com\r\n"
        "ADR;TYPE=WORK:;;1 Engine\\; Way;London;;SW1A 1AA;United Kingdom\r\n"
        "URL:https://example.com/ada\r\n"
        "END:VCARD\r\n"
    )
    assert "WORK,VOICE" not in result


def test_vcard_escapes_input_and_folds_utf8_without_splitting() -> None:
    """User text cannot inject properties and long Unicode lines fold safely."""
    result = normalize_vcard(
        {
            "given_name": "Zoë\nTITLE:Injected",
            "family_name": "界" * 24,
        }
    )

    assert "Zoë\\nTITLE:Injected" in result.replace("\r\n ", "")
    assert "\r\n " in result
    for line in result.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75


@pytest.mark.parametrize(
    ("payload", "path"),
    [
        ({"given_name": "", "family_name": ""}, "payload.given_name"),
        ({"given_name": "Ada", "email": "not-an-email"}, "payload.email"),
        (
            {"given_name": "Ada", "website_url": "ftp://example.com"},
            "payload.website_url",
        ),
        ({"given_name": "a" * 256}, "payload.given_name"),
        (
            {
                "given_name": "Ada",
                "company": "x" * 255,
                "street": "y" * 255,
                "city": "z" * 255,
            },
            "payload",
        ),
    ],
)
def test_vcard_rejects_invalid_or_excessive_contact_fields(
    payload: dict[str, str], path: str
) -> None:
    """Required, structured, and density limits return precise field paths."""
    with pytest.raises(RequestValidationError) as caught:
        normalize_vcard(payload)

    assert caught.value.issues[0].path == path
