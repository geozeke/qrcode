# Getting started

Deploy QR Code Generator with Docker Compose. The application is
stateless and does not require a database or persistent volume.

## Requirements

- Docker Engine
- A current Docker Compose plugin that provides `docker compose`
- The Docker Hub repository path for the published image

## Create `compose.yaml`

Copy the following block with its copy button and save it as
`compose.yaml` on the Docker host:

```yaml
services:
  qrcode:
    image: docker.io/<maintainer-namespace>/qrcode:latest
    pull_policy: always
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      QR_RENDER_TOKEN_SECRET: replace-with-a-random-secret-of-at-least-32-bytes
    init: true
    read_only: true
    tmpfs:
      - /tmp:size=64m,mode=1777
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    pids_limit: 128
    mem_limit: 512m
    cpus: 1.0
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - >-
          import urllib.request;
          urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
```

Make the following minimal changes before starting the service.

### Select the image

Replace `<maintainer-namespace>` with the Docker Hub namespace shown for
the published image. Stable releases provide exact semantic version
tags, a mutable major/minor tag, and `latest`. Releases at `1.0.0` and
later also provide a mutable major tag; major-zero releases omit the
incompatible `0` tag. Prereleases provide only exact version tags. Use
an exact version instead of a floating tag when deployments must be
reproducible.

### Set the render-token secret

Generate a random secret:

```console
openssl rand -hex 32
```

Replace the example `QR_RENDER_TOKEN_SECRET` value with the command's
output. Do not reuse the documented example value.

### Choose the host port

If port 8080 is already in use, change only the host-side port in
`127.0.0.1:8080:8080`. For example, use `127.0.0.1:9080:8080` to listen
on port 9080.

Keep the `127.0.0.1` binding when a reverse proxy runs directly on the
Docker host. See [Deployment topology](deployment.md) before exposing
the application publicly or connecting it to a containerized proxy.

## Start the application

From the directory containing `compose.yaml`, run:

```console
docker compose up --force-recreate -d
```

Because the configuration uses `pull_policy: always`, Compose retrieves
the selected image before recreating the container.

## Verify the deployment

```console
docker compose ps
```

Wait for the `qrcode` service to report `healthy`, then open
<http://127.0.0.1:8080>, using the adjusted host port if you changed it.

Follow application logs when troubleshooting:

```console
docker compose logs --follow qrcode
```

## Update the application

Change the image tag if necessary, then retrieve the selected image and
replace the container with the same startup command:

```console
docker compose up --force-recreate -d
```

## Stop the application

```console
docker compose down
```

No application data is lost when the container is replaced or removed.
