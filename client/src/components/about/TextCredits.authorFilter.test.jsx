/**
 * The Reader's About panel links to "Full credits" as
 * /text-credits?author=<name>, so the Sources page should open already
 * filtered to that author rather than landing on the unfiltered list.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import TextCredits from './TextCredits';

function mockFetch() {
  return vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/passages/translations')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ works: {} }) });
    }
    if (u.startsWith('/api/text-credits')) {
      const params = new URLSearchParams(u.split('?')[1]);
      const query = (params.get('query') || '').toLowerCase();
      const all = [
        { author: 'Seneca', work: 'Thyestes', e_source: 'Perseus', print_source: 'An Edition.' },
        { author: 'Ovid', work: 'Tristia', e_source: 'Perseus', print_source: 'Another Edition.' },
      ];
      const entries = query
        ? all.filter((e) => e.author.toLowerCase().includes(query) || e.work.toLowerCase().includes(query))
        : all;
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ entries, total: entries.length, offset: 0, limit: 50 }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

afterEach(() => { window.history.replaceState({}, '', '/'); });

describe('the ?author= deep link', () => {
  it('pre-fills the filter box and asks the server for that author only', async () => {
    window.history.pushState({}, '', '/text-credits?author=Seneca');
    global.fetch = mockFetch();
    render(<TextCredits />);

    expect(await screen.findByText('Seneca')).toBeInTheDocument();
    expect(screen.queryByText('Ovid')).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('Filter by author or work...').value).toBe('Seneca');
  });

  it('with no author param, shows the unfiltered list as before', async () => {
    global.fetch = mockFetch();
    render(<TextCredits />);

    expect(await screen.findByText('Seneca')).toBeInTheDocument();
    expect(screen.getByText('Ovid')).toBeInTheDocument();
  });
});
