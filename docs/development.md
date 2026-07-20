# Development

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 with npm
- `just`
- Docker Engine
- A current Docker Compose release, available as either `docker compose`
  or `docker-compose`

Verify the container tooling before running deployment tests:

```console
docker info
docker compose version  # or: docker-compose version
```

## Set up

```console
just setup
```

Run the backend and frontend development servers in separate terminals:

```console
QR_RENDER_TOKEN_SECRET="replace-with-at-least-32-random-bytes" \
  uv run uvicorn qrcode_web.app:create_app --factory --reload
```

```console
npm --prefix frontend run dev
```

The frontend development server proxies `/api` and `/health` to the
backend on port 8080.

## Quality checks

```console
just check
just test-e2e
```

Run the complete on-host deployment gate with:

```console
just deployment-test
```

This builds the production image and runs both the application and proxy
deployment suites against the host Docker Engine. The scripts accept
either the `docker compose` plugin form or the standalone
`docker-compose` command. The image installs pinned `uv` tooling and
syncs its production environment from `uv.lock` with Python 3.12.
Individual suites remain available with:

```console
just compose-smoke
just proxy-smoke
```

The application suite verifies health, a real preview/download cycle,
the packaged frontend, loopback binding, OCI metadata, resource limits,
the non-root runtime user, read-only root filesystem, and graceful
shutdown. The proxy suite verifies private application networking plus
loopback binding and the documented request-size and rate limits.

## Documentation

Documentation sources are Markdown files in `docs/`. Preview the site at
<http://localhost:8000> while editing:

```console
just docs-serve
```

Build the same strict static site used by GitHub Pages:

```console
just docs-build
```

The generated `site/` directory is build output and must not be
committed.

## Continuous integration

Pull requests and pushes to `main` run formatting, linting, type checks,
backend and frontend tests, strict documentation builds,
direct-dependency license policy checks, and the complete on-host Docker
deployment gate. Pushes to `main` additionally run desktop/mobile
browser tests. Release tags rerun the deployment gate against the exact
release candidate before publishing images.

A weekly security workflow runs Python and npm dependency audits,
CodeQL analysis, repository scanning, and the license inventory check.
Dependabot monitors uv, npm, Docker, Docker Compose, and GitHub Actions
dependencies.
