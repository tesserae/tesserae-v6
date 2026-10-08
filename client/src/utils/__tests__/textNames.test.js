import { describe, it, expect } from 'vitest';
import {
  resolveDisplayCitation,
  citationFromCorpusMap,
  siteIdFromRef,
  looksLikeRawSiteId,
  collapseLineRuns,
  formatLineGroup,
  formatRefrainPopover,
} from '../textNames';

// Result card tidy (2026-10-08): the card showed "Vergil, Aeneid 1.1" for
// Latin but raw internal ids ("hafez.diwan.5097") for Persian and Urdu,
// because only Latin/Greek/English had a static abbreviation table. These
// helpers resolve any language against the corpus list's own author/title
// (what `/api/texts?language=<lang>` already carries), the same record the
// corpus browser and the Reader read from.

const faTexts = new Map([
  ['hafez.diwan', { author: 'Hafez', title: 'Diwan' }],
  ['iqbal.zabur_e_ajam', { author: 'Iqbal', title: 'Zabur-e Ajam' }],
]);

describe('looksLikeRawSiteId', () => {
  it('is true for a lower-case dotted id', () => {
    expect(looksLikeRawSiteId('hafez.diwan.5097')).toBe(true);
  });
  it('is false once a citation has a comma (an "Author, Work" form)', () => {
    expect(looksLikeRawSiteId('Hafez, Diwan 5097')).toBe(false);
  });
  it('is false for a bare resolved author with no comma, e.g. a single name', () => {
    // A single capitalized token is not the raw lower-case dotted shape.
    expect(looksLikeRawSiteId('Homer')).toBe(false);
  });
  it('is true for an empty or missing value', () => {
    expect(looksLikeRawSiteId('')).toBe(true);
    expect(looksLikeRawSiteId(undefined)).toBe(true);
  });
});

describe('citationFromCorpusMap', () => {
  it('resolves a Persian ref against the corpus map', () => {
    const hit = citationFromCorpusMap('hafez.diwan.5097', faTexts);
    expect(hit).toEqual({
      author: 'Hafez', work: 'Diwan', reference: '5097', siteId: 'hafez.diwan.5097', idCut: 2,
    });
  });

  it('resolves a multi-segment locus (poem.line) by the longest matching id', () => {
    const hit = citationFromCorpusMap('iqbal.zabur_e_ajam.26.1', faTexts);
    expect(hit.author).toBe('Iqbal');
    expect(hit.work).toBe('Zabur-e Ajam');
    expect(hit.reference).toBe('26.1');
  });

  it('returns null when nothing in the map matches', () => {
    expect(citationFromCorpusMap('unknown.work.1', faTexts)).toBeNull();
  });

  it('returns null without a map', () => {
    expect(citationFromCorpusMap('hafez.diwan.5097', null)).toBeNull();
  });
});

describe('resolveDisplayCitation', () => {
  it('keeps the Latin static-table result unchanged (it already reads as a name)', () => {
    const { text, siteId } = resolveDisplayCitation('Vergil, Aeneid 1.1', 'verg. aen. 1.1', null);
    expect(text).toBe('Vergil, Aeneid 1.1');
    expect(siteId).toBe('verg. aen. 1.1');
  });

  it('upgrades a raw Persian id to "Author, Work reference" once the corpus map is loaded', () => {
    const { text, siteId } = resolveDisplayCitation('hafez.diwan.5097', 'hafez.diwan.5097', faTexts);
    expect(text).toBe('Hafez, Diwan 5097');
    expect(siteId).toBe('hafez.diwan.5097');
  });

  it('upgrades a raw Urdu-shaped id the same way', () => {
    const urTexts = new Map([['ghalib.diwan_wikisource', { author: 'Ghalib', title: 'Diwan Wikisource' }]]);
    const { text } = resolveDisplayCitation('ghalib.diwan_wikisource.264.30', 'ghalib.diwan_wikisource.264.30', urTexts);
    expect(text).toBe('Ghalib, Diwan Wikisource 264.30');
  });

  it('leaves a Greek static-table citation alone too', () => {
    const { text } = resolveDisplayCitation('Homer, Iliad 1.1', 'hom. il. 1.1', null);
    expect(text).toBe('Homer, Iliad 1.1');
  });

  it('upgrades a Hebrew-shaped raw id once its map is loaded', () => {
    const heTexts = new Map([['hebrew_bible.genesis', { author: 'Hebrew Bible', title: 'Genesis' }]]);
    const { text } = resolveDisplayCitation('hebrew_bible.genesis.1.1', 'hebrew_bible.genesis.1.1', heTexts);
    expect(text).toBe('Hebrew Bible, Genesis 1.1');
  });

  it('falls back to the raw id when the corpus map has not loaded and no better text exists', () => {
    const { text, siteId } = resolveDisplayCitation('', 'nobody.knows.1', null);
    expect(siteId).toBe('nobody.knows.1');
    // No static table and no corpus map: the best this can do is name the
    // first segment as the author, which is what expandLocus's own fallback
    // already does for an unmapped tag.
    expect(text.toLowerCase()).toContain('nobody');
  });
});

describe('collapseLineRuns', () => {
  it('collapses a run of three or more into "a to b"', () => {
    expect(collapseLineRuns([1, 2, 3, 4, 5, 6, 7])).toEqual(['1 to 7']);
  });
  it('keeps a non-consecutive set as separate numbers', () => {
    expect(collapseLineRuns([5097, 5098, 5100, 5102])).toEqual(['5097', '5098', '5100', '5102']);
  });
  it('spells out a run of exactly two rather than writing "a to b" for it', () => {
    // "5097 to 5098" is longer than "5097, 5098"; the spec's own worked
    // example keeps a two-line run unranged for this reason.
    expect(collapseLineRuns([1, 2, 3, 5, 7, 8])).toEqual(['1 to 3', '5', '7', '8']);
  });
});

describe('formatLineGroup', () => {
  it('names the work once and lists non-consecutive lines plainly', () => {
    const refs = ['hafez.diwan.5097', 'hafez.diwan.5098', 'hafez.diwan.5100', 'hafez.diwan.5102',
      'hafez.diwan.5104', 'hafez.diwan.5106', 'hafez.diwan.5108', 'hafez.diwan.5110'];
    const group = formatLineGroup(refs, faTexts);
    expect(group.label).toBe('Hafez, Diwan');
    expect(group.text).toBe('lines 5097, 5098, 5100, 5102, 5104, 5106, 5108, 5110');
  });

  it('collapses a consecutive run and keeps a poem-number prefix in the label', () => {
    const refs = ['iqbal.zabur_e_ajam.26.1', 'iqbal.zabur_e_ajam.26.2', 'iqbal.zabur_e_ajam.26.3',
      'iqbal.zabur_e_ajam.26.4', 'iqbal.zabur_e_ajam.26.5', 'iqbal.zabur_e_ajam.26.6', 'iqbal.zabur_e_ajam.26.7'];
    const group = formatLineGroup(refs, faTexts);
    expect(group.label).toBe('Iqbal, Zabur-e Ajam 26');
    expect(group.text).toBe('lines 1 to 7');
  });

  it('returns null for an empty list', () => {
    expect(formatLineGroup([], faTexts)).toBeNull();
  });
});

describe('formatRefrainPopover', () => {
  it('gives the spec\'s own worked example', () => {
    const poetics = {
      source_lines: ['hafez.diwan.5097', 'hafez.diwan.5098', 'hafez.diwan.5100', 'hafez.diwan.5102',
        'hafez.diwan.5104', 'hafez.diwan.5106', 'hafez.diwan.5108', 'hafez.diwan.5110'],
      target_lines: ['iqbal.zabur_e_ajam.26.1', 'iqbal.zabur_e_ajam.26.2', 'iqbal.zabur_e_ajam.26.3',
        'iqbal.zabur_e_ajam.26.4', 'iqbal.zabur_e_ajam.26.5', 'iqbal.zabur_e_ajam.26.6', 'iqbal.zabur_e_ajam.26.7'],
    };
    const { heading, explanation } = formatRefrainPopover(poetics, faTexts);
    expect(heading).toBe('8 + 7 refrain lines');
    expect(explanation).toContain('Hafez, Diwan: lines 5097, 5098, 5100, 5102, 5104, 5106, 5108, 5110');
    expect(explanation).toContain('Iqbal, Zabur-e Ajam 26: lines 1 to 7');
    expect(explanation).toContain('one result stands for the pair');
  });
});

describe('siteIdFromRef', () => {
  it('strips embedded markup and trims', () => {
    expect(siteIdFromRef('hafez.diwan.<em>5097</em>')).toBe('hafez.diwan.5097');
    expect(siteIdFromRef('  verg. aen. 1.1  ')).toBe('verg. aen. 1.1');
  });
});
