# QR Code Project Notes

This repository contains a self-hostable QR code generator web app. The
product is a focused utility for entering QR payloads, configuring visual
options, previewing the result, and downloading generated codes.

## Current State

- `plan/scope.md` is the current source of truth for product scope,
  architecture direction, and accepted decisions.
- `README.md` is a concise project entry point. Detailed documentation
  lives as Markdown in `docs/` and is built with Zensical.
- Application implementation is underway. Keep changes within the agreed
  scope unless the user explicitly changes it.

## Entry Points

- Backend: Python/FastAPI, with internal HTTP routes for the web UI.
- Frontend: SvelteKit with TypeScript.
- Deployment: Docker, with Docker Compose as the main self-hosted setup.
- Python dependency management and tooling: Astral `uv`.
- Backend source is under `src/qrcode_web/`, frontend source is under
  `frontend/`, and backend tests are under `tests/`.

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
- Keep detailed user, deployment, and contributor documentation in
  `docs/`. Keep `README.md` intentionally concise and link into the
  documentation site and local Markdown sources.
- Run `just docs-build` after documentation or Zensical configuration
  changes. GitHub Pages publishes the strict Zensical build from `main`.
- Use Conventional Commit titles for pull requests. Changelog-visible
  types and release steps are documented in `docs/development.md`.
- Do not edit generated release or archive sections directly. Preview
  pending entries with `just changelog` and prepare releases with
  `just bump <version>`.
- When reviewing or changing `.gitignore`, also inspect Git's configured
  global excludes and account for them in recommendations.
