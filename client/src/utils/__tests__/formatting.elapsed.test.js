import { describe, it, expect } from 'vitest';
import { formatElapsedTime, formatRunningTime } from '../formatting';

describe('the running clock shows whole seconds', () => {
  it('drops the decimal under a minute', () => {
    expect(formatRunningTime(21)).toBe('21s');
    expect(formatRunningTime(21.7)).toBe('21s');
    expect(formatRunningTime(1)).toBe('1s');
  });
  it('shows minutes and seconds past a minute', () => {
    expect(formatRunningTime(135)).toBe('2m 15s');
    expect(formatRunningTime(60)).toBe('1m 0s');
  });
  it('shows nothing before the first second', () => {
    expect(formatRunningTime(0)).toBe('');
    expect(formatRunningTime(null)).toBe('');
  });
});

describe('a finished search keeps its measured decimal', () => {
  it('keeps one decimal under a minute', () => {
    expect(formatElapsedTime(3.42)).toBe('3.4s');
  });
});
