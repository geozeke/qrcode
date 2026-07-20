#!/usr/bin/env python3
"""Provide changelog, release-note, and Conventional Commit helpers.

Functions
---------
parse_version
    Parse a supported semantic version.
split_changelog
    Split changelog Markdown into its preamble and release sections.
archive_changelog
    Move inactive minor release lines into archive files.
extract_release_notes
    Return one release section without its heading.
validate_commit_title
    Validate a Conventional Commit title accepted by this project.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

SEMVER_CORE = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
PRERELEASE = r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
SEMVER_RE = re.compile(rf"^(?P<version>{SEMVER_CORE}{PRERELEASE})$")
HEADING_RE = re.compile(
    rf"^## \[(?P<label>Unreleased|{SEMVER_CORE}{PRERELEASE})\]"
    r"(?: - (?P<date>\d{4}-\d{2}-\d{2}))?$"
)
GROUP_RE = re.compile(r"^### (?P<group>.+)$")
COMMIT_TITLE_RE = re.compile(
    r"^(?P<type>feat|change|deprecate|remove|fix|security|perf|deploy|docs|"
    r"build|chore|ci|refactor|style|test|revert)"
    r"(?:\([a-z0-9][a-z0-9._/-]*\))?(?:!)?: [^\s].*$"
)
PrereleaseKey = tuple[tuple[int, int | str], ...]


@dataclass(frozen=True)
class Version:
    """Represent a supported semantic version.

    Parameters
    ----------
    text
        Normalized version text without a leading ``v``.
    major
        Major version component.
    minor
        Minor version component.
    patch
        Patch version component.
    prerelease
        Parsed prerelease identifiers.
    """

    text: str
    major: int
    minor: int
    patch: int
    prerelease: PrereleaseKey

    @property
    def major_minor(self) -> tuple[int, int]:
        """Return the major and minor release line."""
        return self.major, self.minor

    def sort_key(self) -> tuple[int, int, int, bool, PrereleaseKey]:
        """Return a key that sorts stable versions after prereleases."""
        return self.major, self.minor, self.patch, not self.prerelease, self.prerelease


@dataclass(frozen=True)
class Section:
    """Represent a second-level changelog section.

    Parameters
    ----------
    label
        ``Unreleased`` or a normalized semantic version.
    text
        Complete Markdown for the section, including its heading.
    """

    label: str
    text: str

    @property
    def version(self) -> Version | None:
        """Return the parsed version, or ``None`` for Unreleased."""
        if self.label == "Unreleased":
            return None
        return parse_version(self.label)


def _prerelease_key(text: str) -> PrereleaseKey:
    """Return a SemVer-compatible prerelease key."""
    if "-" not in text:
        return ()
    identifiers = text.split("-", maxsplit=1)[1].split(".")
    if any(
        identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0")
        for identifier in identifiers
    ):
        raise ValueError(
            f"Numeric prerelease identifiers cannot contain leading zeros: {text}"
        )
    return tuple(
        (0, int(identifier)) if identifier.isdigit() else (1, identifier)
        for identifier in identifiers
    )


def parse_version(text: str) -> Version:
    """Parse a supported semantic version.

    Parameters
    ----------
    text
        Bare semantic version without build metadata or a leading ``v``.

    Returns
    -------
    Version
        Parsed version components.

    Raises
    ------
    ValueError
        If the value is not a supported semantic version.
    """
    match = SEMVER_RE.fullmatch(text)
    if not match:
        raise ValueError(f"Expected a bare semantic version, got: {text}")
    normalized = match.group("version")
    core = normalized.split("-", maxsplit=1)[0]
    major, minor, patch = (int(part) for part in core.split("."))
    return Version(normalized, major, minor, patch, _prerelease_key(normalized))


def split_changelog(text: str) -> tuple[str, list[Section]]:
    """Split changelog Markdown into a preamble and release sections.

    Parameters
    ----------
    text
        Changelog Markdown.

    Returns
    -------
    tuple[str, list[Section]]
        Preamble and ordered second-level sections.
    """
    lines = text.splitlines()
    headings = [index for index, line in enumerate(lines) if HEADING_RE.fullmatch(line)]
    if not headings:
        return text.strip(), []
    preamble = "\n".join(lines[: headings[0]]).strip()
    sections: list[Section] = []
    for position, start in enumerate(headings):
        end = headings[position + 1] if position + 1 < len(headings) else len(lines)
        match = HEADING_RE.fullmatch(lines[start])
        if match is None:
            raise ValueError(f"Invalid changelog heading: {lines[start]}")
        sections.append(
            Section(match.group("label"), "\n".join(lines[start:end]).strip())
        )
    return preamble, sections


def format_changelog(preamble: str, sections: list[Section]) -> str:
    """Format a preamble and release sections as normalized Markdown."""
    parts = [preamble.strip(), *(section.text.strip() for section in sections)]
    return "\n\n".join(part for part in parts if part).strip() + "\n"


def _group_content(section: Section) -> tuple[str, list[str], dict[str, list[str]]]:
    """Return a section heading, introduction, and grouped content."""
    lines = section.text.splitlines()
    heading = lines[0]
    introduction: list[str] = []
    groups: dict[str, list[str]] = {}
    current = ""
    for line in lines[1:]:
        match = GROUP_RE.fullmatch(line)
        if match:
            current = match.group("group")
            groups.setdefault(current, [])
        elif current and line.strip():
            groups[current].append(line)
        elif line.strip():
            introduction.append(line)
    return heading, introduction, groups


def merge_unreleased(generated: Section, curated: Section) -> Section:
    """Merge a generated first release with the curated Unreleased baseline."""
    heading, generated_intro, generated_groups = _group_content(generated)
    _curated_heading, curated_intro, curated_groups = _group_content(curated)
    merged = {group: list(lines) for group, lines in curated_groups.items()}
    for group, lines in generated_groups.items():
        merged.setdefault(group, []).extend(
            line for line in lines if line not in merged[group]
        )
    introduction = [*generated_intro]
    introduction.extend(line for line in curated_intro if line not in introduction)
    parts = [heading, *introduction]
    for group, lines in merged.items():
        parts.append(f"### {group}\n\n" + "\n".join(lines))
    return Section(generated.label, "\n\n".join(parts))


def has_release_entries(section: Section) -> bool:
    """Return whether a release section contains at least one list entry."""
    return any(line.startswith("- ") for line in section.text.splitlines())


def archive_changelog(
    version: str,
    changelog_path: Path,
    archive_dir: Path,
) -> list[Path]:
    """Move releases outside the target minor line into archive files.

    Parameters
    ----------
    version
        Target release version.
    changelog_path
        Active changelog path.
    archive_dir
        Directory containing one archive per minor release line.

    Returns
    -------
    list[pathlib.Path]
        Archive files created or updated.
    """
    target = parse_version(version)
    preamble, sections = split_changelog(changelog_path.read_text(encoding="utf-8"))
    inactive: dict[tuple[int, int], list[Section]] = {}
    active: list[Section] = []
    for section in sections:
        parsed = section.version
        if parsed is None or parsed.major_minor == target.major_minor:
            active.append(section)
        else:
            inactive.setdefault(parsed.major_minor, []).append(section)
    if not inactive:
        return []

    archive_dir.mkdir(parents=True, exist_ok=True)
    updated: list[Path] = []
    for major_minor, moved in inactive.items():
        archive_path = archive_dir / f"v{major_minor[0]}.{major_minor[1]}.x.md"
        existing: list[Section] = []
        if archive_path.exists():
            _existing_preamble, existing = split_changelog(
                archive_path.read_text(encoding="utf-8")
            )
        merged = {section.label: section for section in existing if section.version}
        merged.update({section.label: section for section in moved})

        def release_sort_key(
            section: Section,
        ) -> tuple[int, int, int, bool, PrereleaseKey]:
            parsed = section.version
            if parsed is None:
                raise ValueError("Archive contains an Unreleased section")
            return parsed.sort_key()

        ordered = sorted(merged.values(), key=release_sort_key, reverse=True)
        archive_preamble = (
            f"# Changelog archive: {major_minor[0]}.{major_minor[1]}.x\n\n"
            "Archived QR Code Generator releases for this minor version line."
        )
        archive_path.write_text(
            format_changelog(archive_preamble, ordered), encoding="utf-8"
        )
        updated.append(archive_path)
    changelog_path.write_text(format_changelog(preamble, active), encoding="utf-8")
    return updated


def extract_release_notes(tag: str, changelog_path: Path, archive_dir: Path) -> str:
    """Return release notes for a tag without the release heading.

    Parameters
    ----------
    tag
        Release tag in ``vX.Y.Z`` form.
    changelog_path
        Active changelog path.
    archive_dir
        Changelog archive directory.

    Returns
    -------
    str
        Non-empty Markdown release notes.

    Raises
    ------
    ValueError
        If the tag is invalid or matching notes are missing or empty.
    """
    if not tag.startswith("v"):
        raise ValueError("Release tag must start with v")
    version = parse_version(tag.removeprefix("v"))
    candidates = [
        changelog_path,
        archive_dir / f"v{version.major}.{version.minor}.x.md",
    ]
    matches: list[Section] = []
    for candidate in candidates:
        if not candidate.exists():
            continue
        _preamble, sections = split_changelog(candidate.read_text(encoding="utf-8"))
        matches.extend(section for section in sections if section.label == version.text)
    if not matches:
        raise ValueError(f"Release notes for {version.text} were not found")
    if len(matches) > 1:
        raise ValueError(f"Duplicate changelog sections for {version.text}")
    body = "\n".join(matches[0].text.splitlines()[1:]).strip()
    if not body:
        raise ValueError(f"Release notes for {version.text} are empty")
    return body + "\n"


def validate_commit_title(title: str) -> None:
    """Validate a project Conventional Commit title.

    Parameters
    ----------
    title
        Pull-request or commit title.

    Raises
    ------
    ValueError
        If the title does not match the accepted convention.
    """
    if not COMMIT_TITLE_RE.fullmatch(title):
        raise ValueError(
            "Expected '<type>(optional-scope): description' using a documented "
            "Conventional Commit type"
        )


def project_versions(project_root: Path) -> dict[str, str]:
    """Read every tracked application version.

    Parameters
    ----------
    project_root
        Repository root containing Python and frontend metadata.

    Returns
    -------
    dict[str, str]
        Version values keyed by their source file.

    Raises
    ------
    ValueError
        If the project package is absent from the uv lockfile.
    """
    with (project_root / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    package_json = json.loads(
        (project_root / "frontend/package.json").read_text(encoding="utf-8")
    )
    package_lock = json.loads(
        (project_root / "frontend/package-lock.json").read_text(encoding="utf-8")
    )
    with (project_root / "uv.lock").open("rb") as uv_lock_file:
        uv_lock = tomllib.load(uv_lock_file)
    locked_project = next(
        (package for package in uv_lock["package"] if package["name"] == "qrcode-web"),
        None,
    )
    if locked_project is None:
        raise ValueError("qrcode-web is missing from uv.lock")
    return {
        "pyproject.toml": str(pyproject["project"]["version"]),
        "uv.lock": str(locked_project["version"]),
        "frontend/package.json": str(package_json["version"]),
        "frontend/package-lock.json": str(package_lock["version"]),
        "frontend/package-lock.json package": str(
            package_lock["packages"][""]["version"]
        ),
    }


def validate_project_version(project_root: Path, expected: str | None = None) -> str:
    """Require synchronized project versions and optionally an expected value.

    Parameters
    ----------
    project_root
        Repository root containing version metadata.
    expected
        Required version when validating a release tag.

    Returns
    -------
    str
        The synchronized project version.

    Raises
    ------
    ValueError
        If versions differ or do not match ``expected``.
    """
    versions = project_versions(project_root)
    unique = set(versions.values())
    if len(unique) != 1:
        details = ", ".join(
            f"{source}={version}" for source, version in versions.items()
        )
        raise ValueError(f"Project versions are not synchronized: {details}")
    version = unique.pop()
    parse_version(version)
    if expected is not None and version != expected:
        raise ValueError(
            f"Project version {version} does not match expected {expected}"
        )
    return version
