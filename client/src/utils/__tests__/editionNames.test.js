import { describe, it, expect } from 'vitest';
import { expandEditions } from '../editionNames';

describe('edition abbreviations written out', () => {
  it('spells out the publications in an EDR record line', () => {
    expect(expandEditions('Not. Sc., 1888, p. 562 (G.F. Gamurrini) - AE 1889 (1)')).toBe(
      "Notizie degli Scavi di Antichità (Not. Sc.), 1888, p. 562 (G.F. Gamurrini) - L'Année épigraphique (AE) 1889 (1)");
    expect(expandEditions('CIL 11, 01923 (A) (1)')).toBe('Corpus Inscriptionum Latinarum (CIL) 11, 01923 (A) (1)');
    expect(expandEditions('P.Oxy. 63 4394')).toBe('The Oxyrhynchus Papyri (P.Oxy.) 63 4394');
  });
  it('matches whole tokens only and leaves unknown abbreviations alone', () => {
    expect(expandEditions('IGDS 12')).toBe('Inscriptions grecques dialectales de Sicile (IGDS) 12');
    expect(expandEditions('IG II2 18')).toBe('Inscriptiones Graecae (IG) II2 18');
    expect(expandEditions('M. Horster, Bauinschriften römischer Kaiser 77')).toBe('M. Horster, Bauinschriften römischer Kaiser 77');
    expect(expandEditions('AEGEAN 3')).toBe('AEGEAN 3');
    expect(expandEditions(null)).toBe(null);
  });
});
