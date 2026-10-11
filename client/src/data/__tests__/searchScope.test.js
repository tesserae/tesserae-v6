import { describe, it, expect, vi, afterEach } from 'vitest';
import { createElement } from 'react';
import { render } from '@testing-library/react';
import HelpPage from '../../components/pages/HelpPage';
import { SEARCH_SCOPE, allMeasuredRows } from '../searchScope';

const FIELDS = ['id', 'name', 'does', 'scope', 'covers', 'limits', 'measured', 'helpSection'];

afterEach(() => { delete global.fetch; });

describe('SEARCH_SCOPE', () => {
  it('gives every entry the eight fields', () => {
    for (const [key, e] of Object.entries(SEARCH_SCOPE)) {
      for (const f of FIELDS) expect(e[f], `${key}.${f}`).toBeTruthy();
      expect(e.id).toBe(key);
      expect(Array.isArray(e.measured)).toBe(true);
    }
  });

  it('gives every measured row its four fields', () => {
    for (const e of Object.values(SEARCH_SCOPE)) {
      for (const m of e.measured) {
        for (const f of ['language', 'against', 'result', 'date']) {
          expect(typeof m[f], `${e.id}.${f}`).toBe('string');
        }
        expect(m.language && m.against && m.result).toBeTruthy();
      }
    }
  });

  it('says "Not measured yet" for the searches with no test', () => {
    expect(SEARCH_SCOPE.documents.measured[0].result).toBe('Not measured yet');
    expect(SEARCH_SCOPE.objects.measured[0].result).toBe('Not measured yet');
  });

  it('is what the Help table renders, row for row in order', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ languages: [], stoplists: {} }) }));
    const { container } = render(createElement(HelpPage, { initialSection: 'how-well' }));
    const rows = [...container.querySelectorAll('tbody tr')].map(
      (tr) => [...tr.querySelectorAll('td')].map((td) => td.textContent));
    const expected = allMeasuredRows().map((m) => [m.search, m.language, m.against, m.result, m.date]);
    expect(rows).toEqual(expected);
    const union = [];
    // The Translation tab is not a search, so its row stays out of the Help table.
    for (const e of Object.values(SEARCH_SCOPE)) {
      if (e.id === 'reader_translation') continue;
      for (const m of e.measured) if (!union.includes(m)) union.push(m);
    }
    expect(new Set(allMeasuredRows())).toEqual(new Set(union));
  });

  it('has the six Reader entries, and the Help table gains only Reuse, Scholarship and Scholarship (Theme Search) after Objects', () => {
    const ids = ['reader_similar', 'reader_reuse', 'reader_parallels', 'reader_scholarship', 'reader_translation', 'reader_coins'];
    for (const id of ids) {
      for (const f of FIELDS) expect(SEARCH_SCOPE[id][f], `${id}.${f}`).toBeTruthy();
      expect(SEARCH_SCOPE[id].measured.length).toBeGreaterThan(0);
    }
    const searches = allMeasuredRows().map((m) => m.search);
    const i = searches.indexOf('Objects');
    expect(searches.slice(i + 1)).toEqual(['Reuse (Reader)', 'Scholarship (Reader)', 'Scholarship (Theme Search)']);
    expect(searches).not.toContain('Translation (Reader)');
    expect(SEARCH_SCOPE.reader_coins.measured).toEqual(SEARCH_SCOPE.coins.measured);
    expect(SEARCH_SCOPE.reader_parallels.measured).toEqual(SEARCH_SCOPE.line.measured);
  });

  it('has the Scholarship Theme Search entry with its measured row', () => {
    const e = SEARCH_SCOPE.scholarship_theme;
    for (const f of FIELDS) expect(e[f], f).toBeTruthy();
    expect(e.covers).toMatch(/82,814 windows/);
    const [m] = e.measured;
    expect(m.language).toBe('English and Latin and Greek notes');
    expect(m.against).toBe('Fifteen scholar questions, one judge, the first 230 characters of each note');
    expect(m.result).toMatch(/13 of 15 questions \(nDCG at 10 of 0\.64\)/);
    expect(m.result).toMatch(/Meaning alone 11 of 15, keyword alone 12 of 15/);
    expect(m.date).toBe('October 2026');
  });

  it('gives the Scholarship Theme Search a live count from /api/scope', async () => {
    const { liveCovers } = await import('../searchScope');
    expect(liveCovers('scholarship_theme', { scholarship_windows: 82814 })).toBe('82,814 windows now.');
    expect(liveCovers('scholarship_theme', { scholarship_windows: null })).toBeNull();
  });
});
