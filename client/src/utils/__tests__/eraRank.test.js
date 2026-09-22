import { describe, it, expect } from 'vitest';
import { ERA_ORDER_BY_LANG, eraRank, orderEras } from '../eras';

// The Corpus Browser's "chronological" sort kept its own copy of the era
// order and wrote it in snake_case ('early_imperial') while the backend sends
// labels ('Early Imperial'). Every lookup returned -1, so every author
// compared equal and the era step did nothing. Latin, Greek and English hid
// it by falling through to the year; Hebrew, where none of the 39 works has a
// year, and Coptic, where 140 of 187 have none, fell all the way through to
// alphabetical by author.

describe('eraRank', () => {
  it('ranks the labels the backend actually sends', () => {
    expect(eraRank('grc', 'Archaic')).toBeLessThan(eraRank('grc', 'Classical'));
    expect(eraRank('grc', 'Classical')).toBeLessThan(eraRank('grc', 'Hellenistic'));
    expect(eraRank('la', 'Republic')).toBeLessThan(eraRank('la', 'Augustan'));
    expect(eraRank('la', 'Augustan')).toBeLessThan(eraRank('la', 'Early Imperial'));
  });

  it('does not recognise the snake_case form that caused the bug', () => {
    // If someone reintroduces 'early_imperial' it must not quietly rank
    // first; it is unknown, and unknown sorts last.
    expect(eraRank('la', 'early_imperial')).toBe(eraRank('la', 'a totally unknown era'));
  });

  it('puts an era it does not know last, never first', () => {
    const known = ERA_ORDER_BY_LANG.la.map((e) => eraRank('la', e));
    const unknown = eraRank('la', 'Something New');
    expect(Math.max(...known)).toBeLessThan(unknown);
  });

  it('treats a missing era as unknown rather than throwing', () => {
    expect(() => eraRank('la', undefined)).not.toThrow();
    expect(eraRank('la', undefined)).toBe(ERA_ORDER_BY_LANG.la.length);
    expect(eraRank('la', null)).toBe(ERA_ORDER_BY_LANG.la.length);
  });

  it('falls back to the Latin order for a language it has no table for', () => {
    expect(eraRank('xx', 'Republic')).toBe(eraRank('la', 'Republic'));
  });

  it('orders Hebrew, where no work carries a year', () => {
    expect(eraRank('he', 'Biblical')).toBeLessThan(eraRank('he', 'Unknown'));
  });

  it('orders Coptic, where most works carry no year', () => {
    expect(eraRank('cop', 'Early Coptic'))
      .toBeLessThan(eraRank('cop', 'Classical Coptic'));
    expect(eraRank('cop', 'Classical Coptic'))
      .toBeLessThan(eraRank('cop', 'Late Antique Coptic'));
  });
});

describe('the English table covers what the corpus is tagged with', () => {
  it('has no century label among the period names', () => {
    // 'Nineteenth century' was carried by one author, Poe, and a century is
    // not a period in the same series as Romantic and Victorian. He is
    // tagged Romantic in backend/author_dates.json as of 2026-09-22.
    expect(ERA_ORDER_BY_LANG.en).not.toContain('Nineteenth century');
    expect(ERA_ORDER_BY_LANG.en).toContain('Romantic');
  });

  it('would still place a stray century label last rather than lose it', () => {
    const last = Math.max(...ERA_ORDER_BY_LANG.en.map((e) => eraRank('en', e)));
    expect(eraRank('en', 'Nineteenth century')).toBeGreaterThan(last - 1);
  });

  it('keeps Romantic before Victorian, which is where Poe now sits', () => {
    expect(eraRank('en', 'Romantic')).toBeLessThan(eraRank('en', 'Victorian'));
  });
});

describe('eraRank and orderEras agree', () => {
  it('both keep an unknown era rather than dropping it', () => {
    const counts = { 'Archaic': 2, 'Something New': 1 };
    expect(orderEras('grc', counts)).toContain('Something New');
    expect(eraRank('grc', 'Something New')).toBeGreaterThan(eraRank('grc', 'Archaic'));
  });

  it('put the known eras in the same relative order', () => {
    const counts = { 'Hellenistic': 1, 'Archaic': 1, 'Classical': 1 };
    const byOrderEras = orderEras('grc', counts);
    const bySort = Object.keys(counts).sort((a, b) => eraRank('grc', a) - eraRank('grc', b));
    expect(bySort).toEqual(byOrderEras);
  });
});
