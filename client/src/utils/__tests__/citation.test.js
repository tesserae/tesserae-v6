import { describe, it, expect } from 'vitest';
import { reproducibleCitation, mlaCitation, chicagoCitation, buildCitation } from '../citation';

const DATE = new Date('2026-09-08T12:00:00');

const parallel = {
  kind: 'fusion search',
  source: 'Hafez, Diwan 1626',
  target: 'Ghalib, Diwan 264.30',
  language: 'Persian',
  score: 4.835,
  channels: 'semantic, shared vocabulary',
  corpusVersion: '2026-09-06',
  url: 'https://tesserae.caset.buffalo.edu/?source=hafez.diwan.tess',
  date: DATE,
};

const theme = {
  kind: 'theme search',
  query: 'a city laid waste by invaders',
  language: 'Persian and Urdu',
  corpusVersion: '2026-09-08',
  date: DATE,
};

describe('reproducible citation', () => {
  it('names the corpus version, the search and the loci', () => {
    const c = reproducibleCitation(parallel);
    expect(c).toContain('corpus 2026-09-06');
    expect(c).toContain('fusion search');
    expect(c).toContain('Hafez, Diwan 1626 ~ Ghalib, Diwan 264.30');
    expect(c).toContain('score 4.835');
    expect(c).toContain('accessed 2026-09-08');
  });

  it('carries the rerun link on its own line', () => {
    expect(reproducibleCitation(parallel).split('\n')[1]).toBe(parallel.url);
  });

  it('quotes the query for a search that takes one', () => {
    expect(reproducibleCitation(theme)).toContain('query: "a city laid waste by invaders"');
  });

  // The whole point of this format is the stamp, but a missing one must not
  // produce a broken reference: some indexes carry no version row.
  it('omits the version cleanly when there is none', () => {
    const c = reproducibleCitation({ ...parallel, corpusVersion: undefined });
    expect(c).not.toContain('corpus ');
    expect(c).not.toContain(', ,');
    expect(c).not.toContain('. .');
    expect(c).toContain('Tesserae V6, fusion search');
  });
});

describe('bibliography styles', () => {
  it('MLA separates containers with periods, since the loci contain commas', () => {
    const c = mlaCitation(parallel);
    expect(c).toContain('Coffee, Neil, et al. Tesserae V6.');
    expect(c).toContain('Accessed 8 Sept. 2026.');
  });

  it('Chicago reads as a note and ends with the site', () => {
    const c = chicagoCitation(parallel);
    expect(c.startsWith('Neil Coffee et al., Tesserae V6')).toBe(true);
    expect(c).toContain('accessed September 8, 2026');
    expect(c.endsWith('https://tesserae.caset.buffalo.edu.')).toBe(true);
  });

  it('handles a finding with only a query and no loci', () => {
    expect(mlaCitation(theme)).toContain('Search for');
    expect(mlaCitation(theme)).not.toContain('Parallel between');
  });
});

describe('buildCitation', () => {
  it('dispatches by style and falls back to the reproducible one', () => {
    expect(buildCitation('mla', parallel)).toBe(mlaCitation(parallel));
    expect(buildCitation('nonsense', parallel)).toBe(reproducibleCitation(parallel));
  });
});
