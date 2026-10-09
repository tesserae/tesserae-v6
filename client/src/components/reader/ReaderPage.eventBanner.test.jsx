/** Arriving in the Reader from an Event page names the event and links back to it. */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';

const reply = (obj) => Promise.resolve({
  ok: true, json: () => Promise.resolve(obj), text: () => Promise.resolve(JSON.stringify(obj)),
});

afterEach(() => { cleanup(); vi.clearAllMocks(); window.history.replaceState({}, '', '/'); });

describe('arriving from an Event page', () => {
  it('names the event and links back to it', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/text/')) {
        return reply({ units: [{ ref: 'ov. tr. 3.1', text: 'a line' }], metadata: { display_name: 'a text' } });
      }
      if (u.includes('/authors?')) return reply([]);
      if (u.includes('/texts?')) return reply([]);
      if (u.startsWith('/api/languages')) return reply({ languages: [{ code: 'la' }, { code: 'grc' }] });
      return reply({});
    });
    window.history.replaceState({}, '', '/read?work=ovid.tristia.part.3.tess&lang=la&ref='
      + encodeURIComponent('ov. tr. 3.1') + '&event=Q179591&eventLabel=' + encodeURIComponent('Battle of Cannae'));
    const { default: ReaderPage } = await import('./ReaderPage');
    render(<ReaderPage />);
    const banner = await screen.findByTestId('reader-event-banner');
    expect(banner.textContent).toContain('Battle of Cannae');
    expect(within(banner).getByRole('link', { name: /back to the event/ })).toHaveAttribute('href', '/events/Q179591');
  });
});
