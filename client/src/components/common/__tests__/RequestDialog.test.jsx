/**
 * The one dialog behind every requests-workflow entry point (2026-10-08):
 * the Cite popup's "Report a problem", the Reader's "Suggest a correction",
 * and the footer/Help "Suggest a change". Checks the context it shows read-
 * only, what it sends, and the correction-only field.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RequestDialog from '../RequestDialog';

afterEach(() => { delete global.fetch; });

function mockFetch(ok = true) {
  const fetchMock = vi.fn(() => Promise.resolve({
    ok, status: ok ? 200 : 500, json: () => Promise.resolve({ success: ok }),
  }));
  global.fetch = fetchMock;
  return fetchMock;
}

describe('RequestDialog — context', () => {
  it('shows the given context fields read-only', () => {
    mockFetch();
    render(
      <RequestDialog
        isOpen
        onClose={() => {}}
        type="result-problem"
        context={{ page_url: 'https://tesserae.example/search', language: 'Latin',
                  source: 'Vergil, Aen. 1.1', score: '7.200' }}
      />
    );
    expect(screen.getByText('https://tesserae.example/search')).toBeTruthy();
    expect(screen.getByText('Latin')).toBeTruthy();
    expect(screen.getByText('Vergil, Aen. 1.1')).toBeTruthy();
    expect(screen.getByText('7.200')).toBeTruthy();
  });

  it('renders no context block when context is empty', () => {
    mockFetch();
    render(<RequestDialog isOpen onClose={() => {}} type="suggestion" context={{}} />);
    expect(screen.queryByText('Page:')).toBeNull();
  });
});

describe('RequestDialog — the correction box', () => {
  it('only appears when showCorrection is true', () => {
    mockFetch();
    render(<RequestDialog isOpen onClose={() => {}} type="result-problem" context={{}} />);
    expect(screen.queryByLabelText(/corrected text/i)).toBeNull();
  });

  it('appears for a text correction and is optional', () => {
    mockFetch();
    render(<RequestDialog isOpen onClose={() => {}} type="text-correction" context={{}} showCorrection />);
    expect(screen.getByLabelText(/corrected text \(optional\)/i)).toBeTruthy();
  });
});

describe('RequestDialog — sending', () => {
  it('posts type, message, context and contact to /api/feature-request', async () => {
    const fetchMock = mockFetch();
    const user = userEvent.setup();
    render(
      <RequestDialog
        isOpen
        onClose={() => {}}
        type="suggestion"
        context={{ page_url: 'https://tesserae.example/help' }}
      />
    );
    await user.type(screen.getByLabelText(/what would you like to see/i), 'Add a dark mode');
    await user.type(screen.getByLabelText(/your name/i), 'A Scholar');
    await user.type(screen.getByLabelText(/^email/i), 'scholar@example.edu');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/feature-request');
    const body = JSON.parse(options.body);
    expect(body).toMatchObject({
      type: 'suggestion',
      source: 'site',
      message: 'Add a dark mode',
      name: 'A Scholar',
      contact: 'scholar@example.edu',
      context: { page_url: 'https://tesserae.example/help' },
    });
    expect(screen.getByText(/thank you/i)).toBeTruthy();
  });

  it('does not submit an empty message', async () => {
    const fetchMock = mockFetch();
    const user = userEvent.setup();
    render(<RequestDialog isOpen onClose={() => {}} type="suggestion" context={{}} />);
    await user.click(screen.getByRole('button', { name: 'Send' }));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('shows an error message when the request fails', async () => {
    const fetchMock = mockFetch(false);
    const user = userEvent.setup();
    render(<RequestDialog isOpen onClose={() => {}} type="suggestion" context={{}} />);
    await user.type(screen.getByLabelText(/what would you like to see/i), 'hello');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/something went wrong/i)).toBeTruthy();
  });
});
