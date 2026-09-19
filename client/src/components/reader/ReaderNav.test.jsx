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
                      onWork={onWork} onJump={() => true} />);
    fireEvent.click(screen.getByLabelText('Previous: Book 1'));
    expect(onWork).toHaveBeenCalledWith('vergil.aeneid.part.1.tess');
    fireEvent.click(screen.getByLabelText('Next: Book 3'));
    expect(onWork).toHaveBeenCalledWith('vergil.aeneid.part.3.tess');
  });

  it('disables the link past either end', () => {
    render(<ReaderNav sections={sections} work="vergil.aeneid.part.1.tess"
                      onWork={() => {}} onJump={() => true} />);
    expect(screen.getByLabelText('No previous book')).toBeDisabled();
    expect(screen.getByLabelText('Next: Book 2')).not.toBeDisabled();
  });

  it('shows no book links for a work in one file', () => {
    render(<ReaderNav sections={[sections[0]]} work="vergil.aeneid.part.1.tess"
                      onWork={() => {}} onJump={() => true} />);
    expect(screen.queryByLabelText(/Next/)).toBeNull();
    expect(screen.getByLabelText('Back to top')).toBeInTheDocument();
  });

  it('hands the typed locus to onJump and reports a miss', () => {
    const onJump = vi.fn((q) => q === '6.851');
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
