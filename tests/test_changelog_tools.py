"""Tests for changelog and release-maintenance helpers."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import bump_version as bump_version_script  # noqa: E402
from scripts import tag_release as tag_release_script  # noqa: E402
from scripts.changelog_tools import (  # noqa: E402
    Section,
    archive_changelog,
    extract_release_notes,
    has_release_entries,
    merge_unreleased,
    parse_version,
    split_changelog,
    validate_commit_title,
    validate_project_version,
)

PREAMBLE = "# Changelog\n\nRelease history."


def release(version: str, note: str = "Changed") -> str:
    """Return a minimal release section."""
    return f"## [{version}] - 2026-07-20\n\n### Changed\n\n- {note}"


@pytest.mark.parametrize(
    "version",
    ("0.1.0", "1.2.3-beta.1", "2.0.0-rc.2"),
)
def test_parse_version_accepts_supported_semver(version: str) -> None:
    """Supported stable and prerelease versions parse."""
    assert parse_version(version).text == version


@pytest.mark.parametrize(
    "version", ("v1.2.3", "1.2", "1.2.3+build", "01.2.3", "1.2.3-rc.01")
)
def test_parse_version_rejects_unsupported_values(version: str) -> None:
    """Leading v, build metadata, and malformed versions are rejected."""
    with pytest.raises(ValueError, match="semantic version|leading zeros"):
        parse_version(version)


@pytest.mark.parametrize(
    "title",
    (
        "feat: add QR export",
        "fix(a11y): label the preview",
        "deploy(compose)!: rename the secret",
        "build(deps-dev): bump pytest",
        "security: reject forged tokens",
    ),
)
def test_validate_commit_title_accepts_documented_types(title: str) -> None:
    """Documented Conventional Commit titles are accepted."""
    validate_commit_title(title)


@pytest.mark.parametrize(
    "title",
    ("Add QR export", "unknown: change", "fix(): empty scope", "fix missing colon"),
)
def test_validate_commit_title_rejects_invalid_titles(title: str) -> None:
    """Unclassified and malformed titles are rejected."""
    with pytest.raises(ValueError, match="Conventional Commit"):
        validate_commit_title(title)


def test_merge_unreleased_combines_matching_groups() -> None:
    """The curated initial baseline merges with generated release notes."""
    generated = Section(
        "0.1.0",
        release("0.1.0", "Generated entry"),
    )
    curated = Section(
        "Unreleased",
        "## [Unreleased]\n\n### Changed\n\n- Curated entry\n\n"
        "### Security\n\n- Safe by default",
    )

    merged = merge_unreleased(generated, curated)

    assert merged.text.count("### Changed") == 1
    assert "- Curated entry\n- Generated entry" in merged.text
    assert "### Security" in merged.text
    assert has_release_entries(merged)


def test_archive_changelog_moves_inactive_minor_lines(tmp_path: Path) -> None:
    """A new minor line archives older releases and retains the active line."""
    changelog = tmp_path / "CHANGELOG.md"
    archives = tmp_path / "changelogs"
    changelog.write_text(
        f"{PREAMBLE}\n\n{release('0.2.0')}\n\n{release('0.1.1')}\n\n"
        f"{release('0.1.0')}\n",
        encoding="utf-8",
    )

    updated = archive_changelog("0.2.0", changelog, archives)

    assert updated == [archives / "v0.1.x.md"]
    active = changelog.read_text(encoding="utf-8")
    assert "[0.2.0]" in active
    assert "[0.1.1]" not in active
    archived = updated[0].read_text(encoding="utf-8")
    assert archived.index("[0.1.1]") < archived.index("[0.1.0]")


def test_archive_changelog_keeps_patch_and_prerelease_line(tmp_path: Path) -> None:
    """Patch and prerelease entries remain together in the active minor line."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        f"{PREAMBLE}\n\n{release('1.4.1')}\n\n{release('1.4.0-rc.1')}\n",
        encoding="utf-8",
    )

    assert archive_changelog("1.4.1", changelog, tmp_path / "changelogs") == []
    assert "[1.4.0-rc.1]" in changelog.read_text(encoding="utf-8")


def test_archive_changelog_merges_an_existing_archive(tmp_path: Path) -> None:
    """Newly moved releases merge with existing archive entries once."""
    changelog = tmp_path / "CHANGELOG.md"
    archives = tmp_path / "changelogs"
    archives.mkdir()
    changelog.write_text(
        f"{PREAMBLE}\n\n{release('0.2.0')}\n\n{release('0.1.1')}\n",
        encoding="utf-8",
    )
    archive = archives / "v0.1.x.md"
    archive.write_text(f"# Archive\n\n{release('0.1.0')}\n", encoding="utf-8")

    archive_changelog("0.2.0", changelog, archives)
    archived = archive.read_text(encoding="utf-8")

    assert archived.count("## [0.1.1]") == 1
    assert archived.count("## [0.1.0]") == 1
    assert archived.index("[0.1.1]") < archived.index("[0.1.0]")


def test_extract_release_notes_uses_active_then_archive(tmp_path: Path) -> None:
    """Release notes are found in both active and archived changelogs."""
    changelog = tmp_path / "CHANGELOG.md"
    archives = tmp_path / "changelogs"
    archives.mkdir()
    changelog.write_text(
        f"{PREAMBLE}\n\n{release('0.2.0', 'Active')}\n", encoding="utf-8"
    )
    (archives / "v0.1.x.md").write_text(
        f"# Archive\n\n{release('0.1.0', 'Archived')}\n", encoding="utf-8"
    )

    assert "- Active" in extract_release_notes("v0.2.0", changelog, archives)
    archived = extract_release_notes("v0.1.0", changelog, archives)
    assert "- Archived" in archived
    assert "## [0.1.0]" not in archived


def test_extract_release_notes_rejects_missing_and_empty_notes(tmp_path: Path) -> None:
    """Missing and empty release sections fail closed."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(f"{PREAMBLE}\n\n## [0.1.0] - 2026-07-20\n", encoding="utf-8")

    with pytest.raises(ValueError, match="empty"):
        extract_release_notes("v0.1.0", changelog, tmp_path / "changelogs")
    with pytest.raises(ValueError, match="not found"):
        extract_release_notes("v0.2.0", changelog, tmp_path / "changelogs")


def test_extract_release_notes_rejects_active_archive_duplicate(tmp_path: Path) -> None:
    """The same release cannot exist in active and archived changelogs."""
    changelog = tmp_path / "CHANGELOG.md"
    archives = tmp_path / "changelogs"
    archives.mkdir()
    content = f"{PREAMBLE}\n\n{release('0.1.0')}\n"
    changelog.write_text(content, encoding="utf-8")
    (archives / "v0.1.x.md").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate"):
        extract_release_notes("v0.1.0", changelog, archives)


def test_split_changelog_preserves_unreleased_section() -> None:
    """The initial Unreleased baseline is parsed as a normal section."""
    preamble, sections = split_changelog(
        f"{PREAMBLE}\n\n## [Unreleased]\n\n### Added\n\n- Initial"
    )

    assert preamble == PREAMBLE
    assert sections == [
        Section("Unreleased", "## [Unreleased]\n\n### Added\n\n- Initial")
    ]


def write_version_files(project_root: Path, version: str = "0.1.0") -> None:
    """Write minimal synchronized project metadata for release tests."""
    (project_root / "frontend").mkdir()
    (project_root / "pyproject.toml").write_text(
        f'[project]\nname = "qrcode-web"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (project_root / "uv.lock").write_text(
        f'version = 1\n\n[[package]]\nname = "qrcode-web"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    package = {"name": "qrcode-web-frontend", "version": version}
    (project_root / "frontend/package.json").write_text(
        json.dumps(package), encoding="utf-8"
    )
    package_lock = {
        "name": "qrcode-web-frontend",
        "version": version,
        "packages": {"": package},
    }
    (project_root / "frontend/package-lock.json").write_text(
        json.dumps(package_lock), encoding="utf-8"
    )


def run_git(project_root: Path, *args: str) -> str:
    """Run Git in a temporary release repository."""
    return subprocess.run(
        ("git", *args),
        cwd=project_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def create_release_repository(tmp_path: Path) -> Path:
    """Create a clean main branch with a local bare origin."""
    project_root = tmp_path / "project"
    origin = tmp_path / "origin.git"
    project_root.mkdir()
    run_git(project_root, "init", "--initial-branch=main")
    run_git(project_root, "config", "user.name", "Release Test")
    run_git(project_root, "config", "user.email", "release@example.test")
    write_version_files(project_root)
    (project_root / "CHANGELOG.md").write_text(
        f"{PREAMBLE}\n\n{release('0.1.0', 'First release')}\n", encoding="utf-8"
    )
    run_git(project_root, "add", ".")
    run_git(project_root, "commit", "--message", "chore(release): prepare for 0.1.0")
    subprocess.run(
        ("git", "init", "--bare", str(origin)), check=True, capture_output=True
    )
    run_git(project_root, "remote", "add", "origin", str(origin))
    run_git(project_root, "push", "--set-upstream", "origin", "main")
    return project_root


def test_validate_project_version_rejects_mismatched_metadata(tmp_path: Path) -> None:
    """Release validation fails when frontend and backend versions drift."""
    write_version_files(tmp_path)
    package_path = tmp_path / "frontend/package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = "0.2.0"
    package_path.write_text(json.dumps(package), encoding="utf-8")

    with pytest.raises(ValueError, match="not synchronized"):
        validate_project_version(tmp_path)


def test_tag_release_creates_and_pushes_annotated_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid release creates one annotated tag on the matching origin."""
    project_root = create_release_repository(tmp_path)
    monkeypatch.setattr(tag_release_script, "PROJECT_ROOT", project_root)

    tag = tag_release_script.tag_release()

    assert tag == "v0.1.0"
    assert run_git(project_root, "cat-file", "-t", tag) == "tag"
    assert run_git(project_root, "ls-remote", "--tags", "origin", f"refs/tags/{tag}")


def test_tag_release_rejects_untracked_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Untracked files make release tagging fail closed."""
    project_root = create_release_repository(tmp_path)
    (project_root / "untracked.txt").write_text("dirty", encoding="utf-8")
    monkeypatch.setattr(tag_release_script, "PROJECT_ROOT", project_root)

    with pytest.raises(ValueError, match="clean"):
        tag_release_script.tag_release()


def test_release_commit_validation_rejects_nonconventional_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release preparation rejects direct non-Conventional commits."""

    def fake_run(*args: str, capture: bool = False) -> str:
        assert args == (
            "git",
            "log",
            "v0.1.0..HEAD",
            "--no-merges",
            "--format=%s",
        )
        assert capture
        return "feat: valid change\nPlain-language commit\n"

    monkeypatch.setattr(bump_version_script, "run", fake_run)

    with pytest.raises(ValueError, match="Plain-language commit"):
        bump_version_script.validate_release_commits(["v0.1.0"])


def test_bump_restores_versions_after_command_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed metadata command restores every file changed by the bump."""
    write_version_files(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        f"{PREAMBLE}\n\n## [Unreleased]\n\n### Added\n\n- Initial\n",
        encoding="utf-8",
    )
    version_paths = (
        tmp_path / "pyproject.toml",
        tmp_path / "uv.lock",
        tmp_path / "frontend/package.json",
        tmp_path / "frontend/package-lock.json",
        changelog,
    )
    originals = {path: path.read_bytes() for path in version_paths}

    def fake_run(*args: str, capture: bool = False) -> str:
        if args[:2] == ("git", "tag"):
            return "v0.1.0\n"
        if args[:2] == ("uv", "version"):
            (tmp_path / "pyproject.toml").write_text("changed", encoding="utf-8")
            (tmp_path / "uv.lock").write_text("changed", encoding="utf-8")
            return ""
        if args[0] == "npm":
            raise subprocess.CalledProcessError(1, args)
        raise AssertionError(f"Unexpected command: {args}, capture={capture}")

    def fake_prepare(
        version: str,
        destination: Path,
        archive_dir: Path,
        promotion_from: str | None = None,
    ) -> None:
        del archive_dir, promotion_from
        destination.write_text(
            f"{PREAMBLE}\n\n{release(version, 'Prepared')}\n", encoding="utf-8"
        )

    monkeypatch.setattr(bump_version_script, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(bump_version_script, "run", fake_run)
    monkeypatch.setattr(bump_version_script, "require_clean_tree", lambda: None)
    monkeypatch.setattr(
        bump_version_script, "validate_release_commits", lambda tags: None
    )
    monkeypatch.setattr(bump_version_script, "prepare_changelog", fake_prepare)
    monkeypatch.setattr(bump_version_script.shutil, "which", lambda command: command)

    with pytest.raises(subprocess.CalledProcessError):
        bump_version_script.bump("0.2.0")

    assert {path: path.read_bytes() for path in version_paths} == originals
