# Deployment

## Quick start

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

Before starting the service:

- replace `<maintainer-namespace>` with the Docker Hub namespace shown
  for the published image;
- replace `QR_RENDER_TOKEN_SECRET` with a random value of at least 32
  bytes, such as the output of `openssl rand -hex 32`; and
- change the host-side `8080` in `127.0.0.1:8080:8080` if that port is
  already in use.

From the directory containing `compose.yaml`, start or replace the
service:

```console
docker compose up --force-recreate -d
```

Open <http://127.0.0.1:8080>, using the adjusted host port if you changed
it. Keep the loopback binding when a reverse proxy runs on the Docker
host; see the topology guidance below for a containerized proxy.

## Recommended topology

Run QR Code Generator behind a reverse proxy that provides TLS, host
routing, and any required access control. The application intentionally
does not trust forwarded identity headers or provide built-in accounts.

The default Compose port mapping is:

```yaml
ports:
  - "127.0.0.1:${QR_HOST_PORT:-8080}:8080"
```

This is appropriate when the reverse proxy runs directly on the Docker
host. For a containerized proxy, attach both services to a private Docker
network, remove the host port publication, and proxy to `qrcode:8080`.

The repository includes an optional Nginx-based example that removes the
application port and exposes the proxy on host loopback port 8081:

```console
docker compose -f compose.yaml -f compose.proxy.yaml up --build --detach --wait
```

Open <http://127.0.0.1:8081>. The included proxy is a local reference
configuration. Add a public hostname and TLS configuration, or adapt its
limits to an existing production reverse proxy, before exposing it
publicly.

The proxy override relies on Compose's `!reset` merge tag, so use a
current Docker Compose release.

`QR_HOST_PORT` and `QR_PROXY_HOST_PORT` can override the default host
ports without changing the tracked Compose files.

## Proxy safeguards

Configure the reverse proxy to:

- reject request bodies larger than 5 MiB;
- allow 120 preview requests per minute per client with a burst of 20;
- allow 30 download requests per minute per client with a burst of 5;
- terminate TLS; and
- apply deployer-selected authentication or network restrictions.

Do not forward the application directly to the public internet without
considering access controls. Anyone who can reach it can generate codes.

## Runtime constraints

The provided Compose service uses a read-only root filesystem, a 64 MiB
temporary filesystem, dropped Linux capabilities, a 128-process limit,
one CPU, and 512 MiB of memory. No persistent storage is required.

## Published images

Release tags publish multi-architecture `linux/amd64` and `linux/arm64`
images to Docker Hub. The repository owner configures these GitHub values:

- Repository variable `DOCKERHUB_REPOSITORY`, containing
  `namespace/qrcode`
- Repository variable `DOCKERHUB_USERNAME`
- Repository secret `DOCKERHUB_TOKEN`, containing a Docker Hub access
  token

Stable releases publish both their exact semantic version and `latest`.
Prereleases publish only their exact version. GHCR publishing remains a
later addition and will use the same immutable version tags.
