import { describe, expect, it } from 'vitest';
import { previewErrorMessage, roundCoordinate, validatePayload, type PayloadFields } from './forms';

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
    expect(
      validatePayload(
        fields({
          payload_type: 'geo',
          latitude: '40.71281234567890',
          longitude: '-74.00601250000000',
        }),
      ),
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

describe('coordinate rounding', () => {
  it('rounds excess precision half away from zero', () => {
    expect(roundCoordinate('40.71281234567890')).toBe('40.712812');
    expect(roundCoordinate('-74.00601250000000')).toBe('-74.006013');
    expect(roundCoordinate('1.9999999')).toBe('2.000000');
    expect(roundCoordinate('-0.0000005')).toBe('-0.000001');
  });

  it('preserves valid inputs that already have six or fewer decimals', () => {
    expect(roundCoordinate('40.7128')).toBe('40.7128');
    expect(roundCoordinate('-74.006000')).toBe('-74.006000');
  });
});

describe('operational errors', () => {
  it('provides specific recovery messages for resource failures', () => {
    expect(previewErrorMessage(413)).toMatch(/5 MiB/);
    expect(previewErrorMessage(503, 'render_busy')).toMatch(/busy/);
    expect(previewErrorMessage(504, 'render_timeout')).toMatch(/too long/);
  });
});
