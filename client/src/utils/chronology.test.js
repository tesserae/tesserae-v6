/**
 * One chronology, used by Theme Search and by the Reader's panel.
 *
 * It lived only in ThemeSearchPage, so the Reader grew its own list of
 * cross-language results ordered by score with no dates at all -- the same kind
 * of list behaving differently on two pages of one site. The similar-passages
 * order needed to be chronological, not a raw score order.
 */
import { describe, expect, it } from 'vitest';
import { chronological, byBestMatch, dateParts } from './chronology';

const STATIUS = { work: 'statius.silvae', year: 96, date_note: 'd. c. 96 CE', score: 0.9 };
const SILIUS = { work: 'silius_italicus.punica', year: 101, date_note: 'd. 101 CE', score: 0.8 };
const OVID = { work: 'ovid.metamorphoses', year: 17, date_note: 'd. 17/18 CE', score: 0.7 };
const UNDATED = { work: 'ferdowsi.diwan', score: 0.95 };

describe('oldest first', () => {
  it('orders by year, not by score', () => {
    const out = chronological([STATIUS, SILIUS, OVID]);
    expect(out.map((r) => r.year)).toEqual([17, 96, 101]);
  });

  it('is what the Reader panel was NOT doing', () => {
    // Ranked by score the order was Statius 96, Silius 101, Ovid 17: a line of
    // descent presented backwards.
    const byScore = [STATIUS, SILIUS, OVID];
    expect(byScore.map((r) => r.year)).not.toEqual(
      chronological(byScore).map((r) => r.year));
  });

  it('puts undated works last rather than guessing', () => {
    const out = chronological([UNDATED, OVID, STATIUS]);
    expect(out[out.length - 1].work).toBe('ferdowsi.diwan');
  });

  it('does not mutate its input', () => {
    const input = [STATIUS, OVID];
    chronological(input);
    expect(input[0]).toBe(STATIUS);
  });
});

describe('the date shown on a card', () => {
  it('leads with the date and names the qualifier', () => {
    const d = dateParts(STATIUS);
    expect(d.date).toBe('c. 96 CE');
    expect(d.kind).toBe('died');
  });

  it('falls back to the year when there is no note', () => {
    expect(dateParts({ year: -19 }).date).toBe('19 BCE');
  });

  it('returns nothing for an undated work', () => {
    expect(dateParts(UNDATED)).toBeNull();
  });

  // Quintus Smyrnaeus's card read "3" over "flourished · rd c. CE (disputed;
  // late 2nd-4th)": the year pattern took the first digit of a century.
  it('keeps a century whole in the chip', () => {
    const d = dateParts({ year: 300, date_note: 'fl. 3rd c. CE (disputed; late 2nd-4th)' });
    expect(d.date).toBe('3rd c. CE');
    expect(d.kind).toBe('flourished');
    expect(d.about).toBe('disputed; late 2nd-4th');
  });

  it('reads the century forms the author notes use', () => {
    expect(dateParts({ date_note: 'fl. c. 2nd cent. CE' }).date).toBe('c. 2nd cent. CE');
    expect(dateParts({ date_note: 'comp. c. 2nd-3rd c. CE (Orphic Hymns)' })).toEqual(
      { date: 'c. 2nd-3rd c. CE', kind: 'composed', about: 'Orphic Hymns' });
    expect(dateParts({ date_note: 'fl. 3rd-early 4th c. CE' }).date).toBe('3rd-early 4th c. CE');
    expect(dateParts({ date_note: 'fl. c. 1st c. BCE/CE' }).date).toBe('c. 1st c. BCE/CE');
    expect(dateParts({ date_note: 'c. 3rd cent. BCE' }).date).toBe('c. 3rd cent. BCE');
  });

  it('still reads years as before', () => {
    expect(dateParts({ date_note: 'd. c. 215 CE (c. 150-215), Clement of Alexandria' }).date).toBe('c. 215 CE');
    expect(dateParts({ date_note: 'fl. c. 100 CE' }).date).toBe('c. 100 CE');
  });
});

describe('same-year grouping (added with the best-work tie-break)', () => {
  const r = (work, year, score) => ({ work, year, score });

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

describe('byBestMatch', () => {
  const r = (work, year, score) => ({ work, year, score });

  it('orders by score, not by the API language rotation', () => {
    const rotated = [r('euripides', -406, 0.856), r('gellius', 180, 0.7), r('cowper', 1800, 0.82)];
    const out = byBestMatch(rotated);
    expect(out.map((x) => x.work)).toEqual(['euripides', 'cowper', 'gellius']);
  });

  it('keeps a work together, best passage first', () => {
    const rows = [r('a', 1, 0.5), r('b', 2, 0.9), r('a', 1, 0.95), r('b', 2, 0.6)];
    const out = byBestMatch(rows);
    expect(out.map((x) => `${x.work}${x.score}`)).toEqual(['a0.95', 'a0.5', 'b0.9', 'b0.6']);
  });

  it('does not mutate its input', () => {
    const rows = [r('a', 1, 0.1), r('b', 2, 0.9)];
    const copy = JSON.parse(JSON.stringify(rows));
    byBestMatch(rows);
    expect(rows).toEqual(copy);
  });
});
