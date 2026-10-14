import { describe, it, expect } from 'vitest';
import hostData from '../imageHosts.json';
import { hostOf, imageLinkLabel, isHiddenImageLink, splitImageLinks } from '../imageLinks';

describe('imageLinks', () => {
  it('hostOf returns empty for bare file names', () => {
    expect(hostOf('ISic000001.jpg')).toBe('');
    expect(hostOf('https://Lupa.at/1')).toBe('lupa.at');
  });
  it('hides dead hosts and bare file names only', () => {
    for (const h of hostData.deadHosts) expect(isHiddenImageLink(`http://${h}/x`)).toBe(true);
    expect(isHiddenImageLink('ISic000001.jpg')).toBe(true);
    expect(isHiddenImageLink('https://lupa.at/1')).toBe(false);
  });
  it('labels', () => {
    expect(imageLinkLabel('https://edh.ub.uni-heidelberg.de/edh/foto/F034014'))
      .toBe('Photo F034014 at Epigraphic Database Heidelberg');
    expect(imageLinkLabel('https://some.unlisted.org/a')).toBe('Link at some.unlisted.org');
  });
  it('every listed host has a name and kind and none is also dead', () => {
    for (const [h, v] of Object.entries(hostData.hosts)) {
      expect(v.name && v.kind).toBeTruthy();
      expect(hostData.deadHosts).not.toContain(h);
    }
  });
  it('splitImageLinks counts omissions', () => {
    const r = splitImageLinks(['https://lupa.at/1', 'https://access.bl.uk/x', 'a.jpg']);
    expect(r.shown.length).toBe(1);
    expect(r.omitted).toBe(2);
  });
});
