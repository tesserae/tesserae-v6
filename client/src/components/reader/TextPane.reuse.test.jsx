/**
 * The "quoted in N works" mark: a small button beside a line the corpus-wide
 * reuse table shows repeated in other works, from the reuseMarks prop
 * (ref -> {n_works, n_possible_works}) ReaderPage fetches from
 * GET /api/reuse/marks.
 *
 * TIERED (2026-09-19): n_works counts only STRICT pairs (the original
 * jaccard/containment rules) and draws the solid mark; n_possible_works
 * counts only POSSIBLE pairs (the rare-single-ngram rule alone -- one rare
 * shared phrase, weaker evidence) and draws a lighter, dashed-outline mark,
 * shown only when there is no strict pair at all. A line never shows both.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import TextPane from './TextPane';

const UNITS = [
  { ref: 'verg. aen. 1.1', text: 'Arma virumque cano, Troiae qui primus ab oris' },
  { ref: 'verg. aen. 1.2', text: 'Italiam fato profugus' },
];

describe('the strict (solid) reuse mark', () => {
  it('appears only on a line the reuse table has a strict count for', () => {
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={() => {}}
                reuseMarks={{ 'verg. aen. 1.1': { n_works: 3, n_possible_works: 0 } }}
                onReuseClick={() => {}} />
    );
    const mark = screen.getByTitle('Quoted in 3 other works');
    expect(mark).toBeTruthy();
    expect(mark.textContent).toBe('3');
    expect(screen.getAllByText('3').length).toBe(1);
  });

  it('singular count reads "1 other work"', () => {
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={() => {}}
                reuseMarks={{ 'verg. aen. 1.1': { n_works: 1, n_possible_works: 0 } }}
                onReuseClick={() => {}} />
    );
    expect(screen.getByTitle('Quoted in 1 other work')).toBeTruthy();
  });

  it('draws no mark when reuseMarks is empty', () => {
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={() => {}}
                reuseMarks={{}} onReuseClick={() => {}} />
    );
    expect(screen.queryByTitle(/Quoted in/, { exact: false })).toBeNull();
    expect(screen.queryByTitle(/Possible echo/, { exact: false })).toBeNull();
  });

  it('clicking the mark calls onReuseClick with that line, not onSelect', () => {
    const onReuseClick = vi.fn();
    const onSelect = vi.fn();
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={onSelect}
                reuseMarks={{ 'verg. aen. 1.1': { n_works: 2, n_possible_works: 0 } }}
                onReuseClick={onReuseClick} />
    );
    screen.getByTitle('Quoted in 2 other works').click();
    expect(onReuseClick).toHaveBeenCalledWith(expect.objectContaining({ ref: 'verg. aen. 1.1' }));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('takes priority over a possible count on the same line', () => {
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={() => {}}
                reuseMarks={{ 'verg. aen. 1.1': { n_works: 2, n_possible_works: 1 } }}
                onReuseClick={() => {}} />
    );
    expect(screen.getByTitle('Quoted in 2 other works')).toBeTruthy();
    expect(screen.queryByTitle(/Possible echo/, { exact: false })).toBeNull();
  });
});

describe('the possible (lighter, outlined) reuse mark', () => {
  it('appears when a line has only possible pairs (no strict ones)', () => {
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={() => {}}
                reuseMarks={{ 'verg. aen. 1.1': { n_works: 0, n_possible_works: 1 } }}
                onReuseClick={() => {}} />
    );
    const mark = screen.getByLabelText('possible echo in 1 work');
    expect(mark).toBeTruthy();
    expect(mark.textContent).toBe('1');
    expect(mark.title).toMatch(/^Possible echo in 1 other work/);
    expect(screen.queryByTitle(/^Quoted in/, { exact: false })).toBeNull();
  });

  it('is visually distinct from the strict mark (dashed, not solid)', () => {
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={() => {}}
                reuseMarks={{ 'verg. aen. 1.1': { n_works: 0, n_possible_works: 2 } }}
                onReuseClick={() => {}} />
    );
    const mark = screen.getByLabelText('possible echo in 2 works');
    expect(mark.className).toContain('border-dashed');
    expect(mark.className).not.toContain('text-red-700');
  });

  it('clicking it calls onReuseClick with that line, not onSelect', () => {
    const onReuseClick = vi.fn();
    const onSelect = vi.fn();
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={onSelect}
                reuseMarks={{ 'verg. aen. 1.1': { n_works: 0, n_possible_works: 1 } }}
                onReuseClick={onReuseClick} />
    );
    screen.getByLabelText('possible echo in 1 work').click();
    expect(onReuseClick).toHaveBeenCalledWith(expect.objectContaining({ ref: 'verg. aen. 1.1' }));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('does not appear when both counts are zero', () => {
    render(
      <TextPane units={UNITS} language="la" selection={null} onSelect={() => {}}
                reuseMarks={{ 'verg. aen. 1.1': { n_works: 0, n_possible_works: 0 } }}
                onReuseClick={() => {}} />
    );
    expect(screen.queryByTitle(/Quoted in/, { exact: false })).toBeNull();
    expect(screen.queryByTitle(/Possible echo/, { exact: false })).toBeNull();
  });
});
