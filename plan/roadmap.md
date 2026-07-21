# QR Code Generator Design Roadmap

Last updated: 2026-07-21

## Purpose

This roadmap describes future product and platform work for the deployed
QR Code Generator. Current behavior, deployment, and contributor
workflows are documented in `README.md` and `docs/`.

The horizons below express dependency and priority order, not promised
release numbers or delivery dates. Candidate features remain subject to
their listed design gates.

## Roadmap Principles

- Prioritize QR workflow improvements before adding unrelated code
  formats or persistent product features.
- Preserve scanner reliability when new styling, payload, or format
  capabilities are introduced.
- Add one well-tested integration or format at a time before creating a
  broad abstraction around it.
- Review privacy, licensing, operating cost, and self-hosting impact
  before adopting a new service or dependency.
- Keep speculative options clearly separated from accepted direction.

## Horizon 1: QR Workflow Expansion

### Map-Assisted Location Selection

Add an interactive map to help users select coordinates for location QR
codes while preserving manual latitude and longitude entry.

Accepted direction:

- Keep the map and coordinate fields synchronized in both directions.
- Allow a user to pan, zoom, click or tap to place a point, and move the
  point by entering valid coordinates manually.
- Implement one mapping integration first. Do not create a
  multi-provider abstraction until a working integration exposes shared
  requirements.
- Treat search, autocomplete, geocoding, and reverse geocoding as
  separate follow-up capabilities.

Design gates:

- Select Leaflet, MapLibre GL JS, or OpenLayers and a compatible tile
  provider.
- Review provider attribution, credentials, pricing, usage limits, and
  privacy behavior before implementation.
- Define secure deployer configuration before supporting a provider
  that requires credentials.

Acceptance gates:

- Map interaction and manual entry remain usable independently.
- Coordinate changes cannot leave the map, form, preview, and download
  in conflicting states.
- The feature includes keyboard-accessible controls and clear provider
  attribution.

### Digital Business Cards

Add digital business cards encoded as vCards.

Candidate fields:

- Full name, personal phone, email address, company, work title, work
  phone, fax, street, city, state, country, postal code, and website URL.

Design gates:

- Choose vCard 3.0 or 4.0 based on scanner and contact-application
  compatibility tests.
- Decide how personal and work phone numbers are labeled when both are
  present.
- Decide whether the first implementation supports one address or a
  collection of typed addresses.
- Define required fields, escaping, normalization, and practical QR
  density limits before exposing the form.

Acceptance gates:

- Representative exports import correctly into major mobile contact
  applications.
- Optional fields are omitted cleanly and user-entered text cannot
  break the vCard structure.

### Communication And Event Payloads

Add email, SMS, phone-number, and calendar-event payloads after the
vCard encoding contract is established.

Design gates:

- Select interoperable URI or payload formats for each capability.
- Define required and optional fields, escaping rules, length limits,
  timezone behavior, and scanner compatibility fixtures.
- Decide whether calendar support covers a single timed event only or
  also all-day and recurring events.

Acceptance gates:

- Each payload opens in the intended class of mobile application on
  representative scanners.
- Payload-specific forms reject ambiguous or structurally invalid data
  before preview and export.

### Stateless Presets

Add built-in presets as editable starting points without introducing
saved user configuration.

Initial candidates:

- Print: PDF, A4, portrait, a 100 mm symbol, and default margins.
- Web: SVG, standard digital scale, and no frame.
- Label: defer until supported label dimensions and layout rules are
  specified.

Accepted direction:

- Applying a preset visibly updates the ordinary controls and leaves
  them editable.
- A manual change after applying a preset marks the configuration as
  custom.
- Presets cannot bypass validation or scanner-reliability checks.

Acceptance gates:

- Preset results match the visible controls exactly.
- Resetting the form restores the ordinary default state rather than a
  hidden preset state.

## Horizon 2: Format And Platform Expansion

### Additional Code Formats

Introduce additional formats incrementally, beginning with a focused
use case and scanner test matrix for each format.

Candidate formats:

- Compact QR variants: Micro QR Code and rMQR Code.
- Retail and linear barcodes: UPC-A, UPC-E, EAN-13, EAN-8, and Code 128.
- Additional two-dimensional formats: Data Matrix, PDF417, and Aztec.

Accepted direction:

- Each format defines its supported payloads, validation, render
  options, export behavior, and human-readable text behavior.
- Add one production encoder path at a time and isolate it from the
  user interface and export implementations.
- Do not expose QR-specific visual controls for formats that cannot
  support them safely.

Design gates:

- Choose the first format based on a concrete user workflow rather than
  implementing the full candidate list together.
- For UPC-A, decide whether 11-digit input receives a calculated check
  digit and whether human-readable digits are rendered below the code.
- Evaluate encoder and decoder dependencies for license compatibility,
  maintenance health, output control, and supported platforms.
- Define physical sizing, quiet-zone, checksum, and character-set rules
  for each selected format.

Acceptance gates:

- Representative outputs decode with independent scanners and conform
  to the selected format's structural rules.
- Unsupported payload and styling combinations are unavailable or
  rejected before export.
- All supported export formats preserve required geometry.

### Public Automation API

Promote generation capabilities into a documented API for external
automation only after a stable compatibility contract is designed.

Design gates:

- Define API versioning, authentication, CORS, rate limits, idempotency,
  error compatibility, and deprecation policy.
- Decide whether synchronous generation is sufficient or whether large
  jobs require an asynchronous workflow.
- Separate the public contract from web-interface implementation
  details so frontend changes do not become API breaking changes.
- Define safe handling for secrets and sensitive payloads used by
  automation clients.

Acceptance gates:

- Publish an OpenAPI contract, examples, compatibility policy, and
  deployment guidance.
- Add contract tests covering authentication, validation, versioning,
  limits, and error responses.

### Reverse-Proxy Authentication Guidance

Add supported deployment examples where a reverse proxy controls access
before requests reach the application.

Candidate integrations include Authelia with HAProxy, Authentik,
oauth2-proxy, Caddy, Traefik, nginx, mTLS, and VPN-only access.

Design gates:

- Select one reference deployment before documenting alternatives.
- Define its threat model, trusted network boundary, logout behavior,
  health-check access, and failure behavior.
- Keep trusted identity-header support disabled unless an explicit
  configuration and header-sanitization contract is designed.

Acceptance gates:

- The reference deployment denies unauthenticated access without
  disrupting health monitoring or normal generation flows.
- Documentation explains which component terminates TLS, authenticates
  users, and strips untrusted identity headers.

### Container Registry Expansion

Add GitHub Container Registry as a second publication target while
keeping Docker Hub available during the transition.

Accepted direction:

- Publish identical immutable version tags to both registries.
- Publish matching stable mutable tags, including `latest`, according
  to the release policy.
- Keep both registries active until a separate Docker Hub retirement
  decision is made.
- Document one preferred pull reference while showing the equivalent
  reference for the other registry.

Acceptance gates:

- Images from both registries have matching digests, platforms,
  metadata, attestations, and startup behavior.
- A failure to publish or verify either required target prevents an
  incomplete release from being presented as successful.

## Horizon 3: Persistent And Multi-User Capabilities

### Saved History And Reusable Templates

Add a persistent library only after its data ownership, lifecycle, and
deployment model are defined.

Candidate stored data includes generated-code records, payload data,
visual settings, reusable templates, uploaded logos, generated files,
timestamps, and ownership metadata. Each category must be justified
individually; enabling persistence does not imply storing all of them.

Design gates:

- Select a database and define schemas, migrations, backup, restore,
  retention, cleanup, and storage-capacity guidance.
- Decide whether generated files are retained or reproduced from saved
  source settings.
- Define encryption and access controls for sensitive payloads such as
  WiFi credentials and contact details.
- Decide whether logos are stored, referenced externally, or required
  again when regenerating a saved code.
- Specify import, export, deletion, and data-portability behavior.

Acceptance gates:

- Upgrades preserve stored records through tested migrations and have a
  documented backup and recovery path.
- Deletion and retention behavior covers database records, files,
  logos, derived exports, and backups consistently.
- A deployment can continue using generation features without enabling
  the persistent library.

### Identity, Ownership, And Sharing

Add application-aware identity only when saved resources or a public
API creates a concrete need for ownership and authorization.

Design gates:

- Choose between application-managed accounts, trusted identity from a
  supported proxy, or both.
- Define administrators, ordinary users, resource ownership, sharing,
  revocation, session lifetime, account recovery, and audit events.
- Establish how deployments migrate from anonymous use to identified
  users without assigning existing sensitive data incorrectly.
- Decide whether shared templates are instance-wide, group-scoped, or
  explicitly shared by owners.

Acceptance gates:

- Authorization is enforced server-side for every stored resource and
  automation endpoint.
- Identity claims are accepted only from explicitly configured trusted
  infrastructure.
- Backup, export, deletion, and audit behavior respects resource
  ownership and administrator boundaries.

## Deferred Decisions

The following choices should be made only when their dependent feature
enters implementation:

- Mapping library, tile provider, and optional geocoding provider.
- vCard version and multi-address behavior.
- Calendar event scope and timezone representation.
- First additional code format and its encoder dependency.
- Public API authentication and versioning model.
- Reference reverse-proxy authentication integration.
- Persistent storage engine and retained data categories.
- Identity provider, ownership model, and sharing semantics.
- Docker Hub retirement timing after GHCR adoption.
