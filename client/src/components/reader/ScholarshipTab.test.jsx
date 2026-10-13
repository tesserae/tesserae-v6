/**
 * Bolding a citation in a scholarship snippet: an exact match of the surface
 * the backend found works most of the time, but Google Books and CORE
 * return their own OCR-ish spacing ("Aen . 1.1 arma virumque cano",
 * "Aen . 1.1-4") that an exact match never hits, so the "cites ..." line
 * was right and the snippet next to it was never bolded at all.
 * findMark() is the tolerant fallback: the work's
 * abbreviation or title next to its locus, loose about spacing around
 * periods and commas and a following range, else the passage's own
 * opening words.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ScholarshipTab, { findMark } from './ScholarshipTab';

const AENEID_1_1 = { work: 'vergil.aeneid', author: 'Vergil', title: 'Aeneid', abbrev: 'Aen.', lo: '1.1', hi: '1.7' };

function marked(text, mark, passage, fallbackWords) {
  const hit = findMark(text, mark, passage, fallbackWords);
  if (!hit) return null;
  return text.slice(hit.start, hit.end);
}

describe('findMark: tolerant citation bolding', () => {
  it('bolds "Aen . 1.1" (spaces around the abbreviation\'s period)', () => {
    const text = 'Aen . 1.1 arma virumque cano';
    expect(marked(text, null, AENEID_1_1)).toBe('Aen . 1.1');
  });

  it('bolds "Aen. 1.1-4" (a range after the locus)', () => {
    const text = 'the storm answers the calm of Aen. 1.1-4 exactly.';
    const hit = marked(text, null, AENEID_1_1);
    expect(hit).toBe('Aen. 1.1-4');
  });

  it('bolds "Aeneid 1.1" (the full title, not the abbreviation)', () => {
    const text = 'see Aeneid 1.1 for the opening of the poem';
    expect(marked(text, null, AENEID_1_1)).toBe('Aeneid 1.1');
  });

  it('still prefers an exact surface match when one is given and present', () => {
    const text = 'the proem (Aen. 1.1-7) states the theme';
    expect(marked(text, 'Aen. 1.1-7', AENEID_1_1)).toBe('Aen. 1.1-7');
  });

  it('finds the exact surface case-insensitively before trying the tolerant match', () => {
    const text = 'ARMA VIRUMQUE CANO, Troiae qui primus ab oris';
    expect(marked(text, 'arma virumque cano', AENEID_1_1)).toBe('ARMA VIRUMQUE CANO');
  });

  it('falls back to the passage\'s opening words when nothing names the work or locus', () => {
    const text = 'a commentary that never mentions Vergil by name: arma virumque cano, Troiae qui primus.';
    expect(marked(text, null, AENEID_1_1, 'arma virumque cano')).toBe('arma virumque cano');
  });

  it('finds nothing to bold when neither a citation nor the opening words appear', () => {
    const text = 'a paragraph about something else entirely.';
    expect(findMark(text, null, AENEID_1_1, 'arma virumque cano')).toBeNull();
  });

  it('bolds the first occurrence when the citation appears more than once', () => {
    const text = 'Aen. 1.1 opens the poem; later scholars return to Aen. 1.1 again.';
    const hit = findMark(text, null, AENEID_1_1);
    expect(hit.start).toBe(text.indexOf('Aen. 1.1'));
  });
});

/**
 * The footer boilerplate (the long "Found by title and abstract in OpenAlex
 * and Crossref..." paragraph and the HathiTrust explanation underneath it)
 * is replaced by one short line: a "Where these results come from" link to
 * the matching Help section, and the existing HathiTrust link on its own
 * (ScholarshipTab fix, 2026-10-08).
 */
const UNITS = [{ ref: '1.1', text: 'arma virumque cano' }];
const SELECTION = { startIdx: 0, endIdx: 0 };

function respond(data) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
}

afterEach(() => { delete global.fetch; });

describe('ScholarshipTab \u2014 shortened footer', () => {
  it('drops the long services paragraph and the separate HathiTrust explanation', async () => {
    global.fetch = vi.fn(() => respond({
      commentary: [], results: [], index: { results: [] }, fulltext: { results: [] },
      books: { results: [], hathitrust_url: 'https://babel.hathitrust.org/cgi/ls?q1=example' },
    }));
    render(<ScholarshipTab work="vergil.aeneid" language="la" selection={SELECTION} units={UNITS} />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    expect(screen.queryByText(/Found by title and abstract in OpenAlex/)).toBeNull();
    expect(screen.queryByText(/Sources and licenses are on the Sources page/)).toBeNull();
    expect(screen.queryByText(/without showing the text/)).toBeNull();
    expect(screen.getByRole('button', { name: 'Where these results come from' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Search HathiTrust\u2019s full text for this passage' })).toBeTruthy();
  });

  it('hides the HathiTrust link when the lookup gives none, keeping the Help link', async () => {
    global.fetch = vi.fn(() => respond({
      commentary: [], results: [], index: { results: [] }, fulltext: { results: [] }, books: { results: [] },
    }));
    render(<ScholarshipTab work="vergil.aeneid" language="la" selection={SELECTION} units={UNITS} />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    expect(screen.getByRole('button', { name: 'Where these results come from' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: /HathiTrust/ })).toBeNull();
  });

  it('"Where these results come from" dispatches tesserae:open-help at the scholarship-sources anchor', async () => {
    global.fetch = vi.fn(() => respond({
      commentary: [], results: [], index: { results: [] }, fulltext: { results: [] }, books: { results: [] },
    }));
    const handler = vi.fn();
    window.addEventListener('tesserae:open-help', handler);
    const user = userEvent.setup();
    render(<ScholarshipTab work="vergil.aeneid" language="la" selection={SELECTION} units={UNITS} />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    await user.click(screen.getByRole('button', { name: 'Where these results come from' }));
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler.mock.calls[0][0].detail).toEqual({ section: 'reader', anchor: 'scholarship-sources' });
    window.removeEventListener('tesserae:open-help', handler);
  });
});
