/**
 * Arabic is indexed but held until a reader grades it (2026-10-07): Help
 * leaves its page out of the menu and says it is not yet open, and brings it
 * back when the site serves Arabic.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import HelpPage from '../HelpPage';

function serve(codes) {
  global.fetch = vi.fn((url) => Promise.resolve({ ok: true, json: () => Promise.resolve(
    String(url).startsWith('/api/languages') ? { languages: codes.map((code) => ({ code })) } : { stoplists: {} }) }));
}
afterEach(() => { delete global.fetch; });

describe('Help and the held Arabic corpus', () => {
  it('hides the Arabic page and marks Arabic not yet open when the site does not serve it', async () => {
    serve(['la', 'grc', 'en', 'cop', 'he', 'fa', 'ur']);
    render(<HelpPage initialSection="languages" />);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Arabic' })).toBeNull());
    expect(screen.getByText('Arabic (not yet open)')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Persian' })).toBeTruthy();
  });

  it('shows the Arabic page when the site serves Arabic', async () => {
    serve(['la', 'grc', 'fa', 'ur', 'ar']);
    render(<HelpPage initialSection="languages" />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Arabic' })).toBeTruthy());
    expect(screen.queryByText('Arabic (not yet open)')).toBeNull();
  });
});
