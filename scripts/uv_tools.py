"""Maintain synchronized uv toolchain versions across repository tooling.

Functions
---------
check_uv_versions
    Validate that every tracked uv toolchain reference uses one version.
update_uv_version
    Replace every tracked uv toolchain reference with a requested version.
verify_uv_release
    Confirm that a requested version is a published Astral uv release.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .changelog_tools import parse_version

ROOT = Path(__file__).resolve().parents[1]
UV_IMAGE_PATTERN = re.compile(
    r"(?m)^(FROM\s+ghcr\.io/astral-sh/uv:)([^\s]+)(\s+AS uv\s*)$"
)
SETUP_UV_PATTERN = re.compile(
    r'(uses:\s+astral-sh/setup-uv@[^\n]+\n\s+with:\n\s+version:\s+")([^"]+)(")'
)
DEPLOYMENT_PATTERN = re.compile(r'(?m)^(\s*"uv )([^\s"]+)( "\*\) ;;)$')
LICENSE_PATTERN = re.compile(
    r'(?m)^("ghcr\.io/astral-sh/uv:)([^"]+)(" = "Apache-2\.0 OR MIT"\s*)$'
)
UV_RELEASE_URL = "https://api.github.com/repos/astral-sh/uv/releases/tags/{version}"


def _replace_once(pattern: re.Pattern[str], text: str, version: str, name: str) -> str:
    """Replace one version capture group in text.

    Parameters
    ----------
    pattern
        Pattern with the version in capture group two.
    text
        Text containing the reference to update.
    version
        Validated replacement version.
    name
        Human-readable reference name used in error messages.

    Returns
    -------
    str
        Updated text.

    Raises
    ------
    ValueError
        If the reference is missing or appears more than once.
    """
    updated, count = pattern.subn(rf"\g<1>{version}\g<3>", text)
    if count != 1:
        raise ValueError(f"Expected exactly one {name} reference, found {count}")
    return updated


def _version_from_once(pattern: re.Pattern[str], text: str, name: str) -> str:
    """Read one version capture group from text.

    Parameters
    ----------
    pattern
        Pattern with the version in capture group two.
    text
        Text containing the reference to inspect.
    name
        Human-readable reference name used in error messages.

    Returns
    -------
    str
        Referenced version.

    Raises
    ------
    ValueError
        If the reference is missing or appears more than once.
    """
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {name} reference, found {len(matches)}")
    return matches[0].group(2)


def _workflow_paths(root: Path) -> list[Path]:
    """Return sorted workflow paths that install uv.

    Parameters
    ----------
    root
        Repository root containing GitHub workflow files.

    Returns
    -------
    list[pathlib.Path]
        Workflow paths with at least one ``astral-sh/setup-uv`` use.
    """
    paths = []
    for path in sorted((root / ".github" / "workflows").glob("*.yml")):
        if SETUP_UV_PATTERN.search(path.read_text(encoding="utf-8")):
            paths.append(path)
    if not paths:
        raise ValueError("No GitHub Actions setup-uv references were found")
    return paths


def uv_versions(root: Path = ROOT) -> dict[str, str]:
    """Return every tracked uv toolchain version.

    Parameters
    ----------
    root
        Repository root containing the tracked uv references.

    Returns
    -------
    dict[str, str]
        Mapping from reference labels to their declared versions.
    """
    versions = {
        "Dockerfile": _version_from_once(
            UV_IMAGE_PATTERN,
            (root / "Dockerfile").read_text(encoding="utf-8"),
            "uv image",
        ),
        "scripts/deployment_test.sh": _version_from_once(
            DEPLOYMENT_PATTERN,
            (root / "scripts" / "deployment_test.sh").read_text(encoding="utf-8"),
            "deployment uv assertion",
        ),
        "config/dependency-licenses.toml": _version_from_once(
            LICENSE_PATTERN,
            (root / "config" / "dependency-licenses.toml").read_text(encoding="utf-8"),
            "uv image license",
        ),
    }
    for path in _workflow_paths(root):
        matches = list(SETUP_UV_PATTERN.finditer(path.read_text(encoding="utf-8")))
        for index, match in enumerate(matches, start=1):
            versions[f"{path.relative_to(root)}#{index}"] = match.group(2)
    return versions


def check_uv_versions(root: Path = ROOT) -> str:
    """Require all tracked uv toolchain versions to match.

    Parameters
    ----------
    root
        Repository root containing the tracked uv references.

    Returns
    -------
    str
        The synchronized bare semantic version.

    Raises
    ------
    ValueError
        If versions are malformed or do not match.
    """
    versions = uv_versions(root)
    for source, version in versions.items():
        try:
            parse_version(version)
        except ValueError as exc:
            raise ValueError(f"Invalid uv version in {source}: {version}") from exc
    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        details = ", ".join(
            f"{source}={version}" for source, version in sorted(versions.items())
        )
        raise ValueError(f"uv versions are not synchronized: {details}")
    return unique_versions.pop()


def verify_uv_release(version: str) -> str:
    """Require a uv release tag to exist in Astral's GitHub repository.

    Parameters
    ----------
    version
        Bare semantic uv version to verify.

    Returns
    -------
    str
        Normalized verified version.

    Raises
    ------
    ValueError
        If the version is malformed, does not name a published release, or
        cannot be verified.
    """
    normalized_version = parse_version(version).text
    request = Request(
        UV_RELEASE_URL.format(version=normalized_version),
        headers={"Accept": "application/vnd.github+json", "User-Agent": "qrcode"},
    )
    try:
        with urlopen(request, timeout=10):
            pass
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError(
                f"uv {normalized_version} is not a published Astral release"
            ) from exc
        raise ValueError(
            f"Unable to verify uv {normalized_version}: GitHub returned HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise ValueError(
            f"Unable to verify uv {normalized_version}: {exc.reason}"
        ) from exc
    except OSError as exc:
        raise ValueError(f"Unable to verify uv {normalized_version}: {exc}") from exc
    return normalized_version


def update_uv_version(version: str, root: Path = ROOT) -> None:
    """Update every tracked uv toolchain reference.

    Parameters
    ----------
    version
        Bare semantic uv version to apply.
    root
        Repository root containing the tracked uv references.

    Raises
    ------
    ValueError
        If the requested version is invalid or an expected reference is absent
        or ambiguous.
    """
    normalized_version = verify_uv_release(version)
    paths_and_patterns = (
        (root / "Dockerfile", UV_IMAGE_PATTERN, "uv image"),
        (
            root / "scripts" / "deployment_test.sh",
            DEPLOYMENT_PATTERN,
            "deployment uv assertion",
        ),
        (
            root / "config" / "dependency-licenses.toml",
            LICENSE_PATTERN,
            "uv image license",
        ),
    )
    updates = {
        path: _replace_once(
            pattern, path.read_text(encoding="utf-8"), normalized_version, name
        )
        for path, pattern, name in paths_and_patterns
    }
    workflow_count = 0
    for path in _workflow_paths(root):
        text = path.read_text(encoding="utf-8")
        updated, count = SETUP_UV_PATTERN.subn(rf"\g<1>{normalized_version}\g<3>", text)
        updates[path] = updated
        workflow_count += count
    if workflow_count == 0:
        raise ValueError("No GitHub Actions setup-uv references were found")
    for path, text in updates.items():
        path.write_text(text, encoding="utf-8")
    check_uv_versions(root)
