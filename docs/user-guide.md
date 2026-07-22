# User guide

## Create a code

1. Select a content type and enter its required fields.
2. Choose appearance settings while keeping scan reliability in mind.
3. Wait for the live preview to finish.
4. Select an export format and download the validated preview.

Changing any field invalidates the previous download until the updated
preview succeeds. Superseded preview requests are cancelled.

## Content types

### Website URL

Enter an HTTP or HTTPS URL. If the scheme is omitted, the application
adds `https://`.

### Location

Enter decimal latitude and longitude coordinates. Values with more than
six fractional digits are rounded to six places, providing roughly
11-centimeter coordinate resolution.

### Plain text

Enter up to 1,000 UTF-8 bytes. Text is preserved as entered.

### WiFi hotspot

Choose Open, WPA/WPA2/WPA3 Personal, or WEP security and enter the
network details. WiFi credentials exist only in the request and
generated QR code; they are not stored or logged by the application.

## Appearance and logos

Dot modules require Q or H error correction. Logos require square
modules and H error correction; selecting a logo applies those safe
settings automatically. PNG and JPEG logos up to 5 MiB are accepted.

Generated foreground and background colors must meet the application's
scanner-safety contrast rules. Dark mode changes only the interface and
never changes generated QR colors.

## Exports

- PNG supports transparent backgrounds and three digital scales.
- JPG uses an opaque background.
- SVG preserves vector QR geometry and can use transparency.
- PDF provides physical symbol, page, orientation, margin, and caption
  controls.
