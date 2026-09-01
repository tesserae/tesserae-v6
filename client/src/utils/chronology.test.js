import { describe, it, expect } from 'vitest';
import { chronological } from './chronology';

const r = (work, year, score) => ({ work, year, score });

describe('chronological', () => {
  it('orders by year, oldest first, undated last', () => {
    const out = chronological([r('b', 1540, 0.9), r('a', -406, 0.5), r('c', undefined, 0.99)]);
    expect(out.map((x) => x.work)).toEqual(['a', 'b', 'c']);
  });

  it('keeps same-year works together, best work first', () => {
    const rows = [
      r('philoctetes', -406, 0.9),
      r('alcestis', -406, 0.85),
      r('philoctetes', -406, 0.84),
      r('alcestis', -406, 0.7),
      r('philoctetes', -406, 0.6),
    ];
    const out = chronological(rows);
    expect(out.map((x) => x.work)).toEqual(
      ['philoctetes', 'philoctetes', 'philoctetes', 'alcestis', 'alcestis']);
    expect(out[0].score).toBe(0.9);
  });

  it('never places a later year before an earlier one regardless of score', () => {
    const out = chronological([r('eobanus', 1540, 0.99), r('euripides', -406, 0.1)]);
    expect(out[0].work).toBe('euripides');
  });
});
