import { describe, it, expect } from 'vitest';
import { displayRef, readableLocus } from './refId';
import { shortRef } from './ResultsPanel';

describe('Ennius loci of uncertain book or work', () => {
  it('reads sedinc and opinc plainly', () => {
    expect(readableLocus('sedinc.481')).toBe('481 (book uncertain)');
    expect(readableLocus('opinc.1a')).toBe('uncertain work 1a');
  });
  it('applies in the card reference and in displayRef', () => {
    expect(shortRef('ennius ann. sedinc.481')).toBe('481 (book uncertain)');
    expect(displayRef('ennius ann. opinc.37')).toBe('ennius ann. uncertain work 37');
  });
  it('leaves ordinary references alone', () => {
    expect(shortRef('vergil aen. 1.94')).toBe('1.94');
    expect(displayRef('sal.  Cat..58.15')).toBe('sal. Cat. 58.15');
  });
});
