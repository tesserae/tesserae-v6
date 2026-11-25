import { describe, it, expect } from 'vitest';
import { fitTabs } from '../Navigation';

describe('fitTabs', () => {
  it('keeps every tab when they all fit or nothing is measured', () => {
    expect(fitTabs([100, 100, 100], 400, 60)).toBe(3);
    expect(fitTabs([0, 0, 0], 400, 60)).toBe(3);
    expect(fitTabs([100, 100], 0, 60)).toBe(2);
  });
  it('counts the More button when deciding whether every tab fits (2026-11-25)', () => {
    // 4 tabs of 100 fill 400 px exactly, but More (60 px) is always beside them: 3 fit.
    expect(fitTabs([100, 100, 100, 100], 400, 60)).toBe(3);
    expect(fitTabs([100, 100, 100, 100], 460, 60)).toBe(4);
  });
  it('moves the trailing tabs into More when the row is too narrow', () => {
    // 5 tabs of 100 in 350 px with a 60 px More button: 2 fit beside More
    expect(fitTabs([100, 100, 100, 100, 100], 350, 60)).toBe(2);
    expect(fitTabs([100, 100, 100, 100, 100], 460, 60)).toBe(4);
  });
});
