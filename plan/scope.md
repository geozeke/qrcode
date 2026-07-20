# QR Code Generator Project Scope

Last updated: 2026-07-20

## Project State

Planning decisions for the first release are agreed, and implementation
is underway. This document remains the source of truth for accepted
product scope and architecture.

Repository status:

- The project has been initialized as a Git repository.
- The current branch is `main`.
- The origin remote is `git@github.com:geozeke/qrcode.git`.
- The repository has been pushed to origin.
- Backend, frontend, container, and test scaffolding now exists locally.
- Payload, visual, logo, and export rendering are implemented.
- Resource-limit and privacy hardening is implemented, including bounded
  worker processes, route deadlines, request limits, sanitized errors,
  privacy-safe logging, and response security headers.

## Product Goal

Build a clean, elegant, self-hostable web application for generating QR
codes. Users should enter content, configure visual options, preview the
generated code, and download it as a file.

The project should start with a stable QR-code core and remain
extensible so barcode formats and additional QR payload types can be
added later without major restructuring.

## Initial Hosting Direction

Primary deployment target:

- Self-hosted Docker deployment.
- Docker Compose is the main documented setup for self-hosting.
- The Docker container should include the web server needed to serve the
  application.
- The Docker container should include a Docker-native health monitor so
  running containers can report healthy or unhealthy status.
- The first release should be packaged as a single self-contained web
  app container unless a later technical constraint requires otherwise.
- Persistent storage is not required for the first release because the
  app is stateless.
- The first release should use a reverse proxy as the documented and
  recommended public-access path.

Deployment options still to discuss:

- None currently for the first-release deployment model.

Future deployment effort:

- None currently. The project scope is Docker-only unless a later
  product decision reopens non-Docker deployment.

Access model:

- The first release should be a private, open self-hosted utility.
- The app should not include built-in authentication, local users,
  passwords, login sessions, or account management in the first release.
- Anyone who can reach the deployed web app can use it, so deployers
  should restrict access with private networking, firewall rules, VPNs,
  or reverse proxy controls when needed.
- Reverse proxy authentication is a future deployment capability, not a
  first-release requirement.
- The reverse proxy should provide public TLS termination, host routing,
  and any deployer-selected access control. The application must not
  configure, bundle, or implement reverse-proxy authentication.
- The application does not need to generate absolute URLs or consume
  forwarded headers in the first release. Do not trust forwarded or
  identity headers in the application.

Container health monitoring:

- The backend should expose a lightweight `GET /health` route for
  container health checks.
- The health route should return `200 OK` with a small JSON response
  when the app process is running and able to serve HTTP requests.
- The Docker image should define a `HEALTHCHECK` that calls the local
  health route inside the container.
- The Docker Compose service should include matching healthcheck
  settings so self-hosted users can inspect status through Docker
  Compose.
- The health check should remain stateless and inexpensive. It should
  not generate QR codes, process uploads, write files, or depend on a
  database.
- Deployment documentation should show how to inspect health status with
  `docker compose ps`.

## Container Runtime And Web Serving

Decision:

- Build SvelteKit as a static single-page application with an SPA
  fallback; do not use server-side rendering in the first release.
- Build frontend assets in a Node build stage, then copy only the static
  output into the Python runtime image. Do not ship Node or frontend
  source in the final image.
- Serve static assets and the SPA fallback through FastAPI/Starlette in
  the same Uvicorn process as the internal API.
- Reserve `/api/*` and `/health` for FastAPI. Other non-asset GET routes
  return the SPA entry document.
- Run a single Uvicorn process as a dedicated non-root user, bound to
  `0.0.0.0:8080`. Require `QR_RENDER_TOKEN_SECRET`; allow `PORT` with
  `8080` as its default.
- The frontend uses relative `/api/...` URLs. Do not enable CORS or
  require runtime frontend configuration.
- Run the container with a read-only root filesystem and use a writable
  temporary directory only when an image library requires it.
- On `SIGTERM`, stop accepting new requests, allow up to 30 seconds for
  in-flight work, then exit.

Caching and security headers:

- Cache fingerprinted frontend assets for one year and send `no-cache`
  for the SPA entry document. Preserve `no-store` behavior for API
  previews and render-token responses.
- Set `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  and a same-origin Content Security Policy that allows only required
  `data:` and `blob:` image sources.

Docker Compose reverse-proxy model:

- The primary Compose file publishes `127.0.0.1:8080:8080`, limiting
  application access to host loopback for host-installed reverse
  proxies.
- Document an optional Compose override for containerized reverse
  proxies: attach the application to the proxy's private Docker network,
  remove the host port publication, and proxy to `qrcode:8080`.
- Use `init: true` in Docker Compose. The application service has no
  persistent volume or database requirement.
- The Docker health check calls `127.0.0.1:8080/health` with a 30-second
  start period and interval, a 5-second timeout, and three retries.
- Set Docker Compose limits to one CPU, 512 MiB memory, 128 PIDs,
  dropped Linux capabilities, `no-new-privileges`, a read-only root
  filesystem, and a 64 MiB `/tmp` tmpfs.

## Website Experience

The app should present a clean, elegant website for user input and code
generation.

Expected website workflow:

1. Select payload type.
2. Enter payload details.
3. Configure visual options.
4. Preview generated result.
5. Download as PNG, JPG, SVG, or PDF.
6. Start a new code from a clear `New Code` or `Reset` control.

The interface should be practical and focused on generating codes, not a
marketing site.

The website should include a clear `New Code` or `Reset` control so
users can discard the current form state and create another QR code
without refreshing the page.

Preview behavior decision:

- QR previews should update live while users edit payload and visual
  options.
- Debounce preview requests by 300 ms and abort superseded requests to
  avoid excessive backend work and UI churn.
- The preview should show validation feedback instead of generating a
  code when the current form state is incomplete or invalid.
- The download action should use the same validated render state shown
  in the preview.

Dark mode decision:

- Optional dark mode is part of the first stable release.
- Dark mode is useful because this is a utility that users may keep open
  while working, and the UI will likely include color pickers, previews,
  and form controls that benefit from reduced eye strain.
- Dark mode should be a UI preference only. It must not change the
  generated QR code colors unless the user explicitly changes
  foreground/background colors.
- The app should still default generated codes to high-contrast,
  scanner-friendly colors.

## Technology Direction

Decision:

- Backend: Python/FastAPI.
- Frontend: SvelteKit with TypeScript.
- Python dependency management and tooling: Astral `uv`.
- Packaging: Docker, with Docker Compose for local/self-hosted
  deployment.

Rationale:

- Python/FastAPI is a strong fit for a Docker-only utility because it
  provides clear request/response modeling, validation, file upload
  handling, and API ergonomics.
- Python has a broad ecosystem for image processing, PDF generation,
  validation, and barcode/QR-code related libraries.
- Docker-only deployment makes FastAPI's development speed and library
  ecosystem a better fit than optimizing for non-Docker distribution.
- `uv` provides fast, reproducible Python dependency management and
  project tooling for local development, CI, and container builds.
- SvelteKit with TypeScript is a strong fit for a polished web UI,
  maintainable form-heavy workflows, preview state, and a compact app
  structure.
- SvelteKit should integrate cleanly into a Docker build that serves the
  web UI alongside the FastAPI backend.
- A FastAPI backend can expose a clear generation API and keep generation
  logic centralized.

Current decision: use a Python/FastAPI backend with a SvelteKit
TypeScript frontend, managed with `uv` and deployed through Docker
Compose.

## QR Generation And Rendering Dependencies

Decision:

- Use Segno as the production QR encoder, pinned with
  `segno>=1.6.6,<2`.
- Use Segno's QR-only generation path and enforce the first-release
  version-20 limit in the application.
- Isolate all Segno calls behind a single encoder adapter. Convert its
  classified matrix into a normalized internal model containing the QR
  version, error correction level, module grid, and module-kind map.
- Use the normalized model, rather than a third-party themed renderer,
  to enforce functional-module, dot-style, and logo-placement
  constraints.
- Use Pillow for PNG/JPG drawing, logo validation/compositing, and JPEG
  encoding.
- Generate SVG directly from the normalized model with Python's
  standard-library XML facilities. Do not add a separate SVG renderer.
- Use the open-source ReportLab toolkit for vector PDF generation and
  captions. Do not use ReportLab Plus, RML, `rlextra`, or `pyRXP`.
- Use ZXing-C++ only as a development and test decoder for generated
  exports. It must not ship in the production container.

Dependency licensing policy:

- Every production and test dependency must permit no-fee use,
  modification, and redistribution for both non-commercial and
  commercial use.
- Do not add dependencies that require a paid license, license key,
  hosted service, usage-based fee, or restrictive non-commercial-only
  terms.
- Prefer permissive licenses. Adding GPL, AGPL, LGPL, or another
  reciprocal/copyleft dependency requires an explicit later decision.
- Record the license of every direct dependency, preserve required
  notices, and run dependency/license scanning in CI.
- The selected stack meets this policy: Segno is BSD-3-Clause, Pillow is
  MIT-CMU, ReportLab Toolkit is BSD, and ZXing-C++ is Apache-2.0.

Dependency upgrade guidance:

- Treat Segno's module classification as an adapter boundary. A Segno
  upgrade requires adapter and decode tests to pass before adoption.

## Local Development And Compose Validation

Decision:

- Use host-native development on the Apple host for the normal edit,
  debug, and test loop.
- Run the FastAPI backend and SvelteKit frontend development servers
  directly on the host so hot reload, IDE debugging, and unit tests stay
  fast and simple.
- Use an Ubuntu VM with Docker Engine and the Docker Compose plugin as
  the preferred local environment for Compose validation.
- Clone the repository in the Ubuntu VM, pull the branch being tested,
  and run `docker compose up --build` from the VM checkout.
- Keep Docker Compose as the documented self-hosted deployment
  interface. The Ubuntu VM validation workflow should match that
  documented deployment path.

Validation targets:

- Validate the production image's health check, runtime user, network
  binding, packaged frontend assets, port mapping, and graceful shutdown
  through Docker Compose in the Ubuntu VM.
- Validate loopback-only host publication and optional private Docker
  network connectivity to a containerized reverse proxy.
- Keep the `Dockerfile` and Compose configuration portable so they also
  work in CI and other standard Docker Engine environments.

## Code Formats

Initial required formats:

- QR Code.

Initial QR Code format interpretation:

- The initial QR Code format means standard square Model 2 QR Code.
- Standard QR Code should support multiple visual module styles,
  including square modules and dot/circle modules, as rendering options
  rather than separate code formats.
- Module styling must preserve required QR structure, quiet zones,
  contrast, finder patterns, timing patterns, alignment patterns, and
  scanner reliability.

Extensibility requirement:

- The project should be structured around pluggable code format
  generators so future barcode formats can be added cleanly.
- Each format should define its own validation, supported payloads,
  render options, and export capabilities.

Future barcode/code formats:

- Micro QR Code.
- rMQR Code / Rectangular Micro QR Code.
- UPC-A.
- Code 128.
- EAN-13.
- EAN-8.
- UPC-E.
- Data Matrix.
- PDF417.
- Aztec.

## QR Code Types And Payloads

Initial payload types:

- URL.
- Location using latitude/longitude.
- Plain text.
- WiFi hotspot.

Recommended QR payload support for initial stable release:

- URL: trim surrounding whitespace. If no URI scheme is present, prepend
  `https://`; otherwise accept only a valid `http` or `https` URL with a
  non-empty host. Encode the resulting URL unchanged after validation.
- Geo location: accept decimal WGS-84 latitude and longitude with up to
  six fractional digits, canonicalize negative zero to zero, and
  generate `geo:latitude,longitude` payloads without altitude,
  uncertainty, or CRS parameters.
- Plain text: generate raw UTF-8 text payloads without trimming or other
  normalization.
- WiFi hotspot: generate scanner-compatible WiFi network payloads using
  the `WIFI:` format and its required escaping rules.

Future payload types:

- Digital business card.
- Email.
- SMS.
- Phone number.
- Calendar event.

Planned digital business card encoding format:

- vCard.

Planning note:

- Decide later whether to use vCard 3.0 or vCard 4.0 based on scanner
  compatibility and implementation details.

## Map-Assisted Location QR Future Scope

Add after the first release is stable.

Future capability:

- Add an interactive map to help users choose coordinates for location
  QR codes.
- Users should be able to pan and zoom the map, click or tap a point,
  and have the latitude and longitude fields update from that point.
- Manual latitude and longitude entry should remain supported. When
  users enter valid coordinates manually, the map should zoom to that
  point and show or move a pin.
- The generated QR payload should remain `geo:lat,long`.

Initial rollout approach:

- Implement one mapping provider integration at a time.
- Start with map click/manual coordinate synchronization before adding
  search, geocoding, autocomplete, or reverse geocoding.
- Do not build a broad multi-provider abstraction until at least one
  provider integration is working and shared requirements are clear.

Free/open mapping options to evaluate:

- Leaflet with compatible tile providers.
- MapLibre GL JS with compatible vector or raster tile providers.
- OpenLayers with compatible tile providers.

Provider-account mapping options to evaluate:

- Google Maps Platform.
- Mapbox.
- TomTom.

Planning notes:

- Provider credentials should be supplied by the deployer when required.
- Provider pricing, attribution, usage limits, and privacy behavior must
  be reviewed before implementing a provider integration.
- Storing provider credentials in the application is out of scope unless
  a later design defines secure configuration and deployment behavior.
- Search, geocoding, autocomplete, and reverse geocoding are separate
  future decisions because they add provider-specific policy, billing,
  and privacy concerns.

## Digital Business Card Future Scope

Add after the core code generation feature is stable.

Fields requested:

- Full name.
- Phone number.
- Email address.
- Company name.
- Work title.
- Work phone.
- Fax.
- Street.
- City.
- State.
- Country.
- Postal code.
- Website URL.

Planning note:

- Confirm whether personal phone and work phone should both be included
  when present.
- Confirm whether address fields should support multiple addresses in
  the future.

## WiFi Hotspot Initial Scope

Fields requested:

- Network name.
- Password.
- Encryption.
- Hidden network.

Encryption options requested:

- None.
- WPA/WPA2/WPA3 Personal.
- WEP (legacy).

WiFi encoding rules:

- Support Open, WPA/WPA2/WPA3 Personal, and legacy WEP networks only.
  Enterprise WiFi is out of scope for the first release.
- Serialize WPA, WPA2, and WPA3 Personal networks as `T:WPA`, Open
  networks as `T:nopass`, and WEP networks as `T:WEP`.
- The hidden-network control defaults to off. Include `H:true` only when
  it is selected.
- Serialize fields in the order `WIFI:T:{type};S:{ssid};P:{password};`
  followed by `H:true;` when applicable, and terminate the payload with
  `;`. Omit the password field for Open networks.
- Escape backslash, semicolon, comma, double quote, and colon in SSID
  and password values by prefixing each with a backslash. Do not
  percent-encode these values.

## Visual Options

Required visual options:

- Selectable QR module style, initially square modules and dot/circle
  modules.
- Selectable foreground color.
- Selectable background color.
- Optional transparent background for PNG and SVG exports.
- Selectable border type.
- Selectable border width.
- User-selectable QR error correction level.
- Custom logo upload for QR codes.

QR error correction levels:

- L, Low: 7%.
- M, Medium: 15%.
- Q, Quartile: 25%.
- H, High: 30%.

Default QR error correction level:

- M, Medium.

Logo planning notes:

- Logo upload is part of the first stable release.
- Uploaded logos should be used temporarily for the current generation
  request and should not be stored by the application.
- Logo upload should support PNG and JPEG/JPG files.
- SVG logos do not need to be supported.
- Logos are allowed only with square modules and error correction level
  H.
- A logo must use an opaque white square backing with at least one
  module
  of padding on every side.
- The logo image itself may occupy at most 15% of the QR symbol width,
  excluding the quiet zone.
- A logo upload is limited to 5 MiB, 4,000,000 pixels, and 4,096 pixels
  in either dimension. It must contain one non-animated PNG or JPEG
  image.
- Determine the format by Pillow decoding rather than the filename or
  declared MIME type. Fully decode accepted images, convert them to RGB
  or RGBA, and discard EXIF, XMP, ICC, filename, and other source
  metadata before composition.
- A logo must be centered and must not overlap any functional module,
  including finder, separator, timing, alignment, format/version, or
  dark modules. The app must reject a logo request when no compliant
  centered area exists.
- The app must block logo-plus-dot module combinations.

Border types:

- Quiet-zone only.
- Solid frame.
- Rounded frame.
- Label/caption frame.
- Transparent padding.

Border planning notes:

- Quiet-zone only is the default. It adds no decoration beyond the
  required four-module quiet zone, and the border-width control is
  disabled.
- Solid frame, rounded frame, label/caption frame, and transparent
  padding support widths of 1, 2, or 4 modules. The default width is
  2 modules.
- Frames and captions begin after a fixed two-module outer gap beyond
  the quiet zone. This gap uses the configured background for opaque
  exports and remains transparent for transparent PNG/SVG exports.
- Solid frames use a square-cornered foreground-color rectangle. Rounded
  frames use the same geometry with an outer corner radius of twice the
  selected frame width, capped at eight modules.
- Transparent padding adds only transparent or empty space of the
  selected width after the outer gap; it draws no frame.
- Do not offer independent border colors. Frames and caption text use
  the QR foreground color; opaque panel and gap areas use the QR
  background color.
- A label/caption frame is a solid frame with a centered caption band
  below the symbol. It requires plain-text caption input.
- Trim caption input, require from 1 through 80 Unicode characters, and
  escape it for SVG/PDF without interpreting markup.
- Wrap captions to at most two lines. Use a shared sans-serif style with
  a minimum 9 pt PDF size and a module-relative digital size. Reject
  captions that cannot fit within the selected export.
- The border caption is independent of the optional PDF page caption.

Module style planning notes:

- Square modules should be the default because they are the most
  conservative scanner-reliability choice.
- Dot/circle modules are a visual rendering style for standard Model 2
  QR Code, not a separate QR format.
- Square modules may use any supported error correction level, with M as
  the default.
- Dot/circle modules require error correction level Q or H, with Q as
  the default. The UI must not allow L or M while dot/circle modules are
  selected.
- Dot/circle modules must have a diameter equal to one module and must
  not expose a dot-size control.
- Dot/circle styling applies only to data and error-correction modules.
  Finder patterns, separators, timing patterns, alignment patterns,
  format/version information, the dark module, and the quiet zone must
  remain square and unmodified.

## Scanner-Reliability Constraints

These constraints take precedence over visual customization in the first
stable release.

- Generate only standard Model 2 QR Code versions 1 through 20. Reject
  payloads that require versions 21 through 40, and warn when a payload
  requires version 11 through 20.
- Render a fixed quiet zone of four light modules on every side. Solid,
  rounded, caption, and transparent-padding borders must sit outside the
  quiet zone and must not obscure it. Decorative elements must also
  remain outside the fixed two-module outer gap.
- Default to black (`#000000`) foreground on white (`#FFFFFF`)
  background. Opaque exports require a darker foreground and a WCAG
  relative-luminance
  contrast ratio of at least 7:1; reject lower-contrast combinations.
- Transparent PNG and SVG exports require a foreground relative
  luminance
  of at most 0.15 and must show a persistent warning that the final code
  needs a plain, light, high-contrast background with a clear margin.
- Raster exports must use an integer scale of at least eight pixels per
  module, including the quiet zone, and must not resample the final QR
  image. SVG and PDF exports must preserve whole-module geometry. When a
  physical size is selected, require at least one millimeter per module.

## Export Formats

Required download formats:

- PNG.
- JPG.
- SVG.
- PDF.

Website requirement:

- The website should include a download button for the selected output
  format.

Planning notes:

- SVG is best for vector use and print workflows.
- PNG is best for quick sharing and common document insertion.
- JPG is useful when users need broad compatibility with systems that do
  not accept PNG or SVG.
- PDF is useful for print and layout workflows.

Export sizing:

- Digital downloads use module-scale presets rather than a fixed pixel
  canvas: Compact at 8 pixels per module, Standard at 12 pixels per
  module, and Large at 24 pixels per module. Standard is the default.
- The chosen scale applies to the QR matrix and its four-module quiet
  zone. Frames, captions, and external padding extend the final canvas
  outside that area.

Format-specific behavior:

- PNG is a lossless RGBA or RGB image at the selected pixel dimensions
  with 300-DPI metadata.
- JPG is an opaque RGB image on white at quality 95, with chroma
  subsampling disabled and no resampling.
- SVG must retain QR modules and structural patterns as vector geometry
  in a module-based `viewBox` that includes the quiet zone. PNG/JPG
  logos must be embedded as self-contained data URIs; SVG must not use
  external image references or rasterize the QR code.
- PDF is a single vector page. Support A4 (the default) and US Letter,
  portrait and landscape orientation, and 12 mm (the default), 20 mm, or
  25 mm margins.
- PDF QR-symbol sizes are 50, 75, 100 (the default), 125, and 150 mm.
  Reject sizes that do not fit the usable page area or fall below one
  millimeter per module. The selected size includes the quiet zone but
  excludes external frames and captions.
- PDF captions are optional and blank by default. Limit captions to 120
  characters, center them below the QR symbol in 12 pt text, and keep at
  least 4 mm between the caption and the quiet zone.
- Border captions follow the border contract and are independent of the
  optional PDF page caption.

Transparency and downloads:

- Transparency is available only for PNG and SVG. It makes the
  background and quiet zone transparent, while modules and the logo's
  required white backing remain opaque.
- Transparent exports must show a warning that the final code needs a
  plain, light, high-contrast background with a clear margin around it.
- JPG and PDF exports must use an opaque white background.
- Download filenames use `qrcode-{payload-type}.{extension}`. Responses
  use `image/png`, `image/jpeg`, `image/svg+xml`, and `application/pdf`
  MIME types for PNG, JPG, SVG, and PDF respectively.

## Persistence Model

Decision:

- The first version should be stateless and temporary.
- The app should not save generation history, reusable templates,
  payload data, generated files, or uploaded logos in the initial
  release.
- Uploaded logos are allowed for QR generation, but they should be
  processed only for the current request and discarded afterward.

Stateless behavior:

- Users enter data, configure the code, generate/download the result,
  and nothing is saved by the application after the request finishes.
- Users can reset the current form state to create another QR code
  without storing or reusing the previous payload, logo, or generated
  file.
- This keeps the first version simpler because it likely does not need a
  database, user accounts, stored uploads, backup strategy, or data
  cleanup jobs.
- This is a good fit for a private self-hosted utility where users
  mainly need quick one-off QR codes.
- Tradeoff: users cannot return later to reuse a previous code, edit a
  saved configuration, or manage a library of templates.

Future saved history/templates option:

- The app stores generated-code records, reusable visual presets,
  payload templates, and possibly uploaded logos.
- This is useful if users expect repeated workflows, shared branding,
  auditability, or a searchable library of past codes.
- This adds product value but increases implementation scope because the
  app needs persistent storage, data models, migration strategy, backup
  guidance, and possibly authentication.
- If enabled, we need to decide what is saved: payload data, visual
  settings, generated files, uploaded logos, timestamps, and user
  ownership.

Implementation guidance:

- Design the request and generation model so persistence can be added
  later without rewriting the generator internals.

## Authentication Direction

Decision:

- The first release should be open and unauthenticated inside the
  application.
- The app is intended for private self-hosted deployment where network
  access controls decide who can reach it.
- Built-in authentication is out of scope for the first stable release.

Rationale:

- Keeping authentication out of the first release preserves the
  stateless deployment model.
- Avoiding local users and app-managed sessions keeps the initial app
  focused on QR code generation.
- Many self-hosted deployments already centralize authentication at the
  reverse proxy or private network layer.

Future reverse proxy authentication capability:

- Document deployments where HAProxy, Caddy, Traefik, nginx, or another
  reverse proxy enforces authentication before requests reach the app.
- Authelia with HAProxy is a likely future example for SSO, MFA, and
  policy-based access control.
- Authentik, oauth2-proxy, mTLS, VPN-only access, and trusted identity
  headers are also possible future deployment patterns.
- If trusted identity headers are ever supported by the app, they must
  be disabled by default and only trusted when the deployer explicitly
  enables them behind a trusted proxy.

## Suggested Architecture

Planning concept:

- A web frontend gathers input and shows a live preview.
- A backend generation API validates payloads and render options.
- The first release should have API-shaped backend routes for the
  website to call, but these routes do not need to be documented or
  supported as a public automation API yet.
- Code format generators are isolated behind a shared interface.
- Export renderers produce PNG, JPG, SVG, and PDF from a normalized
  generated-code representation.

Possible internal modules:

- `payloads`: URL, geo, plain text, WiFi, future vCard.
- `formats`: QR Code, future barcode formats.
- `rendering`: colors, borders, logos, quiet zones, dimensions.
- `exports`: PNG, JPG, SVG, PDF.
- `api`: HTTP routes, request validation, error responses.
- `web`: frontend application.

Key design principle:

- Payload types and code formats should not be tightly coupled. For
  example, URL and plain text payloads are QR payloads, while a future
  UPC-A format would have a numeric barcode-specific payload.
- Keep request and response structures clean enough that a documented
  HTTP API can be promoted later without rewriting the generation core.

## HTTP API Direction

Decision:

- The first release uses same-origin, unversioned internal routes. They
  are not a supported automation API, and the app must not enable CORS.
- `POST /api/preview` accepts `multipart/form-data` with a `request`
  JSON field containing the complete render state and an optional
  PNG/JPG `logo` file. It returns `200 image/png` with
  `Cache-Control: no-store` and an `X-Render-Token` response header.
- `POST /api/download` accepts the same multipart fields plus
  `render_token`. The `request` includes the selected output format and
  export settings. It returns the requested file with its selected MIME
  type and a `Content-Disposition: attachment` header.
- Preview performs validation. Do not add a separate validation route.
- Normalize each request before rendering, then compute a canonical
  fingerprint from the normalized state and the SHA-256 hash of the
  logo.
- The preview response returns a 10-minute HMAC-authenticated render
  token containing only the expiry, fingerprint, and logo hash. It must
  not include payload text or WiFi passwords.
- Download recomputes the fingerprint from its submitted request and
  logo, then accepts it only when it matches the token. The backend must
  not store render records, uploads, or tokens.
- Require `QR_RENDER_TOKEN_SECRET` at startup with at least 32 random
  bytes. Never log render tokens or request content.
- Use `400` for malformed multipart/JSON, `415` for unsupported logo
  media, `422` for field validation errors, `409` for a state or logo
  mismatch, `410` for an expired token, and a sanitized `500` response
  for unexpected render failures.
- Use `413` when the request, request JSON, or logo exceeds its
  configured size limit; `503` with `render_busy` when the render queue
  is full; and `504` with `render_timeout` when rendering exceeds its
  time limit.
- Validation responses use
  `{error, issues: [{path, code, message}]}`.
- A documented public HTTP API for external automation is a future
  capability, not a first-release commitment.
- First-release HTTP routes should not require app-level
  authentication.
- The backend should expose an unauthenticated internal `GET /health`
  route for Docker container health checks.

Rationale:

- The signed render token ensures that a download uses the same
  validated source and render state as its preview without making the
  stateless app retain uploaded logos or generated files.
- Deferring public API support and built-in authentication avoids extra
  first-release work around compatibility, authentication behavior, rate
  limits, and long-term versioning.

## Resource Limits And Privacy

Request and rendering limits:

- Limit every preview and download request to 5 MiB. Limit the JSON
  `request` part to 16 KiB and the optional logo file to 5 MiB.
- Configure Pillow's maximum pixel limit to 4,000,000 and treat every
  decompression-bomb warning as an error.
- Render in a bounded local worker process pool with at most two
  concurrent jobs and a queue of four. The stateless workers do not
  require network access beyond the container's existing network
  configuration.
- Limit previews to 5 seconds and downloads to 15 seconds. Cancel and
  terminate timed-out worker work.
- A timed-out worker is disposable because rendering is stateless and
  does not write persistent data.

Reverse-proxy limits:

- The documented reverse-proxy configuration must enforce the same 5 MiB
  request limit.
- The proxy must limit each client to 120 preview requests per minute
  with a burst of 20, and 30 download requests per minute with a burst
  of 5.
- These proxy controls are defense in depth. The application does not
  use forwarded headers to identify clients.

Privacy and logging:

- Send `Cache-Control: no-store` on preview and download responses.
- Do not use analytics, request-body logging, or persistent
  error-reporting services in the first release.
- Application logs may contain only timestamp, a generated request ID,
  route, status, duration, response size, and stable error code.
- Logs and HTTP responses must never contain request bodies, headers,
  payload data, WiFi credentials, logo bytes or filename, render tokens,
  canonical fingerprints, or stack traces.
- Generate a server-side opaque request ID and return it in an error
  header. Keep detailed exception data only in process-local
  diagnostics, not logs or HTTP responses.
- Process logos in memory when possible. Otherwise use the container
  tmpfs and `finally` cleanup. Never persist or serve uploads.

## Validation Rules To Define

URL:

- Trim surrounding whitespace.
- If the input has no URI scheme, prepend `https://`.
- Accept only valid `http` or `https` URLs with a non-empty host.
- Reject malformed URLs, embedded whitespace or control characters, and
  all other schemes. Do not test whether a URL is reachable.

Location:

- Latitude must be between -90 and 90.
- Longitude must be between -180 and 180.
- Accept decimal values with up to six fractional digits. Reject
  exponent notation and locale-specific comma notation.
- Canonicalize negative zero to zero and encode
  `geo:latitude,longitude`, with no altitude, uncertainty, or CRS
  parameter.

Plain text:

- Require from 1 through 1,000 UTF-8 bytes.
- Preserve all text exactly, including leading/trailing whitespace and
  line breaks, and encode it as UTF-8 byte data with ECI assignment 26.
- Show a warning when text length creates a dense or hard-to-scan QR
  code.
- Reject content that requires a QR Code version greater than 20, and
  warn when it requires version 11 through 20.

WiFi:

- Require an SSID of 1 through 32 UTF-8 bytes and reject control
  characters.
- For WPA, accept an 8 through 63 character printable-ASCII passphrase.
- For WEP, accept 5 or 13 printable-ASCII characters, or 10 or 26
  hexadecimal characters.
- Open networks require an empty password. Do not support 64-character
  raw WPA pre-shared keys in the first release.

Future UPC-A:

- UPC-A is numeric and typically 12 digits including check digit, or 11
  digits with check digit generated.
- Decide whether the app accepts 11 digits and calculates the check
  digit automatically.
- Decide whether to display human-readable digits under the barcode.

Colors:

- Require a darker foreground, an opaque-export contrast ratio of at
  least 7:1, and the transparent-export foreground limit defined in the
  scanner-reliability constraints.

Logo:

- Validate file type, dimensions, and maximum size.
- Accept PNG and JPEG/JPG logos.
- Do not support SVG logos in the first release.
- Process uploaded logos temporarily and do not persist them after
  generation.
- Require square modules, error correction level H, a padded opaque
  white backing, the 15%-width limit, and a compliant centered placement
  that does not overlap functional modules.
- Enforce the configured logo upload, image-size, format-detection,
  decompression-bomb, and metadata-stripping rules.

Border:

- Accept only the configured border types and widths.
- Require a caption for label/caption frames, enforce its length and
  text-only rules, and reject captions that cannot fit the selected
  export.
- Preserve the required quiet zone and fixed outer gap for every border
  type and export format.

## Testing And CI

Hosting target:

- The project will be hosted on GitHub.
- GitHub Actions is the recommended CI system unless a later requirement
  points elsewhere.

Documentation target:

- Initial project documentation should live in `README.md`.
- Keep README-only documentation for the first release. A formal
  documentation site is a future option only if the project outgrows
  that workflow; do not plan a GitLab Pages dependency.

Maintainer workflow and releases:

- Adopt `just` as the single local maintainer interface. Its recipes
  should include `setup`, `sync`, `lint`, `typecheck`, `test`,
  `test-e2e`, `image`, `compose-smoke`, `check`, `outdated`, `upgrade`,
  `bump`, and `tag-release`.
- `check` must run the same quality gates required by pull-request CI.
- Keep nontrivial maintenance automation in tracked `scripts/` and call
  it from `just`. Do not add an extra generated wrapper layer.
- Add tested helpers for guarded release-tag creation, release-note
  extraction, targeted first-order dependency upgrades, and image-tag
  preparation as needed.
- Use a root `CHANGELOG.md` and `git-cliff` to generate release notes.
  Do not introduce changelog archives unless the active changelog becomes
  unwieldy.
- Store the application version as SemVer and create immutable Git tags
  in the form `vX.Y.Z`.
- The release-tag helper must require the `main` branch, a clean working
  tree, `main` matching `origin/main`, and a tag that does not already
  exist.
- Prerelease tags publish only their exact version. Stable releases also
  update the mutable `latest` image tag.
- Initially publish release images to a configurable Docker Hub
  repository, `docker.io/<maintainer-namespace>/qrcode`. Do not hard-code
  a personal Docker Hub namespace in scripts or workflows.
- Do not publish an `edge` image for ordinary pushes to `main` in the
  first release process.
- When GHCR is introduced, dual-publish identical immutable version tags
  and `latest` to Docker Hub and `ghcr.io/geozeke/qrcode`. Keep both
  registries active until a later explicit Docker Hub retirement decision.
- Document the preferred registry and image pull reference in `README.md`.

Recommended test layers:

- Backend unit tests for QR payload generation, URL validation, geo
  validation, plain text handling, WiFi payload handling, error
  correction options, color validation, border options, logo handling,
  and export rendering.
- Payload tests for scheme insertion and rejection, exact `geo:` output,
  UTF-8 text preservation and byte limits, and Open, WPA, WEP, hidden,
  and escaped-character WiFi payloads.
- Encoder-adapter tests that verify Segno module classification at QR
  versions 1, 7, and 20. Use ZXing-C++ in development and CI to decode
  generated export fixtures.
- Backend integration tests for HTTP routes used by the website,
  including preview and download endpoints.
- API tests that accept a valid preview token for the same normalized
  request, reject altered state or logo bytes, reject expired or
  tampered tokens, verify validation error responses, and verify
  no-store previews.
- Resource-limit tests for oversized or chunked requests, forged MIME
  types, malformed images, animation, decompression bombs, queue
  saturation, and preview/download timeouts.
- Privacy tests that verify logs and error responses exclude payload
  data, WiFi passwords, logo filenames, tokens, and stack traces.
- Frontend unit/component tests for form behavior, validation states,
  option selection, dark mode, and download controls.
- End-to-end browser tests for the main user flows: generate URL QR
  code, generate geo QR code, generate plain text QR code, generate WiFi
  QR code, upload logo, change colors, switch dark mode, and download
  each required format.
- Browser tests that verify rapid edits cancel stale previews and cannot
  replace the latest preview or render token.
- Image/export tests that verify PNG, JPG, SVG, and PDF outputs are
  generated, non-empty, and have expected dimensions/content
  characteristics.
- Export-contract tests that verify module-scale geometry for versions 1
  and 20, PNG/JPG dimensions and modes, SVG vector geometry and embedded
  logos, PDF layout/caption spacing, transparent alpha behavior, and
  opaque JPG/PDF behavior.
- Border tests that verify every type and width preserves the quiet zone
  and outer gap, leaves functional modules unchanged, applies
  transparency correctly, and renders safely escaped, wrapped captions
  in every format.
- Scanner-reliability tests that verify quiet-zone and functional-module
  invariants and successfully decode representative square, dot,
  transparent, logo, and version-20 exports after rasterization.
- Accessibility checks for the website UI, especially form labels,
  keyboard navigation, contrast, and dark mode.
- Docker smoke tests that build the container, start it, and verify the
  web server responds.
- Docker health smoke tests that start the container and verify it
  reaches healthy status.
- Docker/reverse-proxy tests that verify loopback-only publication and
  optional shared-network connectivity.
- Reverse-proxy configuration tests that verify its request-size and
  rate-limit settings match the application policy.
- Local Ubuntu VM Compose checks during development to reproduce and
  debug Dockerfile, health check, and Linux runtime behavior.

Recommended GitHub Actions pipeline:

- Pull request workflow: run the local `check`-equivalent formatting,
  linting, Python and TypeScript type checks, backend/frontend unit and
  integration tests, decoder-based QR fixtures, and a single-platform
  Docker image build.
- Main branch workflow: run the full pull-request workflow plus browser
  end-to-end and Docker Compose smoke tests.
- Release workflow: trigger only from a version tag; rerun every required
  validation, generate GitHub release notes from `CHANGELOG.md`, build
  and publish multi-architecture images, and verify a started container's
  health endpoint before publication.
- Release images must support `linux/amd64` and `linux/arm64` and carry
  OCI source, version, revision, and license labels, an SBOM, and a
  provenance attestation.
- Fail closed: do not create a release or publish an image when a
  required test, build, or health check fails.
- Dependency/security workflow: run weekly and when dependency files
  change; scan Python and TypeScript dependencies, check the adopted
  license policy, run useful static analysis, and enable Dependabot for
  Python, npm, and GitHub Actions updates.

Recommended quality gates:

- Python formatting, linting, type checking, and FastAPI test checks.
- TypeScript type checking.
- Frontend linting.
- Backend and frontend test suites.
- Docker image builds successfully.
- Docker container reaches healthy status after startup.
- Basic browser flow passes before release.
- Pull-request quality gates are required GitHub branch-protection checks.

Testing priorities for the first stable release:

- QR codes should be scanner-reliable for default settings.
- QR codes should meet the scanner-reliability constraints in Phase 2;
  unsafe visual-option combinations must be blocked before export.
- Export files should be valid in all required formats: PNG, JPG, SVG,
  and PDF.
- Logo upload should be validated and should not persist files.
- Color and border choices should not silently create unusable codes
  without warning.
- Docker Compose should start the app consistently.
- The same OCI image should behave consistently in the local Ubuntu VM,
  CI, and deployment.

## Phased Scope

Phase 1: Planning

- Capture project requirements.
- Decide stack.
- Decide deployment model.
- Decide first release scope.
- Define UX and architecture at a high level.

Phase 2: Core MVP

- Single Dockerized web app container with included web server.
- Docker-native health monitoring through a backend health route,
  Docker image `HEALTHCHECK`, and Docker Compose healthcheck settings.
- Web UI.
- Internal backend routes for website-driven QR generation and
  downloads.
- QR generation for URL, geo location, plain text, and WiFi hotspot.
- QR module style selection for square modules and dot/circle modules.
- Color selection.
- Error correction selection with M default.
- Border type and width options.
- Temporary custom logo upload for QR codes.
- Optional dark mode for the website UI.
- `New Code` or `Reset` control for clearing the current form and
  starting another QR code.
- PNG, JPG, SVG, and PDF downloads.
- Baseline payload, rendering, export, scanner-reliability, API, and
  browser-flow tests.
- Local `just` recipes and matching GitHub Actions quality gates.

Phase 3: Stabilization

- Improve validation and scanner reliability warnings.
- Expand test coverage and harden release automation.
- Refine GitHub Actions workflows for multi-architecture publishing,
  provenance, SBOMs, dependency policy checks, and a later GHCR
  dual-publish transition.
- Refine UI and Docker deployment documentation.

Phase 4: Advanced QR Payloads

- Digital business card.
- Additional communication payloads such as email, SMS, and phone
  number.

Phase 5: Additional Code Formats

- Add barcode and additional 2D code formats through the extensible
  generator structure.
- Consider Micro QR Code and rMQR Code / Rectangular Micro QR Code for
  constrained physical labels or narrow print areas.
- UPC-A is a future capability, not part of the first stable release.

## Presets

Decision:

- Do not provide named presets in the first stable release. Use the
  scanner-safe defaults and clearly grouped, explicit controls instead.
- The `New Code` or `Reset` action is the only first-release mechanism
  for returning to a known initial configuration.
- Do not store a preset selection or user configuration. This preserves
  the first-release stateless model.

Rationale:

- High contrast is already the default and is enforced by the color
  constraints.
- Logo safety is enforced by validation and must not depend on a user
  selecting a preset.
- Print and web needs are expressed through the existing PDF and digital
  export controls.
- A label-ready preset would require label-size and layout decisions that
  are outside the first-release scope.

Future preset direction:

- After the core application is stable, consider only built-in,
  stateless one-click starting points. Do not add saved user templates
  or preset persistence without a later explicit decision.
- Initial candidates are Print (PDF, A4, portrait, 100 mm symbol, and
  default margins), Web (SVG, Standard digital scale, no frame), and
  Label only after its dimensions and layout are specified.
- Applying a future preset must visibly set the ordinary controls and
  leave them editable. Any subsequent manual change must show the state
  as custom.
- Presets must never bypass validation or scanner-reliability
  constraints.

## Current Assumptions

- Docker self-hosting is required.
- Docker Compose is the main documented setup.
- The implementation stack is Python/FastAPI backend plus SvelteKit
  TypeScript frontend.
- Python dependency management and tooling should use Astral `uv`.
- Host-native development is the preferred day-to-day workflow.
- An Ubuntu VM with Docker Engine and the Docker Compose plugin is the
  preferred local environment for Compose validation.
- The first release should be a single self-contained Docker web app
  container with an included web server.
- The first release container should include Docker-native health
  monitoring backed by a lightweight backend health route.
- The first release should be stateless and should not require
  persistent storage or a persistent database.
- The first release should be open and unauthenticated inside the app,
  intended for private self-hosted access.
- Authelia and other reverse proxy authentication integrations are
  potential future deployment capabilities, not first-release
  requirements.
- The backend should expose internal HTTP routes for the website, while
  a documented external automation API is a future capability.
- Temporary custom logo upload for QR codes is part of the first stable
  release.
- Optional dark mode for the website UI is part of the first stable
  release.
- QR previews should update live while users edit payload and visual
  options.
- Standard square Model 2 QR Code is the only first-release code
  format.
- Square and dot/circle modules are first-release rendering styles for
  standard QR Code, not separate code formats.
- Barcode generation, including UPC-A, is a future capability.
- Micro QR Code and rMQR Code / Rectangular Micro QR Code are future
  code-format candidates, not part of the initial release.
- URL, location, plain text, and WiFi hotspot are the first QR payload
  types.
- Map-assisted location QR code selection is a future capability, not a
  first-release requirement.
- Future map-assisted location support should implement one mapping
  provider integration at a time.
- Digital business card is planned later, after the core app is stable.
- Digital business cards should use vCard format.
- Error correction level M is the default for QR codes.
- PNG, JPG, SVG, and PDF are required export formats.
- Transparent backgrounds should be supported for PNG and SVG as an
  advanced export option, with opaque white as the default.
- Logo uploads should support PNG and JPEG/JPG, but not SVG.
- Supported border types are quiet-zone only, solid frame, rounded
  frame, label/caption frame, and transparent padding.
- GitHub Actions is the recommended CI system.
- Initial documentation should live in `README.md`.
- Docker Hub is the initial image registry; GHCR is a later dual-publish
  registry, not an immediate replacement.
- The project should prioritize scan reliability over visual
  customization when those goals conflict.
