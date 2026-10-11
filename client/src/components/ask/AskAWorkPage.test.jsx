/**
 * Ask a Work: one work, one question, Theme Search inside the work, and a strip
 * of where the passages fall.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import AskAWorkPage, { bookOf, stripLayout } from './AskAWorkPage';

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
function themeCalls() {
  return global.fetch.mock.calls.map((c) => String(c[0])).filter((u) => u.startsWith('/api/passages/theme-search'));
}

beforeEach(() => {
  window.history.replaceState({}, '', '/ask-a-work');
  window.localStorage.clear();
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  reply = { query: 'q', results: RESULTS, restricted: true, confidence: { level: 'restricted' }, note: 'Confidence is not rated.' };
  global.fetch = vi.fn((url) => {
    const u = String(url);
    const body = u.startsWith('/api/texts') ? TEXTS
      : u.startsWith('/api/passages/works') ? { works: COVERED }
      : u.startsWith('/api/passages/theme-search') ? reply
      : u.startsWith('/api/passages/lines') ? { lines: [{ ref: 'a', text: 'Arma virumque cano' }] }
      : {};
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
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

describe('Ask a Work', () => {
  it('renders the controls', async () => {
    render(<AskAWorkPage />);
    expect(screen.getByRole('heading', { name: 'Ask a Work' })).toBeInTheDocument();
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

  it('calls the route with the work and a limit of 50', async () => {
    render(<AskAWorkPage />);
    await ask();
    const u = themeCalls()[0];
    expect(u).toContain('works=vergil.aeneid');
    expect(u).toContain('limit=50');
    expect(u).toContain('q=fathers%20and%20sons');
  });

  it('lists cards in the route order with the strong mark and Reader links', async () => {
    render(<AskAWorkPage />);
    await ask();
    const cards = screen.getAllByTestId('ask-card');
    expect(cards.map((c) => within(c).getAllByRole('link')[0].textContent))
      .toEqual(['verg. aen. 2.40', 'verg. aen. 1.10', 'verg. aen. 3.50']);
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

  it('pages by offset with Show more', async () => {
    reply = { query: 'q', results: Array.from({ length: 50 }, (_, n) => row(n, `verg. aen. 1.${n + 1}`)), restricted: true, confidence: { level: 'restricted' } };
    render(<AskAWorkPage />);
    await ask();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(themeCalls()).toHaveLength(2));
    expect(themeCalls()[1]).toContain('offset=50');
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
    const ex = await screen.findByRole('button', { name: /fathers and sons/ });
    expect(screen.queryByRole('button', { name: /the rise of Sejanus/ })).toBeNull();
    fireEvent.click(ex);
    await screen.findAllByTestId('ask-card');
    expect(themeCalls()[0]).toContain('works=vergil.aeneid');
  });
});
