/**
 * The legend row on a phone shrinks to its three buttons. The swatch lines
 * move into the key, so one tap away shows the whole legend.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ReaderPage from './ReaderPage';
import { installPhone } from '../../test/phone';

const AUTHORS = [{ name: 'Vergil', works: [
  { id: 'vergil.aeneid.part.1.tess', author_key: 'vergil', work_key: 'aeneid',
    work: 'Aeneid', title: 'Aeneid, Book 1', part: 'Book 1', is_part: true },
] }];

beforeEach(() => {
  window.localStorage.clear();
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
  window.history.replaceState({}, '', '/read?work=vergil.aeneid.part.1.tess&lang=la');
  const reply = (obj) => Promise.resolve({
    ok: true, json: () => Promise.resolve(obj), text: () => Promise.resolve(JSON.stringify(obj)) });
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/text/')) {
      return reply({ units: [{ ref: 'verg. aen. 1.1', text: 'Arma virumque cano' }],
                     metadata: { display_name: 'a text' } });
    }
    if (u.includes('/authors?')) return reply(AUTHORS);
    if (u.includes('/texts?')) return reply([]);
    if (u.startsWith('/api/languages')) return reply({ languages: [{ code: 'la' }] });
    return reply({});
  });
});
afterEach(() => { cleanup(); delete global.fetch; });

describe('legend row', () => {
  it('on a desktop shows the swatch lines beside the buttons', async () => {
    render(<ReaderPage />);
    expect(await screen.findByText('verbal parallels')).toBeInTheDocument();
    expect(screen.getByText('darker = more connections')).toBeInTheDocument();
  });

  it('on a phone shows only Key, Original and English, and the key carries the swatches', async () => {
    const env = installPhone(true);
    try {
      render(<ReaderPage />);
      const key = await screen.findByRole('button', { name: 'Key' });
      expect(screen.getByRole('button', { name: 'Original' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'English' })).toBeInTheDocument();
      expect(screen.queryByText('verbal parallels')).toBeNull();
      expect(screen.queryByText('darker = more connections')).toBeNull();
      fireEvent.click(key);
      await waitFor(() => expect(screen.getByTestId('reader-key')).toBeInTheDocument());
      const k = screen.getByTestId('reader-key');
      expect(k).toHaveTextContent('verbal parallels');
      expect(k).toHaveTextContent('similar passages');
      expect(k).toHaveTextContent('darker = more connections');
      expect(k).toHaveTextContent('quoted by that many other works');
    } finally { env.restore(); }
  });
});
