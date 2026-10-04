import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import TextCredits from '../../about/TextCredits';
import RareWordsExplorer from '../../corpus/RareWordsExplorer';
import GenreClassificationTab from '../../admin/tabs/GenreClassificationTab';

beforeEach(() => vi.restoreAllMocks());

for (const [name, Component, endpoint, field] of [
  ['TextCredits', TextCredits, '/api/text-credits', 'entries'],
  ['RareWordsExplorer', RareWordsExplorer, '/api/rare-lemmata-full', 'words'],
]) {
  describe(`${name} accumulating pagination`, () => {
    const mock = () => {
      global.fetch = vi.fn(async url => {
        const u = new URL(String(url), 'http://localhost');
        if (u.pathname !== endpoint) return { ok: true, json: async () => ({}) };
        const offset = Number(u.searchParams.get('offset'));
        const limit = Number(u.searchParams.get('limit'));
        const tag = u.searchParams.get('query') || u.searchParams.get('language') === 'he' ? 'b' : 'a';
        return { ok: true, json: async () => ({ [field]: Array.from({ length: Math.min(limit, 125 - offset) }, (_, i) => ({
          author: `${tag}-word-${offset + i + 1}`, work: 'Work', lemma: `${tag}-word-${offset + i + 1}`, count: 1,
        })), total: 125 }) };
      });
    };
    it('loads batches through the existing offset/limit contract and preserves earlier rows', async () => {
      mock(); render(<Component />);
      await screen.findByText('a-word-1');
      expect(screen.queryByText('a-word-51')).toBeNull();
      fireEvent.click(screen.getByRole('button', { name: /Show more/ }));
      await screen.findByText('a-word-51');
      expect(screen.getByText('a-word-1')).toBeInTheDocument();
      expect(global.fetch.mock.calls.some(([u]) => String(u).includes('offset=50') && String(u).includes('limit=50'))).toBe(true);
      fireEvent.click(screen.getByRole('button', { name: /Show more/ }));
      await screen.findByText('a-word-125');
      expect(screen.queryByRole('button', { name: /Show more/ })).toBeNull();
    });
    it('restarts at offset 0 after changing the batch size', async () => {
      mock(); render(<Component />);
      await screen.findByText('a-word-1');
      fireEvent.click(screen.getByRole('button', { name: /Show more/ }));
      await screen.findByText('a-word-51');
      fireEvent.change(screen.getByRole('combobox', { name: 'Show' }), { target: { value: '25' } });
      await screen.findByText('a-word-25');
      expect(screen.queryByText('a-word-26')).toBeNull();
      expect(global.fetch.mock.calls.some(([u]) => String(u).includes('offset=0') && String(u).includes('limit=25'))).toBe(true);
    });
    it('drops accumulated rows when the query/language changes', async () => {
      mock(); render(<Component />);
      await screen.findByText('a-word-1');
      fireEvent.click(screen.getByRole('button', { name: /Show more/ }));
      await screen.findByText('a-word-51');
      if (name === 'TextCredits') fireEvent.change(screen.getByPlaceholderText('Filter by author or work...'), { target: { value: 'new' } });
      else fireEvent.click(screen.getByRole('button', { name: 'Hebrew' }));
      await screen.findByText('b-word-1');
      expect(screen.queryByText('a-word-1')).toBeNull();
      expect(screen.queryByText('b-word-51')).toBeNull();
    });
    it('retains rows and displays errors from a failed next batch', async () => {
      mock(); render(<Component />);
      await screen.findByText('a-word-1');
      global.fetch.mockResolvedValueOnce({ ok: false });
      fireEvent.click(screen.getByRole('button', { name: /Show more/ }));
      await screen.findByText(/Please try again/);
      expect(screen.getByText('a-word-1')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Show more/ })).toBeEnabled();
    });
  });
}

describe('GenreClassificationTab shared local pagination', () => {
  it('navigates and changes sizes without requests, then resets on filters', async () => {
    global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({
      texts: Array.from({ length: 125 }, (_, i) => ({ filename: `poet.work.${i}`, author: 'poet', work: `Work${i + 1}`, genre: 'epic', era: 'unknown', meter: 'unknown', confidence: 'manual' })),
      genres: ['epic'], total: 125,
    }) }));
    render(<GenreClassificationTab />);
    await screen.findByText('Work1');
    expect(screen.queryByText('Work51')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
    expect(screen.getByText('Work51')).toBeInTheDocument();
    expect(screen.queryByText('Work1')).toBeNull();
    fireEvent.change(screen.getByRole('combobox', { name: 'Show' }), { target: { value: '20' } });
    expect(screen.getByText('Work1')).toBeInTheDocument();
    expect(screen.queryByText('Work21')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Go to page 3' }));
    fireEvent.change(screen.getByPlaceholderText('Search by author, work, or filename...'), { target: { value: 'Work1' } });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled());
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
});
