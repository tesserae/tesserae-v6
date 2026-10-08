/**
 * The public Requests page (2026-10-08): a read-only mirror of GET
 * /api/requests, grouped Open / Done, with a "Suggest a change" link to
 * the same dialog every other entry point uses.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RequestsPage from '../RequestsPage';

afterEach(() => { delete global.fetch; });

const LISTING = {
  open: [
    { number: 10, title: 'Add a dark mode', type: 'suggestion', status: 'open',
      created_at: '2026-10-05T00:00:00Z', closed_at: null, summary: '', url: 'https://github.com/org/repo/issues/10' },
  ],
  done: [
    { number: 5, title: 'Fix the Reader on phones', type: 'bug', status: 'done',
      created_at: '2026-09-01T00:00:00Z', closed_at: '2026-09-10T00:00:00Z',
      summary: 'Fixed the Reader toolbar on small screens', url: 'https://github.com/org/repo/issues/5',
      pr_url: 'https://github.com/org/repo/pull/6' },
  ],
};

function serve(body) {
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(body) }));
}

describe('RequestsPage', () => {
  it('groups requests into Open and Done, newest first', async () => {
    serve(LISTING);
    render(<RequestsPage />);
    await waitFor(() => expect(screen.getByText('Add a dark mode')).toBeTruthy());
    expect(screen.getByText('Fix the Reader on phones')).toBeTruthy();
    expect(screen.getByText('Fixed the Reader toolbar on small screens')).toBeTruthy();
    expect(screen.getByText('Open (1)')).toBeTruthy();
    expect(screen.getByText('Done (1)')).toBeTruthy();
  });

  it('shows a status chip and the pull request link for a done item', async () => {
    serve(LISTING);
    render(<RequestsPage />);
    await waitFor(() => expect(screen.getByText('Done (1)')).toBeTruthy());
    expect(screen.getByText('Open')).toBeTruthy();
    expect(screen.getByText('Done')).toBeTruthy();
    expect(screen.getByRole('link', { name: /see the fix/i })).toHaveProperty(
      'href', 'https://github.com/org/repo/pull/6');
  });

  it('opens the suggestion dialog from the page', async () => {
    serve(LISTING);
    const user = userEvent.setup();
    render(<RequestsPage />);
    await waitFor(() => expect(screen.getByText('Open (1)')).toBeTruthy());
    await user.click(screen.getByRole('button', { name: 'Suggest a change' }));
    expect(screen.getByRole('dialog', { name: /suggest a change/i })).toBeTruthy();
  });

  it('says so when nothing is open', async () => {
    serve({ open: [], done: [] });
    render(<RequestsPage />);
    await waitFor(() => expect(screen.getByText('Nothing open right now.')).toBeTruthy());
    expect(screen.getByText('Nothing closed recently.')).toBeTruthy();
  });
});
