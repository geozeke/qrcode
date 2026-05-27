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

- Backend: Go, with internal HTTP routes for the web UI.
- Frontend: TypeScript with a lightweight modern framework.
- Deployment: Docker, with Docker Compose as the main self-hosted setup.
- Future source areas may include payload, format, rendering, export, API,
  and web modules.

## Working Constraints

- Do not traverse generated dependency or build-output directories such
  as `node_modules/`, `dist/`, `build/`, `coverage/`, or Go build/test
  caches unless the task specifically requires it.
- Wrap Markdown prose to 72 characters when practical, but do not break links,
  code spans, tables, or other formatting that wrapping would harm.
- When making code changes, keep documentation and metadata consistent. This
  includes `README.md`, `AGENTS.md`, code comments, user-facing messages, and
  similar project text.
- Preserve scanner reliability over visual customization when those goals
  conflict.
