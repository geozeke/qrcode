# QR Code Generator

A private, stateless, self-hostable web application for creating
scanner-safe QR codes and exporting them as PNG, JPG, SVG, or PDF.

The project is under active development. User, deployment, and
contributor documentation lives in [`docs/`](docs/index.md) and is
published at <https://geozeke.github.io/qrcode/>.

## Quick start

Copy `.env.example` to `.env`, replace the example render-token secret,
then run:

```console
docker compose up --build
```

Open <http://127.0.0.1:8080>. Public deployments should place the app
behind a reverse proxy.

## Documentation

Preview the Zensical documentation locally with:

```console
just docs-serve
```

See the [development guide](docs/development.md) for the complete local
workflow.
