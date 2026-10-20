"""Tests for synchronized uv toolchain maintenance helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import uv_tools  # noqa: E402
from scripts.changelog_tools import parse_version  # noqa: E402
from scripts.uv_tools import check_uv_versions, update_uv_version, verify_uv_release  # noqa: E402


@pytest.fixture(autouse=True)
def mock_release_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep updater tests independent of the external release service."""
    monkeypatch.setattr(
        uv_tools,
        "verify_uv_release",
        lambda version: parse_version(version).text,
    )


def write_uv_references(root: Path, version: str = "1.2.3") -> None:
    """Write a minimal repository with all tracked uv version references."""
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "config").mkdir()
    (root / "Dockerfile").write_text(
        f"FROM ghcr.io/astral-sh/uv:{version} AS uv\n",
        encoding="utf-8",
    )
    (root / ".github" / "workflows" / "quality.yml").write_text(
        "steps:\n"
        "  - uses: astral-sh/setup-uv@abc\n"
        "    with:\n"
        f'      version: "{version}"\n'
        "  - uses: astral-sh/setup-uv@def\n"
        "    with:\n"
        f'      version: "{version}"\n',
        encoding="utf-8",
    )
    (root / "scripts" / "deployment_test.sh").write_text(
        f'    "uv {version} "*) ;;\n',
        encoding="utf-8",
    )
    (root / "config" / "dependency-licenses.toml").write_text(
        f'[containers]\n"ghcr.io/astral-sh/uv:{version}" = "Apache-2.0 OR MIT"\n',
        encoding="utf-8",
    )


def test_check_uv_versions_reads_synchronized_references(tmp_path: Path) -> None:
    """A complete repository reports its one shared uv version."""
    write_uv_references(tmp_path)

    assert check_uv_versions(tmp_path) == "1.2.3"


def test_update_uv_version_updates_every_reference(tmp_path: Path) -> None:
    """One update replaces Docker, workflow, test, and license references."""
    write_uv_references(tmp_path)

    update_uv_version("2.3.4", tmp_path)

    assert check_uv_versions(tmp_path) == "2.3.4"
    assert "1.2.3" not in "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            tmp_path / "Dockerfile",
            tmp_path / ".github" / "workflows" / "quality.yml",
            tmp_path / "scripts" / "deployment_test.sh",
            tmp_path / "config" / "dependency-licenses.toml",
        )
    )


def test_check_uv_versions_rejects_mismatched_references(tmp_path: Path) -> None:
    """A mismatched tracked reference reports every observed version."""
    write_uv_references(tmp_path)
    deployment_path = tmp_path / "scripts" / "deployment_test.sh"
    deployment_path.write_text('    "uv 2.3.4 "*) ;;\n', encoding="utf-8")

    with pytest.raises(ValueError, match="uv versions are not synchronized"):
        check_uv_versions(tmp_path)


def test_update_uv_version_rejects_invalid_version(tmp_path: Path) -> None:
    """Malformed version input does not modify repository references."""
    write_uv_references(tmp_path)

    with pytest.raises(ValueError, match="bare semantic version"):
        update_uv_version("v2.3.4", tmp_path)

    assert check_uv_versions(tmp_path) == "1.2.3"


def test_verify_uv_release_accepts_published_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing Astral release tag is accepted before updating references."""
    requested_urls = []

    class Response:
        """Minimal context-managed HTTP response fixture."""

        def __enter__(self) -> Response:
            """Return the response context value."""
            return self

        def __exit__(self, *args: object) -> None:
            """Close the response context without suppressing errors."""

    def fake_urlopen(request: object, timeout: int) -> Response:
        """Capture the release URL and return a successful response."""
        assert timeout == 10
        requested_urls.append(request.full_url)
        return Response()

    monkeypatch.setattr(uv_tools, "urlopen", fake_urlopen)

    assert verify_uv_release("2.3.4") == "2.3.4"
    assert requested_urls == [
        "https://api.github.com/repos/astral-sh/uv/releases/tags/2.3.4"
    ]


def test_verify_uv_release_rejects_missing_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing release tag prevents any update."""

    def fake_urlopen(request: object, timeout: int) -> None:
        """Raise the HTTP error GitHub uses for an unknown tag."""
        del request, timeout
        raise HTTPError("https://example.test", 404, "Not Found", {}, None)

    monkeypatch.setattr(uv_tools, "urlopen", fake_urlopen)

    with pytest.raises(ValueError, match="is not a published Astral release"):
        verify_uv_release("2.3.4")


def test_verify_uv_release_reports_unavailable_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connectivity failure does not allow an unverified version update."""

    def fake_urlopen(request: object, timeout: int) -> None:
        """Raise a representative network failure."""
        del request, timeout
        raise URLError("network unavailable")

    monkeypatch.setattr(uv_tools, "urlopen", fake_urlopen)

    with pytest.raises(ValueError, match="Unable to verify uv"):
        verify_uv_release("2.3.4")


def test_update_uv_version_rejects_missing_reference(tmp_path: Path) -> None:
    """A missing expected reference prevents an incomplete update."""
    write_uv_references(tmp_path)
    (tmp_path / "Dockerfile").write_text("FROM python:3.14-slim\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected exactly one uv image reference"):
        update_uv_version("2.3.4", tmp_path)


def test_update_uv_version_rejects_ambiguous_reference(tmp_path: Path) -> None:
    """Duplicate expected references prevent a partial toolchain update."""
    write_uv_references(tmp_path)
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text(encoding="utf-8")
        + "FROM ghcr.io/astral-sh/uv:1.2.3 AS uv\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Expected exactly one uv image reference"):
        update_uv_version("2.3.4", tmp_path)
