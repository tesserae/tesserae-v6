/**
 * The example searches under the Theme Search box follow the visitor's view:
 * Literature keeps the literary five, History offers six historical themes.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import ThemeSearchPage from './ThemeSearchPage';
import { setView } from '../../collections/collectionsStore';

beforeEach(() => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/languages')) {
      return Promise.resolve({ json: () => Promise.resolve({ languages: [{ code: 'la' }, { code: 'grc' }, { code: 'en' }] }) });
    }
    return Promise.resolve({ json: () => Promise.resolve({}) });
  });
});
afterEach(() => { act(() => setView('literature')); });

describe('Theme Search examples per view', () => {
  it('Literature view shows the literary examples', async () => {
    act(() => setView('literature'));
    render(<ThemeSearchPage />);
    expect(await screen.findByRole('button', { name: /a mother laments her dead son/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /a debate in the assembly over how the city should be governed/ })).toBeNull();
  });

  it('History view shows its own six examples instead', async () => {
    act(() => setView('history'));
    render(<ThemeSearchPage />);
    await waitFor(() => expect(screen.getByRole('button', { name: /a debate in the assembly over how the city should be governed/ })).toBeTruthy());
    expect(screen.getByRole('button', { name: /a general addresses his troops before battle/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /a plague spreads through the city and the dead lie unburied/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /a mother laments her dead son/ })).toBeNull();
  });
});
