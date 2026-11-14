/**
 * The phone sheet keeps a finger's vertical drag to itself.
 *
 * On a phone the results panel is a sheet fixed over the bottom of the text.
 * Its body scrolls, but when the body has nothing to scroll (a translation
 * shorter than the sheet) or has reached its end, the browser passed the
 * movement on to the page, and the Greek behind the sheet scrolled instead
 * (owner, iPhone, 2026-11-14). A touchmove inside the sheet is now cancelled
 * unless a box inside the sheet can still scroll in that direction; sideways
 * drags (the tab strip) and the desktop column are left alone.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';
import { resetScholarshipLanguagesCache } from '../../utils/scholarshipLanguages';
import { installPhone } from '../../test/phone';

const UNITS = [{ ref: 'verg. aen. 1.1', text: 'Arma virumque cano' }];

function mount() {
  render(<ResultsPanel selection={null} language="la" work="vergil.aeneid" units={UNITS} />);
}

/** jsdom has TouchEvent but no Touch, so the touch list goes on by hand. */
function touch(el, type, x, y) {
  const e = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(e, 'touches', { value: [{ clientX: x, clientY: y }] });
  el.dispatchEvent(e);
  return e;
}

/** Give a box a scroll position and size the way the browser would. */
function sizeBox(el, { scrollHeight, clientHeight, scrollTop }) {
  Object.defineProperty(el, 'scrollHeight', { value: scrollHeight, configurable: true });
  Object.defineProperty(el, 'clientHeight', { value: clientHeight, configurable: true });
  el.scrollTop = scrollTop;
}

let env;
beforeEach(() => {
  resetScholarshipLanguagesCache();
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
  env = installPhone(true);
  // Tailwind's classes are not loaded in the test, so the body's overflow is
  // declared the way the stylesheet would.
  const style = window.getComputedStyle;
  vi.spyOn(window, 'getComputedStyle').mockImplementation((el) => {
    const cs = style(el);
    if (el?.dataset?.testid === 'results-panel-body') {
      return new Proxy(cs, { get: (t, k) => (k === 'overflowY' ? 'auto' : t[k]) });
    }
    return cs;
  });
});

afterEach(() => {
  env.restore();
  vi.restoreAllMocks();
  delete global.fetch;
  window.history.replaceState({}, '', '/');
});

describe('a vertical drag on the phone sheet', () => {
  it('is stopped when the body has nothing to scroll', () => {
    mount();
    const body = screen.getByTestId('results-panel-body');
    sizeBox(body, { scrollHeight: 200, clientHeight: 200, scrollTop: 0 });
    touch(body, 'touchstart', 100, 300);
    expect(touch(body, 'touchmove', 100, 250).defaultPrevented).toBe(true);
    expect(touch(body, 'touchmove', 100, 350).defaultPrevented).toBe(true);
  });

  it('is left to the body while the body can still scroll that way', () => {
    mount();
    const body = screen.getByTestId('results-panel-body');
    sizeBox(body, { scrollHeight: 1000, clientHeight: 200, scrollTop: 0 });
    touch(body, 'touchstart', 100, 300);
    // At the top: an upward finger (reading on) scrolls the body, a downward
    // one would only move the page.
    expect(touch(body, 'touchmove', 100, 250).defaultPrevented).toBe(false);
    expect(touch(body, 'touchmove', 100, 350).defaultPrevented).toBe(true);
    sizeBox(body, { scrollHeight: 1000, clientHeight: 200, scrollTop: 800 });
    touch(body, 'touchstart', 100, 300);
    expect(touch(body, 'touchmove', 100, 250).defaultPrevented).toBe(true);
    expect(touch(body, 'touchmove', 100, 350).defaultPrevented).toBe(false);
  });

  it('leaves a sideways drag alone, so the tab strip can scroll', () => {
    mount();
    const strip = screen.getByRole('button', { name: 'Reuse' }).parentElement;
    touch(strip, 'touchstart', 300, 100);
    expect(touch(strip, 'touchmove', 200, 110).defaultPrevented).toBe(false);
  });

  it('does nothing on a desktop, where the panel is a column beside the text', () => {
    env.setPhone(false);
    mount();
    const body = screen.getByTestId('results-panel-body');
    sizeBox(body, { scrollHeight: 200, clientHeight: 200, scrollTop: 0 });
    touch(body, 'touchstart', 100, 300);
    expect(touch(body, 'touchmove', 100, 250).defaultPrevented).toBe(false);
  });
});
