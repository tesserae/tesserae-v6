import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';

import { renderDocumentText } from '../documentDisplay';

const tokens = ['uf', 'iiviri', 'duoviri', 'ob', 'honorem'];

function cardText(hit) {
  const { container } = render(<p>{renderDocumentText(hit)}</p>);
  return container;
}

describe('a gap in the stone on a document card', () => {
  it('shows a gray [...] marker at each position in gap_before', () => {
    const c = cardText({ tokens, text: tokens.join(' '), gap_before: [0, 3] });
    const markers = c.querySelectorAll('[title="text lost"]');
    expect(markers).toHaveLength(2);
    expect(markers[0].textContent.trim()).toBe('[...]');
    expect(markers[0].className).toContain('text-gray-400');
    expect(c.textContent.replace(/\s+/g, ' ').trim()).toBe('[...] uf iiviri duoviri [...] ob honorem');
  });

  it('shows a marker after the last word when the gap is at the end of the line', () => {
    const c = cardText({ tokens, text: tokens.join(' '), gap_before: [5] });
    expect(c.querySelectorAll('[title="text lost"]')).toHaveLength(1);
    expect(c.textContent.replace(/\s+/g, ' ').trim()).toBe('uf iiviri duoviri ob honorem [...]');
  });

  it('is unchanged for a hit without gap_before', () => {
    const c = cardText({ tokens, text: tokens.join(' '), restored_indices: [2] });
    expect(c.querySelectorAll('[title="text lost"]')).toHaveLength(0);
    expect(c.textContent.replace(/\s+/g, ' ').trim()).toBe('uf iiviri duoviri ob honorem');
    expect(c.querySelectorAll('[title="editorially restored"]')).toHaveLength(1);
  });
});

describe('restored words on a multi-line card', () => {
  // Written: "ob honorem / uf IIviri (duoviri)", the "/" is written position 2.
  // The card's tokens leave the "/" out, so written position 3 ("uf") is token 2.
  const hit = {
    language: 'la',
    text: 'ob honorem / uf IIviri (duoviri)',
    tokens: ['ob', 'honorem', 'uf', 'iiuiri', 'duouiri'],
    restored_indices: [3, 5],
    fragment_indices: [4],
  };

  it('keeps the underline on the right words after a "/"', () => {
    const c = cardText(hit);
    const under = [...c.querySelectorAll('[title="editorially restored"]')].map((e) => e.textContent);
    expect(under).toEqual(['uf', 'duouiri']);
    const frag = [...c.querySelectorAll('[title="surviving fragment of a damaged word"]')].map((e) => e.textContent);
    expect(frag).toEqual(['iiuiri']);
  });

  it('leaves the positions alone when the text does not line up with the tokens', () => {
    const c = cardText({ ...hit, text: 'something else entirely', restored_indices: [1] });
    const under = [...c.querySelectorAll('[title="editorially restored"]')].map((e) => e.textContent);
    expect(under).toEqual(['honorem']);
  });

  it('counts a numeral as written but not as a token', () => {
    const c = cardText({ language: 'la', text: 'anno XII uf', tokens: ['anno', 'xii', 'uf'], restored_indices: [2] });
    // "XII" is letters, so it is a token: position 2 is still "uf".
    expect([...c.querySelectorAll('[title="editorially restored"]')].map((e) => e.textContent)).toEqual(['uf']);
    const d = cardText({ language: 'la', text: 'anno 12 uf', tokens: ['anno', 'uf'], restored_indices: [2] });
    expect([...d.querySelectorAll('[title="editorially restored"]')].map((e) => e.textContent)).toEqual(['uf']);
  });
});

describe("an editor's gloss on a written-out word", () => {
  const hit = {
    language: 'la',
    text: 'uf IIviri (duoviri) ob',
    tokens: ['uf', 'iiuiri', 'duouiri', 'ob'],
  };

  it('shows the gloss token in parentheses, keeping its restored underline', () => {
    const c = cardText({ ...hit, gloss_indices: [2], restored_indices: [2] });
    expect(c.textContent.replace(/\s+/g, ' ').trim()).toBe('uf iiuiri (duouiri) ob');
    const under = [...c.querySelectorAll('[title="editorially restored"]')].map((e) => e.textContent);
    expect(under).toEqual(['duouiri']);
  });

  it('puts one pair of parentheses round a run of gloss tokens', () => {
    const c = cardText({ ...hit, gloss_indices: [1, 2] });
    expect(c.textContent.replace(/\s+/g, ' ').trim()).toBe('uf (iiuiri duouiri) ob');
  });

  it('is unchanged for a hit without gloss_indices', () => {
    const c = cardText(hit);
    expect(c.textContent.replace(/\s+/g, ' ').trim()).toBe('uf iiuiri duouiri ob');
  });
});
