# QR Code Project Notes

This repository is for a planning-stage, self-hostable QR code generator
web app. The intended product is a focused utility for entering QR payloads,
configuring visual options, previewing the result, and downloading generated
codes.

## Current State

- `plan/scope.md` is the current source of truth for product scope,
  architecture direction, and open questions.
- `README.md` is currently only a stub.
- No application source exists yet. Do not add application code until the
  planning scope is agreed.

## Planned Entry Points

- Backend: Python/FastAPI, with internal HTTP routes for the web UI.
- Frontend: SvelteKit with TypeScript.
- Deployment: Docker, with Docker Compose as the main self-hosted setup.
- Python dependency management and tooling: Astral `uv`.
- Future source areas may include payload, format, rendering, export, API,
  and web modules.

## Working Constraints

- Do not traverse generated dependency or build-output directories such
  as `.venv/`, `node_modules/`, `dist/`, `build/`, `coverage/`, Python
  caches, or `uv` cache/artifact directories unless the task
  specifically requires it.
- Use `rg` for searches. Start repository exploration with `README.md`,
  `plan/scope.md`, and relevant source directories once they exist.
- Wrap Markdown prose to 72 characters when practical, but do not break links,
  code spans, tables, or other formatting that wrapping would harm.
- When making code changes, keep documentation and metadata consistent. This
  includes `README.md`, `AGENTS.md`, code comments, user-facing messages, and
  similar project text.
- Preserve scanner reliability over visual customization when those goals
  conflict.
- For Python code, prefer `pathlib.Path` objects over raw path strings
  where practical, use semantically equivalent truthiness checks, and use
  snake_case names.
- Use strict NumPy-style docstrings for Python modules, classes, and
  functions.
- Run Ruff through `uv` for Python code changes when project tooling is
  available.
- When reviewing or changing `.gitignore`, also inspect Git's configured
  global excludes and account for them in recommendations.
