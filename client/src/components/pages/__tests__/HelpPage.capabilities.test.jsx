import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import LanguageCapabilities from '../LanguageCapabilities';

const ANSWER = {
  computed_at: '2026-11-10',
  capabilities: [
    { key: 'texts', heading: 'Texts', name: 'Texts' },
    { key: 'syntax', heading: 'Grammar parse', name: 'Grammar parse' },
    { key: 'meter', heading: 'Scansion', name: 'Scansion (meter)' }
  ],
  languages: [{
    code: 'la', label: 'Latin',
    capabilities: {
      texts: { state: 'full', count: 1883, note: '1883 text files' },
      syntax: { state: 'partial', count: 10, note: '10 of 20 texts parsed' },
      meter: { state: 'none', count: 0, note: 'Latin verse only so far' }
    }
  }]
};

afterEach(() => { vi.unstubAllGlobals(); });

describe('LanguageCapabilities', () => {
  it('draws one dot per cell with its state and a hover title', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(ANSWER) })));
    const { container } = render(<LanguageCapabilities />);
    expect(screen.getByText(/Loading the table/)).toBeTruthy();
    await waitFor(() => expect(screen.getByText('Latin')).toBeTruthy());
    const dots = [...container.querySelectorAll('[data-state]')];
    expect(dots.map((d) => d.getAttribute('data-state'))).toEqual(['full', 'partial', 'none']);
    expect(dots[1].getAttribute('title')).toContain('10 of 20 texts parsed');
    expect(container.innerHTML).not.toMatch(/blue/);
    expect(screen.getByText(/2026-11-10/)).toBeTruthy();
  });

  it('shows nothing on an error', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('down'))));
    const { container } = render(<LanguageCapabilities />);
    await waitFor(() => expect(container.innerHTML).toBe(''));
  });
});
