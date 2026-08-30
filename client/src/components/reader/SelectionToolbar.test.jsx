import { describe, it, expect } from 'vitest';
import { wordOf, scopeFor } from './SelectionToolbar';

describe('wordOf', () => {
  it('returns a double-clicked word, shorn of punctuation', () => {
    expect(wordOf({ text: 'cano' })).toBe('cano');
    expect(wordOf({ text: 'cano.' })).toBe('cano');
    expect(wordOf({ text: '“virumque,”' })).toBe('virumque');
  });
  it('handles Greek and Hebrew', () => {
    expect(wordOf({ text: 'ἄειδε' })).toBe('ἄειδε');
    expect(wordOf({ text: 'בְּרֵאשִׁית' })).toBe('בְּרֵאשִׁית');
  });
  it('returns null for phrases, empty, and non-letters', () => {
    expect(wordOf({ text: 'arma virumque' })).toBe(null);
    expect(wordOf({ text: '' })).toBe(null);
    expect(wordOf({ text: '123' })).toBe(null);
    expect(wordOf(null)).toBe(null);
  });
});

describe('scopeFor', () => {
  it('seeds word for a single selected word', () => {
    expect(scopeFor({ lineCount: 1, text: 'cano' })).toBe('word');
  });
  it('seeds line for one or two lines, passage for three or more', () => {
    expect(scopeFor({ lineCount: 1, text: 'arma virumque cano' })).toBe('line');
    expect(scopeFor({ lineCount: 2, text: 'x y' })).toBe('line');
    expect(scopeFor({ lineCount: 3, text: 'x y z' })).toBe('passage');
    expect(scopeFor(null)).toBe('line');
  });
});
