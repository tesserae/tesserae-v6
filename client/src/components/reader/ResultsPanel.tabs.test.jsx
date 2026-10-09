/**
 * The tab strip: short labels ("Similar", "Parallels", "Translation",
 * "Reuse", and the trial "Scholarship") so all five fit one row.
 *
 * Wrapping used to be the strip's answer to overflow, but with five tabs
 * (Scholarship added) that pushed the fifth to a second line, where it no
 * longer read as one of the tabs (owner review, 2026-10-08). The strip now
 * stays one row at the panel's normal width and falls back to a horizontal
 * scroll -- never a second line -- if it is still too narrow.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';
import { resetScholarshipLanguagesCache } from '../../utils/scholarshipLanguages';

const UNITS = [{ ref: 'verg. aen. 1.1', text: 'Arma virumque cano' }];

function mount(props = {}) {
  render(
    <ResultsPanel
      selection={null}
      language="la"
      work="vergil.aeneid"
      units={UNITS}
      {...props}
    />
  );
}

beforeEach(() => {
  resetScholarshipLanguagesCache();
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
});

afterEach(() => {
  delete global.fetch;
  window.history.replaceState({}, '', '/');
});

describe('the tab strip', () => {
  it('uses short labels that fit one row', () => {
    mount();
    for (const label of ['Similar', 'Parallels', 'Translation', 'Reuse']) {
      expect(screen.getByRole('button', { name: label })).toBeTruthy();
    }
    // The old, longer wording is gone from the tab strip itself (it may
    // still appear elsewhere, e.g. explanatory copy).
    expect(screen.queryByRole('button', { name: 'Similar Passages' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Verbal Parallels' })).toBeNull();
  });

  it('keeps the full name as a tooltip on the short label', () => {
    mount();
    expect(screen.getByRole('button', { name: 'Similar' }).title).toBe('Similar Passages');
    expect(screen.getByRole('button', { name: 'Parallels' }).title).toBe('Verbal Parallels');
  });

  it('never wraps to a second line; it scrolls instead if it does not fit', () => {
    mount();
    const strip = screen.getByRole('button', { name: 'Reuse' }).parentElement;
    expect(strip.className).not.toContain('flex-wrap');
    expect(strip.className).toContain('flex-nowrap');
    expect(strip.className).toContain('overflow-x-auto');
  });
});

describe('the Scholarship tab, trial switch plus language gating', () => {
  function mockSources(languages) {
    global.fetch = vi.fn((url) => {
      if (String(url).startsWith('/api/scholarship/sources')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ commentaries: [], languages }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
  }

  it('does not render at all without the ?scholarship=1 trial, even for a covered language', async () => {
    mockSources(['la', 'grc', 'he', 'en']);
    mount({ language: 'la' });
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Scholarship' })).toBeNull());
  });

  it('renders, in the one-row strip, for a language the site holds scholarship for', async () => {
    window.history.pushState({}, '', '/read?scholarship=1');
    mockSources(['la', 'grc', 'he', 'en']);
    mount({ language: 'la' });
    expect(await screen.findByRole('button', { name: 'Scholarship' })).toBeTruthy();
    const strip = screen.getByRole('button', { name: 'Reuse' }).parentElement;
    expect(strip.className).not.toContain('flex-wrap');
  });

  it('does not render for a language with no installed scholarship (Persian)', async () => {
    window.history.pushState({}, '', '/read?scholarship=1');
    mockSources(['la', 'grc', 'he', 'en']);
    mount({ language: 'fa' });
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Scholarship' })).toBeNull();
  });
});
