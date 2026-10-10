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
    for (const e of Object.values(SEARCH_SCOPE)) for (const m of e.measured) if (!union.includes(m)) union.push(m);
    expect(new Set(allMeasuredRows())).toEqual(new Set(union));
  });
});
