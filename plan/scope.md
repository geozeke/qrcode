# QR Code Generator Project Scope

Last updated: 2026-05-27

## Project State

This project is in planning only. No application code should be written until the planning scope is agreed.

The only intended artifact at this stage is this document: `./plan/scope.md`.

## Product Goal

Build a clean, elegant, self-hostable web application for generating QR codes. Users should enter content, configure visual options, preview the generated code, and download it as a file.

The project should start with a stable QR-code core and remain extensible so barcode formats and additional QR payload types can be added later without major restructuring.

## Initial Hosting Direction

Primary deployment target:

- Self-hosted Docker deployment.
- Docker Compose is the main documented setup for self-hosting.
- The Docker container should include the web server needed to serve the application.
- The first release should be packaged as a single self-contained web app container unless a later technical constraint requires otherwise.
- Persistent storage is not required for the first release because the app is stateless.

Deployment options still to discuss:

- None currently for the first-release deployment model.

Future deployment effort:

- Standalone installable binaries are out of initial scope and should be considered after the Docker-based application is stable.
- Future binary packaging may include Linux, macOS, and Windows, but target platforms do not need to be decided yet.

## Website Experience

The app should present a clean, elegant website for user input and code generation.

Expected website workflow:

1. Select payload type.
2. Enter payload details.
3. Configure visual options.
4. Preview generated result.
5. Download as PNG, JPG, SVG, or PDF.

The interface should be practical and focused on generating codes, not a marketing site.

Dark mode decision:

- Optional dark mode is part of the first stable release.
- Dark mode is useful because this is a utility that users may keep open while working, and the UI will likely include color pickers, previews, and form controls that benefit from reduced eye strain.
- Dark mode should be a UI preference only. It must not change the generated QR code colors unless the user explicitly changes foreground/background colors.
- The app should still default generated codes to high-contrast, scanner-friendly colors.

## Technology Direction

Decision:

- Backend: Go.
- Frontend: TypeScript with a lightweight modern framework.
- Packaging: Docker, with Docker Compose for local/self-hosted deployment.

Rationale:

- Go is a strong fit for a self-hosted utility because it builds into a small standalone binary, has good Docker ergonomics, simple deployment, and mature image/SVG/PDF libraries.
- TypeScript is a strong fit for a polished web UI and maintainable form-heavy workflows.
- A Go backend can expose a clear generation API and keep generation logic centralized.

Frontend framework options to evaluate:

- SvelteKit: concise, good for polished interactive tools, simple app structure.
- React with Vite: very common ecosystem, broad component/library support.
- Vue: approachable, good for form-heavy interfaces.

Alternative stacks to consider:

- Full-stack TypeScript/Node.js: simpler single-language development, but standalone binary distribution is less clean than Go.
- Python/FastAPI: productive and library-rich, but Docker-first deployment would be preferred over binary distribution.
- Rust: excellent binary story and performance, but likely slower to develop.

Current decision: use a Go backend with a TypeScript frontend.

## Code Formats

Initial required formats:

- QR Code.

Extensibility requirement:

- The project should be structured around pluggable code format generators so future barcode formats can be added cleanly.
- Each format should define its own validation, supported payloads, render options, and export capabilities.

Future barcode/code formats:

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

Recommended QR payload support for initial stable release:

- URL: generate a normal URL string after validation.
- Geo location: generate `geo:lat,long` payloads.
- Plain text: generate raw text payloads.

Future payload types:

- Digital business card.
- WiFi hotspot.
- Email.
- SMS.
- Phone number.
- Calendar event.

Planned digital business card encoding format:

- vCard.

Planning note:

- Decide later whether to use vCard 3.0 or vCard 4.0 based on scanner compatibility and implementation details.

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

- Confirm whether personal phone and work phone should both be included when present.
- Confirm whether address fields should support multiple addresses in the future.

## WiFi Hotspot Future Scope

Add after the core code generation feature is stable.

Fields requested:

- Network name.
- Password.
- Encryption.

Encryption options requested:

- None.
- WPA/WPA2.
- WPA3.
- WEP.

Planning note:

- The user wrote `WAP3`; likely intended `WPA3`. Confirm before implementation.
- Need to define how hidden SSIDs should be handled.

## Visual Options

Required visual options:

- Selectable foreground color.
- Selectable background color.
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
- Uploaded logos should be used temporarily for the current generation request and should not be stored by the application.
- Logo upload should support PNG and JPEG/JPG files.
- SVG logos do not need to be supported.
- Logo support should probably require or recommend higher error correction, especially Q or H.
- The app should validate that a logo does not make the QR code unreadable.

Border types:

- Quiet-zone only.
- Solid frame.
- Rounded frame.
- Label/caption frame.
- Transparent padding.

Border planning notes:

- QR codes require a quiet zone for reliable scanning, so visual border settings must not break scan reliability.

## Export Formats

Required download formats:

- PNG.
- JPG.
- SVG.
- PDF.

Website requirement:

- The website should include a download button for the selected output format.

Planning notes:

- SVG is best for vector use and print workflows.
- PNG is best for quick sharing and common document insertion.
- JPG is useful when users need broad compatibility with systems that do not accept PNG or SVG.
- PDF is useful for print and layout workflows.
- Need to decide whether PDF should contain only the code or support page layout options such as page size, margins, and labels.

## Persistence Model

Decision:

- The first version should be stateless and temporary.
- The app should not save generation history, reusable templates, payload data, generated files, or uploaded logos in the initial release.
- Uploaded logos are allowed for QR generation, but they should be processed only for the current request and discarded afterward.

Stateless behavior:

- Users enter data, configure the code, generate/download the result, and nothing is saved by the application after the request finishes.
- This keeps the first version simpler because it likely does not need a database, user accounts, stored uploads, backup strategy, or data cleanup jobs.
- This is a good fit for a private self-hosted utility where users mainly need quick one-off QR codes.
- Tradeoff: users cannot return later to reuse a previous code, edit a saved configuration, or manage a library of templates.

Future saved history/templates option:

- The app stores generated-code records, reusable visual presets, payload templates, and possibly uploaded logos.
- This is useful if users expect repeated workflows, shared branding, auditability, or a searchable library of past codes.
- This adds product value but increases implementation scope because the app needs persistent storage, data models, migration strategy, backup guidance, and possibly authentication.
- If enabled, we need to decide what is saved: payload data, visual settings, generated files, uploaded logos, timestamps, and user ownership.

Implementation guidance:

- Design the request and generation model so persistence can be added later without rewriting the generator internals.

## Suggested Architecture

Planning concept:

- A web frontend gathers input and shows a live or near-live preview.
- A backend generation API validates payloads and render options.
- The first release should have API-shaped backend routes for the website to call, but these routes do not need to be documented or supported as a public automation API yet.
- Code format generators are isolated behind a shared interface.
- Export renderers produce PNG, JPG, SVG, and PDF from a normalized generated-code representation.

Possible internal modules:

- `payloads`: URL, geo, plain text, future vCard, future WiFi.
- `formats`: QR Code, future barcode formats.
- `rendering`: colors, borders, logos, quiet zones, dimensions.
- `exports`: PNG, JPG, SVG, PDF.
- `api`: HTTP routes, request validation, error responses.
- `web`: frontend application.

Key design principle:

- Payload types and code formats should not be tightly coupled. For example, URL and plain text payloads are QR payloads, while a future UPC-A format would have a numeric barcode-specific payload.
- Keep request and response structures clean enough that a documented HTTP API can be promoted later without rewriting the generation core.

## HTTP API Direction

Decision:

- The first release should include backend HTTP routes used by the website for QR generation, preview, validation, and file download.
- Those routes should be designed cleanly, but they are considered internal application routes at first.
- A documented public HTTP API for external automation is a future capability, not a first-release commitment.

Rationale:

- The website will need a generation interface anyway, so the backend should use clear request and response structures from the start.
- Deferring public API support avoids extra first-release work around versioning, formal documentation, authentication behavior, rate limits, and long-term compatibility.
- This keeps the project extensible for future scripts, integrations, and batch generation.

## Validation Rules To Define

URL:

- Require a valid scheme such as `http` or `https`.
- Decide whether to auto-prefix `https://` when omitted.

Location:

- Latitude must be between -90 and 90.
- Longitude must be between -180 and 180.
- Decide display precision and validation behavior.

Plain text:

- Decide max length for UI and generation.
- Show a warning when text length creates a dense or hard-to-scan QR code.

Future UPC-A:

- UPC-A is numeric and typically 12 digits including check digit, or 11 digits with check digit generated.
- Decide whether the app accepts 11 digits and calculates the check digit automatically.
- Decide whether to display human-readable digits under the barcode.

Colors:

- Ensure sufficient contrast between foreground and background.
- Warn or block combinations likely to fail scanning.

Logo:

- Validate file type, dimensions, and maximum size.
- Accept PNG and JPEG/JPG logos.
- Do not support SVG logos in the first release.
- Process uploaded logos temporarily and do not persist them after generation.

## Testing And CI

Hosting target:

- The project will be hosted on GitHub.
- GitHub Actions is the recommended CI system unless a later requirement points elsewhere.

Recommended test layers:

- Backend unit tests for QR payload generation, URL validation, geo validation, plain text handling, error correction options, color validation, border options, logo handling, and export rendering.
- Backend integration tests for HTTP routes used by the website, including preview and download endpoints.
- Frontend unit/component tests for form behavior, validation states, option selection, dark mode, and download controls.
- End-to-end browser tests for the main user flows: generate URL QR code, generate geo QR code, generate plain text QR code, upload logo, change colors, switch dark mode, and download each required format.
- Image/export tests that verify PNG, JPG, SVG, and PDF outputs are generated, non-empty, and have expected dimensions/content characteristics.
- Accessibility checks for the website UI, especially form labels, keyboard navigation, contrast, and dark mode.
- Docker smoke tests that build the container, start it, and verify the web server responds.

Recommended GitHub Actions pipeline:

- Pull request workflow: run formatting checks, linting, backend tests, frontend tests, and a Docker build smoke test.
- Main branch workflow: run the full pull request workflow plus end-to-end tests.
- Release workflow: build and publish Docker images after tags or GitHub releases are created.
- Dependency/security workflow: scan Go and TypeScript dependencies, run static analysis where practical, and enable automated dependency update PRs.

Recommended quality gates:

- Go formatting and vet/static checks.
- TypeScript type checking.
- Frontend linting.
- Backend and frontend test suites.
- Docker image builds successfully.
- Basic browser flow passes before release.

Testing priorities for the first stable release:

- QR codes should be scanner-reliable for default settings.
- Export files should be valid in all required formats: PNG, JPG, SVG, and PDF.
- Logo upload should be validated and should not persist files.
- Color and border choices should not silently create unusable codes without warning.
- Docker Compose should start the app consistently.

## Phased Scope

Phase 1: Planning

- Capture project requirements.
- Decide stack.
- Decide deployment model.
- Decide first release scope.
- Define UX and architecture at a high level.

Phase 2: Core MVP

- Single Dockerized web app container with included web server.
- Web UI.
- Internal backend routes for website-driven QR generation and downloads.
- QR generation for URL, geo location, and plain text.
- Color selection.
- Error correction selection with M default.
- Border type and width options.
- Temporary custom logo upload for QR codes.
- Optional dark mode for the website UI.
- PNG, JPG, SVG, and PDF downloads.

Phase 3: Stabilization

- Improve validation and scanner reliability warnings.
- Add tests around QR payload encoding, rendering, and exports.
- Add CI through GitHub Actions for linting, type checks, tests, Docker builds, and release image publishing.
- Refine UI and Docker deployment documentation.

Phase 4: Advanced QR Payloads

- Digital business card.
- WiFi hotspot.

Phase 5: Additional Code Formats

- Add barcode and additional 2D code formats through the extensible generator structure.
- UPC-A is a future capability, not part of the first stable release.

Phase 6: Additional Deployment Options

- Evaluate standalone installable binaries after the Docker deployment is stable.
- Decide whether to provide release binaries for Linux, macOS, Windows, or a smaller initial subset.

## Key Open Questions

1. Is authentication needed, or should this be a private/self-hosted unauthenticated tool by default?
2. Should PDFs be just the generated code, or should they support print layouts such as page size, margins, and labels?
3. Should the app support transparent backgrounds for PNG/SVG?
4. Should QR previews update live while editing, or only after clicking a generate button?
5. Should there be presets, such as print, web, high-contrast, logo-safe, or label-ready?

## Current Assumptions

- Docker self-hosting is required.
- Docker Compose is the main documented setup.
- The implementation stack is Go backend plus TypeScript frontend.
- The first release should be a single self-contained Docker web app container with an included web server.
- Standalone binary installation is a future effort, not part of the initial release scope.
- The first release should be stateless and should not require persistent storage or a persistent database.
- The backend should expose internal HTTP routes for the website, while a documented external automation API is a future capability.
- Temporary custom logo upload for QR codes is part of the first stable release.
- Optional dark mode for the website UI is part of the first stable release.
- QR Code is the only first-release code format.
- Barcode generation, including UPC-A, is a future capability.
- URL, location, and plain text are the first QR payload types.
- Digital business card and WiFi hotspot are planned later, after the core app is stable.
- Digital business cards should use vCard format.
- Error correction level M is the default for QR codes.
- PNG, JPG, SVG, and PDF are required export formats.
- Logo uploads should support PNG and JPEG/JPG, but not SVG.
- Supported border types are quiet-zone only, solid frame, rounded frame, label/caption frame, and transparent padding.
- GitHub Actions is the recommended CI system.
- The project should prioritize scan reliability over visual customization when those goals conflict.
