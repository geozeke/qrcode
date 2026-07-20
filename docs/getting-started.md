# Getting started

The recommended deployment method is Docker Compose. The application is
stateless and does not require a database or persistent volume.

## Requirements

- Docker Engine with the Docker Compose plugin
- A random render-token secret containing at least 32 bytes

## Start the application

Copy the example environment file:

```console
cp .env.example .env
```

Generate a secret and place it in `.env` as
`QR_RENDER_TOKEN_SECRET`:

```console
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Build and start the service:

```console
docker compose up --build --detach
```

Open <http://127.0.0.1:8080>. The default Compose configuration binds
only to host loopback because a reverse proxy is the recommended path
for public access.

## Check service health

```console
docker compose ps
```

The `qrcode` service becomes healthy after its local `/health` check
succeeds.

## Stop the application

```console
docker compose down
```
