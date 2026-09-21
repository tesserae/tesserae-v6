/**
 * ReaderNav: previous/next book, go to line, back to top (NC, 2026-09-19).
 */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import ReaderNav, { ReaderEndNav, sectionsFor } from './ReaderNav';

afterEach(cleanup);

const sections = [
  { file: 'vergil.aeneid.part.1.tess', label: 'Book 1' },
  { file: 'vergil.aeneid.part.2.tess', label: 'Book 2' },
  { file: 'vergil.aeneid.part.3.tess', label: 'Book 3' },
];
const hierarchy = [{ author: 'Vergil', works: [{ work: 'Aeneid', work_key: 'aeneid', sections }] }];

describe('sectionsFor', () => {
  it('finds the books of the work that contains the open file', () => {
    expect(sectionsFor(hierarchy, 'vergil.aeneid.part.2.tess')).toBe(sections);
  });
  it('is empty for an unknown file or a missing hierarchy', () => {
    expect(sectionsFor(hierarchy, 'nope.tess')).toEqual([]);
    expect(sectionsFor(null, 'vergil.aeneid.part.2.tess')).toEqual([]);
  });
});

describe('ReaderNav', () => {
  it('offers the previous and next book and opens them', () => {
    const onWork = vi.fn();
    render(<ReaderNav sections={sections} work="vergil.aeneid.part.2.tess"
                      onWork={onWork} onJump={() => ''} />);
    fireEvent.click(screen.getByLabelText('Previous: Book 1'));
    expect(onWork).toHaveBeenCalledWith('vergil.aeneid.part.1.tess');
    fireEvent.click(screen.getByLabelText('Next: Book 3'));
    expect(onWork).toHaveBeenCalledWith('vergil.aeneid.part.3.tess');
  });

  it('disables the link past either end', () => {
    render(<ReaderNav sections={sections} work="vergil.aeneid.part.1.tess"
                      onWork={() => {}} onJump={() => ''} />);
    expect(screen.getByLabelText('No previous book')).toBeDisabled();
    expect(screen.getByLabelText('Next: Book 2')).not.toBeDisabled();
  });

  it('shows no book links for a work in one file', () => {
    render(<ReaderNav sections={[sections[0]]} work="vergil.aeneid.part.1.tess"
                      onWork={() => {}} onJump={() => ''} />);
    expect(screen.queryByLabelText(/Next/)).toBeNull();
    expect(screen.getByLabelText('Back to top')).toBeInTheDocument();
  });

  it('hands the typed locus to onJump and reports a miss', () => {
    const onJump = vi.fn((q) => (q === '6.851' ? '' : `no line ${q} here`));
    render(<ReaderNav sections={sections} work="vergil.aeneid.part.2.tess"
                      onWork={() => {}} onJump={onJump} />);
    const box = screen.getByLabelText('Go to line');
    fireEvent.change(box, { target: { value: '6.9999' } });
    fireEvent.click(screen.getByText('Go'));
    expect(onJump).toHaveBeenCalledWith('6.9999');
    expect(screen.getByRole('status')).toHaveTextContent('no line 6.9999 here');
    fireEvent.change(box, { target: { value: '6.851' } });
    fireEvent.click(screen.getByText('Go'));
    expect(screen.queryByRole('status')).toBeNull();
    expect(box).toHaveValue('');
  });
});

describe('ReaderEndNav', () => {
  it('repeats the book links and back to top at the end of the text', () => {
    const onWork = vi.fn();
    render(<ReaderEndNav sections={sections} work="vergil.aeneid.part.3.tess" onWork={onWork} />);
    expect(screen.getByLabelText('No next book')).toBeDisabled();
    fireEvent.click(screen.getByLabelText('Previous: Book 2'));
    expect(onWork).toHaveBeenCalledWith('vergil.aeneid.part.2.tess');
    expect(screen.getByLabelText('Back to top')).toBeInTheDocument();
  });
});

describe('books one at a time (2026-09-20)', () => {
  const withWhole = [
    { file: 'silius_italicus.punica.tess', label: 'Punica' },
    { file: 'silius_italicus.punica.part.1.tess', label: 'Book 1' },
    { file: 'silius_italicus.punica.part.8.tess', label: 'Book 8' },
  ];
  it('bookSections skips the whole-file copy when book files exist', async () => {
    const { bookSections } = await import('./ReaderNav');
    expect(bookSections(withWhole).map((s) => s.label)).toEqual(['Book 1', 'Book 8']);
    expect(bookSections(sections)).toEqual(sections);
  });
  it('bookFileFor sends a whole-file work to the book that holds the ref, else Book 1', async () => {
    const { bookFileFor } = await import('./ReaderNav');
    expect(bookFileFor(withWhole, 'silius_italicus.punica.tess', 'sil. 8.135')).toBe('silius_italicus.punica.part.8.tess');
    expect(bookFileFor(withWhole, 'silius_italicus.punica.tess', '')).toBe('silius_italicus.punica.part.1.tess');
    expect(bookFileFor(withWhole, 'silius_italicus.punica.part.8.tess', 'sil. 8.1')).toBe('');
    expect(bookFileFor([{ file: 'catullus.carmina.tess', label: 'Carmina' }], 'catullus.carmina.tess', '1.1')).toBe('');
  });
  it('the floating navigator offers top, end and the neighbouring books', async () => {
    const { ReaderFloatNav } = await import('./ReaderNav');
    const onWork = vi.fn();
    render(<ReaderFloatNav sections={withWhole} work="silius_italicus.punica.part.1.tess" onWork={onWork} />);
    expect(screen.getByLabelText('Back to top')).toBeTruthy();
    expect(screen.getByLabelText('To the end')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Next: Book 8'));
    expect(onWork).toHaveBeenCalledWith('silius_italicus.punica.part.8.tess');
    expect(screen.getByLabelText('No previous book')).toBeDisabled();
  });
});


describe('book files with a suffix after their number (2026-09-20)', () => {
  it('counts dionysius part.12.books_12-20 as a book', async () => {
    const { bookSections, bookFileFor } = await import('./ReaderNav');
    const sections = [
      { file: 'dion.ant.tess', label: 'Whole' },
      { file: 'dion.ant.part.1.tess', label: 'Book 1' },
      { file: 'dion.ant.part.12.books_12-20.tess', label: 'Books 12-20' },
    ];
    expect(bookSections(sections).map((s) => s.file)).toEqual([
      'dion.ant.part.1.tess', 'dion.ant.part.12.books_12-20.tess']);
    expect(bookFileFor(sections, 'dion.ant.part.12.books_12-20.tess', 'dion. ant 15.1.1')).toBe('');
  });
});
