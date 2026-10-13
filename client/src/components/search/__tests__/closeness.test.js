import { describe, it, expect } from 'vitest';
import { closenessSort, closenessLabel } from '../closeness';

const quote = { quotation: true, n_surface: 4, n_matched: 2, span: 2, year: 100, author: 'Martial' };
const rework = { quotation: false, n_surface: 3, n_matched: 2, span: 6, year: -20, author: 'Tibullus' };
const together = { quotation: false, n_surface: 2, n_matched: 2, span: 2, year: 60, author: 'Lucan' };
const apart = { quotation: false, n_surface: 1, n_matched: 2, span: 9, year: -50, author: 'Caesar' };
const oneWord = { quotation: false, n_surface: 1, n_matched: 1, span: 1, year: -200, author: 'Plautus' };

describe('closenessSort', () => {
  it('puts the quotation first, then more of the typed words, then the closer window, then the older text', () => {
    const out = [oneWord, apart, together, rework, quote].sort(closenessSort);
    expect(out.map((r) => r.author)).toEqual(['Martial', 'Tibullus', 'Lucan', 'Caesar', 'Plautus']);
  });
  it('an older line wins a tie', () => {
    const a = { ...together, year: 100, author: 'B' };
    const b = { ...together, year: -100, author: 'A' };
    expect([a, b].sort(closenessSort).map((r) => r.author)).toEqual(['A', 'B']);
  });
});

describe('closenessLabel', () => {
  it('is silent for a one-word query', () => {
    expect(closenessLabel(quote, 1, 1)).toBeNull();
    expect(closenessLabel(quote, 0, 0)).toBeNull();
  });
  it('says "key words" when the search dropped common words of the query', () => {
    expect(closenessLabel(quote, 2, 4).text).toBe('whole phrase');
    expect(closenessLabel(together, 2, 4).text).toBe('key words together');
    expect(closenessLabel(apart, 2, 4).text).toBe('key words apart');
    expect(closenessLabel(oneWord, 2, 4).text).toBe('1 of 2 key words');
  });
  it('says "words" when every word of the query was searched', () => {
    expect(closenessLabel(together, 2, 2).text).toBe('all words, together');
    expect(closenessLabel(apart, 2, 2).text).toBe('all words, apart');
    expect(closenessLabel(oneWord, 3, 3).text).toBe('1 of 3 words');
  });
});
