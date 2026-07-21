# Changelog

All notable changes to QR Code Generator are documented here. The
format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-07-21

[Compare with 0.1.0](https://github.com/geozeke/qrcode/compare/v0.1.0...v0.1.1)

### Security

- Improve dependency audit logs (#24) ([cdbdee4](https://github.com/geozeke/qrcode/commit/cdbdee4ed1c1eb89f36634381de6ce2b6ae2cd8f))

## [0.1.0] - 2026-07-20

[View release tag](https://github.com/geozeke/qrcode/releases/tag/v0.1.0)

### Added

- Generate scanner-safe QR codes for URL, text, geographic, and WiFi
  payloads.
- Preview and export QR codes as PNG, JPG, SVG, or PDF.
- Customize module style, colors, borders, captions, and validated
  logos.
- Use a responsive, accessible interface with persistent dark mode.
- Deploy a stateless, hardened container with Docker Compose and health
  checks.

### Security

- Keep payloads private with stateless rendering, bounded workers,
  request limits, sanitized errors, privacy-safe logs, and response
  security headers.

### Documentation

- Provide user, deployment, and contributor documentation through
  Zensical.

### Fixed

- Fix local upgrade tooling ([f88f158](https://github.com/geozeke/qrcode/commit/f88f158c4af08faf6d0a7d716ffe21cfbf673eb2))
- Fix release validator ([254a97b](https://github.com/geozeke/qrcode/commit/254a97befae263adb2dbc3cdfd218a5cd25f9909))

### Deployment & Operations

- Update CI pipeline (#13) ([c513c92](https://github.com/geozeke/qrcode/commit/c513c92e5dc519c235efbcb18b1c91f30ca6fff4))
- Update dockerhub semantic versioning to support minor tags ([6d99272](https://github.com/geozeke/qrcode/commit/6d992728f8109111597aed5de4be090971ba71f5))
- Set up CI pipeline for dockerhub metadata ([12ae29a](https://github.com/geozeke/qrcode/commit/12ae29a5e5401e6ae1cee31608a2a4f9f97e251b))

### Dependencies

- *(deps)* Upgrade direct dependencies ([8410a62](https://github.com/geozeke/qrcode/commit/8410a62715250039a4f5f89a631dcd874461e943))
