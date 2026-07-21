# Development

## Required developer dependencies

Install all of these tools before running the project setup:

- Git
- Bash
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`)
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22.13 or newer with npm (Node.js 23 is not supported)
- [just](https://just.systems/)
- [git-cliff](https://git-cliff.org/), required by `just changelog` and
  the release-preparation workflow
- curl, used by the Docker deployment smoke tests
- OpenSSL, used to generate secrets for Docker Compose deployments
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

Setup verifies Git, Node.js, npm, and `uv`, installs every locked Python
dependency group, installs the locked frontend dependencies, ensures the
Playwright Chromium browser is available for end-to-end tests, and
records successful initialization in `.init/setup`. It is safe to rerun;
an existing setup rechecks the browser installation. Use the following
commands when a completely fresh environment is needed:

```console
just reset
just setup
```

`just clean` removes generated caches (including the uv cache), reports,
and build outputs while preserving installed environments. `just reset`
additionally removes `.venv`, frontend `node_modules`, and the setup
marker.

Start the backend and frontend development servers together:

```console
just run
```

The recipe generates an ephemeral render-token secret unless
`QR_RENDER_TOKEN_SECRET` is already set, waits for the backend to become
healthy, and then starts Vite. Press Ctrl+C to stop both servers.

The frontend development server proxies `/api` and `/health` to the
backend on port 8080.

## Local and custom container images

Build the production image from the current checkout with:

```console
just image
```

This creates the local `qrcode:local` image. The repository's tracked
Compose files build the checkout by default and use the same tag. Set
`QR_IMAGE` to apply a custom local tag while building:

```console
QR_IMAGE=example.invalid/your-fork/qrcode:dev \
  docker compose up --build --detach --wait
```

The optional local Nginx reference configuration builds the same
checkout, removes the application host port, and exposes the proxy on
loopback port 8081:

```console
docker compose -f compose.yaml -f compose.proxy.yaml \
  up --build --detach --wait
```

These source-tree Compose workflows are for development and deployment
testing. Deploy the published application image by following the
[getting-started guide](getting-started.md).

## Quality checks

```console
just test
just check
just test-e2e
```

`just test` is the normal pre-commit host test suite and runs the backend
and frontend unit/integration tests. `just check` adds formatting,
linting, type checking, a strict documentation build, and dependency
license validation. Browser and Docker deployment suites remain separate
because they require additional host services or installed browser
binaries.

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

## Changelog and releases

Pull-request titles use Conventional Commits because squash merges make
the title the commit subject on `main`. CI validates the title. The
supported user-facing types are:

| Type | Changelog section |
| --- | --- |
| `feat` | Added |
| `change` | Changed |
| `deprecate` | Deprecated |
| `remove` | Removed |
| `fix` | Fixed |
| `security` or `fix(security)` | Security |
| `perf` | Performance |
| `deploy` | Deployment & Operations |
| `docs` | Documentation |
| `build(deps)` or `build(deps-dev)` | Dependencies |
| `revert` | Reverted |

Use an optional scope when it adds useful context, for example
`fix(a11y): label the preview` or
`deploy(compose): document the proxy network`. Mark a breaking change
with `!`, as in `deploy!: rename the render secret`, and explain the
migration in the commit body's `BREAKING CHANGE:` footer. Routine
`build`, `chore`, `ci`, `refactor`, `style`, and `test` commits do not
appear in the changelog unless they are breaking.

Preview changelog-visible commits since the latest release without
changing files:

```console
just changelog
```

Prepare a release from a clean release-preparation branch with an
explicit bare semantic version:

```console
just bump 0.2.0
just check
git add CHANGELOG.md changelogs pyproject.toml uv.lock frontend/package.json frontend/package-lock.json
git commit -m "chore(release): prepare for 0.2.0"
```

The bump command updates both application versions and lockfiles,
generates the release section, and restores the original files if a
step fails. It is safe to rerun the same untagged version after adding
release changes. The initial `0.1.0` preparation promotes the curated
`Unreleased` baseline. Later patch and prerelease entries remain in the
active `X.Y` line; starting a new minor or major line moves older
entries to files under
[the changelog archive](https://github.com/geozeke/qrcode/tree/main/changelogs).

After the release-preparation change is merged, update local `main` and
create the release tag:

```console
git switch main
git pull --ff-only origin main
just tag-release
```

Tagging requires a clean `main` that exactly matches `origin/main`,
synchronized Python and frontend versions, committed release notes, and
a tag that does not already exist. It creates and pushes one annotated
`vX.Y.Z` tag. The tag workflow reruns every release gate, publishes the
Docker images, and creates the GitHub Release from the committed
changelog section. Prerelease versions such as `0.2.0-rc.1` create
GitHub prereleases and do not update the Docker `latest` tag.

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
deployment gate. Pull requests, pushes to `main`, manual quality runs,
and release tags also run desktop/mobile browser tests. Failed browser
runs retain their Playwright report and traces as workflow artifacts for
14 days. Release tags rerun every gate against the exact release
candidate before publishing images.

A weekly security workflow runs Python and npm dependency audits,
CodeQL analysis, repository scanning, and the license inventory check.
Dependabot proposes updates only for direct dependencies declared in
the uv, npm, Docker, Docker Compose, and GitHub Actions manifests. The
security audits continue to scan the complete resolved dependency
graph, including transitive dependencies.

Use `just stale` to report compatible outdated top-level (direct) Python
and frontend dependencies. Use `just upgrade` from a clean worktree to
update those dependencies within the version ranges already declared in
`pyproject.toml` and `frontend/package.json`. The upgrade recipe creates
one local `build(deps):` commit that lists the changed direct versions;
review and test that commit before pushing it.

Dependency resolution may necessarily change transitive versions in a
lockfile when a direct dependency is upgraded. The local recipes do not
select, report, or list those transitive packages as independent
updates. Changes to declared major-version ranges remain explicit
maintainer decisions or separate Dependabot pull requests.

Release tags publish multi-architecture `linux/amd64` and `linux/arm64`
images to Docker Hub and publish matching GitHub Releases. Fork
maintainers who publish their own images configure these GitHub values:

- Repository variable `DOCKERHUB_REPOSITORY`, containing
  `namespace/qrcode`
- Repository variable `DOCKERHUB_USERNAME`
- Repository secret `DOCKERHUB_TOKEN`, containing a Docker Hub access
  token

Pushes that change `README.md` on `main` synchronize the Docker Hub
Repository Overview and short description with the repository. The
workflow can also be run manually after configuring Docker Hub or when
the overview needs to be refreshed.

Stable releases publish their exact semantic version, a mutable
major/minor tag, and `latest`. Releases at `1.0.0` and later also update
a mutable major tag; major-zero releases omit the `0` tag. Prereleases
publish only their exact version. GHCR publishing remains a later
addition and will use the same tag policy.
