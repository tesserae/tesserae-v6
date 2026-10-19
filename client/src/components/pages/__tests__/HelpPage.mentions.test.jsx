/**
 * Help has a Mentions topic opening the People, Places & Things group, and the section carries the anchor #mentions.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HelpPage from '../HelpPage';
import { mockResponse } from '../../../test/mockResponse';

function serve() {
  global.fetch = vi.fn((url) => Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(
    String(url).startsWith('/api/languages') ? { languages: [{ code: 'la' }] } : { stoplists: {} }) })));
}
afterEach(() => { delete global.fetch; });

describe('Help: Mentions', () => {
  it('lists the topic right after Theme Search', async () => {
    serve();
    const { container } = render(<HelpPage />);
    await screen.findByRole('heading', { name: 'Start here' });
    const labels = within(container.querySelector('nav')).getAllByRole('button').map((b) => b.textContent);
    // Theme Search now sits in the searching group, and People & Places opens the People, Places & Things group.
    expect(labels.indexOf('People & Places')).toBeGreaterThan(labels.indexOf('The Reader'));
    expect(labels.indexOf('People & Places')).toBe(labels.indexOf('Tessa, the assistant') + 1);
  });

  it('opens the section with the anchor #mentions, as a live feature', async () => {
    serve();
    const user = userEvent.setup();
    const { container } = render(<HelpPage />);
    await screen.findByRole('heading', { name: 'Start here' });
    await user.click(within(container.querySelector('nav')).getByRole('button', { name: 'People & Places' }));
    await waitFor(() => expect(document.getElementById('mentions')).not.toBeNull());
    expect(screen.queryByText(/entities=1/)).toBeNull();
    expect(screen.queryByText(/is a trial/)).toBeNull();
    expect(screen.getByText(/repaired on 2026-10-19/)).toBeTruthy();
    expect(screen.getAllByRole('button', { name: 'Suggest a change' })).toHaveLength(2);
  });

  it('opens straight at the section when asked', async () => {
    serve();
    render(<HelpPage initialSection="mentions" initialAnchor="mentions" onSectionConsumed={() => {}} />);
    expect(await screen.findByRole('heading', { name: 'People & Places' })).toBeTruthy();
  });
});
