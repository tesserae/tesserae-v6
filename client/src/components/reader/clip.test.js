import { describe, it, expect } from 'vitest';
import { clip } from './ResultsPanel';

const opening = 'Profectio arto comitatu fuit: unus senator consulatu functus, Cocceius Nerva, cui legum peritia, eques Romanus praeter Seianum ex inlustribus Curtius Atticus, ceteri liberalibus studiis praediti, ferme Graeci, quorum sermonibus levaretur. ferebant periti caelestium iis motibus siderum excessisse ';
const tail = 'Roma Tiberium ut reditus illi negaretur. unde exitii causa multis fuit properum finem vitae coniectantibus vulgantibusque; neque enim tam incredibilem casum providebant ut undecim per annos libens patria careret.';
const text = opening + tail;

describe('clip keeps the matched words in view', () => {
  it('finds whole words, not a word hidden inside another, and shows them', () => {
    const out = clip(text, ['roma', 'reditus'], 260, true);
    expect(out).toContain('Roma Tiberium ut reditus');
    expect(out.startsWith('…')).toBe(true);
    expect(out).not.toContain('Profectio arto');
  });
  it('leaves a short passage whole', () => {
    expect(clip('Roma Tiberium ut reditus illi negaretur.', ['roma'], 260, true)).toBe('Roma Tiberium ut reditus illi negaretur.');
  });
  it('shows the opening when no matched word is in the text', () => {
    const out = clip(text, ['nusquam'], 260, true);
    expect(out.startsWith('Profectio arto')).toBe(true);
    expect(out.endsWith('…')).toBe(true);
  });
  it('matches across u and v in Latin', () => {
    const out = clip(text, ['reditvs'], 260, true);
    expect(out).toContain('reditus illi');
  });
});
