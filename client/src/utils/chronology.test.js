/**
 * One chronology, used by Theme Search and by the Reader's panel.
 *
 * It lived only in ThemeSearchPage, so the Reader grew its own list of
 * cross-language results ordered by score with no dates at all -- the same kind
 * of list behaving differently on two pages of one site. NC: "What order are
 * these similar passages in? Should be chronological."
 */
import { describe, expect, it } from 'vitest';
import { chronological, dateParts } from './chronology';

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
});
