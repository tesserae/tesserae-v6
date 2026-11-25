import { describe, it, expect } from 'vitest';
import { legacyRedirect } from '../routePaths';

// String Search left the Intertext Search page's sub-tab row on 2026-11-25
// for its own place in the top row; the old address opens the new page.
describe('legacyRedirect — the old String Search sub-tab address', () => {
  it('sends /?tab=string to /string-search', () => {
    expect(legacyRedirect('/?tab=string')).toBe('/string-search');
  });
  it('keeps the other parameters and the hash', () => {
    expect(legacyRedirect('/?tab=string&lang=grc#top')).toBe('/string-search?lang=grc#top');
  });
  it('leaves the other sub-tabs and pages alone', () => {
    expect(legacyRedirect('/?tab=line')).toBe('/?tab=line');
    expect(legacyRedirect('/browse?tab=string')).toBe('/browse?tab=string');
  });
});
