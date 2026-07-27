#!/usr/bin/env python3
"""Evaluate verified Dependabot metadata against the auto-merge policy."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_ECOSYSTEMS = frozenset(
    {
        "docker",
        "docker-compose",
        "github-actions",
        "npm",
        "uv",
    }
)
SUPPORTED_UPDATE_TYPES = frozenset(
    {
        "version-update:semver-minor",
        "version-update:semver-patch",
    }
)
SAFE_VALUE = re.compile(r"^[a-z0-9:_-]+$")


@dataclass(frozen=True)
class EligibilityDecision:
    """Describe a Dependabot auto-merge eligibility decision.

    Parameters
    ----------
    eligible
        Whether automation may enable auto-merge.
    reason
        Stable machine-readable reason for the decision.
    ecosystem
        Dependabot package ecosystem.
    update_type
        Dependabot semantic update classification.
    maintainer_changes
        Whether a maintainer changed the pull-request branch.
    """

    eligible: bool
    reason: str
    ecosystem: str
    update_type: str
    maintainer_changes: str


def _metadata_value(metadata: Mapping[str, object], name: str) -> str:
    """Return one validated metadata string.

    Parameters
    ----------
    metadata
        Parsed Dependabot metadata.
    name
        Required field name.

    Returns
    -------
    str
        Validated field value.

    Raises
    ------
    ValueError
        If the field is absent, is not a string, or contains unsafe
        characters.
    """
    value = metadata.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Dependabot metadata field {name!r} must be a string")
    if SAFE_VALUE.fullmatch(value) is None:
        raise ValueError(f"Dependabot metadata field {name!r} is malformed")
    return value


def evaluate_metadata(metadata: Mapping[str, object]) -> EligibilityDecision:
    """Evaluate verified Dependabot metadata.

    Parameters
    ----------
    metadata
        Parsed metadata produced by ``dependabot/fetch-metadata``.

    Returns
    -------
    EligibilityDecision
        Eligibility and a stable explanation.

    Raises
    ------
    ValueError
        If required metadata is missing or malformed.
    """
    ecosystem = _metadata_value(metadata, "ecosystem")
    update_type = _metadata_value(metadata, "update_type")
    maintainer_changes = _metadata_value(metadata, "maintainer_changes")
    if maintainer_changes not in {"false", "true"}:
        raise ValueError(
            "Dependabot metadata field 'maintainer_changes' must be true or false"
        )

    reason = "eligible"
    eligible = True
    if maintainer_changes == "true":
        reason = "maintainer-changes"
        eligible = False
    elif ecosystem not in SUPPORTED_ECOSYSTEMS:
        reason = "unsupported-ecosystem"
        eligible = False
    elif update_type not in SUPPORTED_UPDATE_TYPES:
        reason = "unsupported-update-type"
        eligible = False

    return EligibilityDecision(
        eligible=eligible,
        reason=reason,
        ecosystem=ecosystem,
        update_type=update_type,
        maintainer_changes=maintainer_changes,
    )


def load_metadata(path: Path) -> Mapping[str, object]:
    """Load a Dependabot metadata object.

    Parameters
    ----------
    path
        JSON metadata path.

    Returns
    -------
    Mapping[str, object]
        Parsed metadata object.

    Raises
    ------
    ValueError
        If the document is not a JSON object.
    """
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("Dependabot metadata must be a JSON object")
    return metadata


def write_github_output(path: Path, decision: EligibilityDecision) -> None:
    """Write a decision to a GitHub Actions output file.

    Parameters
    ----------
    path
        GitHub Actions output path.
    decision
        Evaluated policy decision.
    """
    values = {
        "eligible": str(decision.eligible).lower(),
        "reason": decision.reason,
        "ecosystem": decision.ecosystem,
        "update_type": decision.update_type,
        "maintainer_changes": decision.maintainer_changes,
    }
    with path.open("a", encoding="utf-8") as output:
        for name, value in values.items():
            output.write(f"{name}={value}\n")


def main() -> None:
    """Parse metadata and write the auto-merge policy decision."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path, help="Verified metadata JSON path.")
    parser.add_argument(
        "--github-output",
        type=Path,
        required=True,
        help="GitHub Actions output file.",
    )
    args = parser.parse_args()
    try:
        decision = evaluate_metadata(load_metadata(args.metadata))
        write_github_output(args.github_output, decision)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
