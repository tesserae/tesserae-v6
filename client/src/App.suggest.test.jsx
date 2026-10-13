/**
 * The header's Suggest a change button opens the request dialog held in App.
 * The setter it called was lost with the footer on 2026-10-12.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act, cleanup } from '@testing-library/react';
import App from './App';

const json = (data) => ({ ok: true, status: 200, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });
function routeFetch(url) {
  if (url.startsWith('/api/texts?language=')) return Promise.resolve(json([]));
  if (url.startsWith('/api/authors')) return Promise.resolve(json([]));
  if (url.startsWith('/api/languages')) return Promise.resolve(json({ languages: [{ code: 'la', label: 'Latin' }] }));
  if (url.startsWith('/api/admin/me')) return Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve({}), text: () => Promise.resolve('{}') });
  if (url.startsWith('/api/auth/user')) return Promise.resolve(json({ user: null }));
  return Promise.resolve(json({}));
}
beforeEach(() => { global.fetch = vi.fn(routeFetch); window.localStorage.clear(); window.sessionStorage.clear(); window.history.replaceState(null, '', '/'); });
afterEach(() => { cleanup(); });

describe('App — the Suggest a change event opens the dialog', () => {
  it('shows the request dialog when the header sends tesserae:open-suggest', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Suggest a change/)).toBeTruthy());
    expect(screen.queryByRole('dialog')).toBeNull();
    await act(async () => { window.dispatchEvent(new CustomEvent('tesserae:open-suggest')); });
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
  });
});
