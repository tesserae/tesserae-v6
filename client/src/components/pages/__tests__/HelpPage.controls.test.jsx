/**
 * Help has a "Collections, Beta marks and other controls" section after
 * Literature and History views, in the Start here group.
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

describe('Help: Collections, Beta marks and other controls', () => {
  it('is listed right after the Literature and History views', async () => {
    serve();
    const { container } = render(<HelpPage />);
    await screen.findByRole('heading', { name: 'Start here' });
    const labels = within(container.querySelector('nav')).getAllByRole('button').map((b) => b.textContent);
    expect(labels.indexOf('Collections, Beta marks and other controls'))
      .toBe(labels.indexOf('Literature and History views') + 1);
  });

  it('renders its five paragraphs', async () => {
    serve();
    const user = userEvent.setup();
    const { container } = render(<HelpPage />);
    await screen.findByRole('heading', { name: 'Start here' });
    await user.click(within(container.querySelector('nav')).getByRole('button', { name: 'Collections, Beta marks and other controls' }));
    expect(await screen.findByRole('heading', { name: 'Collections, Beta marks and other controls' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText(/A Beta mark beside a page name/)).toBeTruthy());
    expect(screen.getByText(/The Suggest a change button in the header/)).toBeTruthy();
    expect(screen.getByText(/remembers the last page and address/)).toBeTruthy();
    expect(screen.getByText(/The Downloads page is under More/)).toBeTruthy();
    expect(screen.getByText(/The Collections button at the left of the top row/)).toBeTruthy();
  });

  it('retires the in-testing labels of Events, Coins and Objects', async () => {
    serve();
    render(<HelpPage />);
    const labels = (await screen.findAllByRole('button')).map((b) => b.textContent);
    expect(labels).toContain('Events');
    expect(labels).toContain('Coins');
    expect(labels).toContain('Objects');
    expect(labels.some((l) => /in testing/.test(l))).toBe(false);
  });
});
