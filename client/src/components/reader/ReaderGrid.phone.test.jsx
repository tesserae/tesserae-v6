/**
 * The margin and the line grid on a phone: a slimmer gutter, smaller marks,
 * narrower number column, and a hanging indent for a line that still wraps.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import ConnectionGutter from './ConnectionGutter';
import TextPane from './TextPane';
import { installPhone } from '../../test/phone';

const UNITS = [{ ref: 'verg. aen. 1.5', text: 'Arma virumque cano, Troiae qui primus ab oris' }];

beforeEach(() => {
  global.fetch = vi.fn(() => new Promise(() => {}));
});
afterEach(() => { cleanup(); delete global.fetch; });

function gutterRoot(container) {
  return container.firstChild;
}

describe('ConnectionGutter', () => {
  it('is the wide gutter with 9 by 7 marks on a desktop', () => {
    const { container } = render(<ConnectionGutter work="w" units={UNITS} />);
    expect(gutterRoot(container).className).toContain('w-9');
    expect(container.querySelector('.w-\\[9px\\]')).not.toBeNull();
  });

  it('is w-5 with 6 by 6 marks on a phone, keeping both hit areas and the spoken text', () => {
    const env = installPhone(true);
    try {
      const { container } = render(<ConnectionGutter work="w" units={UNITS} />);
      expect(gutterRoot(container).className).toContain('w-5');
      expect(gutterRoot(container).className).not.toContain('w-9');
      expect(container.querySelector('.w-\\[9px\\]')).toBeNull();
      expect(container.querySelectorAll('.w-\\[6px\\].h-\\[6px\\]').length).toBeGreaterThanOrEqual(4);
      expect(container.querySelector('.gap-\\[2px\\]')).not.toBeNull();
      expect(container.querySelector('[title="Verbal parallels for this line"]')).not.toBeNull();
      expect(container.querySelector('[title="Similar passages for this line"]')).not.toBeNull();
      expect(container.querySelector('.sr-only').textContent).toMatch(/Two columns of marks/);
    } finally { env.restore(); }
  });
});

describe('TextPane', () => {
  it('keeps the wide grid and no indent on a desktop', () => {
    render(<TextPane units={UNITS} language="la" selection={null} onSelect={() => {}} />);
    const line = document.getElementById('line-verg-aen-1-5') || document.querySelector('[id^="line-"]');
    expect(line.style.gridTemplateColumns.startsWith('2.6rem')).toBe(true);
    expect(line.className).toContain('gap-2');
    expect(screen.getByText(/Arma virumque/).style.textIndent).toBe('');
  });

  it('narrows the number column, the gap and the padding on a phone, with a hanging indent', () => {
    const env = installPhone(true);
    try {
      render(<TextPane units={UNITS} language="la" selection={null} onSelect={() => {}} />);
      const line = document.querySelector('[id^="line-"]');
      expect(line.style.gridTemplateColumns.startsWith('1.6rem')).toBe(true);
      expect(line.className).toContain('gap-1');
      expect(line.className).not.toContain('gap-2');
      const p = screen.getByText(/Arma virumque/);
      expect(p.style.textIndent).toBe('-1em');
      expect(p.style.paddingLeft).toBe('1em');
      expect(line.firstChild.className).toContain('text-[10px]');
      expect(line.firstChild.textContent).toBe('5');
    } finally { env.restore(); }
  });
});
