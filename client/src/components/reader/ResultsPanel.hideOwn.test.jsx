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
