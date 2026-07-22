"""Payload normalization tests."""

from __future__ import annotations

import pytest

from qrcode_web.errors import RequestValidationError
from qrcode_web.payloads import normalize_geo


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
