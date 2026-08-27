import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// jsdom implements neither of these, and a component that asks for either
// throws on render. That took out the whole SearchResults pagination file --
// 28 tests, every one failing with "window.matchMedia is not a function" --
// so the client suite could not be run at all, and UI regressions had no net
// under them. Both are stubbed rather than mocked per-test, because the first
// component to use one should not have to discover this again.
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},        // deprecated, still called by older libraries
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

if (!window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = () => {};
}

afterEach(() => {
  cleanup();
});
