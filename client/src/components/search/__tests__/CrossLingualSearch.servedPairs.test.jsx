/**
 * The page offers only the pairs the server serves (/api/languages
 * crosslingual_pairs) and loads a text list for every language in them.
 * Before this, the lists were fetched for a fixed four languages, so
 * choosing Persian -> Urdu crashed the page, and the Arabic pairs showed
 * although the server does not serve Arabic.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('react-chartjs-2', () => ({ Bar: () => null }));
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {},
  Title: {}, Tooltip: {}, Legend: {},
}));

import CrossLingualSearch from '../CrossLingualSearch';
import { mockResponse } from '../../../test/mockResponse';

const list = (author_key, author, work_key, work) => ({
  authors: [{ author_key, author, works: [{ work_key, work, whole_text: `${author_key}.${work_key}.tess`, parts: [] }] }],
});
const LISTS = {
  grc: list('homer', 'Homer', 'iliad', 'Iliad'),
  la: list('vergil', 'Vergil', 'aeneid', 'Aeneid'),
  fa: list('hafez', 'Hafez', 'diwan', 'Diwan'),
  ur: list('ghalib', 'Ghalib', 'diwan_wikisource', 'Diwan'),
};
const SERVED = [
  { key: 'grc-la', source: 'grc', target: 'la' },
  { key: 'fa-ur', source: 'fa', target: 'ur' },
];

beforeEach(() => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.includes('/api/languages')) {
      return Promise.resolve(mockResponse({ json: () => Promise.resolve({ languages: [], crosslingual_pairs: SERVED }) }));
    }
    const m = u.match(/hierarchy\?language=(\w+)/);
    if (m) return Promise.resolve(mockResponse({ json: () => Promise.resolve(LISTS[m[1]] || { authors: [] }) }));
    return Promise.resolve(mockResponse({ json: () => Promise.resolve({}) }));
  });
});

describe('CrossLingualSearch served pairs', () => {
  it('hides pairs the server does not serve and opens Persian -> Urdu without crashing', async () => {
    render(<CrossLingualSearch />);
    const fa = await screen.findByRole('button', { name: /Persian → Urdu/ });
    expect(screen.queryByRole('button', { name: /Arabic/ })).toBeNull();
    fireEvent.click(fa);
    await waitFor(() => expect(screen.getByText('Persian Source')).toBeTruthy());
    const fetched = global.fetch.mock.calls.map(c => String(c[0]));
    expect(fetched.some(u => u.includes('hierarchy?language=fa'))).toBe(true);
    expect(fetched.some(u => u.includes('hierarchy?language=ur'))).toBe(true);
    expect(fetched.some(u => u.includes('hierarchy?language=ar'))).toBe(false);
  });
});

describe('held pairs', () => {
  it('shows the server\'s reason under the pair buttons and leaves the held pairs out', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/languages')) {
        return Promise.resolve(mockResponse({ json: () => Promise.resolve({
          languages: [],
          crosslingual_pairs: [{ key: 'grc-la', source: 'grc', target: 'la', label: 'Greek → Latin' }],
          crosslingual_held: [
            { key: 'la-en', reason: 'Latin to English searches are offline while the English texts are re-embedded.' },
            { key: 'grc-en', reason: 'Greek to English searches are offline while the English texts are re-embedded.' },
          ],
        }) }));
      }
      return Promise.resolve(mockResponse({ json: () => Promise.resolve({ authors: [], works: [] }) }));
    });
    render(<CrossLingualSearch />);
    const note = await screen.findByTestId('cross-held-note');
    expect(note.textContent).toContain('Latin → English and Greek → English are offline for now.');
    expect(note.textContent).toContain('re-embedded');
    expect(screen.queryByRole('button', { name: 'Latin → English' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Greek → Latin' })).toBeTruthy();
  });
});

describe('Coptic to Greek', () => {
  it('offers the cop-grc pair the server lists and loads both text lists', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('/api/languages')) {
        return Promise.resolve(mockResponse({ json: () => Promise.resolve({
          languages: [],
          crosslingual_pairs: [
            { key: 'grc-la', source: 'grc', target: 'la' },
            { key: 'cop-grc', source: 'cop', target: 'grc', label: 'Coptic → Greek' },
          ],
        }) }));
      }
      const m = u.match(/hierarchy\?language=(\w+)/);
      const lists = { ...LISTS, cop: { authors: [
        { author_key: 'sahidic_coptic', author: 'Sahidic Coptic', works: [{ work_key: 'john', work: 'Mysteries of John', whole_text: 'mysteries.john.tess', parts: [] }] },
        { author_key: 'bohairic_coptic', author: 'Bohairic Coptic', works: [{ work_key: 'john', work: 'John', whole_text: 'bohairic.john.tess', parts: [] }] },
      ] } };
      if (m) return Promise.resolve(mockResponse({ json: () => Promise.resolve(lists[m[1]] || { authors: [] }) }));
      return Promise.resolve(mockResponse({ json: () => Promise.resolve({}) }));
    });
    render(<CrossLingualSearch />);
    const cop = await screen.findByRole('button', { name: /Coptic → Greek/ });
    fireEvent.click(cop);
    await waitFor(() => expect(screen.getByText('Coptic Source')).toBeTruthy());
    const fetched = global.fetch.mock.calls.map(c => String(c[0]));
    expect(fetched.some(u => u.includes('hierarchy?language=cop'))).toBe(true);
    // The default text is an id the served list contains (the live ids are
    // bohairic.john.tess, sahidica.john.tess and so on).
    const served = ['mysteries.john.tess', 'bohairic.john.tess'];
    const values = screen.getAllByRole('combobox').map(el => el.value);
    expect(values.some(v => served.includes(v))).toBe(true);
    expect(values).toContain('bohairic.john.tess');
  });
});
