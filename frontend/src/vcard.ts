export const MAX_VCARD_FILE_BYTES = 64 * 1024;

export interface ImportedVCard {
  fields: {
    given_name: string;
    family_name: string;
    personal_phone: string;
    email: string;
    company: string;
    work_title: string;
    work_phone: string;
    fax: string;
    street: string;
    city: string;
    state: string;
    postal_code: string;
    country: string;
    website_url: string;
  };
  omittedProperties: string[];
  usedFallbackAddress: boolean;
}

interface Property {
  name: string;
  types: Set<string>;
  parameters: Map<string, string>;
  value: string;
  index: number;
}

function splitUnescaped(value: string, delimiter: string): string[] {
  const parts: string[] = [];
  let current = '';
  let escaped = false;
  for (const character of value) {
    if (escaped) {
      current += `\\${character}`;
      escaped = false;
    } else if (character === '\\') {
      escaped = true;
    } else if (character === delimiter) {
      parts.push(current);
      current = '';
    } else {
      current += character;
    }
  }
  if (escaped) current += '\\';
  parts.push(current);
  return parts;
}

function unescapeText(value: string): string {
  return value.replace(/\\([nN\\;,])/g, (_match, escaped: string) =>
    escaped.toLowerCase() === 'n' ? '\n' : escaped,
  );
}

function contentSeparator(line: string): number {
  let quoted = false;
  let escaped = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (escaped) escaped = false;
    else if (character === '\\') escaped = true;
    else if (character === '"') quoted = !quoted;
    else if (character === ':' && !quoted) return index;
  }
  return -1;
}

function parseProperty(line: string, index: number): Property {
  const separator = contentSeparator(line);
  if (separator < 1) throw new Error('The vCard contains a malformed property.');
  const head = line.slice(0, separator);
  const segments = head.split(';');
  const name = (segments.shift() ?? '').split('.').at(-1)?.toUpperCase() ?? '';
  const parameters = new Map<string, string>();
  const types = new Set<string>();
  for (const segment of segments) {
    const equals = segment.indexOf('=');
    const key = (equals < 0 ? 'TYPE' : segment.slice(0, equals)).toUpperCase();
    const parameterValue = (equals < 0 ? segment : segment.slice(equals + 1)).replace(/^"|"$/g, '');
    parameters.set(key, parameterValue);
    if (key === 'TYPE') {
      for (const type of parameterValue.split(',')) types.add(type.toUpperCase());
    }
  }
  if (parameters.has('ENCODING')) {
    throw new Error('Encoded vCard properties are not supported.');
  }
  return { name, types, parameters, value: line.slice(separator + 1), index };
}

function preference(property: Property): number {
  if (property.types.has('PREF')) return 0;
  const value = Number(property.parameters.get('PREF'));
  return Number.isFinite(value) && value > 0 ? value : 1000;
}

function choose(
  properties: Property[],
  predicate = (property: Property): boolean => property.index >= 0,
) {
  return properties
    .filter(predicate)
    .sort((left, right) => preference(left) - preference(right))[0];
}

export function parseVCard(source: string): ImportedVCard {
  const text = source.replace(/^\uFEFF/, '').replace(/\r\n|\r/g, '\n');
  const physicalLines = text.split('\n');
  const lines: string[] = [];
  for (const line of physicalLines) {
    if (/^[ \t]/.test(line) && lines.length) lines[lines.length - 1] += line.slice(1);
    else lines.push(line);
  }
  const begins = lines.filter((line) => line.toUpperCase() === 'BEGIN:VCARD');
  const ends = lines.filter((line) => line.toUpperCase() === 'END:VCARD');
  if (begins.length !== 1 || ends.length !== 1) {
    throw new Error('Choose a .vcf file containing exactly one contact.');
  }
  const begin = lines.findIndex((line) => line.toUpperCase() === 'BEGIN:VCARD');
  const end = lines.findIndex((line) => line.toUpperCase() === 'END:VCARD');
  if (begin >= end) throw new Error('The vCard structure is invalid.');

  const properties = lines
    .slice(begin + 1, end)
    .filter(Boolean)
    .map((line, index) => parseProperty(line, index));
  const version = properties.find((property) => property.name === 'VERSION')?.value;
  if (version !== '3.0' && version !== '4.0') {
    throw new Error('Only vCard 3.0 and 4.0 files are supported.');
  }
  const consumed = new Set<number>();
  const take = (property: Property | undefined): string => {
    if (!property) return '';
    consumed.add(property.index);
    return unescapeText(property.value).trim();
  };
  for (const property of properties.filter((item) => ['VERSION', 'FN', 'N'].includes(item.name))) {
    consumed.add(property.index);
  }

  const name = properties.find((property) => property.name === 'N');
  const nameParts = name ? splitUnescaped(name.value, ';').map(unescapeText) : [];
  const family_name = (nameParts[0] ?? '').trim();
  let given_name = (nameParts[1] ?? '').trim();
  if (!family_name && !given_name && version === '4.0') {
    given_name = take(properties.find((property) => property.name === 'FN'));
  }
  if (!family_name && !given_name) throw new Error('The vCard does not contain a contact name.');

  const phones = properties.filter((property) => property.name === 'TEL');
  const personal = choose(
    phones,
    (property) => property.types.has('CELL') || property.types.has('HOME'),
  );
  const work = choose(
    phones,
    (property) => property.types.has('WORK') && !property.types.has('FAX'),
  );
  const faxProperty = choose(phones, (property) => property.types.has('FAX'));
  const cleanPhone = (property: Property | undefined): string =>
    take(property).replace(/^tel:/i, '');

  const addresses = properties.filter((property) => property.name === 'ADR');
  const workAddress = choose(addresses, (property) => property.types.has('WORK'));
  const address = workAddress ?? choose(addresses);
  const addressParts = address
    ? splitUnescaped(address.value, ';').map((part) => unescapeText(part).trim())
    : [];
  if (address) consumed.add(address.index);

  const organization = choose(properties.filter((property) => property.name === 'ORG'));
  const organizationName = organization
    ? unescapeText(splitUnescaped(organization.value, ';')[0]).trim()
    : '';
  if (organization) consumed.add(organization.index);
  const fields = {
    given_name,
    family_name,
    personal_phone: cleanPhone(personal),
    email: take(choose(properties.filter((property) => property.name === 'EMAIL'))),
    company: organizationName,
    work_title: take(choose(properties.filter((property) => property.name === 'TITLE'))),
    work_phone: cleanPhone(work),
    fax: cleanPhone(faxProperty),
    street: addressParts[2] ?? '',
    city: addressParts[3] ?? '',
    state: addressParts[4] ?? '',
    postal_code: addressParts[5] ?? '',
    country: addressParts[6] ?? '',
    website_url: take(choose(properties.filter((property) => property.name === 'URL'))),
  };
  const omittedProperties = [
    ...new Set(
      properties
        .filter((property) => !consumed.has(property.index))
        .map((property) => property.name)
        .filter((property) => property !== 'VERSION'),
    ),
  ].sort();
  if (nameParts.slice(2).some((part) => part)) omittedProperties.push('N');
  return {
    fields,
    omittedProperties: [...new Set(omittedProperties)].sort(),
    usedFallbackAddress: Boolean(address && !workAddress),
  };
}

export async function readVCardFile(file: File): Promise<ImportedVCard> {
  if (!file.name.toLowerCase().endsWith('.vcf')) throw new Error('Choose a .vcf file.');
  if (file.size > MAX_VCARD_FILE_BYTES) throw new Error('The .vcf file must be 64 KiB or smaller.');
  const bytes = await file.arrayBuffer();
  let text: string;
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  } catch {
    throw new Error('The .vcf file must use UTF-8 text.');
  }
  return parseVCard(text);
}
