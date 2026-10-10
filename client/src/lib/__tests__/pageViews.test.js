import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { recordPageView, getVisitToken } from '../pageViews';

describe('pageViews', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });
  afterEach(() => {
    vi.restoreAllMocks();
    delete navigator.sendBeacon;
    delete global.fetch;
  });

  it('keeps one 24-hex token in sessionStorage', () => {
    const a = getVisitToken();
    expect(a).toMatch(/^[0-9a-f]{24}$/);
    expect(getVisitToken()).toBe(a);
    expect(window.sessionStorage.getItem('tesserae_visit')).toBe(a);
  });

  it('sends the page view with sendBeacon as JSON', async () => {
    navigator.sendBeacon = vi.fn(() => true);
    recordPageView({ path: '/read', page: 'read', language: 'la' });
    expect(navigator.sendBeacon).toHaveBeenCalledTimes(1);
    const [url, blob] = navigator.sendBeacon.mock.calls[0];
    expect(url).toBe('/api/usage/page');
    const sent = JSON.parse(await blob.text());
    expect(sent.visit).toBe(getVisitToken());
    expect(sent).toMatchObject({ path: '/read', page: 'read', language: 'la' });
  });

  it('falls back to fetch with keepalive', () => {
    global.fetch = vi.fn(() => Promise.resolve({}));
    recordPageView({ path: '/about', page: 'about', language: 'grc' });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toBe('/api/usage/page');
    expect(opts.keepalive).toBe(true);
    expect(JSON.parse(opts.body).page).toBe('about');
  });

  it('gets a fresh token when storage is blocked and never throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    expect(getVisitToken()).toMatch(/^[0-9a-f]{24}$/);
    navigator.sendBeacon = vi.fn(() => { throw new Error('boom'); });
    expect(() => recordPageView({ path: '/', page: 'search' })).not.toThrow();
  });
});
