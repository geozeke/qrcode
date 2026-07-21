# Getting started

Deploy QR Code Generator with Docker Compose. The application is
stateless and does not require a database or persistent volume.

## Requirements

- Docker Engine
- A current Docker Compose plugin that provides `docker compose`

## Create `compose.yaml`

Copy the following block with its copy button and save it as
`compose.yaml` on the Docker host:

```yaml
services:
  qrcode:
    image: docker.io/geozeke/qrcode:latest
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

### Set the render-token secret

Generate a random secret:

```console
openssl rand -hex 32
```

Replace the example `QR_RENDER_TOKEN_SECRET` value with the command's
output. Do not reuse the documented example value.

### Choose access topology and host port

The default `127.0.0.1:8080:8080` mapping is for the recommended setup:
a reverse proxy running directly on the Docker host. Leave it unchanged
and configure the proxy to reach `http://127.0.0.1:8080`.

When the reverse proxy runs on another host, replace the mapping with:

```yaml
ports:
  - "8080:8080"
```

Configure the remote proxy to reach the Docker host's network address on
port 8080. This mapping publishes the application on every host network
interface. Restrict access to the remote proxy with effective network
controls, such as cloud security groups, firewall rules, or private
networking.

For direct access from another machine, use the same `"8080:8080"`
mapping. This is appropriate only for a trusted development or private
network: the application does not provide TLS or authentication. Do not
expose it directly to the public internet; use a reverse proxy instead.

For direct access only from the Docker host, retain the default loopback
mapping. If port 8080 is already in use, change only the host-side port:
use `127.0.0.1:9080:8080` for loopback access or `9080:8080` for the
network-reachable mappings above.

See [Deployment topology](deployment.md) for reverse-proxy integration
and safeguards.

## Start the application

From the directory containing `compose.yaml`, run:

```console
docker compose up --force-recreate -d
```

Because the configuration uses `pull_policy: always`, Compose retrieves
the current published image before recreating the container.

## Verify the deployment

```console
docker compose ps
```

Wait for the `qrcode` service to report `healthy`. For the default
mapping, open <http://127.0.0.1:8080>, using the adjusted host port if
you changed it. For remote-proxy or direct network access, use the proxy
URL or the Docker host's reachable address and published port.

Follow application logs when troubleshooting:

```console
docker compose logs --follow qrcode
```

## Update the application

Retrieve the current published image and replace the container with the
same startup command:

```console
docker compose up --force-recreate -d
```

## Stop the application

```console
docker compose down
```

No application data is lost when the container is replaced or removed.
