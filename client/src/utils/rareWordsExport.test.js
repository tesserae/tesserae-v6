import { describe, it, expect } from 'vitest';
import { corpusOccurrencesCsv, corpusOccurrenceRows } from './rareWordsExport';

const result = {
  lemma: 'quercus', display_form: 'quercus',
  source_locations: [{ ref: 'a 1.1' }], target_locations: [{ ref: 'b 2.2' }, { ref: 'b 2.3' }],
  all_corpus_locations: [
    { author: 'Vergil', work: 'Aeneid', citation: 'Vergil Aeneid 1.1', text: 'say "oak" here' },
    { author: 'Ovid', work: 'Met', ref: 'x.3', text: 'again' },
  ],
};

describe('corpusOccurrencesCsv', () => {
  it('writes one row per corpus occurrence with source and target locations', () => {
    const rows = corpusOccurrenceRows([result]);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toEqual(['quercus', 'quercus', 'Vergil, Aeneid', 'Vergil Aeneid 1.1', 'say "oak" here', 'a 1.1', 'b 2.2; b 2.3']);
    expect(rows[1][3]).toBe('x.3');
  });
  it('quotes cells and starts with the header', () => {
    const csv = corpusOccurrencesCsv([result]);
    expect(csv.split('\n')[0]).toBe('"Word","Lemma","Work","Citation","Line Text","Source Locations","Target Locations"');
    expect(csv).toContain('"say ""oak"" here"');
  });
  it('keeps a word with no occurrences as one row', () => {
    expect(corpusOccurrenceRows([{ lemma: 'x', source_locations: [], target_locations: [] }])).toHaveLength(1);
  });
});
