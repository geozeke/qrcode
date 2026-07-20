# QR Code Generator

<img
  src="assets/qr-logo.png"
  alt="QR code encoding message"
  width="180"
/>

QR Code Generator is a focused, self-hostable web utility for creating
scanner-safe QR codes. It accepts website URLs, geographic coordinates,
plain text, and WiFi network details.

Generated codes can use square or dot modules, configurable colors,
frames, captions, and an optional logo. Exports are available as PNG,
JPG, SVG, and PDF.

## Privacy model

The application is stateless:

- Payloads, uploaded logos, render tokens, and generated files are not
  persisted.
- Rendering happens in bounded, disposable worker processes.
- Application logs exclude request bodies and other submitted private
  data.
- The application does not include analytics or external error
  reporting.

Anyone who can reach an instance can use it. Restrict access through
private networking, a firewall, VPN, or reverse-proxy controls when
appropriate.

## Continue

- [Install and run the application](getting-started.md)
- [Create and export QR codes](user-guide.md)
- [Deploy behind a reverse proxy](deployment.md)
- [Set up a development environment](development.md)
- [Read the active changelog](https://github.com/geozeke/qrcode/blob/main/CHANGELOG.md)
- [Browse archived changelogs](https://github.com/geozeke/qrcode/tree/main/changelogs)
