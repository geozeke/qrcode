export type PayloadType = 'url' | 'geo' | 'text' | 'wifi';
export type OutputFormat = 'png' | 'jpg' | 'svg' | 'pdf';
export type Theme = 'light' | 'dark';

export interface PayloadFields {
  payload_type: PayloadType;
  url: string;
  latitude: string;
  longitude: string;
  text: string;
  security: string;
  ssid: string;
  password: string;
}

export type FieldErrors = Partial<Record<string, string>>;

const encoder = new TextEncoder();

function byteLength(value: string): number {
  return encoder.encode(value).length;
}

function containsControl(value: string): boolean {
  return [...value].some((character) => {
    const code = character.charCodeAt(0);
    return code < 32 || code === 127;
  });
}

function validCoordinate(value: string, lower: number, upper: number): boolean {
  if (!/^-?\d+(?:\.\d{1,6})?$/.test(value)) return false;
  const coordinate = Number(value);
  return Number.isFinite(coordinate) && coordinate >= lower && coordinate <= upper;
}

export function validatePayload(fields: PayloadFields): FieldErrors {
  const errors: FieldErrors = {};
  if (fields.payload_type === 'url') {
    const value = fields.url.trim();
    if (!value) {
      errors.url = 'Enter a website URL.';
    } else if (/\s/.test(value) || containsControl(value)) {
      errors.url = 'URLs cannot contain whitespace or control characters.';
    } else {
      try {
        const candidate = new URL(value.includes('://') ? value : `https://${value}`);
        if (!['http:', 'https:'].includes(candidate.protocol) || !candidate.hostname) {
          errors.url = 'Enter a valid HTTP or HTTPS URL.';
        }
      } catch {
        errors.url = 'Enter a valid HTTP or HTTPS URL.';
      }
    }
  } else if (fields.payload_type === 'geo') {
    if (!validCoordinate(fields.latitude, -90, 90)) {
      errors.latitude = 'Enter a latitude from −90 to 90 with up to six decimals.';
    }
    if (!validCoordinate(fields.longitude, -180, 180)) {
      errors.longitude = 'Enter a longitude from −180 to 180 with up to six decimals.';
    }
  } else if (fields.payload_type === 'text') {
    const size = byteLength(fields.text);
    if (size < 1 || size > 1000) {
      errors.text = 'Enter between 1 and 1,000 UTF-8 bytes of text.';
    }
  } else {
    const ssidSize = byteLength(fields.ssid);
    if (ssidSize < 1 || ssidSize > 32 || containsControl(fields.ssid)) {
      errors.ssid = 'Enter an SSID of 1 to 32 UTF-8 bytes without control characters.';
    }
    if (fields.security === 'wpa') {
      if (
        fields.password.length < 8 ||
        fields.password.length > 63 ||
        /[^\x20-\x7e]/.test(fields.password)
      ) {
        errors.password = 'Enter 8 to 63 printable ASCII characters.';
      }
    } else if (fields.security === 'wep') {
      const ascii =
        [5, 13].includes(fields.password.length) && /^[\x20-\x7e]+$/.test(fields.password);
      const hex = [10, 26].includes(fields.password.length) && /^[0-9a-f]+$/i.test(fields.password);
      if (!ascii && !hex) errors.password = 'Enter a valid 5/13-character or 10/26-digit WEP key.';
    }
  }
  return errors;
}

export function previewErrorMessage(status: number, code?: string): string {
  if (status === 413 || code === 'request_too_large') {
    return 'The request or logo is larger than the 5 MiB limit.';
  }
  if (status === 503 || code === 'render_busy') {
    return 'The renderer is busy. The preview will retry after your next change.';
  }
  if (status === 504 || code === 'render_timeout') {
    return 'Rendering took too long. Try a smaller payload or logo.';
  }
  return 'Could not create a preview.';
}
