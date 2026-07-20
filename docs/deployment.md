# Deployment

The [getting-started guide](getting-started.md) provides a complete,
copy-ready Docker Compose deployment. This guide covers network topology,
reverse-proxy integration, and production safeguards.

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
