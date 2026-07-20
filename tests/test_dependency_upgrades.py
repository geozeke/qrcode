"""Tests for direct dependency upgrade helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.changelog_tools import validate_commit_title  # noqa: E402
from scripts.dependency_upgrades import (  # noqa: E402
    COMMIT_SUBJECT,
    DependencyUpdate,
    dependency_updates,
    direct_javascript_dependencies,
    direct_python_dependencies,
    direct_version_snapshot,
    parse_npm_outdated,
    parse_uv_outdated,
    render_commit_message,
    upgrade_candidates,
)


def test_direct_python_dependencies_includes_all_declared_groups(
    tmp_path: Path,
) -> None:
    """Runtime and named dependency groups are first-order dependencies."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["FastAPI>=0.115", "uvicorn[standard]>=0.34"]

[dependency-groups]
dev = ["pytest>=9", "types_reportlab>=4"]
docs = ["zensical>=0.0.51"]
""".strip(),
        encoding="utf-8",
    )

    assert direct_python_dependencies(pyproject) == {
        "fastapi": "FastAPI",
        "uvicorn": "uvicorn",
        "pytest": "pytest",
        "types-reportlab": "types_reportlab",
        "zensical": "zensical",
    }


def test_direct_javascript_dependencies_includes_supported_sections(
    tmp_path: Path,
) -> None:
    """Runtime, development, and optional npm dependencies are direct."""
    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps(
            {
                "dependencies": {"svelte": "^5"},
                "devDependencies": {"@playwright/test": "^1"},
                "optionalDependencies": {"sharp": "^1"},
            }
        ),
        encoding="utf-8",
    )

    assert direct_javascript_dependencies(package_json) == {
        "svelte": "svelte",
        "@playwright/test": "@playwright/test",
        "sharp": "sharp",
    }


def test_parse_uv_outdated_excludes_transitive_and_duplicate_packages() -> None:
    """Only declared depth-one Python dependencies are selected once."""
    output = """
qrcode-web v0.1.0
├── FastAPI v0.115.0 (latest: v0.139.2)
│   └── starlette v0.40.0 (latest: v0.50.0)
├── uvicorn[standard] v0.34.0 (latest: v0.51.0)
└── fastapi v0.115.0 (latest: v0.139.2)
"""

    outdated = parse_uv_outdated(
        {
            "fastapi": "FastAPI",
            "uvicorn": "uvicorn",
            "starlette": "starlette",
        },
        output,
    )

    assert [(item.name, item.current, item.latest) for item in outdated] == [
        ("FastAPI", "0.115.0", "0.139.2"),
        ("uvicorn", "0.34.0", "0.51.0"),
    ]


def test_parse_npm_outdated_excludes_transitive_packages() -> None:
    """Npm output is intersected with package.json direct dependencies."""
    output = json.dumps(
        {
            "@playwright/test": {
                "current": "1.53.0",
                "wanted": "1.61.1",
                "latest": "1.61.1",
            },
            "vite": {"current": "6.4.3", "wanted": "6.4.3", "latest": "7.0.0"},
            "esbuild": {"current": "0.25.0", "wanted": "0.25.1", "latest": "0.25.1"},
        }
    )

    outdated = parse_npm_outdated(
        {"@playwright/test": "@playwright/test", "vite": "vite"}, output
    )

    assert [(item.name, item.wanted, item.latest) for item in outdated] == [
        ("@playwright/test", "1.61.1", "1.61.1"),
        ("vite", "6.4.3", "7.0.0"),
    ]
    assert [item.name for item in upgrade_candidates(outdated)] == ["@playwright/test"]


def test_direct_version_snapshot_reads_both_lockfile_formats(
    tmp_path: Path,
) -> None:
    """Snapshots contain direct versions and omit transitive packages."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\ndependencies = ["FastAPI>=0.115"]\n', encoding="utf-8"
    )
    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps({"devDependencies": {"@playwright/test": "^1"}}),
        encoding="utf-8",
    )
    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_text(
        """
[[package]]
name = "fastapi"
version = "0.139.2"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "starlette"
version = "0.50.0"
source = { registry = "https://pypi.org/simple" }
""".strip(),
        encoding="utf-8",
    )
    npm_lock = tmp_path / "package-lock.json"
    npm_lock.write_text(
        json.dumps(
            {
                "packages": {
                    "": {},
                    "node_modules/@playwright/test": {"version": "1.61.1"},
                    "node_modules/vite": {"version": "6.4.3"},
                    "node_modules/a/node_modules/vite": {"version": "5.0.0"},
                }
            }
        ),
        encoding="utf-8",
    )

    assert direct_version_snapshot(pyproject, package_json, uv_lock, npm_lock) == {
        "python": {"FastAPI": "0.139.2"},
        "javascript": {"@playwright/test": "1.61.1"},
    }


def test_dependency_updates_and_message_include_only_changed_direct_versions() -> None:
    """The commit message lists direct changes and uses an accepted title."""
    before = {
        "python": {"fastapi": "0.115.0", "segno": "1.6.6"},
        "javascript": {"vite": "6.3.0"},
    }
    after = {
        "python": {"fastapi": "0.139.2", "segno": "1.6.6"},
        "javascript": {"vite": "6.4.3"},
    }

    updates = dependency_updates(before, after)

    assert updates == [
        DependencyUpdate("Python", "fastapi", "0.115.0", "0.139.2"),
        DependencyUpdate("JavaScript", "vite", "6.3.0", "6.4.3"),
    ]
    message = render_commit_message(updates)
    assert "segno" not in message
    assert "- Python fastapi: 0.115.0 -> 0.139.2" in message
    assert "- JavaScript vite: 6.3.0 -> 6.4.3" in message
    validate_commit_title(COMMIT_SUBJECT)


def test_dependency_updates_returns_empty_when_only_transitives_change() -> None:
    """An unchanged direct snapshot does not produce a dependency commit."""
    snapshot = {
        "python": {"fastapi": "0.139.2"},
        "javascript": {"vite": "6.4.3"},
    }

    assert dependency_updates(snapshot, snapshot) == []
