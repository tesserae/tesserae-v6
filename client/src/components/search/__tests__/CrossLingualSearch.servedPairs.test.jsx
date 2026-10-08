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
      return Promise.resolve({ json: () => Promise.resolve({ languages: [], crosslingual_pairs: SERVED }) });
    }
    const m = u.match(/hierarchy\?language=(\w+)/);
    if (m) return Promise.resolve({ json: () => Promise.resolve(LISTS[m[1]] || { authors: [] }) });
    return Promise.resolve({ json: () => Promise.resolve({}) });
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
