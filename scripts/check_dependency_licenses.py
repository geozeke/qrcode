"""Verify that every direct dependency has an approved license record."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"^[A-Za-z0-9_.-]+")
APPROVED = {
    "Apache-2.0",
    "Apache-2.0 OR MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "MIT",
    "MIT-CMU",
    "PSF-2.0",
}


def dependency_name(requirement: str) -> str:
    """Extract and normalize a package name from a PEP 508 requirement."""
    match = NAME.match(requirement)
    if match is None:
        raise ValueError(f"Invalid dependency requirement: {requirement}")
    return match.group().lower().replace("_", "-")


def main() -> None:
    """Compare dependency manifests with the reviewed license inventory."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    python_dependencies = {
        dependency_name(requirement)
        for requirement in project["project"]["dependencies"]
    }
    for group in project["dependency-groups"].values():
        python_dependencies.update(
            dependency_name(requirement) for requirement in group
        )

    package = json.loads((ROOT / "frontend" / "package.json").read_text())
    javascript_dependencies = set(package.get("dependencies", {}))
    javascript_dependencies.update(package.get("devDependencies", {}))

    dockerfile = (ROOT / "Dockerfile").read_text()
    container_dependencies = set(re.findall(r"(?m)^FROM\s+(\S+)", dockerfile))
    tool_dependencies = set(
        re.findall(r'"([A-Za-z0-9_.-]+)==\$\{[A-Z0-9_]+\}"', dockerfile)
    )
    for compose_file in ROOT.glob("compose*.yaml"):
        for image in re.findall(r"(?m)^\s+image:\s+([^\s]+)", compose_file.read_text()):
            if not image.startswith("${"):
                container_dependencies.add(image)

    action_dependencies: set[str] = set()
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        action_dependencies.update(
            action
            for action in re.findall(
                r"(?m)^\s+-?\s*uses:\s+([^@\s]+)@[^\s]+", workflow.read_text()
            )
            if not action.startswith("./")
        )

    inventory = tomllib.loads(
        (ROOT / "config" / "dependency-licenses.toml").read_text()
    )
    recorded_python = set(inventory["python"])
    recorded_javascript = set(inventory["javascript"])
    recorded_containers = set(inventory["containers"])
    recorded_tools = set(inventory["tools"])
    recorded_actions = set(inventory["actions"])
    problems: list[str] = []
    for ecosystem, expected, recorded in (
        ("Python", python_dependencies, recorded_python),
        ("JavaScript", javascript_dependencies, recorded_javascript),
        ("Container", container_dependencies, recorded_containers),
        ("Tool", tool_dependencies, recorded_tools),
        ("GitHub Actions", action_dependencies, recorded_actions),
    ):
        if missing := sorted(expected - recorded):
            problems.append(
                f"{ecosystem} dependencies missing license records: {missing}"
            )
        if extra := sorted(recorded - expected):
            problems.append(f"Stale {ecosystem} license records: {extra}")
    for ecosystem in ("python", "javascript", "containers", "tools", "actions"):
        for dependency, license_name in inventory[ecosystem].items():
            if license_name not in APPROVED:
                problems.append(
                    f"{dependency} uses unapproved license {license_name!r}"
                )
    if problems:
        raise SystemExit("\n".join(problems))
    print("All direct dependencies have approved license records.")


if __name__ == "__main__":
    main()
