/**
 * A guard against the exact bug a 2026-09-21 code review found (findings 3
 * and 4): `utils/languageNames.js` is supposed to be the only place that
 * maps a language code to a display name, but Corpus Browser and Rare
 * Words Explorer had each grown their own local, stale copy (missing
 * Hebrew, Persian, Urdu, Arabic), and several other files had too. Those
 * copies read fine in a component test that never exercises an unusual
 * language, so this checks the source text directly: a future contributor
 * who pastes a `{ la: 'Latin', grc: 'Greek', ... }` object back into one of
 * these files should see this test fail, not discover the bug from a
 * scholar reporting "Persian shows up as fa".
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const here = path.dirname(fileURLToPath(import.meta.url));
const clientSrc = path.resolve(here, '..', '..');

// Files that must import the shared helper instead of defining their own
// code -> name lookup. Each entry names the local variable/function a
// duplicate used to define, so a re-introduced copy under a different name
// (e.g. `LANG_MAP` instead of `LANG_NAMES`) would still likely be caught by
// the broader "no hand-rolled { la: 'Latin' ... }" check below.
const FILES_THAT_MUST_IMPORT_THE_SHARED_HELPER = [
  'components/corpus/CorpusBrowser.jsx',
  'components/corpus/RareWordsExplorer.jsx',
  'components/reader/ResultsPanel.jsx',
  'components/reader/ReaderHeader.jsx',
  'components/about/TextCredits.jsx',
  'components/admin/adminConstants.js',
  'components/passages/ThemeExport.jsx',
  'components/passages/ThemeSearchPage.jsx',
  'components/passages/ConnectionsMap.jsx',
  'components/admin/tabs/AnalyticsTab.jsx',
  'components/admin/tabs/MetadataTab.jsx',
  'components/repository/Repository.jsx',
];

function read(relPath) {
  return readFileSync(path.join(clientSrc, relPath), 'utf8');
}

describe('language display names have exactly one source', () => {
  it('utils/languageNames.js knows every language code the site serves', () => {
    const src = read('utils/languageNames.js');
    for (const code of ['la', 'grc', 'en', 'cop', 'he', 'fa', 'ur', 'ar']) {
      expect(src, `LANGUAGE_NAMES should list '${code}'`).toMatch(
        new RegExp(`\\b${code}\\s*:`)
      );
    }
  });

  it.each(FILES_THAT_MUST_IMPORT_THE_SHARED_HELPER)(
    '%s imports the shared language-name helper',
    (relPath) => {
      const src = read(relPath);
      expect(src, `${relPath} should import from utils/languageNames`).toMatch(
        /from ['"].*utils\/languageNames['"]/
      );
    }
  );

  it.each(FILES_THAT_MUST_IMPORT_THE_SHARED_HELPER)(
    "%s does not define its own getLanguageName function",
    (relPath) => {
      const src = read(relPath);
      expect(src, `${relPath} should not redefine getLanguageName`).not.toMatch(
        /getLanguageName\s*=\s*\(/
      );
    }
  );

  it.each(FILES_THAT_MUST_IMPORT_THE_SHARED_HELPER)(
    '%s does not hand-roll a Latin/Greek/English name map of its own',
    (relPath) => {
      const src = read(relPath);
      // The exact shape every duplicate the review found took: an object
      // literal spelling out la/grc/en (with or without more codes) by
      // hand, rather than importing the shared table.
      expect(src).not.toMatch(/\{\s*la:\s*['"]Latin['"]\s*,\s*grc:\s*['"]Greek['"]/);
    }
  );

  it('utils/formatting.js no longer carries a second, dead getLanguageName', () => {
    const src = read('utils/formatting.js');
    expect(src).not.toMatch(/getLanguageName/);
  });

  it('LineSearch.jsx no longer carries its own dead getLanguageName', () => {
    // This copy had zero callers (dead code, missed by the code review
    // entirely -- it named only CorpusBrowser and RareWordsExplorer), so
    // the fix was to delete it rather than import the shared helper.
    const src = read('components/search/LineSearch.jsx');
    expect(src).not.toMatch(/getLanguageName/);
  });

  it('ThemeSearchPage.jsx does not hand-roll its language-choice labels as [code, name] pairs', () => {
    // A fourth copy the review also missed: LANG_CHOICES used to spell out
    // ['he', 'Hebrew'], ['fa', 'Persian'], etc. by hand for the language
    // picker's checkboxes.
    const src = read('components/passages/ThemeSearchPage.jsx');
    expect(src).not.toMatch(/\['he',\s*['"]Hebrew['"]\]/);
  });

  it('ConnectionsMap.jsx does not hand-roll its language-order labels as [code, name] pairs', () => {
    const src = read('components/passages/ConnectionsMap.jsx');
    expect(src).not.toMatch(/\['he',\s*['"]Hebrew['"]\]/);
  });

  it('MetadataTab.jsx does not fall back to "English" for a language it does not special-case', () => {
    // The exact bug: `language === 'la' ? 'Latin' : language === 'grc' ?
    // 'Greek' : 'English'` named every Coptic and Hebrew row "English".
    const src = read('components/admin/tabs/MetadataTab.jsx');
    expect(src).not.toMatch(/:\s*['"]English['"]\s*\}/);
  });

  it('formatLocus is not defined anywhere (both copies were dead code)', () => {
    const formatting = read('utils/formatting.js');
    const textNames = read('utils/textNames.js');
    expect(formatting).not.toMatch(/formatLocus/);
    expect(textNames).not.toMatch(/formatLocus/);
  });

  it("Corpus Browser's era filter reads from the shared per-language era table", () => {
    const src = read('components/corpus/CorpusBrowser.jsx');
    expect(src).toMatch(/from ['"].*utils\/eras['"]/);
    // `erasByLanguage` was the second, hand-written era table (English's
    // 18th century was 'eighteenth_century' there, which matched no work --
    // the backend tags that period 'Neoclassical' or 'Augustan'). It should
    // not come back now that the filter dropdown is derived from
    // utils/eras.js instead. (Note: the file's separate, pre-existing
    // `eraOrder` array -- used for the unrelated "sort authors by era"
    // toggle, not this dropdown -- still legitimately says
    // 'eighteenth_century', so this checks for the removed variable by
    // name rather than for that string.)
    expect(src).not.toMatch(/erasByLanguage/);
  });
});
