/**
 * The tab strip: short labels ("Similar", "Parallels", "Translation",
 * "Reuse") so all four fit one row, and the strip WRAPS to a second line
 * rather than scrolling if it still overflows at a narrow width.
 *
 * NC, looking at Aeneid 1.1 on the preview: "the panel's tab bar now
 * overflows and needs a scroll slider... If users can't see all of them
 * they won't know they're there." A hidden horizontal scroll is exactly
 * that failure mode -- nothing on screen says there is a fourth tab past
 * the edge. Wrapping keeps every tab visible instead.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';

const UNITS = [{ ref: 'verg. aen. 1.1', text: 'Arma virumque cano' }];

function mount(props = {}) {
  render(
    <ResultsPanel
      selection={null}
      language="la"
      work="vergil.aeneid"
      units={UNITS}
      {...props}
    />
  );
}

describe('the tab strip', () => {
  it('uses short labels that fit one row', () => {
    mount();
    for (const label of ['Similar', 'Parallels', 'Translation', 'Reuse']) {
      expect(screen.getByRole('button', { name: label })).toBeTruthy();
    }
    // The old, longer wording is gone from the tab strip itself (it may
    // still appear elsewhere, e.g. explanatory copy).
    expect(screen.queryByRole('button', { name: 'Similar Passages' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Verbal Parallels' })).toBeNull();
  });

  it('keeps the full name as a tooltip on the short label', () => {
    mount();
    expect(screen.getByRole('button', { name: 'Similar' }).title).toBe('Similar Passages');
    expect(screen.getByRole('button', { name: 'Parallels' }).title).toBe('Verbal Parallels');
  });

  it('wraps rather than scrolls when the tabs do not fit one row', () => {
    mount();
    const strip = screen.getByRole('button', { name: 'Reuse' }).parentElement;
    expect(strip.className).toContain('flex-wrap');
    expect(strip.className).not.toContain('overflow-x-auto');
    expect(strip.className).not.toContain('whitespace-nowrap');
  });
});
