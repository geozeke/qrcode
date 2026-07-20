import { describe, expect, it } from 'vitest';
import { previewErrorMessage, validatePayload, type PayloadFields } from './forms';

function fields(overrides: Partial<PayloadFields> = {}): PayloadFields {
  return {
    payload_type: 'url',
    url: 'example.com',
    latitude: '',
    longitude: '',
    text: '',
    security: 'wpa',
    ssid: '',
    password: '',
    ...overrides,
  };
}

describe('payload validation', () => {
  it('accepts scanner-safe URL and coordinate inputs', () => {
    expect(validatePayload(fields())).toEqual({});
    expect(
      validatePayload(fields({ payload_type: 'geo', latitude: '-90', longitude: '180.000000' })),
    ).toEqual({});
  });

  it('rejects incomplete and out-of-contract values', () => {
    expect(validatePayload(fields({ url: 'ftp://example.com' })).url).toMatch(/HTTP/);
    expect(
      validatePayload(fields({ payload_type: 'geo', latitude: '90.1', longitude: '181' })),
    ).toMatchObject({ latitude: expect.any(String), longitude: expect.any(String) });
    expect(validatePayload(fields({ payload_type: 'text', text: '' })).text).toBeDefined();
  });

  it('matches WiFi byte and password constraints', () => {
    expect(
      validatePayload(
        fields({ payload_type: 'wifi', security: 'wpa', ssid: 'Office', password: 'password123' }),
      ),
    ).toEqual({});
    expect(
      validatePayload(
        fields({ payload_type: 'wifi', security: 'wpa', ssid: 'Office', password: 'short' }),
      ).password,
    ).toBeDefined();
  });
});

describe('operational errors', () => {
  it('provides specific recovery messages for resource failures', () => {
    expect(previewErrorMessage(413)).toMatch(/5 MiB/);
    expect(previewErrorMessage(503, 'render_busy')).toMatch(/busy/);
    expect(previewErrorMessage(504, 'render_timeout')).toMatch(/too long/);
  });
});
