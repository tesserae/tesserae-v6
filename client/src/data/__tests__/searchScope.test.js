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

  it('has the six Reader entries, and the Help table gains only Reuse and Scholarship after Objects', () => {
    const ids = ['reader_similar', 'reader_reuse', 'reader_parallels', 'reader_scholarship', 'reader_translation', 'reader_coins'];
    for (const id of ids) {
      for (const f of FIELDS) expect(SEARCH_SCOPE[id][f], `${id}.${f}`).toBeTruthy();
      expect(SEARCH_SCOPE[id].measured.length).toBeGreaterThan(0);
    }
    const searches = allMeasuredRows().map((m) => m.search);
    const i = searches.indexOf('Objects');
    expect(searches.slice(i + 1)).toEqual(['Reuse (Reader)', 'Scholarship (Reader)']);
    expect(searches).not.toContain('Translation (Reader)');
    expect(SEARCH_SCOPE.reader_coins.measured).toEqual(SEARCH_SCOPE.coins.measured);
    expect(SEARCH_SCOPE.reader_parallels.measured).toEqual(SEARCH_SCOPE.line.measured);
  });
});
