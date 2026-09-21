/**
 * `languageNames.js` is supposed to be the ONLY place in the client that
 * maps a language code to a display name (added 2026-09-06 after three
 * components spelled the same chain out by hand). A 2026-09-21 code review
 * (findings 3 and 4) found the rule had already been broken again: Corpus
 * Browser, Rare Words Explorer, and several other files each kept their own
 * copy, and some of those copies were missing Hebrew, Persian, Urdu, and
 * Arabic. This test pins down two things a future stale copy would fail:
 * every language the site actually serves has a real name here, and the
 * fallback for a code nobody has heard of doesn't silently claim to be
 * "English" or the empty string.
 */
import { describe, expect, it } from 'vitest';
import { LANGUAGE_NAMES, languageName } from './languageNames';

// The full set of language codes the site serves: Latin, Greek, English,
// Coptic, and Hebrew are live in production; Persian, Urdu, and Arabic are
// in development (see CLAUDE.md, "Current Development Focus"); Italian, Old
// French, and Middle High German are minor corpora used for a handful of
// cross-lingual comparisons (see texts/it, texts/fro, texts/gmh).
const SERVED_LANGUAGES = ['la', 'grc', 'en', 'cop', 'he', 'fa', 'ur', 'ar', 'it', 'fro', 'gmh'];

describe('LANGUAGE_NAMES / languageName', () => {
  it('has a real display name for every language the site serves', () => {
    for (const code of SERVED_LANGUAGES) {
      const name = languageName(code);
      expect(name, `languageName('${code}')`).toBeTruthy();
      // A real name, not just the raw code echoed back or upper-cased
      // (the fallback for a code the table has never heard of).
      expect(name.toLowerCase()).not.toBe(code.toLowerCase());
    }
  });

  it('gives Hebrew, Persian, Urdu and Arabic their real names', () => {
    // These four were the ones a 2026-09-21 code review found missing from
    // two hand-rolled copies (Corpus Browser, Rare Words Explorer), so they
    // get named individually rather than just looped over above.
    expect(languageName('he')).toBe('Hebrew');
    expect(languageName('fa')).toBe('Persian');
    expect(languageName('ur')).toBe('Urdu');
    expect(languageName('ar')).toBe('Arabic');
  });

  it('falls back to the upper-cased code for one it does not know, never to English', () => {
    expect(languageName('xx')).toBe('XX');
    expect(languageName('xx')).not.toBe('English');
  });

  it('returns an empty string for no code at all', () => {
    expect(languageName('')).toBe('');
    expect(languageName(undefined)).toBe('');
    expect(languageName(null)).toBe('');
  });

  it('exports a plain object a caller can spread to add a local, non-language key', () => {
    // Repository.jsx and AnalyticsTab.jsx both do this (a 'cross' grouping
    // and raw analytics codes that aren't corpus languages), so the export
    // has to stay a plain object, not a Map or a function.
    const extended = { ...LANGUAGE_NAMES, cross: 'Greek-Latin' };
    expect(extended.la).toBe('Latin');
    expect(extended.cross).toBe('Greek-Latin');
  });
});
