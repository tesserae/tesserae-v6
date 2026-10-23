import { describe, it, expect } from 'vitest';
import { displayRef, readableLocus, findRefIndex, marginNumber } from './refId';
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

describe('Go to line finds a unit by what the margin shows', () => {
  const latin = ['verg. aen. 6.850', 'verg. aen. 6.851', 'verg. aen. 7.851'];
  const masnavi = ['rumi.masnavi.1.17', 'rumi.masnavi.1.18', 'rumi.masnavi.11.18'];
  const shahnameh = ['ferdowsi.shahnameh.1.1.1', 'ferdowsi.shahnameh.1.1.2', 'ferdowsi.shahnameh.151.1.1', 'ferdowsi.shahnameh.151.1.2'];
  it('takes book and line after a space, and a bare line when it is unique', () => {
    expect(findRefIndex(latin, '6.851').index).toBe(1);
    expect(findRefIndex(latin, '850').index).toBe(0);
  });
  it('takes a dotted reference when the file joins the locus with dots', () => {
    expect(findRefIndex(masnavi, '1.18').index).toBe(1);
    expect(findRefIndex(masnavi, '11.18').index).toBe(2);
    expect(findRefIndex(shahnameh, '151.1.1').index).toBe(2);
    expect(findRefIndex(shahnameh, '151.1.2').index).toBe(3);
  });
  it('asks for the part before when the entry names several places', () => {
    const r = findRefIndex(shahnameh, '1.1');
    expect(r.index).toBe(-1);
    expect(r.problem).toBe('line 1.1 is in 2 places here; add what comes before it, e.g. 1.1.1');
    const l = findRefIndex(latin, '851');
    expect(l.index).toBe(-1);
    expect(l.problem).toMatch(/2 places here; add what comes before it, e.g. 6.851/);
  });
  it('reports a miss plainly', () => {
    expect(findRefIndex(shahnameh, '999.1.1')).toEqual({ index: -1, problem: 'no line 999.1.1 here' });
    expect(findRefIndex([], '1.1').index).toBe(-1);
  });
});

describe('the margin number', () => {
  it('is the last number of an ordinary reference', () => {
    expect(marginNumber('verg. aen. 6.855', 'la')).toBe(855);
    expect(marginNumber('amm. 14.1.5', 'la')).toBe(5);
    expect(marginNumber('iqbal.asrar_e_khudi.1.10', 'fa')).toBe(10);
  });
  it('is the couplet on the first hemistich of a story.couplet.hemistich reference, and nothing on the second', () => {
    expect(marginNumber('ferdowsi.shahnameh.151.5.1', 'fa')).toBe(5);
    expect(marginNumber('ferdowsi.shahnameh.151.5.2', 'fa')).toBeNull();
    expect(marginNumber('ferdowsi.shahnameh.151.10.1', 'fa')).toBe(10);
  });
  it('is null without a number', () => {
    expect(marginNumber('', 'la')).toBeNull();
  });
});
