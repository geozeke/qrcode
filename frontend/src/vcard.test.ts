import { describe, expect, it } from 'vitest';
import { MAX_VCARD_FILE_BYTES, parseVCard, readVCardFile } from './vcard';

describe('vCard import', () => {
  it('imports supported vCard 3.0 fields and reports omitted values', () => {
    const imported = parseVCard(
      [
        'BEGIN:VCARD',
        'VERSION:3.0',
        'N:Lovelace;Ada;;;',
        'FN:Ada Lovelace',
        'ORG:Analytical Engines;Research',
        'TITLE:Mathematician',
        'TEL;TYPE=CELL,PREF:+44 20 1',
        'TEL;TYPE=WORK,VOICE:+44 20 2',
        'TEL;TYPE=WORK,FAX:+44 20 3',
        'EMAIL;TYPE=INTERNET:ada@example.com',
        'ADR;TYPE=WORK:;;1 Engine Way;London;;SW1A;United Kingdom',
        'URL:https://example.com',
        'NOTE:Not imported',
        'END:VCARD',
      ].join('\r\n'),
    );

    expect(imported.fields).toMatchObject({
      given_name: 'Ada',
      family_name: 'Lovelace',
      personal_phone: '+44 20 1',
      work_phone: '+44 20 2',
      fax: '+44 20 3',
      company: 'Analytical Engines',
      street: '1 Engine Way',
      website_url: 'https://example.com',
    });
    expect(imported.omittedProperties).toEqual(['NOTE']);
    expect(imported.usedFallbackAddress).toBe(false);
  });

  it('imports grouped and folded vCard 4.0 properties with FN fallback', () => {
    const imported = parseVCard(
      [
        '\uFEFFBEGIN:VCARD',
        'VERSION:4.0',
        'FN:Zoë Example',
        'item1.TEL;TYPE=cell:tel:+1-202-555-0100',
        'ADR:;;123 Long Street;New',
        '  York;NY;10001;USA',
        'END:VCARD',
      ].join('\n'),
    );

    expect(imported.fields.given_name).toBe('Zoë Example');
    expect(imported.fields.personal_phone).toBe('+1-202-555-0100');
    expect(imported.fields.city).toBe('New York');
    expect(imported.usedFallbackAddress).toBe(true);
  });

  it.each([
    [
      'multiple contacts',
      'BEGIN:VCARD\nVERSION:3.0\nN:B;A;;;\nEND:VCARD\nBEGIN:VCARD\nVERSION:3.0\nN:D;C;;;\nEND:VCARD',
    ],
    ['unsupported version', 'BEGIN:VCARD\nVERSION:2.1\nN:B;A;;;\nEND:VCARD'],
    ['missing name', 'BEGIN:VCARD\nVERSION:4.0\nEMAIL:a@example.com\nEND:VCARD'],
    ['nonconforming vCard 3.0 name', 'BEGIN:VCARD\nVERSION:3.0\nFN:Ada Lovelace\nEND:VCARD'],
    ['encoded property', 'BEGIN:VCARD\nVERSION:3.0\nN;ENCODING=QUOTED-PRINTABLE:B;A;;;\nEND:VCARD'],
  ])('rejects %s', (_label, value) => {
    expect(() => parseVCard(value)).toThrow();
  });

  it('bounds uploaded files and requires a UTF-8 .vcf extension', async () => {
    const wrongExtension = new File(['BEGIN:VCARD'], 'contact.txt');
    const oversized = new File([new Uint8Array(MAX_VCARD_FILE_BYTES + 1)], 'contact.vcf');
    const invalidUtf8 = new File([new Uint8Array([0xff, 0xfe])], 'contact.vcf');

    await expect(readVCardFile(wrongExtension)).rejects.toThrow(/\.vcf/);
    await expect(readVCardFile(oversized)).rejects.toThrow(/64 KiB/);
    await expect(readVCardFile(invalidUtf8)).rejects.toThrow(/UTF-8/);
  });
});
