/**
 * The English reading view's block header shows the short locus, with the
 * file's tag as hover text (2026-10-15). It printed "thuc. pele. 2.57.1".
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

describe('ReaderPage English view block header', () => {
  it('shows 2.57.1 and keeps the tag in the hover text', async () => {
    window.history.replaceState({}, '', '/read?work=thucydides.peloponnesian_war.part.2.tess&lang=grc&view=english');
    const reply = (obj) => Promise.resolve({
      ok: true, json: () => Promise.resolve(obj), text: () => Promise.resolve(JSON.stringify(obj)),
    });
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/text/')) {
        return reply({ units: [{ ref: 'thuc. pele. 2.57.1', text: 'a line' }], metadata: { display_name: 't' } });
      }
      if (u.startsWith('/api/passages/translation-full')) {
        return reply({ available: true, attribution: 'Crawley', blocks: [
          { ref_start: 'thuc. pele. 2.57.1', ref_end: 'thuc. pele. 2.57.1', text: 'Meanwhile' }] });
      }
      if (u.includes('/authors?')) return reply([]);
      if (u.includes('/texts?')) return reply([]);
      if (u.startsWith('/api/languages')) return reply({ languages: [{ code: 'grc' }] });
      return reply({});
    });
    const { default: ReaderPage } = await import('./ReaderPage');
    render(<ReaderPage />);
    const head = await waitFor(() => screen.getByText('2.57.1'));
    expect(head.getAttribute('title')).toBe('thuc. pele. 2.57.1');
    expect(screen.queryByText(/thuc\. pele\./)).toBeNull();
  });
});
