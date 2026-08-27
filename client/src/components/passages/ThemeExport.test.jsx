/**
 * Exporting a Theme Search.
 *
 * NC: "We need some sort of export function for theme search. The export should
 * include the original passages, properly labeled, in chronological order."
 *
 * The thing most worth pinning down is that the passage TEXT reaches the
 * document, since the whole point is that a Theme Search result otherwise
 * carries only a pointer and a machine-written summary.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ThemeExport from './ThemeExport';

const PAYLOAD = {
  query: 'warrior arming for battle',
  count: 2,
  missing_text: 0,
  confidence: { level: 'high' },
  results: [
    { n: 1, author: 'Homer', work: 'Iliad', locus: '11.15-11.46',
      date: 'c. 750 BCE', era: 'Archaic', language: 'Greek', strong: 'yes',
      themes: 'war; armour', gist: 'Agamemnon arms himself.',
      text: 'κνημῖδας μὲν πρῶτα περὶ κνήμῃσιν ἔθηκε' },
    { n: 2, author: 'Ferdowsi', work: 'Shahnameh', locus: '27931-27942',
      date: 'd. c. 1020 CE', era: 'Ghaznavid', language: 'Persian',
      strong: 'no', themes: 'war', gist: 'A warrior prepares.',
      text: 'نه برگیرد از جای گرزش نهنگ' },
  ],
};

let written;
let opened;

beforeEach(() => {
  written = '';
  opened = true;
  global.fetch = vi.fn(() =>
    Promise.resolve({ json: () => Promise.resolve(PAYLOAD) }));
  vi.stubGlobal('open', vi.fn(() => (opened ? {
    document: { write: (s) => { written += s; }, close: () => {} },
    close: () => {},
  } : null)));
});

afterEach(() => { vi.unstubAllGlobals(); });

describe('the export offers itself only when there is something to export', () => {
  it('shows nothing with no results', () => {
    const { container } = render(<ThemeExport query="x" language="" count={0} />);
    expect(container.textContent).toBe('');
  });

  it('shows nothing with no query', () => {
    const { container } = render(<ThemeExport query="" language="" count={5} />);
    expect(container.textContent).toBe('');
  });

  it('offers both a printable document and a manipulable file', () => {
    render(<ThemeExport query="arming" language="" count={3} />);
    expect(screen.getByText('Printable / PDF')).toBeTruthy();
    expect(screen.getByText('Download CSV')).toBeTruthy();
  });
});

describe('the CSV link carries the search', () => {
  it('asks for csv, the query, and the language filter', () => {
    render(<ThemeExport query="warrior arming" language="grc" count={3} />);
    const href = screen.getByText('Download CSV').getAttribute('href');
    expect(href).toContain('/api/passages/export');
    expect(href).toContain('format=csv');
    expect(decodeURIComponent(href)).toContain('warrior arming');
    expect(href).toContain('languages=grc');
  });
});

describe('the printable document', () => {
  it('contains the source passages, not only the summaries', async () => {
    render(<ThemeExport query="warrior arming" language="" count={2} />);
    fireEvent.click(screen.getByText('Printable / PDF'));
    await waitFor(() => expect(written).toContain('κνημῖδας'));
    // The Persian passage matters most: it is the case that has no other
    // served route to its own text.
    expect(written).toContain('نه برگیرد');
  });

  it('labels each passage with author, work, locus and date', async () => {
    render(<ThemeExport query="x" language="" count={2} />);
    fireEvent.click(screen.getByText('Printable / PDF'));
    await waitFor(() => expect(written).toContain('Homer'));
    expect(written).toContain('Iliad');
    expect(written).toContain('11.15-11.46');
    expect(written).toContain('c. 750 BCE');
  });

  it('sets direction on right-to-left passages only', async () => {
    render(<ThemeExport query="x" language="" count={2} />);
    fireEvent.click(screen.getByText('Printable / PDF'));
    await waitFor(() => expect(written).toContain('نه برگیرد'));
    // Persian is RTL and Greek is not; a page that marks both, or neither,
    // renders one of them wrongly.
    const persian = written.slice(written.indexOf('Ferdowsi'));
    const greek = written.slice(written.indexOf('Homer'), written.indexOf('Ferdowsi'));
    expect(persian).toContain('dir="rtl"');
    expect(greek).not.toContain('dir="rtl"');
  });

  it('marks a weak match as weak', async () => {
    render(<ThemeExport query="x" language="" count={2} />);
    fireEvent.click(screen.getByText('Printable / PDF'));
    await waitFor(() => expect(written).toContain('weak match'));
  });

  it('says the summaries are machine-written', async () => {
    render(<ThemeExport query="x" language="" count={2} />);
    fireEvent.click(screen.getByText('Printable / PDF'));
    await waitFor(() => expect(written).toContain('machine-written'));
  });

  it('escapes markup in the passage rather than injecting it', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve({
      ...PAYLOAD,
      results: [{ ...PAYLOAD.results[0], text: '<script>alert(1)</script>' }],
    }) }));
    render(<ThemeExport query="x" language="" count={1} />);
    fireEvent.click(screen.getByText('Printable / PDF'));
    await waitFor(() => expect(written).toContain('&lt;script&gt;'));
    expect(written).not.toContain('<script>alert(1)</script>');
  });

  it('says so plainly when the pop-up is blocked', async () => {
    opened = false;
    render(<ThemeExport query="x" language="" count={2} />);
    fireEvent.click(screen.getByText('Printable / PDF'));
    expect(await screen.findByText(/blocked the new window/)).toBeTruthy();
  });
});
