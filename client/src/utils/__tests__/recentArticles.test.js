import { describe, it, expect } from 'vitest';
import { mergeRecent, recentUrl, joinNames } from '../recentArticles';

describe('recentArticles', () => {
  it('orders by title naming the work, title words, question words, then year, and dedupes', () => {
    const a = [{ title: 'Milton and Dido', score: 3, year: 2023 }];
    const out = mergeRecent(a, [
      { title: 'Aeneid 4: a commentary', title_names_work: true, score: 1, year: 2020 },
      { title: 'milton and dido', score: 3 },
      { title: 'Dido', title_hits: 2, score: 2, year: 2001 },
    ]);
    expect(out.map((x) => x.title)).toEqual(['Aeneid 4: a commentary', 'Dido', 'Milton and Dido']);
  });
  it('links the free copy, then the DOI, then the page', () => {
    expect(recentUrl({ oa_url: 'o', doi: 'd', url: 'u' })).toBe('o');
    expect(recentUrl({ doi: '10.1/x', url: 'u' })).toBe('https://doi.org/10.1/x');
    expect(recentUrl({ url: 'u' })).toBe('u');
    expect(recentUrl({})).toBeNull();
  });
  it('joins names', () => {
    expect(joinNames(['A', 'B', 'C'])).toBe('A, B and C');
  });
});
