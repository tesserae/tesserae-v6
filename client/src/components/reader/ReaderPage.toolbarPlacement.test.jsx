/**
 * The selection toolbar must not hang over the lines after the selection
 * (2026-10-19). With a fixed line height of 30 pixels, a two-row toolbar of
 * 64 pixels used to sit 8 pixels under the selected line and cover the next two.
 */
import { describe, expect, it } from 'vitest';
import { toolbarTopFor } from './ReaderPage';

const LINE = 30;
const top = (n) => (n - 1) * LINE;       // pane offsetTop of line n
const bottom = (n) => n * LINE;

describe('toolbarTopFor', () => {
  it('goes above the first selected line when there is room, ending above that line', () => {
    const y = toolbarTopFor({ firstTop: top(10), lastBottom: bottom(10), height: 64 });
    expect(y + 64).toBeLessThanOrEqual(top(10));
    expect(y).toBeGreaterThanOrEqual(0);
  });

  it('for a three-line selection, sits above the first line and clears the whole selection', () => {
    const y = toolbarTopFor({ firstTop: top(10), lastBottom: bottom(12), height: 64 });
    expect(y + 64).toBeLessThanOrEqual(top(10));
  });

  it('goes below the last selected line when the pane has no room above', () => {
    const y = toolbarTopFor({ firstTop: top(1), lastBottom: bottom(1), height: 64 });
    expect(y).toBeGreaterThanOrEqual(bottom(1));
  });

  it('goes below when the screen has no room above the line, whatever the pane has', () => {
    const y = toolbarTopFor({ firstTop: top(10), lastBottom: bottom(10), height: 64, viewportRoom: 20 });
    expect(y).toBeGreaterThanOrEqual(bottom(10));
  });

  it('takes the toolbar height into account: a taller toolbar needs more room', () => {
    // 5 lines above the selection leave 120 pixels of pane.
    expect(toolbarTopFor({ firstTop: 120, lastBottom: 150, height: 64 })).toBeLessThan(120);
    expect(toolbarTopFor({ firstTop: 120, lastBottom: 150, height: 130 })).toBeGreaterThanOrEqual(150);
  });
});
