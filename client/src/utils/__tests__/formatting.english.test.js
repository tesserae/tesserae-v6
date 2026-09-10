import { describe, it, expect } from 'vitest';
import { formatReference } from '../formatting';

// The English corpus tags name the author and then the work, often abbreviated
// with periods. The formatter used to take the first token as the work and join
// the rest with periods, giving "Milton P.L..1.225" (2026-09-10).
describe('formatReference for English tags', () => {
  it('expands an abbreviated author-and-work tag', () => {
    expect(formatReference('Milton P.L. 1.225', 'en')).toBe('Milton, Paradise Lost 1.225');
    expect(formatReference('Milton P.R. 2.10', 'en')).toBe('Milton, Paradise Regained 2.10');
    expect(formatReference('Spenser F.Q. 1.1.1', 'en')).toBe('Spenser, The Faerie Queene 1.1.1');
  });

  it('keeps a work that needs no expansion, without a stray period', () => {
    expect(formatReference('Keats Hyperion 1.296', 'en')).toBe('Keats, Hyperion 1.296');
    expect(formatReference('Milton Lycidas 1', 'en')).toBe('Milton, Lycidas 1');
  });

  it('handles the lower-cased dotted authors', () => {
    expect(formatReference('carr. alice. 1.12', 'en')).toBe("Carroll, Alice's Adventures in Wonderland 1.12");
    expect(formatReference('swift. gull. 2.3', 'en')).toBe("Swift, Gulliver's Travels 2.3");
    expect(formatReference('shake. son. 18.1', 'en')).toBe('Shakespeare, Sonnets 18.1');
  });

  it('handles Bible books, including numbered ones', () => {
    expect(formatReference('WEB Genesis 1.1', 'en')).toBe('World English Bible, Genesis 1.1');
    expect(formatReference('WEB 1 Kings 2.3', 'en')).toBe('World English Bible, 1 Kings 2.3');
    expect(formatReference('WEB Song of Solomon 2.1', 'en')).toBe('World English Bible, Song of Solomon 2.1');
  });

  it('still handles the work-first tags', () => {
    expect(formatReference('hamlet 3.1.56', 'en')).toBe('Shakespeare, Hamlet 3.1.56');
    expect(formatReference('richard iii 1.1', 'en')).toBe('Shakespeare, Richard III 1.1');
  });

  it('formats a range of the same work once', () => {
    expect(formatReference('Milton P.L. 1.225-Milton P.L. 1.226', 'en'))
      .toBe('Milton, Paradise Lost 1.225–226');
  });
});
