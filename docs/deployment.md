# Deployment

The [getting-started guide](getting-started.md) provides a complete,
copy-ready Docker Compose deployment. This guide covers network
topology, reverse-proxy integration, and production safeguards.

## Recommended topology

Run QR Code Generator behind a reverse proxy that provides TLS, host
routing, and any required access control. The application intentionally
does not trust forwarded identity headers or provide built-in accounts.

Use this Compose port mapping when the reverse proxy runs directly on
the Docker host:

```yaml
ports:
  - "127.0.0.1:8080:8080"
```

Configure the proxy to reach `http://127.0.0.1:8080`. For a
containerized proxy on the same Docker host, attach both services to a
private Docker network, remove the host port publication, and proxy to
`qrcode:8080`.

## Other access topologies

### Reverse proxy on another host

Replace the loopback mapping with:

```yaml
ports:
  - "8080:8080"
```

The remote proxy connects to the Docker host's reachable address on port
8080. Without a host IP, Docker publishes the port on all host
interfaces. Restrict the port to the remote proxy with effective network
controls, such as private networking, cloud security groups, or verified
firewall rules.

### Direct access without a proxy

For direct access from another machine, use the same `"8080:8080"`
mapping and limit it to a trusted development or private network. The
application does not provide TLS or authentication, so direct public
exposure is not supported. Use a reverse proxy for any public deployment.

For direct access only from the Docker host, retain the default
`127.0.0.1:8080:8080` mapping.

For any topology, change the host-side port only when port 8080 is
occupied: use `127.0.0.1:9080:8080` for loopback access or `9080:8080`
for a network-reachable mapping.

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
