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
