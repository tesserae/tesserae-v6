/**
 * Closed, Tessa is a small round button, and its x tucks it into a slim tab
 * on the right edge, remembered in this browser (2026-10-07: the bubble
 * "permanently blocks reading that corner of the page").
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AssistantDock from '../AssistantDock';
import { installPhone } from '../../../test/phone';

beforeEach(() => {
  window.localStorage.clear();
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ available: true }) }));
});
afterEach(() => { delete global.fetch; });

describe('Tessa launcher', () => {
  it('is a small button that can be tucked to the edge and brought back', async () => {
    const { unmount } = render(<AssistantDock />);
    const open = await screen.findByRole('button', { name: 'Open Tessa, the AI assistant' });
    expect(open.textContent).toBe('Tessa');
    expect(screen.queryByText('AI Assistant')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Tuck Tessa away to the side of the page' }));
    expect(screen.queryByRole('button', { name: 'Open Tessa, the AI assistant' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Show Tessa, the AI assistant' })).toBeTruthy();
    unmount();
    render(<AssistantDock />);                      // remembered across page loads
    expect(await screen.findByRole('button', { name: 'Show Tessa, the AI assistant' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Show Tessa, the AI assistant' }));
    expect(await screen.findByRole('button', { name: 'Open Tessa, the AI assistant' })).toBeTruthy();
  });
});

describe('Tessa on a phone', () => {
  it('is the slim side tab when closed, even if never tucked, and opens from it', async () => {
    const env = installPhone(true);
    try {
      render(<AssistantDock />);
      const tab = await screen.findByRole('button', { name: 'Show Tessa, the AI assistant' });
      expect(tab.textContent).toBe('Tessa');
      expect(tab.className).toContain('right-0');
      expect(screen.queryByRole('button', { name: 'Open Tessa, the AI assistant' })).toBeNull();
      fireEvent.click(tab);
      // the card is open now: the side tab is gone
      expect(screen.queryByRole('button', { name: 'Show Tessa, the AI assistant' })).toBeNull();
    } finally { env.restore(); }
  });
});
