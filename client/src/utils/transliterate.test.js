import { describe, it, expect } from 'vitest';
import cases from '../../../tests/fixtures/transliteration_cases.json';
import { greekToLatin, greekToBetaCode, hebrewToLatin, hasOriginalScript } from './transliterate';

describe('the shared transliteration cases', () => {
  it('has at least forty cases', () => {
    expect(cases.length).toBeGreaterThanOrEqual(40);
  });
  cases.filter((c) => c.greek).forEach((c) => {
    it(`greek ${c.greek}`, () => expect(greekToLatin(c.greek)).toBe(c.latin));
  });
  cases.filter((c) => c.beta).forEach((c) => {
    it(`beta ${c.greek}`, () => expect(greekToBetaCode(c.greek)).toBe(c.beta));
  });
  cases.filter((c) => c.hebrew).forEach((c) => {
    it(`hebrew ${c.hebrew}`, () => expect(hebrewToLatin(c.hebrew)).toBe(c.latin));
  });
});

describe('finding Greek and Hebrew in text', () => {
  it('sees Greek and Hebrew and ignores English', () => {
    expect(hasOriginalScript('the good life, τὸ εὖ ζῆν')).toBe(true);
    expect(hasOriginalScript('שלום')).toBe(true);
    expect(hasOriginalScript('only English here')).toBe(false);
  });
});
