/**
 * The Cite popup's "How to cite Tesserae" link (and the matching Help
 * sentence) open the About page scrolled to its How to Cite section
 * (crosslingual parity, 2026-10-08). AboutPage needed the same
 * initialAnchor/onAnchorConsumed pattern HelpPage already has for its own
 * InfoBadge "More" links.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import AboutPage from '../AboutPage';

afterEach(() => { delete global.fetch; vi.restoreAllMocks(); });

beforeEach(() => {
  global.fetch = vi.fn(() => Promise.resolve({
    json: () => Promise.resolve({ version: '6.0', last_updated: '2026-10-08' }),
  }));
});

describe('AboutPage — anchor scroll', () => {
  it('has an id="how-to-cite" on the How to Cite section', async () => {
    render(<AboutPage />);
    expect(await screen.findByText('How to Cite')).toBeTruthy();
    expect(document.getElementById('how-to-cite')).toBeTruthy();
  });

  it('scrolls to the given anchor once on mount and reports it consumed', async () => {
    const scrollMock = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollMock;
    const onAnchorConsumed = vi.fn();

    render(<AboutPage initialAnchor="how-to-cite" onAnchorConsumed={onAnchorConsumed} />);

    expect(onAnchorConsumed).toHaveBeenCalled();
    await waitFor(() => expect(scrollMock).toHaveBeenCalled());
  });

  it('does nothing when no anchor is given', async () => {
    const scrollMock = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollMock;
    render(<AboutPage />);
    await screen.findByText('How to Cite');
    expect(scrollMock).not.toHaveBeenCalled();
  });
});
