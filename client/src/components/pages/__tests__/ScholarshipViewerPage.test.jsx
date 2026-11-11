import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ScholarshipViewerPage, { stateFromSearch, paramsFromState, recordForRow } from '../ScholarshipViewerPage';
import { pageForPath } from '../../../hooks/routePaths';
import { mockResponse } from '../../../test/mockResponse';
import * as citations from '../../../utils/citations';

const row = (i, extra = {}) => ({
  key: `k${i}`, title: `Invented article ${i}`, authors: ['A. Scholar'], year: 2000 - (i % 50), venue: 'Classical Philology',
  volume: '12', issue: '3', pages: [i], kind: 'article', source: 'ejc', sources: ['ejc'],
  cites: [{ locus: '1.1-4', note: '' }, { locus: '1.7', note: 'the proem' }], sentences: [`Invented sentence ${i}.`],
  url: `https://example.org/${i}`, url_jstor: null, url_ia: `https://archive.org/${i}`, doi: '', ...extra,
});

function reply(over = {}, n = 50, total = 120) {
  const results = Array.from({ length: n }, (_, i) => row(i + 1));
  results[1] = row(2, { source: 'jstor', sources: ['jstor'], sentences: [], url_jstor: 'https://www.jstor.org/stable/2', url_ia: null });
  results[2] = row(3, { kind: 'review', source: 'muse', sources: ['muse'], doi: '10.1353/x.3' });
  return {
    available: true,
    scope: { work: 'vergil.aeneid', lo: '1.1', hi: '1.33', scope: 'passage', label: 'Aeneid 1.1-33' },
    counts: { passage: 123, book: 3886, work: 13571 },
    total, page: 1, per_page: 50, results,
    facets: { source: { ejc: 10, muse: 7, jstor: 103 }, decade: { 1990: 4, 2000: 9 }, kind: { article: 100, review: 15, other: 5 },
              journal: [['Classical Philology', 12], ['Arethusa', 4]] },
    note: 'note', ...over,
  };
}

let calls;
let handler;
beforeEach(() => {
  calls = [];
  handler = () => reply();
  global.fetch = vi.fn((url) => {
    const u = String(url);
    calls.push(u);
    return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(handler(u)) }));
  });
  window.history.replaceState({}, '', '/scholarship/view?work=vergil.aeneid&lo=1.1&hi=1.33&scope=passage');
});
afterEach(() => { delete global.fetch; vi.restoreAllMocks(); });

const lastList = () => calls.filter((u) => u.startsWith('/api/scholarship/list')).pop();

describe('Scholarship viewer page', () => {
  it('is a page of the site at /scholarship/view', () => {
    expect(pageForPath('/scholarship/view')).toBe('scholarship-view');
  });

  it('renders the header counts, summary strip, fifty rows, paging and a JSTOR row without a sentence', async () => {
    render(<ScholarshipViewerPage />);
    expect(await screen.findByTestId('viewer-list')).toBeTruthy();
    expect(screen.getByTestId('viewer-heading').textContent).toBe('Scholarship on Aeneid 1.1-33');
    expect(screen.getByTestId('scope-passage').textContent).toContain('123');
    expect(screen.getByTestId('scope-book').textContent).toContain('Book 1 (3,886)');
    expect(screen.getByTestId('scope-work').textContent).toContain('13,571');
    expect(screen.getByTestId('viewer-total').textContent).toBe('120 articles');
    expect(screen.getByTestId('viewer-summary').textContent).toContain('Early Journal Content 10, Project MUSE 7, JSTOR 103');
    expect(screen.getByTestId('viewer-decades').textContent).toContain('1990s 4, 2000s 9');
    const items = within(screen.getByTestId('viewer-list')).getAllByRole('listitem');
    expect(items).toHaveLength(50);
    expect(screen.getByTestId('viewer-paging').textContent).toContain('page 1 of 3');
    expect(items[0].textContent).toContain('Invented sentence 1.');
    expect(items[0].textContent).toContain('cites 1.1-4, 1.7 (the proem)');
    expect(items[0].textContent).not.toContain('more');
    expect(items[1].textContent).toContain('Invented article 2');
    expect(items[1].textContent).not.toContain('Invented sentence');
    expect(items[2].textContent).toContain('book review');
    expect(screen.getByText(/the sentence itself is not shown, at JSTOR/)).toBeTruthy();
  });

  it('asks for fifty a page and pages with Next', async () => {
    render(<ScholarshipViewerPage />);
    await screen.findByTestId('viewer-list');
    expect(lastList()).toContain('per_page=50');
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(lastList()).toContain('page=2'));
    expect(window.location.search).toContain('page=2');
  });

  it('updates the address and refetches when the sort, a filter and the search change', async () => {
    render(<ScholarshipViewerPage />);
    await screen.findByTestId('viewer-list');
    fireEvent.change(screen.getByTestId('viewer-sort'), { target: { value: 'oldest' } });
    await waitFor(() => expect(lastList()).toContain('sort=oldest'));
    expect(window.location.search).toContain('sort=oldest');

    await userEvent.click(screen.getByTestId('source-jstor'));
    await waitFor(() => expect(lastList()).toContain('source=ejc%2Cmuse'));
    expect(window.location.search).toContain('source=ejc%2Cmuse');

    await userEvent.click(screen.getByTestId('kind-review'));
    await waitFor(() => expect(lastList()).toContain('kind=article%2Cother'));

    fireEvent.change(screen.getByTestId('year-from'), { target: { value: '1900' } });
    await waitFor(() => expect(lastList()).toContain('year_from=1900'));

    fireEvent.change(screen.getByTestId('viewer-journal'), { target: { value: 'Arethusa' } });
    await waitFor(() => expect(lastList()).toContain('journal=Arethusa'));

    fireEvent.change(screen.getByTestId('viewer-search'), { target: { value: 'nymph' } });
    expect(window.location.search).toContain('q=nymph');
    await waitFor(() => expect(lastList()).toContain('q=nymph'));
    expect(lastList()).toContain('sort=oldest');

    await userEvent.click(screen.getByTestId('scope-work'));
    await waitFor(() => expect(lastList()).toContain('scope=work'));
  });

  it('restores every control from the address', async () => {
    window.history.replaceState({}, '', '/scholarship/view?work=vergil.aeneid&lo=1.1&hi=1.33&scope=book&q=dido&source=muse,jstor&kind=review&year_from=1950&year_to=2010&journal=Arethusa&sort=journal&page=2');
    render(<ScholarshipViewerPage />);
    await screen.findByTestId('viewer-list');
    expect(screen.getByTestId('viewer-search')).toHaveValue('dido');
    expect(screen.getByTestId('viewer-sort')).toHaveValue('journal');
    expect(screen.getByTestId('source-ejc')).not.toBeChecked();
    expect(screen.getByTestId('source-muse')).toBeChecked();
    expect(screen.getByTestId('source-jstor')).toBeChecked();
    expect(screen.getByTestId('kind-review')).toBeChecked();
    expect(screen.getByTestId('kind-article')).not.toBeChecked();
    expect(screen.getByTestId('year-from')).toHaveValue(1950);
    expect(screen.getByTestId('year-to')).toHaveValue(2010);
    expect(screen.getByTestId('viewer-journal')).toHaveValue('Arethusa');
    expect(screen.getByTestId('scope-book').getAttribute('aria-pressed')).toBe('true');
    const u = lastList();
    for (const part of ['scope=book', 'q=dido', 'source=muse%2Cjstor', 'kind=review', 'year_from=1950', 'year_to=2010', 'journal=Arethusa', 'sort=journal', 'page=2']) {
      expect(u).toContain(part);
    }
    expect(screen.getByTestId('viewer-paging').textContent).toContain('page 2 of 3');
  });

  it('offers only the whole-work scope, without a count for the others, when the request has no locus, and the extra cited places', async () => {
    window.history.replaceState({}, '', '/scholarship/view?work=vergil.aeneid&scope=work');
    handler = () => {
      const d = reply({ counts: { passage: null, book: null, work: 13571 }, scope: { work: 'vergil.aeneid', scope: 'work', label: 'Aeneid' } });
      d.results[0] = row(1, { cites_total: 62 });
      return d;
    };
    render(<ScholarshipViewerPage />);
    await screen.findByTestId('viewer-list');
    expect(screen.getByTestId('scope-work').textContent).toBe('Whole work (13,571)');
    expect(screen.queryByTestId('scope-passage')).toBeNull();
    expect(screen.queryByTestId('scope-book')).toBeNull();
    expect(screen.getAllByRole('listitem')[0].textContent).toContain(', and 60 more');
  });

  it('says so when nothing matches and gives the endpoint\'s note when the index is unavailable', async () => {
    handler = () => reply({ total: 0, results: [] }, 0, 0);
    const { unmount } = render(<ScholarshipViewerPage />);
    expect((await screen.findByTestId('viewer-empty')).textContent)
      .toBe('No article in the citation indexes cites this scope with these filters.');
    unmount();
    handler = () => ({ available: false, note: 'The citation indexes are not on this server.', results: [] });
    render(<ScholarshipViewerPage />);
    expect((await screen.findByTestId('viewer-unavailable')).textContent).toBe('The citation indexes are not on this server.');
  });

  it('exports RIS for the list and stops at 500 articles', async () => {
    const spy = vi.spyOn(citations, 'download').mockImplementation(() => {});
    handler = (u) => {
      const p = new URL(u, 'http://x').searchParams;
      const per = Number(p.get('per_page'));
      const pg = Number(p.get('page') || 1);
      const total = 700;
      const n = Math.min(per, total - (pg - 1) * per);
      const r = reply({ total, per_page: per, page: pg }, 0, total);
      r.results = Array.from({ length: n }, (_, i) => row((pg - 1) * per + i + 1));
      return r;
    };
    render(<ScholarshipViewerPage />);
    await screen.findByTestId('viewer-list');
    expect(screen.getByTestId('viewer-export-limit').textContent).toContain('500');
    await userEvent.click(screen.getByTestId('viewer-export'));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    const [name, text] = spy.mock.calls[0];
    expect(name.endsWith('.ris')).toBe(true);
    expect((text.match(/^TY {2}- JOUR$/gm) || []).length).toBe(500);
    expect(text).toContain('TI  - Invented article 1\n');
    expect(text).not.toContain('Invented article 501\n');
    const exportCalls = calls.filter((u) => u.includes('per_page=200'));
    expect(exportCalls.length).toBe(3);
  });

  it('builds a citation record with the DOI, issue and first page', () => {
    const rec = recordForRow(row(3, { doi: '10.1353/x.3', pages: [25] }));
    expect(rec.doi).toBe('10.1353/x.3');
    expect(rec.issue).toBe('3');
    expect(rec.pages).toBe('25');
    expect(rec.venue).toBe('Classical Philology');
  });
});

describe('address helpers', () => {
  it('round-trips a state and leaves defaults out', () => {
    const st = stateFromSearch('?work=w&lo=1.1&hi=1.2&scope=passage');
    expect(paramsFromState(st).toString()).toBe('work=w&lo=1.1&hi=1.2&scope=passage');
    const full = stateFromSearch('?work=w&scope=work&source=muse&kind=review,other&sort=most&page=3');
    expect(stateFromSearch(`?${paramsFromState(full)}`)).toEqual(full);
  });
});
