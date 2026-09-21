import { describe, expect, it } from 'vitest';
import { LANG_NAMES } from './adminConstants';

/**
 * RequestsTab, CacheTab and StatsTab all read language display names from
 * this file's `LANG_NAMES`. It used to be its own `{ la, grc, en }` map, so
 * a Hebrew or Coptic feature request in the admin panel showed the raw code
 * (code review 2026-09-21, finding 3/4). It now re-exports the shared table.
 */
describe('adminConstants LANG_NAMES', () => {
  it('names Hebrew, Coptic, Persian, Urdu and Arabic, not just la/grc/en', () => {
    expect(LANG_NAMES.he).toBe('Hebrew');
    expect(LANG_NAMES.cop).toBe('Coptic');
    expect(LANG_NAMES.fa).toBe('Persian');
    expect(LANG_NAMES.ur).toBe('Urdu');
    expect(LANG_NAMES.ar).toBe('Arabic');
    expect(LANG_NAMES.la).toBe('Latin');
    expect(LANG_NAMES.grc).toBe('Greek');
    expect(LANG_NAMES.en).toBe('English');
  });
});
