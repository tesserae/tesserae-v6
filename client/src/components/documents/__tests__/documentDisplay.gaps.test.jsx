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
