// First-party page-view recording: tells the server which page a visit opened.
// A visit is one browser tab, identified by a random token kept in
// sessionStorage and discarded when the tab closes. Failures are silent and
// nothing here waits on the network.

const KEY = 'tesserae_visit';
const ENDPOINT = '/api/usage/page';

function randomHex(n) {
  let out = '';
  try {
    const bytes = new Uint8Array(Math.ceil(n / 2));
    crypto.getRandomValues(bytes);
    for (const b of bytes) out += b.toString(16).padStart(2, '0');
  } catch (e) {
    while (out.length < n) out += Math.floor(Math.random() * 16).toString(16);
  }
  return out.slice(0, n);
}

export function getVisitToken() {
  try {
    const existing = window.sessionStorage.getItem(KEY);
    if (existing && /^[0-9a-f]{16,32}$/.test(existing)) return existing;
    const fresh = randomHex(24);
    window.sessionStorage.setItem(KEY, fresh);
    return fresh;
  } catch (e) {
    return randomHex(24);
  }
}

export function recordPageView({ path, page, language } = {}) {
  try {
    const body = JSON.stringify({
      visit: getVisitToken(),
      path: path || (window.location.pathname + window.location.search),
      page: page || '',
      language: language || '',
      referrer: document.referrer || '',
    });
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const ok = navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }));
      if (ok) return;
    }
    if (typeof fetch === 'function') {
      const p = fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
      });
      if (p && typeof p.catch === 'function') p.catch(() => {});
    }
  } catch (e) {
    // silent
  }
}
