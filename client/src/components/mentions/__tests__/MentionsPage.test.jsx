/**
 * The Mentions page (trial): hidden without ?entities=1, the search list, the entity view with
 * mentions grouped by work, and the row of a shared name.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import MentionsPage, { MentionRow, sharedLabel, sortedCounts, TRIAL_NOTE } from '../MentionsPage';
import { entitiesTrialOn, ENTITIES_KEY } from '../../../hooks/useEntitiesTrial';

const SEARCH = {
  available: true, total: 1,
  results: [{ id: 'ln:E2', label: 'Ares/Mars', type: 'deity', mention_counts: { en: 2, grc: 4, la: 9 },
              mentions_total: 15, label_shared: true, label_shared_with: [] }],
};
const ENTITY = {
  id: 'ln:E2', label: 'Ares/Mars', type: 'deity', identifiers: {}, mention_counts: { la: 1 },
  label_shared: true, label_shared_with: [],
  works: [{ work: 'vergil.aeneid', title: 'Aeneid', author: 'Vergil', language: 'la', count: 1 }],
};
const MENTIONS = {
  total: 1,
  results: [{ window_id: 'vergil.aeneid:fine:1', work: 'vergil.aeneid', language: 'la', ref_start: 'verg. aen. 1.1',
              ref_end: 'verg. aen. 1.2', locus: '1.1', text: 'Troia fuit, et Mars ferox.', token: 'Mars',
              shared_with: ['Mars (Roman family)', 'Marsi'] }],
};

function stubFetch() {
  global.fetch = vi.fn((url) => {
    const body = String(url).includes('/mentions') ? MENTIONS : String(url).includes('/search') ? SEARCH : ENTITY;
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
  });
}

beforeEach(() => {
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/mentions');
  stubFetch();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('the trial switch', () => {
  it('is off by default and on after ?entities=1, for the rest of the visit', () => {
    expect(entitiesTrialOn()).toBe(false);
    window.history.replaceState({}, '', '/?entities=1');
    expect(entitiesTrialOn()).toBe(true);
    expect(window.sessionStorage.getItem(ENTITIES_KEY)).toBe('1');
    window.history.replaceState({}, '', '/theme-search');
    expect(entitiesTrialOn()).toBe(true);
  });

  it('sends a visitor without it to Search and draws nothing', () => {
    const setPageType = vi.fn();
    const { container } = render(<MentionsPage setPageType={setPageType} />);
    expect(container).toBeEmptyDOMElement();
    expect(setPageType).toHaveBeenCalledWith('search');
  });
});

describe('the page', () => {
  beforeEach(() => { window.sessionStorage.setItem(ENTITIES_KEY, '1'); });

  it('shows the title, the gray trial note and a search box', () => {
    render(<MentionsPage setPageType={() => {}} />);
    expect(screen.getByRole('heading', { name: 'Mentions' })).toBeInTheDocument();
    expect(screen.getByTestId('trial-note').textContent).toBe(TRIAL_NOTE);
    expect(screen.getByLabelText('A place, person or god')).toBeInTheDocument();
  });

  it('lists matches with counts in Latin, Greek, English order, then opens one', async () => {
    const user = userEvent.setup();
    render(<MentionsPage setPageType={() => {}} />);
    await user.type(screen.getByLabelText('A place, person or god'), 'mars{enter}');
    const item = await screen.findByTestId('entity-result');
    expect(item.textContent).toMatch(/God · Latin 9 · Greek 4 · English 2/);
    await user.click(screen.getByRole('link', { name: 'Ares/Mars' }));
    expect(await screen.findByRole('heading', { name: 'Ares/Mars' })).toBeInTheDocument();
    await user.click(await screen.findByRole('button', { name: /Vergil, Aeneid/ }));
    const row = await screen.findByTestId('mention-row');
    expect(row.querySelector('mark').textContent).toBe('Mars');
    expect(row.querySelector('a').getAttribute('href')).toBe(
      '/read?work=vergil.aeneid.tess&lang=la&ref=verg.+aen.+1.1&refEnd=verg.+aen.+1.2&tab=similar');
    expect(screen.getByTestId('shared-label').textContent).toBe('name shared with Mars (Roman family) and Marsi');
  });
});

describe('a row', () => {
  it('carries the gray label only when the name is shared', () => {
    const base = MENTIONS.results[0];
    const { rerender } = render(<ul><MentionRow r={{ ...base, shared_with: [] }} /></ul>);
    expect(screen.queryByTestId('shared-label')).toBeNull();
    rerender(<ul><MentionRow r={{ ...base, shared_with: ['Argos'] }} /></ul>);
    expect(screen.getByTestId('shared-label').textContent).toBe('name shared with Argos');
  });

  it('words the label and orders the counts', () => {
    expect(sharedLabel(['A', 'B', 'C'])).toBe('name shared with A, B and C');
    expect(sharedLabel([])).toBe('');
    expect(sortedCounts({ en: 1, la: 2, grc: 3, cop: 4 }).map(([k]) => k)).toEqual(['la', 'grc', 'en', 'cop']);
  });
});
