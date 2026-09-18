/**
 * The "quoted in N works" mark: a small button beside a line the corpus-wide
 * reuse table shows repeated in other works, from the reuseMarks prop
 * (ref -> n_works) ReaderPage fetches from GET /api/reuse/marks.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import TextPane from './TextPane';

const UNITS = [
  { ref: 'verg. aen. 1.1', text: 'Arma virumque cano, Troiae qui primus ab oris' },
  { ref: 'verg. aen. 1.2', text: 'Italiam fato profugus' },
];

describe('the reuse mark', () => {
  it('appears only on a line the reuse table has a count for', () => {
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={() => {}}
                reuseMarks={{ 'verg. aen. 1.1': 3 }} onReuseClick={() => {}} />
    );
    const mark = screen.getByTitle('Quoted in 3 other works');
    expect(mark).toBeTruthy();
    expect(mark.textContent).toBe('3');
    expect(screen.queryByTitle(/Quoted in/, { exact: false })).toBeTruthy();
    // Only one mark drawn, not one per line.
    expect(screen.getAllByText('3').length).toBe(1);
  });

  it('singular count reads "1 other work"', () => {
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={() => {}}
                reuseMarks={{ 'verg. aen. 1.1': 1 }} onReuseClick={() => {}} />
    );
    expect(screen.getByTitle('Quoted in 1 other work')).toBeTruthy();
  });

  it('draws no mark when reuseMarks is empty', () => {
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={() => {}}
                reuseMarks={{}} onReuseClick={() => {}} />
    );
    expect(screen.queryByTitle(/Quoted in/, { exact: false })).toBeNull();
  });

  it('clicking the mark calls onReuseClick with that line, not onSelect', () => {
    const onReuseClick = vi.fn();
    const onSelect = vi.fn();
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={onSelect}
                reuseMarks={{ 'verg. aen. 1.1': 2 }} onReuseClick={onReuseClick} />
    );
    screen.getByTitle('Quoted in 2 other works').click();
    expect(onReuseClick).toHaveBeenCalledWith(expect.objectContaining({ ref: 'verg. aen. 1.1' }));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
