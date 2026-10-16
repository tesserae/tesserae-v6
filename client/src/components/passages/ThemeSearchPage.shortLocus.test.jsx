/**
 * Theme Search cards print the short locus, with the file's tag as hover text
 * (2026-10-15). They printed "thuc. pele. 2.57.1".
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ThemeSearchPage from './ThemeSearchPage';
import { mockResponse } from '../../test/mockResponse';

describe('Theme Search card reference', () => {
  it('uses the server locus and keeps the tag in the hover text', async () => {
    const payload = {
      query: 'the plague strikes the army',
      results: [{ work: 'thucydides.peloponnesian_war.part.2', ref_start: 'thuc. pele. 2.57.1',
        ref_end: 'thuc. pele. 2.58.3', locus: '2.57.1–2.58.3', score: 0.9, strong: true,
        gist: 'Plague reaches the army.', language: 'grc', author: 'Thucydides', title: 'Peloponnesian War' }],
      strong_matches: 1,
      confidence: { level: 'high', coherence: 0.9, head_lift: 0.2, degenerate: false },
    };
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/languages')) {
        return Promise.resolve(mockResponse({ json: () => Promise.resolve({ languages: [{ code: 'grc' }] }) }));
      }
      if (u.startsWith('/api/passages/theme-search')) {
        return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(payload) }));
      }
      return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({}) }));
    });
    render(<ThemeSearchPage />);
    fireEvent.change(await screen.findByPlaceholderText(/warrior arms himself/i),
      { target: { value: 'the plague strikes the army' } });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));
    const loc = await waitFor(() => screen.getByText('2.57.1–2.58.3'));
    expect(loc.getAttribute('title')).toBe('thuc. pele. 2.57.1 – thuc. pele. 2.58.3');
    expect(screen.queryByText(/thuc\. pele\./)).toBeNull();
  });

  it('falls back to the short form of ref_start when the answer has no locus', async () => {
    const { windowLocus } = await import('../reader/refId');
    expect(windowLocus({ ref_start: 'thuc. pele. 2.57.1', ref_end: 'thuc. pele. 2.57.1' })).toBe('2.57.1');
    expect(windowLocus({ ref_start: 'thuc. pele. 2.57.1', ref_end: 'thuc. pele. 2.58.3' })).toBe('2.57.1–2.58.3');
  });
});
