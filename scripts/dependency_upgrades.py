#!/usr/bin/env python3
"""Support direct-dependency reporting and upgrade commits.

Functions
---------
direct_python_dependencies
    Read direct Python dependency names from project metadata.
direct_javascript_dependencies
    Read direct JavaScript dependency names from package metadata.
outdated_dependencies
    Combine compatibility-resolved direct dependencies from both ecosystems.
resolve_compatible_python_lock
    Resolve compatible direct Python dependency upgrades in isolation.
dependency_updates
    Compare direct versions before and after an upgrade.
upgrade_candidates
    Select direct dependencies with compatible updates.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

COMMIT_SUBJECT = "build(deps): upgrade direct dependencies"
REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
UV_OUTDATED_RE = re.compile(
    r"^[├└]── (?P<name>[A-Za-z0-9_.-]+)(?:\[[^]]+\])? "
    r"v(?P<current>\S+).*latest: v(?P<latest>[^)\s]+)"
)


@dataclass(frozen=True)
class OutdatedDependency:
    """Represent an outdated direct dependency.

    Parameters
    ----------
    ecosystem
        Package ecosystem name.
    name
        Dependency name as declared by the project.
    current
        Currently locked version.
    wanted
        Newest version allowed by the declared constraint, when known.
    latest
        Latest version published by the package registry.
    """

    ecosystem: str
    name: str
    current: str
    wanted: str
    latest: str


@dataclass(frozen=True)
class DependencyUpdate:
    """Represent a changed direct dependency version.

    Parameters
    ----------
    ecosystem
        Package ecosystem name.
    name
        Dependency name as declared by the project.
    old_version
        Version locked before the upgrade.
    new_version
        Version locked after the upgrade.
    """

    ecosystem: str
    name: str
    old_version: str
    new_version: str


def normalize_python_name(name: str) -> str:
    """Normalize a Python distribution name.

    Parameters
    ----------
    name
        Distribution name.

    Returns
    -------
    str
        PEP 503-style normalized name.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str:
    """Extract a Python distribution name from a requirement.

    Parameters
    ----------
    requirement
        PEP 508 dependency requirement.

    Returns
    -------
    str
        Declared distribution name.

    Raises
    ------
    ValueError
        If the requirement does not begin with a distribution name.
    """
    match = REQUIREMENT_NAME_RE.match(requirement)
    if not match:
        raise ValueError(f"Could not parse dependency name from {requirement!r}")
    return match.group(1)


def direct_python_dependencies(pyproject_path: Path) -> dict[str, str]:
    """Read direct runtime and dependency-group package names.

    Parameters
    ----------
    pyproject_path
        Project metadata path.

    Returns
    -------
    dict[str, str]
        Normalized names mapped to their declared spelling.
    """
    metadata = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    requirements = list(metadata.get("project", {}).get("dependencies", []))
    for group in metadata.get("dependency-groups", {}).values():
        requirements.extend(group)

    dependencies: dict[str, str] = {}
    for requirement in requirements:
        name = requirement_name(str(requirement))
        dependencies.setdefault(normalize_python_name(name), name)
    return dependencies


def direct_javascript_dependencies(package_path: Path) -> dict[str, str]:
    """Read direct JavaScript dependency names.

    Parameters
    ----------
    package_path
        npm package metadata path.

    Returns
    -------
    dict[str, str]
        Dependency names mapped to their declared spelling.
    """
    metadata = json.loads(package_path.read_text(encoding="utf-8"))
    dependencies: dict[str, str] = {}
    for field in ("dependencies", "devDependencies", "optionalDependencies"):
        for name in metadata.get(field, {}):
            dependencies.setdefault(name, name)
    return dependencies


def resolve_compatible_python_lock(
    pyproject_path: Path,
    lock_path: Path,
    output_path: Path,
) -> None:
    """Resolve compatible direct Python upgrades without changing the project.

    Parameters
    ----------
    pyproject_path
        Project metadata path.
    lock_path
        Current uv lockfile path.
    output_path
        Destination for the resolved candidate lockfile.

    Raises
    ------
    subprocess.CalledProcessError
        If uv cannot resolve the candidate lockfile.

    Notes
    -----
    The resolver receives every direct Python dependency as an explicit
    upgrade target. Its output therefore reflects both the declared version
    ranges and the complete dependency graph, while leaving tracked files
    untouched.
    """
    dependencies = direct_python_dependencies(pyproject_path)
    with tempfile.TemporaryDirectory(prefix="qrcode-uv-upgrade-") as directory:
        project_directory = Path(directory)
        temporary_pyproject = project_directory / "pyproject.toml"
        temporary_lock = project_directory / "uv.lock"
        shutil.copy2(pyproject_path, temporary_pyproject)
        shutil.copy2(lock_path, temporary_lock)

        for filename in ("README.md", "LICENSE"):
            source = pyproject_path.parent / filename
            if source.is_file():
                shutil.copy2(source, project_directory / filename)

        command = ["uv", "lock", "--project", str(project_directory)]
        for name in dependencies.values():
            command.extend(("--upgrade-package", name))
        subprocess.run(command, check=True)
        shutil.copy2(temporary_lock, output_path)


def parse_uv_outdated(
    dependencies: dict[str, str], tree_output: str
) -> list[OutdatedDependency]:
    """Parse outdated direct Python dependencies from ``uv tree``.

    Parameters
    ----------
    dependencies
        Normalized direct dependency names and display names.
    tree_output
        Output from ``uv tree --outdated --depth=1``.

    Returns
    -------
    list[OutdatedDependency]
        Outdated direct dependencies in tree order.
    """
    outdated: list[OutdatedDependency] = []
    seen: set[str] = set()
    for line in tree_output.splitlines():
        match = UV_OUTDATED_RE.match(line)
        if not match:
            continue
        normalized_name = normalize_python_name(match.group("name"))
        if normalized_name not in dependencies or normalized_name in seen:
            continue
        seen.add(normalized_name)
        outdated.append(
            OutdatedDependency(
                ecosystem="Python",
                name=dependencies[normalized_name],
                current=match.group("current"),
                wanted=match.group("latest"),
                latest=match.group("latest"),
            )
        )
    return outdated


def parse_npm_outdated(
    dependencies: dict[str, str], outdated_output: str
) -> list[OutdatedDependency]:
    """Parse outdated direct JavaScript dependencies from npm JSON.

    Parameters
    ----------
    dependencies
        Direct dependency names and display names.
    outdated_output
        JSON output from ``npm outdated``.

    Returns
    -------
    list[OutdatedDependency]
        Outdated direct dependencies sorted by name.
    """
    metadata = json.loads(outdated_output or "{}")
    outdated: list[OutdatedDependency] = []
    for name in sorted(dependencies):
        details = metadata.get(name)
        if not isinstance(details, dict):
            continue
        current = details.get("current")
        wanted = details.get("wanted")
        latest = details.get("latest")
        if (
            not isinstance(current, str)
            or not isinstance(wanted, str)
            or not isinstance(latest, str)
        ):
            continue
        outdated.append(
            OutdatedDependency(
                ecosystem="JavaScript",
                name=dependencies[name],
                current=current,
                wanted=wanted,
                latest=latest,
            )
        )
    return outdated


def compatible_python_dependencies(
    pyproject_path: Path,
    current_lock_path: Path,
    candidate_lock_path: Path,
) -> list[OutdatedDependency]:
    """Return direct Python dependencies with compatible resolved upgrades.

    Parameters
    ----------
    pyproject_path
        Project metadata path.
    current_lock_path
        Existing uv lockfile path.
    candidate_lock_path
        Lockfile resolved with all direct packages as upgrade targets.

    Returns
    -------
    list[OutdatedDependency]
        Direct Python dependencies whose resolved version changes.
    """
    dependencies = direct_python_dependencies(pyproject_path)
    current_versions = locked_python_versions(current_lock_path)
    candidate_versions = locked_python_versions(candidate_lock_path)
    outdated: list[OutdatedDependency] = []
    for normalized_name, display_name in dependencies.items():
        current = current_versions.get(normalized_name)
        candidate = candidate_versions.get(normalized_name)
        if current and candidate and current != candidate:
            outdated.append(
                OutdatedDependency(
                    ecosystem="Python",
                    name=display_name,
                    current=current,
                    wanted=candidate,
                    latest=candidate,
                )
            )
    return outdated


def outdated_dependencies(
    pyproject_path: Path,
    package_path: Path,
    uv_lock_path: Path,
    candidate_uv_lock_path: Path,
    npm_outdated_path: Path,
) -> list[OutdatedDependency]:
    """Return outdated direct dependencies from both ecosystems.

    Parameters
    ----------
    pyproject_path
        Python project metadata path.
    package_path
        npm package metadata path.
    uv_lock_path
        Current uv lockfile path.
    candidate_uv_lock_path
        Candidate lockfile resolved with direct upgrades.
    npm_outdated_path
        Captured ``npm outdated --json`` output.

    Returns
    -------
    list[OutdatedDependency]
        Python dependencies followed by JavaScript dependencies.
    """
    javascript_dependencies = direct_javascript_dependencies(package_path)
    return [
        *compatible_python_dependencies(
            pyproject_path, uv_lock_path, candidate_uv_lock_path
        ),
        *parse_npm_outdated(
            javascript_dependencies,
            npm_outdated_path.read_text(encoding="utf-8"),
        ),
    ]


def upgrade_candidates(
    outdated: list[OutdatedDependency],
) -> list[OutdatedDependency]:
    """Select direct dependencies for compatible package-manager updates.

    Parameters
    ----------
    outdated
        Outdated direct dependencies reported by package managers.

    Returns
    -------
    list[OutdatedDependency]
        Python packages for uv constraint resolution and JavaScript
        packages whose npm ``wanted`` version differs from the current
        version.

    Notes
    -----
    Python compatibility is resolved before this function is called. npm
    exposes the newest compatible version as its ``wanted`` value.
    """
    return [item for item in outdated if item.current != item.wanted]


def locked_python_versions(lock_path: Path) -> dict[str, str]:
    """Read normalized package versions from a uv lockfile.

    Parameters
    ----------
    lock_path
        uv lockfile path.

    Returns
    -------
    dict[str, str]
        Normalized package names mapped to locked versions.
    """
    metadata = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    versions: dict[str, str] = {}
    for package in metadata.get("package", []):
        name = package.get("name")
        version = package.get("version")
        source = package.get("source", {})
        if name and version and not source.get("editable"):
            versions[normalize_python_name(str(name))] = str(version)
    return versions


def locked_javascript_versions(lock_path: Path) -> dict[str, str]:
    """Read installed package versions from an npm lockfile.

    Parameters
    ----------
    lock_path
        npm lockfile path.

    Returns
    -------
    dict[str, str]
        Package names mapped to locked versions.
    """
    metadata = json.loads(lock_path.read_text(encoding="utf-8"))
    packages = metadata.get("packages", {})
    versions: dict[str, str] = {}
    for location, details in packages.items():
        if not location.startswith("node_modules/") or "/node_modules/" in location:
            continue
        name = location.removeprefix("node_modules/")
        version = details.get("version")
        if isinstance(version, str):
            versions[name] = version
    return versions


def direct_version_snapshot(
    pyproject_path: Path,
    package_path: Path,
    uv_lock_path: Path,
    npm_lock_path: Path,
) -> dict[str, dict[str, str]]:
    """Snapshot locked versions for direct dependencies.

    Parameters
    ----------
    pyproject_path
        Python project metadata path.
    package_path
        npm package metadata path.
    uv_lock_path
        uv lockfile path.
    npm_lock_path
        npm lockfile path.

    Returns
    -------
    dict[str, dict[str, str]]
        Direct versions grouped by ecosystem.
    """
    python_dependencies = direct_python_dependencies(pyproject_path)
    python_versions = locked_python_versions(uv_lock_path)
    javascript_dependencies = direct_javascript_dependencies(package_path)
    javascript_versions = locked_javascript_versions(npm_lock_path)
    return {
        "python": {
            display_name: python_versions[normalized_name]
            for normalized_name, display_name in python_dependencies.items()
            if normalized_name in python_versions
        },
        "javascript": {
            display_name: javascript_versions[name]
            for name, display_name in javascript_dependencies.items()
            if name in javascript_versions
        },
    }


def dependency_updates(
    before: dict[str, dict[str, str]], after: dict[str, dict[str, str]]
) -> list[DependencyUpdate]:
    """Compare two direct dependency snapshots.

    Parameters
    ----------
    before
        Versions before an upgrade.
    after
        Versions after an upgrade.

    Returns
    -------
    list[DependencyUpdate]
        Changed direct dependencies grouped and sorted by ecosystem.
    """
    updates: list[DependencyUpdate] = []
    for key, label in (("python", "Python"), ("javascript", "JavaScript")):
        for name in sorted(before.get(key, {})):
            old_version = before[key][name]
            new_version = after.get(key, {}).get(name)
            if new_version and new_version != old_version:
                updates.append(DependencyUpdate(label, name, old_version, new_version))
    return updates


def render_commit_message(updates: list[DependencyUpdate]) -> str:
    """Render a Conventional Commit message for direct updates.

    Parameters
    ----------
    updates
        Changed direct dependency versions.

    Returns
    -------
    str
        Complete commit message.
    """
    lines = [COMMIT_SUBJECT, ""]
    lines.extend(
        f"- {update.ecosystem} {update.name}: "
        f"{update.old_version} -> {update.new_version}"
        for update in updates
    )
    return "\n".join(lines) + "\n"


def _load_outdated(args: argparse.Namespace) -> list[OutdatedDependency]:
    """Load outdated dependencies from parsed arguments."""
    return outdated_dependencies(
        args.pyproject,
        args.package_json,
        args.uv_lock,
        args.candidate_uv_lock,
        args.npm_outdated,
    )


def _report(args: argparse.Namespace) -> int:
    """Print a human-readable direct dependency report."""
    outdated = _load_outdated(args)
    if not outdated:
        print("No outdated top-level dependencies found.")
        return 0

    for ecosystem in ("Python", "JavaScript"):
        matches = [item for item in outdated if item.ecosystem == ecosystem]
        if not matches:
            continue
        print(f"{ecosystem}:")
        for item in matches:
            print(f"  {item.name}: {item.current} -> {item.wanted}")
    return 0


def _select(args: argparse.Namespace) -> int:
    """Print direct package names for shell upgrade orchestration."""
    for item in upgrade_candidates(_load_outdated(args)):
        print(f"{item.ecosystem.lower()}\t{item.name}")
    return 0


def _snapshot(args: argparse.Namespace) -> int:
    """Write a direct dependency version snapshot."""
    snapshot = direct_version_snapshot(
        args.pyproject,
        args.package_json,
        args.uv_lock,
        args.npm_lock,
    )
    args.output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return 0


def _message(args: argparse.Namespace) -> int:
    """Write a dependency upgrade commit message."""
    before: dict[str, dict[str, str]] = json.loads(
        args.before.read_text(encoding="utf-8")
    )
    after = direct_version_snapshot(
        args.pyproject,
        args.package_json,
        args.uv_lock,
        args.npm_lock,
    )
    updates = dependency_updates(before, after)
    if not updates:
        return 1
    args.output.write_text(render_commit_message(updates), encoding="utf-8")
    return 0


def _resolve_python(args: argparse.Namespace) -> int:
    """Write a compatibility-resolved candidate Python lockfile."""
    resolve_compatible_python_lock(args.pyproject, args.uv_lock, args.output)
    return 0


def _add_metadata_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared project metadata arguments to a parser."""
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument(
        "--package-json", type=Path, default=Path("frontend/package.json")
    )


def _add_outdated_arguments(parser: argparse.ArgumentParser) -> None:
    """Add captured outdated-output arguments to a parser."""
    _add_metadata_arguments(parser)
    parser.add_argument("--uv-lock", type=Path, default=Path("uv.lock"))
    parser.add_argument("--candidate-uv-lock", type=Path, required=True)
    parser.add_argument("--npm-outdated", type=Path, required=True)


def _add_lock_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared lockfile arguments to a parser."""
    _add_metadata_arguments(parser)
    parser.add_argument("--uv-lock", type=Path, default=Path("uv.lock"))
    parser.add_argument(
        "--npm-lock", type=Path, default=Path("frontend/package-lock.json")
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser("report")
    _add_outdated_arguments(report)
    report.set_defaults(func=_report)

    select = subparsers.add_parser("select")
    _add_outdated_arguments(select)
    select.set_defaults(func=_select)

    resolve_python = subparsers.add_parser("resolve-python")
    resolve_python.add_argument(
        "--pyproject", type=Path, default=Path("pyproject.toml")
    )
    resolve_python.add_argument("--uv-lock", type=Path, default=Path("uv.lock"))
    resolve_python.add_argument("--output", type=Path, required=True)
    resolve_python.set_defaults(func=_resolve_python)

    snapshot = subparsers.add_parser("snapshot")
    _add_lock_arguments(snapshot)
    snapshot.add_argument("--output", type=Path, required=True)
    snapshot.set_defaults(func=_snapshot)

    message = subparsers.add_parser("message")
    _add_lock_arguments(message)
    message.add_argument("--before", type=Path, required=True)
    message.add_argument("--output", type=Path, required=True)
    message.set_defaults(func=_message)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface.

    Parameters
    ----------
    argv
        Optional command-line arguments.

    Returns
    -------
    int
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
