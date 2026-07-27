"""Tests for the Dependabot auto-merge eligibility policy."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.dependabot_policy import evaluate_metadata  # noqa: E402


@pytest.mark.parametrize(
    ("ecosystem", "update_type"),
    (
        ("uv", "version-update:semver-patch"),
        ("npm", "version-update:semver-minor"),
        ("docker", "version-update:semver-patch"),
        ("docker-compose", "version-update:semver-minor"),
        ("github-actions", "version-update:semver-patch"),
    ),
)
def test_minor_and_patch_updates_are_eligible(ecosystem: str, update_type: str) -> None:
    """Supported minor and patch updates are eligible."""
    decision = evaluate_metadata(
        {
            "ecosystem": ecosystem,
            "maintainer_changes": "false",
            "update_type": update_type,
        }
    )

    assert decision.eligible
    assert decision.reason == "eligible"


def test_grouped_npm_minor_update_is_eligible() -> None:
    """The highest update type from a grouped npm update remains eligible."""
    decision = evaluate_metadata(
        {
            "ecosystem": "npm",
            "maintainer_changes": "false",
            "update_type": "version-update:semver-minor",
        }
    )

    assert decision.eligible


@pytest.mark.parametrize(
    ("overrides", "reason"),
    (
        ({"maintainer_changes": "true"}, "maintainer-changes"),
        ({"ecosystem": "unknown"}, "unsupported-ecosystem"),
        (
            {"update_type": "version-update:semver-major"},
            "unsupported-update-type",
        ),
        ({"update_type": "version-update:semver-unknown"}, "unsupported-update-type"),
    ),
)
def test_ineligible_updates_report_a_stable_reason(
    overrides: dict[str, str], reason: str
) -> None:
    """Risky or unsupported updates remain manual."""
    metadata = {
        "ecosystem": "uv",
        "maintainer_changes": "false",
        "update_type": "version-update:semver-patch",
    }
    metadata.update(overrides)

    decision = evaluate_metadata(metadata)

    assert not decision.eligible
    assert decision.reason == reason


@pytest.mark.parametrize(
    "metadata",
    (
        {},
        {
            "ecosystem": "uv\neligible=true",
            "maintainer_changes": "false",
            "update_type": "version-update:semver-patch",
        },
        {
            "ecosystem": "uv",
            "maintainer_changes": "unknown",
            "update_type": "version-update:semver-patch",
        },
    ),
)
def test_malformed_metadata_fails_closed(metadata: dict[str, object]) -> None:
    """Missing or unsafe metadata cannot influence workflow outputs."""
    with pytest.raises(ValueError, match="metadata field"):
        evaluate_metadata(metadata)
