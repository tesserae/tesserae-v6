/**
 * Search One Text: one work, one question, Theme Search inside the work, and a strip
 * of where the passages fall.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { setView } from '../../collections/collectionsStore';
import AskAWorkPage, { mergeRecent, unitWord, unitForWork, UNRATED_NOTE, bookOf, namesIn, stripLayout } from './AskAWorkPage';
import { mockResponse } from '../../test/mockResponse';

const TEXTS = [
  { id: 'vergil.aeneid.tess', author: 'Vergil', title: 'Aeneid', work: 'Aeneid', is_part: false },
  { id: 'vergil.aeneid.part.1.tess', author: 'Vergil', title: 'Aeneid, Book 1', work: 'Aeneid', is_part: true, part_num: '1' },
  { id: 'vergil.aeneid.part.2.tess', author: 'Vergil', title: 'Aeneid, Book 2', work: 'Aeneid', is_part: true, part_num: '2' },
  { id: 'vergil.aeneid.part.3.tess', author: 'Vergil', title: 'Aeneid, Book 3', work: 'Aeneid', is_part: true, part_num: '3' },
  { id: 'vergil.georgics.tess', author: 'Vergil', title: 'Georgics', work: 'Georgics', is_part: false },
  { id: 'cicero.orator.tess', author: 'Cicero', title: 'Orator', work: 'Orator', is_part: false },
];
const COVERED = ['vergil.aeneid', 'vergil.georgics'];

const row = (n, ref, extra = {}) => ({
  id: `w${n}`, work: 'vergil.aeneid', language: 'la', ref_start: ref, ref_end: ref,
  score: 0.9 - n * 0.01, strong: false, gist: `Gist ${n}`, ...extra,
});
const RESULTS = [
  row(1, 'verg. aen. 2.40', { strong: true }),
  row(2, 'verg. aen. 1.10'),
  row(3, 'verg. aen. 3.50'),
];

let reply;
let mentionsReply;
let summaryReply;
let scholarshipReply;
let citingReply;
function callsTo(prefix) {
  return global.fetch.mock.calls.filter((c) => String(c[0]).startsWith(prefix));
}
function themeCalls() {
  return global.fetch.mock.calls.map((c) => String(c[0])).filter((u) => u.startsWith('/api/passages/theme-search'));
}

beforeEach(() => {
  window.history.replaceState({}, '', '/ask-a-work');
  window.localStorage.clear();
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  reply = { query: 'q', results: RESULTS, restricted: true, confidence: { level: 'restricted' }, note: 'Confidence is not rated.' };
  mentionsReply = (u) => ({ work: 'vergil.aeneid', names: ['Sejanus'], total: 0, results: [], books_searched: [1, 2, 3], u });
  summaryReply = { available: false };
  scholarshipReply = { available: false };
  citingReply = { available: false, results: [] };
  global.fetch = vi.fn((url) => {
    const u = String(url);
    const body = u.startsWith('/api/texts') ? TEXTS
      : u.startsWith('/api/passages/mentions') ? mentionsReply(u)
      : u.startsWith('/api/passages/ask-summary') ? summaryReply
      : u.startsWith('/api/passages/ask-scholarship') ? scholarshipReply
      : u.startsWith('/api/passages/ask-citing') ? citingReply
      : u.startsWith('/api/passages/works') ? { works: COVERED }
      : u.startsWith('/api/passages/theme-search') ? reply
      : u.startsWith('/api/passages/lines') ? { lines: [{ ref: 'a', text: 'Arma virumque cano' }] }
      : {};
    return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(body) }));
  });
});

async function pick(name, label) {
  fireEvent.click(await screen.findByRole('combobox', { name }));
  fireEvent.pointerDown(within(screen.getByRole('listbox', { name })).getByRole('option', { name: label }));
}

async function ask(text = 'fathers and sons') {
  await pick('Author', 'Vergil');
  await pick('Work', 'Aeneid');
  fireEvent.change(screen.getByPlaceholderText(/a subject in plain words/), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: 'Go' }));
  await screen.findAllByTestId('ask-card');
}

describe('reading a reference', () => {
  it('takes the book from the first number of the locus', () => {
    expect(bookOf('verg. aen. 6.268')).toBe(6);
    expect(bookOf('thuc. pele. 2.1.1')).toBe(2);
    expect(bookOf('vergil.aeneid.6.268', 'vergil.aeneid')).toBe(6);
    expect(bookOf('shenoute.a22.1', 'shenoute.a22')).toBeNull();
  });
  it('spreads marks within a book in line order and keeps the books equal in width', () => {
    const l = stripLayout([{ ref_start: 'x 1.30' }, { ref_start: 'x 1.10' }, { ref_start: 'x 2.5' }], 'x', [1, 2, 3]);
    expect(l.books).toEqual([1, 2, 3]);
    const byIndex = Object.fromEntries(l.marks.map((m) => [m.i, m.left]));
    expect(byIndex[1]).toBeLessThan(byIndex[0]);
    expect(byIndex[0]).toBeLessThan(1 / 3);
    expect(byIndex[2]).toBeGreaterThan(1 / 3);
  });
});

describe('Search One Text', () => {
  it('renders the controls', async () => {
    render(<AskAWorkPage />);
    expect(screen.getByRole('heading', { name: 'Search One Text' })).toBeInTheDocument();
    expect(screen.getByText('Pick a work and ask what it says about a subject.')).toBeInTheDocument();
    expect(screen.getByLabelText('Language')).toBeInTheDocument();
    expect(await screen.findByRole('combobox', { name: 'Author' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Work' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('a subject in plain words, such as fate and the plan of the gods')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Go' })).toBeDisabled();
  });

  it('offers only the works the index holds, with no all-works choice', async () => {
    render(<AskAWorkPage />);
    await pick('Author', 'Vergil');
    fireEvent.click(screen.getByRole('combobox', { name: 'Work' }));
    const names = within(screen.getByRole('listbox', { name: 'Work' })).getAllByRole('option').map((o) => o.textContent);
    expect(names).toEqual(['Aeneid', 'Georgics']);
  });

  it('calls the route with the work and a limit of 25', async () => {
    render(<AskAWorkPage />);
    await ask();
    const u = themeCalls()[0];
    expect(u).toContain('works=vergil.aeneid');
    expect(u).toContain('limit=25');
    expect(u).toContain('q=fathers%20and%20sons');
  });

  it('lists cards in the route order with the strong mark and Reader links', async () => {
    render(<AskAWorkPage />);
    await ask();
    const cards = screen.getAllByTestId('ask-card');
    expect(cards.map((c) => within(c).getAllByRole('link')[0].textContent))
      .toEqual(['2.40', '1.10', '3.50']);
    // The file's tag is the hover text, not the printed text.
    expect(within(cards[0]).getByText('2.40').getAttribute('title')).toBe('verg. aen. 2.40');
    expect(within(cards[0]).getByText('strong')).toBeInTheDocument();
    expect(within(cards[1]).queryByText('strong')).toBeNull();
    const href = within(cards[0]).getAllByRole('link')[0].getAttribute('href');
    expect(href).toContain('/read?');
    expect(href).toContain('work=vergil.aeneid.tess');
    expect(await within(cards[0]).findByText('Arma virumque cano')).toBeInTheDocument();
  });

  it('draws one mark per result, and a tap scrolls to the card', async () => {
    render(<AskAWorkPage />);
    await ask();
    const marks = screen.getAllByTestId('ask-mark');
    expect(marks).toHaveLength(3);
    expect(screen.getByText('3 passages in 3 of 3 books')).toBeInTheDocument();
    const cards = screen.getAllByTestId('ask-card');
    // the strong result is in book 2 on the strip and first in the list
    fireEvent.click(screen.getByRole('button', { name: 'verg. aen. 2.40, strong' }));
    const seen = window.HTMLElement.prototype.scrollIntoView.mock.instances;
    expect(seen[seen.length - 1]).toBe(cards[0]);
  });

  it('says so when nothing in the work resembles the subject', async () => {
    reply = { query: 'q', results: [], restricted: true, confidence: { level: 'restricted' }, note: 'x' };
    render(<AskAWorkPage />);
    await pick('Author', 'Vergil');
    await pick('Work', 'Aeneid');
    fireEvent.change(screen.getByPlaceholderText(/a subject in plain words/), { target: { value: 'airplanes' } });
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(await screen.findByText('Nothing in this work resembles that subject.')).toBeInTheDocument();
    expect(screen.queryByTestId('ask-card')).toBeNull();
  });

  it('holds the passages back behind a button when the level is low', async () => {
    reply = { query: 'q', results: RESULTS, confidence: { level: 'low' }, note: '' };
    render(<AskAWorkPage />);
    await pick('Author', 'Vergil');
    await pick('Work', 'Aeneid');
    fireEvent.change(screen.getByPlaceholderText(/a subject in plain words/), { target: { value: 'airplanes' } });
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(await screen.findByText('Nothing in this work resembles that subject.')).toBeInTheDocument();
    expect(screen.queryByTestId('ask-card')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Show the closest passages anyway' }));
    expect(screen.getAllByTestId('ask-card')).toHaveLength(3);
  });

  it.each([
    ['moderate', 'Moderate match.'],
    ['strong', 'Strong match.'],
  ])('shows the %s banner with the route note when a band was fitted', async (level, label) => {
    reply = { query: 'q', results: RESULTS, restricted: true, note: 'Band note.',
      confidence: { level, fitted: 'within-work 2026-10-11', work_head_lift: 0.03, work_coherence: 0.91 } };
    render(<AskAWorkPage />);
    await ask();
    const band = screen.getByTestId('ask-band');
    expect(band).toHaveTextContent(label);
    expect(band).toHaveTextContent('Band note.');
    expect(screen.queryByTestId('ask-unrated')).toBeNull();
    expect(screen.queryByText(/Confidence is not rated/)).toBeNull();
  });

  it('shows the passages under a Closest passages banner for a fitted low band', async () => {
    // The lowest level is a caution about the order, with the list shown and
    // the route's own sentence under the label (refit 2026-10-12).
    reply = { query: 'q', results: RESULTS, restricted: true, note: 'Band note.',
      confidence: { level: 'low', fitted: 'within-work 2026-10-11' } };
    render(<AskAWorkPage />);
    await pick('Author', 'Vergil');
    await pick('Work', 'Aeneid');
    fireEvent.change(screen.getByPlaceholderText(/a subject in plain words/), { target: { value: 'airplanes' } });
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    const band = await screen.findByTestId('ask-band');
    expect(band).toHaveTextContent('Closest passages.');
    expect(band).toHaveTextContent('Band note.');
    expect(screen.queryByText('Nothing in this work resembles that subject.')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Show the closest passages anyway' })).toBeNull();
    expect(screen.getAllByTestId('ask-card').length).toBe(RESULTS.length);
  });
  it('says the search is not rated when the route reports no band', async () => {
    render(<AskAWorkPage />);
    await ask();
    expect(screen.getByTestId('ask-unrated')).toHaveTextContent(UNRATED_NOTE);
    expect(screen.queryByTestId('ask-band')).toBeNull();
  });

  it('says the list is ranked by closeness, and names the source when it is the text', async () => {
    mentionsReply = () => ({
      work: 'vergil.aeneid', names: ['Sejanus'], total: 2, ranked_by: 'closeness', source: 'text',
      results: [named(0, 'verg. aen. 1.20'), named(1, 'verg. aen. 1.30')], books_searched: [1, 2, 3],
    });
    render(<AskAWorkPage />);
    await ask('the rise of Sejanus');
    const section = await screen.findByTestId('ask-names');
    expect(within(section).getByText(/2 passages whose text names Sejanus, the closest to your question first/)).toBeInTheDocument();
  });

  it('pages by offset with Show more', async () => {
    reply = { query: 'q', results: Array.from({ length: 25 }, (_, n) => row(n, `verg. aen. 1.${n + 1}`)), restricted: true, confidence: { level: 'restricted' } };
    render(<AskAWorkPage />);
    await ask();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(themeCalls()).toHaveLength(2));
    expect(themeCalls()[1]).toContain('offset=25');
  });

  it('fills the controls from the address and runs the search', async () => {
    window.history.replaceState({}, '', '/ask-a-work?work=vergil.aeneid&lang=la&q=fathers%20and%20sons');
    render(<AskAWorkPage />);
    await screen.findAllByTestId('ask-card');
    expect(themeCalls()[0]).toContain('works=vergil.aeneid');
    expect(screen.getByPlaceholderText(/a subject in plain words/).value).toBe('fathers and sons');
    expect(await screen.findByRole('combobox', { name: 'Work' })).toHaveValue('Aeneid');
    expect(window.location.search).toContain('work=vergil.aeneid');
  });

  it('shows an example only for a work the index holds, and the example runs', async () => {
    render(<AskAWorkPage />);
    const ex = await screen.findByRole('button', { name: /Dido falls in love with Aeneas/ });
    expect(screen.queryByRole('button', { name: /the Pannonian legions mutiny/ })).toBeNull();
    fireEvent.click(ex);
    await screen.findAllByTestId('ask-card');
    expect(themeCalls()[0]).toContain('works=vergil.aeneid');
  });
});

const named = (n, ref, extra = {}) => ({
  id: `m${n}`, work: 'vergil.aeneid', language: 'la', ref_start: ref, ref_end: ref,
  gist: `Names ${n}`, matched: ['Sejanus'], mentions: 2, ...extra,
});

describe('the order of the list', () => {
  it('is by closeness by default and by the work on request, the strip unchanged', async () => {
    render(<AskAWorkPage />);
    await pick('Author', 'Vergil');
    await pick('Work', 'Aeneid');
    fireEvent.change(screen.getByPlaceholderText(/a subject in plain words/), { target: { value: 'fathers and sons' } });
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    const before = (await screen.findAllByTestId('ask-card')).map((c) => c.querySelector('a').textContent);
    expect(before).toEqual(RESULTS.map((r) => r.ref_start.split(' ').pop()));
    fireEvent.click(screen.getByRole('button', { name: 'Order of the work' }));
    const after = screen.getAllByTestId('ask-card').map((c) => c.querySelector('a').textContent);
    const key = (ref) => [bookOf(ref, 'vergil.aeneid'), Number((ref.match(/(\d+)\s*$/) || [0, 0])[1])];
    const sorted = [...before].sort((a, b) => (key(a)[0] - key(b)[0]) || (key(a)[1] - key(b)[1]));
    expect(after).toEqual(sorted);
    expect(screen.getAllByTestId('ask-mark').length).toBe(RESULTS.length);
  });
});

describe('the strip explains its shades', () => {
  it('names the shades under the strip and titles each bar', async () => {
    render(<AskAWorkPage />);
    await pick('Author', 'Vergil');
    await pick('Work', 'Aeneid');
    fireEvent.change(screen.getByPlaceholderText(/a subject in plain words/), { target: { value: 'fathers and sons' } });
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    await screen.findAllByTestId('ask-card');
    expect(screen.getByTestId('ask-strip-legend').textContent).toMatch(/Hover a bar/);
    const marks = screen.getAllByTestId('ask-mark');
    expect(marks[0].getAttribute('title')).toMatch(/^verg\. aen\./);
  });
});

describe('the unit of the strip', () => {
  it('reads fragments, poems, letters or books from the references', () => {
    expect(unitWord([{ ref_start: 'sappho. frag. 31.1' }])).toBe('fragments');
    expect(unitWord([{ ref_start: 'catu. carm. 61.93' }])).toBe('poems');
    expect(unitWord([{ ref_start: 'plin. ep. 6.16' }])).toBe('letters');
    expect(unitWord([{ ref_start: 'verg. aen. 1.1' }])).toBe('books');
    expect(unitWord([])).toBe('books');
    expect(unitForWork('sappho.fragments')).toBe('fragments');
    expect(unitForWork('catullus.carmina')).toBe('poems');
    expect(unitForWork('tacitus.annales')).toBe('books');
  });
});

describe('names in a question', () => {
  it('keeps capitalised words after the first, drops stop words and possessives, at most four', () => {
    expect(namesIn('the rise of Sejanus')).toEqual(['Sejanus']);
    expect(namesIn('What did Tiberius think of Sejanus\u2019s power?')).toEqual(['Tiberius', 'Sejanus']);
    expect(namesIn('Sejanus and the fathers')).toEqual([]);
    expect(namesIn('fathers and sons')).toEqual([]);
    expect(namesIn('why A B Cato Livia Nero Drusus Piso')).toEqual(['B', 'Cato', 'Livia', 'Nero']);
  });
});

describe('books of a work', () => {
  it('shows the book selects for a work with books and sends the range', async () => {
    render(<AskAWorkPage />);
    await pick('Author', 'Vergil');
    await pick('Work', 'Aeneid');
    const from = screen.getByLabelText('From book');
    const to = screen.getByLabelText('To book');
    expect(from.value).toBe('1');
    expect(to.value).toBe('3');
    fireEvent.change(from, { target: { value: '2' } });
    fireEvent.change(screen.getByPlaceholderText(/a subject in plain words/), { target: { value: 'fathers and sons' } });
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    await screen.findAllByTestId('ask-card');
    expect(themeCalls()[0]).toContain('books=2-3');
    expect(screen.getByTestId('ask-heading').textContent).toContain('Vergil, Aeneid, books 2 to 3');
    expect(window.location.search).toContain('books=2-3');
  });

  it('sends no books for the whole work, and no selects for a work without books', async () => {
    render(<AskAWorkPage />);
    await ask();
    expect(themeCalls()[0]).not.toContain('books=');
    expect(screen.getByTestId('ask-heading').textContent).not.toContain('books');
    cleanup();
    render(<AskAWorkPage />);
    await pick('Author', 'Vergil');
    await pick('Work', 'Georgics');
    expect(screen.queryByLabelText('From book')).toBeNull();
  });

  it('reads books from the address and draws only the books searched', async () => {
    reply = { ...reply, results: [row(1, 'verg. aen. 2.40'), row(2, 'verg. aen. 3.50')], books_searched: [2, 3] };
    window.history.replaceState({}, '', '/ask-a-work?work=vergil.aeneid&lang=la&q=fathers%20and%20sons&books=2-3');
    render(<AskAWorkPage />);
    await screen.findAllByTestId('ask-card');
    expect(themeCalls()[0]).toContain('books=2-3');
    expect(screen.getByText('2 passages in 2 of 2 books')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText('From book').value).toBe('2'));
  });
});

describe('passages that name a person', () => {
  it('asks for them, shows ten, adds grey marks and reveals the rest with Show all', async () => {
    const all = Array.from({ length: 12 }, (_, n) => named(n, `verg. aen. 1.${n + 20}`));
    mentionsReply = (u) => (u.includes('offset=0')
      ? { work: 'vergil.aeneid', names: ['Sejanus'], total: 12, results: all.slice(0, 10).concat(all.slice(10, 12)).slice(0, 12), books_searched: [1, 2, 3] }
      : { work: 'vergil.aeneid', names: ['Sejanus'], total: 12, results: [] });
    render(<AskAWorkPage />);
    await ask('the rise of Sejanus');
    const section = await screen.findByTestId('ask-names');
    expect(callsTo('/api/passages/mentions')[0][0]).toContain('names=Sejanus');
    expect(callsTo('/api/passages/mentions')[0][0]).toContain('work=vergil.aeneid');
    expect(within(section).getByText('Passages that name Sejanus')).toBeInTheDocument();
    expect(within(section).getByText(/12 passages whose description names Sejanus, in the order of the work/)).toBeInTheDocument();
    expect(callsTo('/api/passages/mentions')[0][0]).toContain('q=the+rise+of+Sejanus');
    expect(within(section).getAllByTestId('ask-name-card')).toHaveLength(10);
    const grey = screen.getAllByTestId('ask-mark-name');
    expect(grey).toHaveLength(12);
    expect(grey[0].getAttribute('aria-label')).toMatch(/, names Sejanus$/);
    expect(grey[0].className).toContain('bg-gray-400');
    fireEvent.click(within(section).getByRole('button', { name: 'Show all 12' }));
    expect(within(section).getAllByTestId('ask-name-card')).toHaveLength(12);
  });

  it('pages by offset when the total is more than what was loaded', async () => {
    const page = (from, k) => Array.from({ length: k }, (_, n) => named(from + n, `verg. aen. 1.${from + n + 20}`));
    mentionsReply = (u) => ({
      work: 'vergil.aeneid', names: ['Sejanus'], total: 30,
      results: u.includes('offset=0') ? page(0, 25) : u.includes('offset=25') ? page(25, 5) : [],
    });
    render(<AskAWorkPage />);
    await ask('the rise of Sejanus');
    const section = await screen.findByTestId('ask-names');
    fireEvent.click(within(section).getByRole('button', { name: 'Show all 30' }));
    await waitFor(() => expect(within(section).getAllByTestId('ask-name-card')).toHaveLength(30));
    expect(callsTo('/api/passages/mentions').some((c) => String(c[0]).includes('offset=25'))).toBe(true);
  });

  it('says so quietly when nothing names the person', async () => {
    render(<AskAWorkPage />);
    await ask('the rise of Sejanus');
    expect(await screen.findByText('No passage description or text names Sejanus in this work.')).toBeInTheDocument();
  });

  it('makes no request when the question has no capitalised word', async () => {
    render(<AskAWorkPage />);
    await ask('fathers and sons');
    await screen.findByTestId('ask-strip');
    expect(callsTo('/api/passages/mentions')).toHaveLength(0);
    expect(screen.queryByTestId('ask-names')).toBeNull();
  });
});

describe('what the work says', () => {
  it('sends the first twelve passages and renders the summary with reference links', async () => {
    reply = { ...reply, results: Array.from({ length: 14 }, (_, n) => row(n + 1, `verg. aen. 1.${n + 10}`)) };
    summaryReply = { available: true, summary: 'Fathers are lost in verg. aen. 1.10 and mourned in verg. aen. 1.12.', cites: ['verg. aen. 1.10', 'verg. aen. 1.12'] };
    render(<AskAWorkPage />);
    await ask();
    const block = await screen.findByTestId('ask-summary');
    const [, init] = callsTo('/api/passages/ask-summary')[0];
    const body = JSON.parse(init.body);
    expect(body.question).toBe('fathers and sons');
    expect(body.work_label).toBe('Vergil, Aeneid');
    expect(body.passages).toHaveLength(12);
    expect(body.passages[0]).toEqual({ ref: 'verg. aen. 1.10', gist: 'Gist 1' });
    expect(within(block).getByText('Summary of the passages found')).toBeInTheDocument();
    expect(within(block).getByText(/Written by Tessa from the passage descriptions/)).toBeInTheDocument();
    const cards = screen.getAllByTestId('ask-card');
    fireEvent.click(within(block).getByRole('button', { name: 'verg. aen. 1.12' }));
    const seen = window.HTMLElement.prototype.scrollIntoView.mock.instances;
    expect(seen[seen.length - 1]).toBe(cards[2]);
  });

  it('shows the reading line while it runs', async () => {
    let release;
    const base = global.fetch;
    global.fetch = vi.fn((url, init) => (String(url).startsWith('/api/passages/ask-summary')
      ? new Promise((res) => { release = () => res(mockResponse({ ok: true, json: () => Promise.resolve({ available: false }) })); })
      : base(url, init)));
    render(<AskAWorkPage />);
    await ask();
    expect(await screen.findByText('Tessa is reading the passages.')).toBeInTheDocument();
    release();
    await waitFor(() => expect(screen.queryByText('Tessa is reading the passages.')).toBeNull());
  });

  it('renders nothing when the summary is unavailable', async () => {
    render(<AskAWorkPage />);
    await ask();
    await waitFor(() => expect(callsTo('/api/passages/ask-summary')).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText('Tessa is reading the passages.')).toBeNull());
    expect(screen.queryByTestId('ask-summary')).toBeNull();
  });
});

describe('what the secondary literature says', () => {
  it('keeps Greek in its own letters, adds a transliteration and a toggle', async () => {
    scholarshipReply = {
      available: true,
      holdings: 'The secondary sources I can read include 1 note from How and Wells.',
      summary: 'How and Wells take τὸ εὖ ζῆν (the good life) to join two ideas [1].',
      cites: [{ n: 1, kind: 'commentary', label: 'How and Wells', link: { kind: 'reader', url: '/read?x' } }],
    };
    render(<AskAWorkPage />);
    await ask();
    const block = await screen.findByTestId('ask-scholarship');
    expect(block).toHaveTextContent('τὸ εὖ ζῆν (to eu zēn) (the good life)');
    fireEvent.click(screen.getByTestId('transliteration-toggle'));
    expect(block).not.toHaveTextContent('to eu zēn');
    window.localStorage.clear();
  });

  it('renders the paragraph with note links in new tabs and the holdings line', async () => {
    scholarshipReply = {
      available: true,
      holdings: 'The secondary sources I can read include 2 notes from Servius on Vergil, Aeneid.',
      summary: 'These notes treat her passion as divine design [1] and as tragic [2].',
      cites: [
        { n: 1, kind: 'commentary', label: 'Servius on verg. aen. 4.1', link: { kind: 'reader', url: '/read?work=vergil.aeneid.tess&lang=la&ref=4.1' } },
        { n: 2, kind: 'article', label: 'Dido (1890)', link: { kind: 'jstor', url: 'https://www.jstor.org/stable/1' } },
      ],
    };
    render(<AskAWorkPage />);
    await ask();
    const block = await screen.findByTestId('ask-scholarship');
    const [, init] = callsTo('/api/passages/ask-scholarship')[0];
    expect(JSON.parse(init.body)).toEqual({ question: 'fathers and sons', work: 'vergil.aeneid', lang: 'la' });
    expect(within(screen.getByTestId('ask-scholarship-box')).getByText('Scholarship')).toBeInTheDocument();
    expect(within(block).getByText('Summary of the scholarship found')).toBeInTheDocument();
    expect(within(block).getByTestId('ask-scholarship-covers')).toHaveTextContent('does not cover the articles that cite these passages');
    expect(screen.getByTestId('ask-scholarship-more').getAttribute('href')).toMatch(/in=scholarship&work=vergil\.aeneid$/);
    const link = within(block).getByRole('link', { name: '[2]' });
    expect(link).toHaveAttribute('href', 'https://www.jstor.org/stable/1');
    expect(link).toHaveAttribute('target', '_blank');
    expect(within(block).getByTestId('ask-scholarship-holdings')).toHaveTextContent('2 notes from Servius');
  });

  it('puts the online articles above an empty Scholarship box', async () => {
    scholarshipReply = {
      available: true, none_relevant: true, summary: '', cites: [],
      holdings: 'The secondary sources I can read include 2 notes from Servius on Vergil, Aeneid.',
    };
    const base = global.fetch;
    global.fetch = vi.fn((url, init) => {
      const u = String(url);
      if (u.startsWith('/api/passages/recent-scholarship')) {
        return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({ service: new URL(u, 'http://x').searchParams.get('service') || 'openalex', available: true, results: [{ title: 'Dido in Love', year: 2019, authors: ['A. Reader'] }] }) }));
      }
      return base(url, init);
    });
    render(<AskAWorkPage />);
    await ask();
    const recentBox = await screen.findByTestId('ask-recent');
    const scholBox = await screen.findByTestId('ask-scholarship');
    expect(recentBox.compareDocumentPosition(scholBox) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(scholBox).getByTestId('ask-scholarship-none')).toBeInTheDocument();
  });

  it('says plainly that no held note or article discusses the question', async () => {
    scholarshipReply = {
      available: true, none_relevant: true, summary: '', cites: [],
      holdings: 'The secondary sources I can read include 2 notes from Servius on Vergil, Aeneid.',
    };
    render(<AskAWorkPage />);
    await ask();
    const block = await screen.findByTestId('ask-scholarship');
    expect(within(block).getByTestId('ask-scholarship-none')).toHaveTextContent(
      'None of the commentary notes or journal articles held for this work discuss this question.');
    expect(within(block).getByTestId('ask-scholarship-holdings')).toHaveTextContent('2 notes from Servius');
    expect(screen.getByTestId('ask-scholarship-more')).toBeInTheDocument();
  });

  it('shows only the holdings line when the collection has nothing', async () => {
    scholarshipReply = { available: false, holdings: 'I have no secondary sources on Sappho, Fragments to draw on.' };
    render(<AskAWorkPage />);
    await ask();
    expect(await screen.findByTestId('ask-scholarship-holdings')).toHaveTextContent('I have no secondary sources on Sappho');
    expect(screen.queryByTestId('ask-scholarship')).toBeNull();
  });

  it('shows nothing when the request fails, and the summary is unaffected', async () => {
    summaryReply = { available: true, summary: 'A summary.', cites: [] };
    const base = global.fetch;
    global.fetch = vi.fn((url, init) => (String(url).startsWith('/api/passages/ask-scholarship')
      ? Promise.reject(new Error('down')) : base(url, init)));
    render(<AskAWorkPage />);
    await ask();
    expect(await screen.findByTestId('ask-summary')).toBeInTheDocument();
    expect(screen.queryByTestId('ask-scholarship')).toBeNull();
    expect(screen.queryByTestId('ask-scholarship-holdings')).toBeNull();
  });
});

describe('recent articles from the live services', () => {
  const item = (title, extra = {}) => ({
    title, authors: ['A. Scholar'], year: 2015, venue: 'Classical Quarterly', doi: null, url: 'https://example.org/p',
    oa_url: null, excerpt: 'Dido yields to desire.', score: 1, ...extra,
  });

  it('merges by DOI then title and orders by score then year', () => {
    const a = [item('Alpha', { doi: '10.1/a', score: 1, year: 2001 })];
    const out = mergeRecent(a, [item('alpha again', { doi: '10.1/A' }), item('Beta', { score: 2, year: 1999 }), item('Beta')]);
    expect(out.map((x) => x.title)).toEqual(['Beta', 'Alpha']);
  });

  it('paints items as each service answers, then posts the paragraph after the requests settle', async () => {
    let releaseCrossref;
    const gate = new Promise((r) => { releaseCrossref = r; });
    const base = global.fetch;
    const order = [];
    global.fetch = vi.fn((url, init) => {
      const u = String(url);
      if (u.startsWith('/api/passages/recent-scholarship')) {
        const svc = new URL(u, 'http://x').searchParams.get('service');
        order.push(`get:${svc}`);
        const reply = (body) => Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(body) }));
        if (svc === 'openalex') return reply({ service: svc, available: true, results: [item('Dido in Love', { oa_url: 'https://free.example/d.pdf' })] });
        if (svc === 'crossref') return gate.then(() => reply({ service: svc, available: true, results: [item('Politics of Passion', { doi: '10.1/pp', year: 2020 })] }));
        if (svc === 's2') return reply({ service: svc, available: false, results: [], reason: 'off' });
        return reply({ service: svc, available: true, results: [] });
      }
      if (u.startsWith('/api/passages/ask-scholarship')) {
        order.push('post');
        return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({ available: false, holdings: 'Holdings line.' }) }));
      }
      return base(url, init);
    });
    render(<AskAWorkPage />);
    await ask();
    const first = await screen.findByTestId('ask-recent');
    expect(within(first).getAllByTestId('ask-recent-item')).toHaveLength(1);
    expect(within(first).getByRole('link', { name: 'Dido in Love' })).toHaveAttribute('href', 'https://free.example/d.pdf');
    expect(within(first).getByText('free copy')).toBeInTheDocument();
    expect(screen.getByTestId('ask-recent-pending')).toHaveTextContent('Asking Crossref for articles...');
    expect(order).not.toContain('post');
    releaseCrossref();
    await waitFor(() => expect(screen.getAllByTestId('ask-recent-item')).toHaveLength(2));
    await waitFor(() => expect(screen.queryByTestId('ask-recent-pending')).toBeNull());
    const second = screen.getAllByTestId('ask-recent-item')[1];
    expect(within(second).getByRole('link', { name: 'Dido in Love' })).toBeInTheDocument();
    expect(within(screen.getAllByTestId('ask-recent-item')[0]).getByRole('link', { name: 'Politics of Passion' }))
      .toHaveAttribute('href', 'https://doi.org/10.1/pp');
    await screen.findByTestId('ask-scholarship-holdings');
    expect(order.filter((x) => x.startsWith('get:'))).toHaveLength(5);
    expect(order.indexOf('post')).toBeGreaterThan(order.lastIndexOf(order.find((x) => x.startsWith('get:'))));
    expect(order[order.length - 1]).toBe('post');
  });

  it('stands beside the passages with the summary and the scholarship paragraph, after them in the page', async () => {
    const base = global.fetch;
    global.fetch = vi.fn((url, init) => {
      const u = String(url);
      if (u.startsWith('/api/passages/recent-scholarship')) {
        const svc = new URL(u, 'http://x').searchParams.get('service');
        const results = svc === 'openalex' ? [item('Dido in Love', { year: 1955 })] : [];
        return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({ service: svc, available: true, results }) }));
      }
      if (u.startsWith('/api/passages/ask-scholarship')) {
        return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({ available: false, holdings: 'Holdings line.' }) }));
      }
      return base(url, init);
    });
    render(<AskAWorkPage />);
    await ask();
    const side = await screen.findByTestId('ask-side');
    await screen.findByTestId('ask-scholarship-holdings');
    expect(within(side).getByTestId('ask-recent')).toBeInTheDocument();
    expect(within(side).getByText('Found online for this question')).toBeInTheDocument();
    // Both lists sit inside the one Scholarship box (2026-10-16).
    const box = within(side).getByTestId('ask-scholarship-box');
    expect(within(box).getByTestId('ask-recent')).toBeInTheDocument();
    expect(within(box).getByTestId('ask-scholarship-holdings')).toBeInTheDocument();
    expect(within(side).queryByText('Recent articles')).toBeNull();
    expect(within(side).getByTestId('ask-scholarship-holdings')).toBeInTheDocument();
    const columns = screen.getByTestId('ask-columns');
    const strip = screen.getByTestId('ask-strip');
    expect(columns).toContainElement(strip);
    expect(columns).toContainElement(side);
    // The passages and their strip come before the side column in the page's order.
    expect(strip.compareDocumentPosition(side) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('leaves the section out when every service answered with nothing', async () => {
    render(<AskAWorkPage />);
    await ask();
    await screen.findAllByTestId('ask-card');
    await waitFor(() => expect(callsTo('/api/passages/ask-scholarship')).toHaveLength(1));
    expect(screen.queryByTestId('ask-recent')).toBeNull();
    expect(screen.queryByTestId('ask-recent-pending')).toBeNull();
  });
});

describe('words no passage description contains', () => {
  it('names the unknown words in one line when the note is not shown', async () => {
    reply = { ...reply, confidence: { level: 'restricted', vocab_checked: true, unknown_words: ['potatoes'], no_known_words: false } };
    render(<AskAWorkPage />);
    await ask();
    expect(await screen.findByTestId('ask-unknown-words')).toHaveTextContent(
      'The word potatoes appears in no passage description, so it did not help the search.');
    expect(screen.getAllByTestId('ask-card').length).toBeGreaterThan(0);
  });

  it('holds the list when no word of the question is known', async () => {
    reply = { ...reply, confidence: { level: 'restricted', vocab_checked: true, unknown_words: ['xqzv', 'plorf'], no_known_words: true },
      note: 'None of these words appears in any passage description: xqzv, plorf. There is nothing for Theme Search to match.' };
    render(<AskAWorkPage />);
    await pick('Author', 'Vergil');
    await pick('Work', 'Aeneid');
    fireEvent.change(screen.getByPlaceholderText(/a subject in plain words/), { target: { value: 'xqzv plorf' } });
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(await screen.findByTestId('ask-nothing')).toHaveTextContent('None of these words appears');
    expect(screen.queryAllByTestId('ask-card')).toHaveLength(0);
  });
});

describe('a visit with no work chosen', () => {
  it('opens on the Aeneid, with its example subjects', async () => {
    render(<AskAWorkPage />);
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Author' })).toHaveValue('Vergil'));
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Work' })).toHaveValue('Aeneid'));
    expect(await screen.findByRole('button', { name: /Dido falls in love with Aeneas/ })).toBeInTheDocument();
    // The holdings mock covers the Aeneid and the Georgics only, so the
    // chips for other works are hidden here; one Aeneid chip is the rule.
    expect(screen.getAllByRole('button', { name: /in the Aeneid/ })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: /the fall of Troy/ })).toBeNull();
  });
});


describe('switching the view while on the page', () => {
  it('follows the new view when no subject has been typed', async () => {
    const texts = TEXTS.concat([
      { id: 'tacitus.annales.tess', author: 'Tacitus', title: 'Annals', work: 'Annals', is_part: false },
    ]);
    const covered = COVERED.concat(['tacitus.annales']);
    const inner = global.fetch;
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/texts')) return Promise.resolve(mockResponse({ ok: true, json: async () => texts }));
      if (u.startsWith('/api/passages/works')) return Promise.resolve(mockResponse({ ok: true, json: async () => ({ works: covered }) }));
      return inner(url);
    });
    render(<AskAWorkPage />);
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Work' })).toHaveValue('Aeneid'));
    act(() => { setView('history'); });
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Author' })).toHaveValue('Tacitus'));
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Work' })).toHaveValue('Annals'));
    act(() => { setView('literature'); });
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Work' })).toHaveValue('Aeneid'));
  });
});

describe('the History view', () => {
  it('opens on the Annals, with the history example subjects', async () => {
    window.localStorage.setItem('tesserae_view', 'history');
    const texts = TEXTS.concat([
      { id: 'tacitus.annales.tess', author: 'Tacitus', title: 'Annals', work: 'Annals', is_part: false },
      { id: 'livy.ab_urbe_condita.tess', author: 'Livy', title: 'Ab Urbe Condita', work: 'Ab Urbe Condita', is_part: false },
    ]);
    const covered = COVERED.concat(['tacitus.annales', 'livy.ab_urbe_condita']);
    const inner = global.fetch;
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/texts')) return Promise.resolve(mockResponse({ ok: true, json: async () => texts }));
      if (u.startsWith('/api/passages/works')) return Promise.resolve(mockResponse({ ok: true, json: async () => ({ works: covered }) }));
      return inner(url);
    });
    render(<AskAWorkPage />);
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Author' })).toHaveValue('Tacitus'));
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Work' })).toHaveValue('Annals'));
    expect(await screen.findByRole('button', { name: /Lucretia and Sextus Tarquinius/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /the Pannonian legions mutiny/ })).toBeInTheDocument();
    // The Literature examples are not shown, even for a work the index holds.
    expect(screen.queryByRole('button', { name: /Dido falls in love with Aeneas/ })).toBeNull();
  });
});

describe('articles that cite the passages found', () => {
  const ITEMS = [
    { title: 'Arms and the Poem', authors: ['C. Scholar'], year: 2001, journal: 'American Journal of Philology', url: 'https://doi.org/10.1353/x.1', source: 'muse', cites: ['verg. aen. 2.40', 'verg. aen. 1.10'], sentences: [] },
    { title: 'On the Proem', authors: [], year: 1910, journal: 'Classical Philology', url: 'https://www.jstor.org/stable/1', source: 'ejc', cites: ['verg. aen. 3.50'], sentences: [{ ref: 'verg. aen. 3.50', text: 'Invented early sentence.' }] },
  ];

  it('asks for the page\'s passages and lists the articles with badges and jump links', async () => {
    citingReply = { available: true, results: ITEMS, total: 2, note: '' };
    render(<AskAWorkPage />);
    await ask();
    const box = await screen.findByTestId('ask-citing');
    expect(within(box).getByText('Articles that cite these passages')).toBeInTheDocument();
    expect(box).toHaveTextContent('From the journal citation indexes (journals of 1827 to 1922, and Project MUSE journals from 1996 on): articles whose pages cite one of the passages above.');
    const items = within(box).getAllByTestId('ask-citing-item');
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByRole('link', { name: 'Arms and the Poem' })).toHaveAttribute('href', 'https://doi.org/10.1353/x.1');
    expect(items[0]).toHaveTextContent('C. Scholar, American Journal of Philology, 2001');
    expect(items[0]).toHaveTextContent('MUSE');
    expect(items[1]).toHaveTextContent('1827 to 1922');
    expect(items[0]).toHaveTextContent('cites 2.40, 1.10');
    const call = callsTo('/api/passages/ask-citing')[0];
    expect(JSON.parse(call[1].body)).toEqual({
      work: 'vergil.aeneid',
      refs: RESULTS.map((r) => ({ ref_start: r.ref_start, ref_end: r.ref_end })),
    });
    fireEvent.click(within(items[0]).getByRole('button', { name: '1.10' }));
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('sits inside the Scholarship box, before the list found online', async () => {
    citingReply = { available: true, results: ITEMS, total: 2, note: '' };
    const base = global.fetch;
    global.fetch = vi.fn((url, init) => {
      const u = String(url);
      if (u.startsWith('/api/passages/recent-scholarship')) {
        return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({ service: 'openalex', available: true, results: [{ title: 'Dido in Love', year: 2019, authors: ['A. Reader'] }] }) }));
      }
      return base(url, init);
    });
    render(<AskAWorkPage />);
    await ask();
    const citing = await screen.findByTestId('ask-citing');
    const recentBox = await screen.findByTestId('ask-recent');
    expect(within(screen.getByTestId('ask-scholarship-box')).getByTestId('ask-citing')).toBe(citing);
    expect(citing.compareDocumentPosition(recentBox) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('shows eight and a Show all toggle for a longer list', async () => {
    citingReply = {
      available: true, total: 11,
      results: Array.from({ length: 11 }, (_, i) => ({ title: `Article ${i + 1}`, authors: [], year: 2000 - i, journal: 'J', url: `https://doi.org/10.1/${i}`, source: 'muse', cites: ['verg. aen. 1.10'], sentences: [] })),
    };
    render(<AskAWorkPage />);
    await ask();
    expect(await screen.findAllByTestId('ask-citing-item')).toHaveLength(8);
    fireEvent.click(screen.getByTestId('ask-citing-toggle'));
    expect(screen.getAllByTestId('ask-citing-item')).toHaveLength(11);
  });

  it('says plainly when no article cites the passages', async () => {
    citingReply = { available: true, results: [], total: 0, note: '' };
    render(<AskAWorkPage />);
    await ask();
    expect(await screen.findByTestId('ask-citing-none')).toHaveTextContent('No article in the citation indexes cites these passages.');
  });

  it('shows nothing when the indexes are unavailable', async () => {
    render(<AskAWorkPage />);
    await ask();
    await waitFor(() => expect(callsTo('/api/passages/ask-citing')).toHaveLength(1));
    expect(screen.queryByTestId('ask-citing')).toBeNull();
  });

  it('puts the articles in the export, with title, journal and link only', async () => {
    citingReply = { available: true, results: ITEMS, total: 2, note: '' };
    const blobs = [];
    URL.createObjectURL = vi.fn((b) => { blobs.push(b); return 'blob:x'; });
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    render(<AskAWorkPage />);
    await ask();
    const box = await screen.findByTestId('ask-citing');
    fireEvent.click(within(within(box).getByTestId('cite-all')).getByRole('button', { name: 'RIS' }));
    await waitFor(() => expect(blobs).toHaveLength(1));
    const text = await new Promise((res) => { const f = new FileReader(); f.onload = () => res(f.result); f.readAsText(blobs[0]); });
    expect(text).toContain('Arms and the Poem');
    expect(text).toContain('On the Proem');
    expect(text).not.toContain('Invented early sentence.');
    vi.restoreAllMocks();
  });
});

// An author with one work has it chosen at once (owner, 2026-10-16: "It's
// silly to have to pick one"); an author with several leaves the choice open.
describe('one work is chosen by itself', () => {
  it('picks Orator when Cicero is chosen', async () => {
    // Cicero's one work must be in the covered list to be offered at all.
    const covered = COVERED.concat(['cicero.orator']);
    const inner = global.fetch;
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/passages/works')) return Promise.resolve(mockResponse({ ok: true, json: async () => ({ works: covered }) }));
      return inner(url);
    });
    render(<AskAWorkPage />);
    await pick('Author', 'Cicero');
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Work' })).toHaveValue('Orator'));
  });
  it('leaves the work open for an author with several', async () => {
    render(<AskAWorkPage />);
    await pick('Author', 'Vergil');
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Author' })).toHaveValue('Vergil'));
    expect(screen.getByRole('combobox', { name: 'Work' })).not.toHaveValue('Aeneid');
    expect(screen.getByRole('combobox', { name: 'Work' })).not.toHaveValue('Georgics');
  });
});
