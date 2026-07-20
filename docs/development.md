# Development

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 with npm
- `just`
- Docker for container checks

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

Docker and proxy smoke tests are separate because they require Docker
Engine:

```console
just compose-smoke
just proxy-smoke
```

The first command verifies health, the packaged frontend, the non-root
runtime user, read-only root filesystem, and graceful shutdown. The
second verifies private application networking plus the documented
request-size and rate-limit configuration.

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

Pull requests run formatting, linting, type checks, backend and frontend
tests, strict documentation builds, direct-dependency license policy
checks, and a production image build. Pushes to `main` additionally run
desktop/mobile browser tests and both Compose smoke suites.

A weekly security workflow runs Python and npm dependency audits,
CodeQL analysis, repository scanning, and the license inventory check.
Dependabot monitors uv, npm, Docker, Docker Compose, and GitHub Actions
dependencies.
