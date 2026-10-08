import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('react-chartjs-2', () => ({ Bar: () => null }));
vi.mock('chart.js', () => ({ Chart: { register: () => {} }, CategoryScale: {}, LinearScale: {}, BarElement: {}, Title: {}, Tooltip: {}, Legend: {} }));
vi.mock('../../../utils/api', async importOriginal => ({ ...await importOriginal(), wildcardSearch: vi.fn() }));
import { wildcardSearch } from '../../../utils/api';
import LineSearch from '../LineSearch';
import WildcardSearch from '../WildcardSearch';
import CrossLingualSearch from '../CrossLingualSearch';
import CorpusSearchResults from '../CorpusSearchResults';

const rows = (tag = 'a') => Array.from({ length: 125 }, (_, i) => ({
  text: `${tag}-row-${i + 1}`, author: 'Poet', work: 'Work', title: 'Work',
  locus: `1.${i + 1}`, reference: `1.${i + 1}`, year: i + 1,
  is_poetry: i < 60, citation: 'Poet, Work', text_id: 'poet.work',
  source: { ref: `1.${i + 1}`, text: `${tag}-row-${i + 1}` },
  target: { ref: `2.${i + 1}`, text: `target-${i + 1}` },
  overall_score: 125 - i, matched_words: [],
}));
let responseRows;
beforeEach(() => {
  responseRows = rows();
  wildcardSearch.mockReset();
  wildcardSearch.mockImplementation(async () => ({ results: [...responseRows], total: 125 }));
  global.fetch = vi.fn(async url => {
    if (String(url).startsWith('/api/texts/hierarchy')) return { json: async () => ({ authors: [{
      author_key: 'poet', author: 'Poet', works: [{ work_key: 'work', work: 'Work', whole_text: 'poet.work', parts: [] }],
    }] }) };
    if (String(url) === '/api/search' || String(url) === '/api/line-search') return { json: async () => ({ results: [...responseRows] }) };
    return { json: async () => [] };
  });
});

async function setup(name) {
  if (name === 'CorpusSearchResults') {
    const props = { results: responseRows, query: { lemmas: [] }, loading: false, language: 'la' };
    const view = render(<CorpusSearchResults {...props} />);
    return { newSearch: async () => view.rerender(<CorpusSearchResults {...props} results={[...responseRows]} />) };
  }
  if (name === 'LineSearch') {
    render(<LineSearch language="la" />);
    fireEvent.click(screen.getByRole('button', { name: 'Input Search Text' }));
    fireEvent.change(screen.getByPlaceholderText('Enter word or phrase...'), { target: { value: 'amor' } });
  } else if (name === 'WildcardSearch') {
    render(<WildcardSearch language="la" />);
    fireEvent.change(screen.getByPlaceholderText('Enter search query...'), { target: { value: 'am*' } });
  } else {
    render(<CrossLingualSearch />);
    await screen.findByRole('button', { name: /^Search$/ });
    await waitFor(() => expect(screen.getByRole('button', { name: /^Search$/ })).toBeEnabled());
  }
  const search = () => fireEvent.click(screen.getByRole('button', { name: name === 'LineSearch' ? 'Search Lines' : /^Search$/ }));
  search();
  await screen.findByText('a-row-1');
  return { newSearch: search };
}
const countRows = () => screen.getAllByText(/^[ab]-row-\d+$/).length;
const requests = () => global.fetch.mock.calls.length + wildcardSearch.mock.calls.length;
// CrossLingualSearch now carries pagination both above and below its result
// list (crosslingual parity, 2026-10-08), so "Previous"/"Next"/"Go to page
// N" each match two buttons there (one set per instance); every other
// component here still has exactly one, so [0] is a no-op for them.
const pageBtn = (name) => screen.getAllByRole('button', { name })[0];

for (const name of ['LineSearch', 'WildcardSearch', 'CrossLingualSearch', 'CorpusSearchResults']) {
  describe(`${name} shared pagination integration`, () => {
    it('renders the first 50 of the full response', async () => {
      await setup(name);
      expect(countRows()).toBe(50);
      expect(screen.getByText('a-row-50')).toBeInTheDocument();
      expect(screen.queryByText('a-row-51')).toBeNull();
      expect(pageBtn('Previous')).toBeDisabled();
    });
    it('navigates numbered pages locally and preserves global rank', async () => {
      await setup(name);
      const before = requests();
      fireEvent.click(pageBtn('Go to page 2'));
      expect(screen.getByText('a-row-51')).toBeInTheDocument();
      expect(screen.queryByText('a-row-1')).toBeNull();
      expect(pageBtn('Go to page 2')).toHaveAttribute('aria-current', 'page');
      expect(screen.getByText('51.')).toBeInTheDocument();
      expect(requests()).toBe(before);
    });
    it('moves with Next/Previous and disables Next on the last page', async () => {
      await setup(name);
      const before = requests();
      fireEvent.click(pageBtn('Next'));
      fireEvent.click(pageBtn('Next'));
      expect(countRows()).toBe(25);
      expect(screen.getByText('a-row-101')).toBeInTheDocument();
      expect(pageBtn('Next')).toBeDisabled();
      fireEvent.click(pageBtn('Previous'));
      expect(screen.getByText('a-row-51')).toBeInTheDocument();
      expect(requests()).toBe(before);
    });
    it('uses central sizes and returns to page 1 when choosing 20', async () => {
      await setup(name);
      const before = requests();
      fireEvent.click(pageBtn('Go to page 3'));
      const select = screen.getByRole('combobox', { name: 'Show' });
      expect([...select.options].map(o => Number(o.value))).toEqual([10, 20, 50, 100]);
      fireEvent.change(select, { target: { value: '20' } });
      expect(countRows()).toBe(20);
      expect(screen.getByText('a-row-1')).toBeInTheDocument();
      expect(pageBtn('Previous')).toBeDisabled();
      expect(requests()).toBe(before);
    });
    it('resets a later page for a new result identity, even with the same query and count', async () => {
      const { newSearch } = await setup(name);
      fireEvent.click(pageBtn('Go to page 3'));
      responseRows = rows('b');
      await act(async () => { await newSearch(); });
      await screen.findByText('b-row-1');
      expect(countRows()).toBe(50);
      expect(screen.queryByText('b-row-101')).toBeNull();
      expect(pageBtn('Previous')).toBeDisabled();
    });
    it('resets before slicing after a filter or sort change', async () => {
      await setup(name);
      fireEvent.click(pageBtn('Go to page 2'));
      const before = requests();
      if (name === 'CrossLingualSearch') {
        const select = screen.getAllByRole('combobox').find(s => [...(s.options || [])].some(o => o.value === 'score'));
        fireEvent.change(select, { target: { value: 'source' } });
      } else {
        fireEvent.click(screen.getByRole('checkbox', { name: /Poetry/ }));
        expect(screen.queryByText('a-row-1')).toBeNull();
        expect(screen.getByText('a-row-61')).toBeInTheDocument();
      }
      expect(pageBtn('Previous')).toBeDisabled();
      expect(countRows()).toBe(50);
      expect(requests()).toBe(before);
    });
  });
}

it('LineSearch browse list preserves its 100-line default and resets on a new load', async () => {
  let tag = 'a';
  global.fetch = vi.fn(async url => {
    if (String(url).startsWith('/api/texts?')) return { json: async () => [{ id: 'poet.work', author: 'Poet', title: 'Work' }] };
    return { json: async () => ({ lines: Array.from({ length: 125 }, (_, i) => ({ locus: `1.${i + 1}`, text: `${tag}-row-${i + 1}` })) }) };
  });
  render(<LineSearch language="la" />);
  // Author/Work are SearchableSelect since 2026-10-06: a real <select> (the
  // phone fallback) alongside a text-input combobox (the desktop control,
  // with no .options), both matching role=combobox in a test environment
  // that does not evaluate the sm: breakpoint -- so this is scoped to actual
  // <select> elements before reading .options off them.
  const findNativeSelect = (match) => screen.getAllByRole('combobox')
    .filter(s => s.tagName === 'SELECT')
    .find(s => [...s.options].some(match));
  await waitFor(() => expect(findNativeSelect(o => o.text === 'Select author...')).toBeEnabled());
  const author = findNativeSelect(o => o.text === 'Select author...');
  fireEvent.change(author, { target: { value: 'Poet' } });
  const work = findNativeSelect(o => o.value === 'poet.work');
  fireEvent.change(work, { target: { value: 'poet.work' } });
  fireEvent.click(screen.getByRole('button', { name: 'Load Lines' }));
  await screen.findByText('a-row-1');
  expect(countRows()).toBe(100);
  const before = requests();
  fireEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
  expect(screen.getByText('a-row-101')).toBeInTheDocument();
  expect(requests()).toBe(before);
  tag = 'b';
  fireEvent.click(screen.getByRole('button', { name: 'Load Lines' }));
  await screen.findByText('b-row-1');
  expect(countRows()).toBe(100);
  expect(screen.queryByText('b-row-101')).toBeNull();
});
