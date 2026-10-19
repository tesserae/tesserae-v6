/**
 * The full-translation block header shows the short locus, with the file's tag
 * as hover text (2026-10-15). It printed "thuc. pele. 2.57.1".
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';

const UNITS = [{ ref: 'thuc. pele. 2.57.1', text: 'x' }];

describe('translation block header', () => {
  it('shows 2.57.1 and keeps the tag in the hover text', async () => {
    const body = {
      available: true, attribution: 'Crawley', alignment_confidence: 'high',
      blocks: [{ ref_start: 'thuc. pele. 2.57.1', ref_end: 'thuc. pele. 2.58.3', text: 'Meanwhile' }],
    };
    global.fetch = vi.fn(() => Promise.resolve({
      ok: true, json: () => Promise.resolve(body), text: () => Promise.resolve(JSON.stringify(body)),
      headers: { get: () => 'application/json' },
    }));
    render(<ResultsPanel selection={null} language="grc" work="thucydides.peloponnesian_war.part.2"
                         units={UNITS} initialTab="translation" />);
    fireEvent.click(await screen.findByRole('button', { name: /show full translation/i }));
    const head = await screen.findByText('2.57.1–2.58.3');
    expect(head.getAttribute('title')).toBe('thuc. pele. 2.57.1 – thuc. pele. 2.58.3');
    expect(screen.queryByText(/thuc\. pele\./)).toBeNull();
  });
});


describe('shortRef keeps every level of the locus', () => {
  it('keeps a Roman act and a book number', async () => {
    const { shortRef } = await import('./ResultsPanel');
    expect(shortRef('hamlet III.1.66')).toBe('III.1.66');
    expect(shortRef('Spenser F.Q. 3.9.359')).toBe('3.9.359');
    expect(shortRef('thuc. pele. 2.57.1')).toBe('2.57.1');
    expect(shortRef('verg. aen. 1.1')).toBe('1.1');
    expect(shortRef('ennius ann. sedinc.481')).toBe('481 (book uncertain)');
  });
});
