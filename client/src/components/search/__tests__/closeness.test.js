import { describe, it, expect } from 'vitest';
import { closenessSort, closenessLabel } from '../closeness';

const quote = { quotation: true, n_matched: 2, year: 100, author: 'Martial' };
const allApart = { quotation: false, n_matched: 2, year: -50, author: 'Varro' };
const oneWord = { quotation: false, n_matched: 1, year: -60, author: 'Caesar' };
const oneWordOlder = { quotation: false, n_matched: 1, year: -200, author: 'Plautus' };

describe('closenessSort', () => {
  it('puts quotations first, then more shared words, then the older text', () => {
    const out = [oneWord, allApart, oneWordOlder, quote].sort(closenessSort);
    expect(out.map((r) => r.author)).toEqual(['Martial', 'Varro', 'Plautus', 'Caesar']);
  });
});

describe('closenessLabel', () => {
  it('is silent for a one-word query', () => {
    expect(closenessLabel(quote, 1)).toBeNull();
    expect(closenessLabel(quote, 0)).toBeNull();
  });
  it('names the three cases', () => {
    expect(closenessLabel(quote, 2).text).toBe('whole phrase');
    expect(closenessLabel(allApart, 2).text).toBe('all words, apart');
    expect(closenessLabel(oneWord, 4).text).toBe('1 of 4 words');
  });
});
