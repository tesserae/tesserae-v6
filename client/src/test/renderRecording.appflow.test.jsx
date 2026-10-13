/**
 * The App-level flows the page snapshots cannot reach (cleaning job H4,
 * 2026-10-13): a deep-linked comparison that runs, the Search Corpus side
 * panel, the Save Parallel dialog with its fields, and the request it sends.
 * The search call is stubbed (the stream is the server's); everything the
 * App does with the reply is real. Recorded on main before App.jsx was split.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { makeRows } from './renderFixtures';

vi.mock('react-chartjs-2', async () => {
  const { forwardRef, createElement } = await vi.importActual('react');
  return { Bar: forwardRef(({ data }, ref) => createElement('div', { ref, 'data-labels': JSON.stringify(data?.labels || []) }, 'chart')) };
});
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {}, Title: {}, Tooltip: {}, Legend: {},
}));
vi.mock('../utils/api', async (importOriginal) => {
  const real = await importOriginal();
  const rows = (await import('./renderFixtures')).makeRows();
  // The third row on screen carries no channels, so the Save Parallel request can be
  // recorded; a row with a channels array is the characterization test below.
  delete [...rows].sort((a, b) => b.fused_score - a.fused_score)[2].channels;
  const reply = {
    type: 'complete', results: rows, elapsed_time: 3.2, source_lines: 756, target_lines: 700, total_matches: rows.length, corpus_version: 'v-fixed',
  };
  return {
    ...real,
    searchFusionStream: vi.fn(async () => reply),
    searchTextsStream: vi.fn(async () => reply),
    searchTexts: vi.fn(async () => reply),
  };
});

import App from '../App';

const json = (data, ok = true) => ({
  ok, status: ok ? 200 : 400,
  json: () => Promise.resolve(data),
  text: () => Promise.resolve(JSON.stringify(data)),
});
const TEXTS = [
  { id: 'vergil.aeneid.part.1.tess', author: 'Vergil', title: 'Aeneid 1', line_count: 756, language: 'la' },
  { id: 'lucan.bellum_civile.part.1.tess', author: 'Lucan', title: 'Civil War 1', line_count: 700, language: 'la' },
];
const posted = [];
const routeFetch = (url, init) => {
  const u = String(url);
  if (u.startsWith('/api/intertexts/my')) { posted.push(JSON.parse(init.body)); return Promise.resolve(json({ ok: true })); }
  if (u.startsWith('/api/corpus-search')) {
    return Promise.resolve(json({ results: [
      { text_id: 'vergil.aeneid.part.2.tess', author: 'Vergil', title: 'Aeneid 2', locus: '2.5', citation: 'Vergil, Aeneid 2.5', text: 'arma virum que', matched_lemmas: ['arma', 'virum'], tokens: ['arma', 'virum', 'que'], highlight_indices: [0, 1], year: -19, era: 'Augustan' },
    ] }));
  }
  if (u.startsWith('/api/texts?language=')) return Promise.resolve(json(TEXTS));
  if (u.startsWith('/api/authors')) return Promise.resolve(json([]));
  if (u.startsWith('/api/languages')) return Promise.resolve(json({ languages: [{ code: 'la', label: 'Latin' }] }));
  if (u.startsWith('/api/admin/me')) return Promise.resolve(json({}, false));
  if (u.startsWith('/api/auth/user')) return Promise.resolve(json({ user: { id: 1, first_name: 'Test', last_name: 'User' } }));
  if (u.startsWith('/api/version')) return Promise.resolve(json({ bundle: null }));
  if (u.startsWith('/api/assistant/status')) return Promise.resolve(json({ available: false }));
  if (u.startsWith('/api/passages/pair-lift')) return Promise.resolve(json({ results: [] }));
  return Promise.resolve(json({}));
};

const normalize = (html) => html
  .replace(/\d{4}-\d{2}-\d{2}/g, 'DATE')
  .replace(/:r[0-9a-z]+:/g, ':rID:')
  .replace(/></g, '>\n<');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const settle = async (max = 30) => {
  let last = null;
  let same = 0;
  for (let i = 0; i < max && same < 3; i += 1) {
    await act(async () => { await sleep(20); });
    const now = document.body.innerHTML;
    same = now === last ? same + 1 : 0;
    last = now;
  }
};

beforeEach(() => {
  posted.length = 0;
  global.fetch = vi.fn(routeFetch);
  window.localStorage.clear();
  window.sessionStorage.setItem('tess_show_dist_chart', 'false');
  window.history.replaceState({}, '', '/?source=vergil.aeneid.part.1.tess&target=lucan.bellum_civile.part.1.tess&lang=la&tab=parallel');
});
afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/');
});

describe('App flows: results, Search Corpus, Save Parallel', () => {
  it('runs the deep-linked comparison and shows the results', async () => {
    render(<App />);
    await screen.findAllByRole('button', { name: 'Register' }, { timeout: 15000 });
    await settle();
    expect(normalize(document.body.innerHTML)).toMatchSnapshot();
    expect(makeRows().length).toBe(30);
  });

  it('opens the Search Corpus side panel from a card', async () => {
    render(<App />);
    const buttons = await screen.findAllByRole('button', { name: 'Search Corpus' }, { timeout: 15000 });
    await userEvent.click(buttons[0]);
    await waitFor(() => expect(global.fetch.mock.calls.some(([u]) => String(u).startsWith('/api/corpus-search'))).toBe(true));
    await settle(60);
    await settle();
    expect(normalize(document.body.innerHTML)).toMatchSnapshot();
    expect(global.fetch.mock.calls.filter(([u]) => String(u).startsWith('/api/corpus-search')).map(([, i]) => JSON.parse(i.body))).toMatchSnapshot('corpus-search request');
  });

  it('opens the Save Parallel dialog, fills it and sends the parallel', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<App />);
    const buttons = await screen.findAllByRole('button', { name: 'Register' }, { timeout: 15000 });
    await userEvent.click(buttons[2]);
    await screen.findByText('Rate this parallel:', {}, { timeout: 15000 });
    await settle();
    expect(normalize(document.body.innerHTML)).toMatchSnapshot('dialog open');
    await userEvent.click(screen.getByRole('button', { name: 'Make Public' }));
    await userEvent.click(screen.getAllByRole('button', { name: '★' })[3]);
    fireEvent.change(screen.getByPlaceholderText(/Add scholarly commentary/), { target: { value: 'a note' } });
    await settle();
    expect(normalize(document.body.innerHTML)).toMatchSnapshot('dialog filled');
    await userEvent.click(screen.getAllByText('Save Parallel').find((el) => el.tagName === 'BUTTON'));
    await waitFor(() => expect(posted.length).toBe(1));
    await settle();
    expect(posted[0]).toMatchSnapshot('request body');
    expect(window.location.pathname).toBe('/repository');
    expect(alertSpy).not.toHaveBeenCalled();
  });

  it('records what happens today when a fusion row (channels is an array) is saved', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<App />);
    const buttons = await screen.findAllByRole('button', { name: 'Register' }, { timeout: 15000 });
    await userEvent.click(buttons[0]);
    await screen.findByText('Rate this parallel:', {}, { timeout: 15000 });
    await userEvent.click(screen.getAllByRole('button', { name: '★' })[2]);
    await userEvent.click(screen.getAllByText('Save Parallel').find((el) => el.tagName === 'BUTTON'));
    await settle();
    expect(alertSpy.mock.calls).toMatchSnapshot();
    expect(posted.length).toBe(0);
  });

  it('Cancel closes the dialog and clears it', async () => {
    render(<App />);
    const buttons = await screen.findAllByRole('button', { name: 'Register' }, { timeout: 15000 });
    await userEvent.click(buttons[0]);
    await screen.findByText('Rate this parallel:', {}, { timeout: 15000 });
    await userEvent.click(screen.getAllByRole('button', { name: '★' })[1]);
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await settle();
    expect(screen.queryByText('Rate this parallel:')).toBeNull();
    await userEvent.click(buttons[0]);
    await screen.findByText('Rate this parallel:', {}, { timeout: 15000 });
    expect(screen.getByText('Required')).toBeTruthy();
  });
});
