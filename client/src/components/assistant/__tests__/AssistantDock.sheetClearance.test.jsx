/**
 * Between 768 and 1023 pixels the Reader's results sheet is fixed along the
 * bottom edge with its tab strip, and Tessa's round pill sat over the last tab
 * (second phone pass, 2026-10-11). The pill now rides above the strip there.
 * jsdom does not apply Tailwind's media queries, so these tests read the layout
 * classes: the width is stubbed, the dock and the sheet are rendered together,
 * and the pill's offset is compared with the strip's height.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import AssistantDock from '../AssistantDock';
import ResultsPanel from '../../reader/ResultsPanel';

const realMatchMedia = window.matchMedia;
const realWidth = window.innerWidth;

// matchMedia answers min-width and max-width queries against the stubbed width.
const stubWidth = (px) => {
  window.innerWidth = px;
  window.matchMedia = (query) => {
    const max = /max-width:\s*(\d+)px/.exec(query);
    const min = /min-width:\s*(\d+)px/.exec(query);
    const matches = (max ? px <= Number(max[1]) : true) && (min ? px >= Number(min[1]) : true);
    return {
      matches, media: query, onchange: null,
      addEventListener: () => {}, removeEventListener: () => {},
      addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
    };
  };
};

beforeEach(() => {
  window.localStorage.clear();
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, text: () => Promise.resolve(JSON.stringify({ available: true })) }));
});
afterEach(() => {
  delete global.fetch;
  window.matchMedia = realMatchMedia;
  window.innerWidth = realWidth;
});

const renderBoth = () => render(
  <>
    <ResultsPanel selection={null} language="la" work="vergil.aeneid.tess" units={[]} />
    <AssistantDock />
  </>
);

const rem = (cls, prefix) => {
  const m = new RegExp(`(?:^|\\s)${prefix}\\[([\\d.]+)rem\\]`).exec(cls);
  return m ? Number(m[1]) : null;
};

describe('Tessa pill and the Reader results sheet', () => {
  it.each([800, 900, 1000])('at %i px the pill sits above the sheet strip', async (px) => {
    stubWidth(px);
    const { container } = renderBoth();
    const pill = (await screen.findByRole('button', { name: 'Open Tessa, the AI assistant' })).parentElement;
    const sheet = container.querySelector('aside');
    // The sheet is fixed to the bottom edge, collapsed to a 2.75rem strip.
    expect(sheet.className).toContain('fixed');
    expect(sheet.className).toContain('bottom-0');
    const strip = rem(sheet.className, 'max-h-');
    expect(strip).toBe(2.75);
    // The pill's bottom offset clears the strip with the old 1rem margin on top.
    expect(rem(pill.className, 'bottom-')).toBe(strip + 1);
    // From 1024 pixels the sheet is a side column and the pill is back at bottom-4.
    expect(pill.className).toContain('lg:bottom-4');
    expect(pill.className).not.toMatch(/(^|\s)bottom-4(\s|$)/);
  });

  it('below 768 px Tessa is the side tab, with no bottom offset to change', async () => {
    stubWidth(600);
    renderBoth();
    const tab = await screen.findByRole('button', { name: 'Show Tessa, the AI assistant' });
    expect(tab.className).toContain('right-0');
    expect(tab.className).not.toContain('bottom-');
  });

  it('at 1100 px the pill keeps its bottom-4 offset (the lg: class)', async () => {
    stubWidth(1100);
    renderBoth();
    const pill = (await screen.findByRole('button', { name: 'Open Tessa, the AI assistant' })).parentElement;
    expect(pill.className).toContain('lg:bottom-4');
  });
});
