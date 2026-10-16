import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import FusionFlowchart, { CHIP_WIDTH, CHIP_PITCH } from '../FusionFlowchart';
import { CHANNEL_SHORT } from '../../../utils/channels';

const FAN = [
  'lemma', 'lemma_min1', 'exact', 'sound', 'edit_distance', 'semantic',
  'dictionary', 'syntax', 'syntax_structural', 'rare_word', 'quotation',
];

describe('FusionFlowchart channel chips', () => {
  it('shows every chip with the text from the shared CHANNEL_SHORT table', () => {
    const { container } = render(<FusionFlowchart />);
    const texts = [...container.querySelectorAll('.fan g')]
      .filter((g) => g.querySelector('rect'))
      .map((g) => g.querySelector('text').textContent.replace(/\s+/g, ' ').trim());
    // tspans of a two-word label are joined without a space by textContent
    const normalize = (s) => s.replace(/ /g, '');
    expect(texts.map(normalize)).toEqual(FAN.map((n) => normalize(CHANNEL_SHORT[n])));
    expect(texts).toHaveLength(11);
  });

  it('keeps the chips inside the viewBox without overlap and each line short enough', () => {
    const { container } = render(<FusionFlowchart />);
    const rects = [...container.querySelectorAll('.fan rect[class^="chip-"]')];
    const xs = rects.map((r) => Number(r.getAttribute('x')));
    xs.forEach((x, i) => {
      if (i) expect(x - xs[i - 1]).toBeGreaterThanOrEqual(CHIP_WIDTH);
    });
    expect(CHIP_PITCH).toBeGreaterThan(CHIP_WIDTH);
    expect(xs[xs.length - 1] + CHIP_WIDTH).toBeLessThanOrEqual(660);
    FAN.forEach((n) => {
      CHANNEL_SHORT[n].split(' ').forEach((w) => expect(w.length).toBeLessThanOrEqual(10));
    });
  });

  it('names the weights and badges from the same table', () => {
    const { container } = render(<FusionFlowchart />);
    const badges = [...container.querySelectorAll('.rbadge')].map((b) => b.textContent);
    expect(badges).toEqual([CHANNEL_SHORT.lemma, CHANNEL_SHORT.sound, CHANNEL_SHORT.rare_word]);
  });
});
