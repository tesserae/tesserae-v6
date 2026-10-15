/**
 * The Parallels tab's switch "Hide <Author>'s own works": off by default, sends
 * exclude_author when on, re-runs the search, and is remembered in the browser.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';

const UNITS = [{ ref: 'verg. aen. 1.1', text: 'Arma virumque cano, Troiae qui primus ab oris' }];
const KEY = 'tesserae_reader_hide_own_author';
let bodies;

function mount() {
  return render(
    <ResultsPanel
      selection={{ refStart: 'verg. aen. 1.1', refEnd: 'verg. aen. 1.1', startIdx: 0, endIdx: 0 }}
      language="la"
      work="vergil.aeneid.part.1.tess"
      units={UNITS}
      onOpenPassage={vi.fn()}
      initialTab="verbal"
    />
  );
}

beforeEach(() => {
  bodies = [];
  window.localStorage.clear();
  global.fetch = vi.fn((url, opts) => {
    bodies.push(JSON.parse(opts?.body || '{}'));
    return Promise.resolve({ json: () => Promise.resolve({ results: [] }) });
  });
});
afterEach(() => { cleanup(); window.localStorage.clear(); });

describe('Hide the author\'s own works', () => {
  it('is off by default and sends no exclude_author', async () => {
    mount();
    const box = await screen.findByLabelText(/Hide Vergil.s own works/);
    expect(box.checked).toBe(false);
    await waitFor(() => expect(bodies.length).toBeGreaterThan(0));
    expect(bodies[0].exclude_author).toBeUndefined();
  });

  it('sends exclude_author when switched on, re-runs, and remembers the choice', async () => {
    mount();
    const box = await screen.findByLabelText(/Hide Vergil.s own works/);
    await waitFor(() => expect(bodies.length).toBe(1));
    fireEvent.click(box);
    await waitFor(() => expect(bodies.length).toBe(2));
    expect(bodies[1].exclude_author).toBe('vergil');
    expect(window.localStorage.getItem(KEY)).toBe('on');
  });

  it('starts switched on when the browser remembers it', async () => {
    window.localStorage.setItem(KEY, 'on');
    mount();
    const box = await screen.findByLabelText(/Hide Vergil.s own works/);
    expect(box.checked).toBe(true);
    await waitFor(() => expect(bodies.length).toBeGreaterThan(0));
    expect(bodies[0].exclude_author).toBe('vergil');
  });
});

describe('Show more matches', () => {
  const full = (n) => ({
    capped: true,
    results: Array.from({ length: n }, (_, i) => ({
      author: 'Ovid', work: 'Met', text_id: 'ovid.met.tess', locus: `1.${i + 1}`,
      year: 8, matched_words: ['arma'], text: 'arma virum',
    })),
  });

  it('starts at 50, asks for 100 on Show more, and resets on a new selection', async () => {
    const limits = [];
    global.fetch = vi.fn((url, opts) => {
      const b = JSON.parse(opts?.body || '{}');
      limits.push(b.max_results);
      return Promise.resolve({ json: () => Promise.resolve(full(b.max_results)) });
    });
    const props = { language: 'la', work: 'vergil.aeneid.part.1.tess', units: [
      ...UNITS, { ref: 'verg. aen. 1.2', text: 'Italiam fato profugus' }],
      onOpenPassage: vi.fn(), initialTab: 'verbal' };
    const sel = (i) => ({ refStart: `verg. aen. 1.${i + 1}`, refEnd: `verg. aen. 1.${i + 1}`, startIdx: i, endIdx: i });
    const { rerender } = render(<ResultsPanel {...props} selection={sel(0)} />);
    await waitFor(() => expect(limits).toEqual([50]));
    fireEvent.click(await screen.findByText('Show more matches'));
    await waitFor(() => expect(limits).toContain(100));
    rerender(<ResultsPanel {...props} selection={sel(1)} />);
    await waitFor(() => expect(limits[limits.length - 1]).toBe(50));
  });

  it('shows no button when the list came back short', async () => {
    global.fetch = vi.fn(() => Promise.resolve({
      json: () => Promise.resolve({ capped: false, results: full(3).results }) }));
    mount();
    await screen.findByLabelText(/Hide Vergil.s own works/);
    await waitFor(() => expect(screen.queryByText('Show more matches')).toBeNull());
  });
});
