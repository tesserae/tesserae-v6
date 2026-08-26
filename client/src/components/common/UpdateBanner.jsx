import { useEffect, useState } from 'react';

/**
 * Tells the reader when the page they are running is out of date.
 *
 * WHY THIS EXISTS
 *
 * index.html is served with no Cache-Control, so a browser may keep a copy for
 * hours. Every frontend deploy renames the bundle, so a stale page asks for a
 * file that is no longer there. Apache falls back to index.html for any unknown
 * path, which means the request returns 200 OK with Content-Type text/html: the
 * PAGE, pretending to be JavaScript. The browser tries to execute HTML, fails at
 * parse, and nothing runs at all. No app, no error handler, no message. NC hit
 * this twice in one day and both times it looked like the feature was broken.
 *
 * Keeping old bundles on disk stops the hard failure: a stale page then loads
 * its old JavaScript and works, one version behind. This tells the reader that
 * is what is happening, instead of leaving them on old code indefinitely.
 *
 * The real fix is a Cache-Control header on index.html, which needs a change to
 * the Apache vhost. This is the half that does not need root.
 */

/** The bundle this code is running from, e.g. "index-CsZxXAwc.js". */
function runningBundle() {
  try {
    const m = String(import.meta.url).match(/(index-[A-Za-z0-9_-]+\.js)/);
    return m ? m[1] : null;
  } catch {
    return null;
  }
}

const CHECK_EVERY_MS = 10 * 60 * 1000;

export default function UpdateBanner() {
  const [stale, setStale] = useState(false);

  useEffect(() => {
    const mine = runningBundle();
    // In development the module is not a hashed bundle; nothing to compare.
    if (!mine) return undefined;

    let cancelled = false;
    const check = async () => {
      try {
        const res = await fetch('/api/version', { cache: 'no-store' });
        const d = await res.json();
        // Only ever report staleness, never the reverse: a failed check must not
        // clear a banner the reader has already been shown.
        if (!cancelled && d?.bundle && d.bundle !== mine) setStale(true);
      } catch {
        /* offline or the endpoint is unavailable; say nothing */
      }
    };

    check();
    const timer = window.setInterval(check, CHECK_EVERY_MS);
    // Coming back to a tab left open overnight is the commonest way to be stale.
    const onFocus = () => check();
    window.addEventListener('focus', onFocus);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener('focus', onFocus);
    };
  }, []);

  if (!stale) return null;

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-sm text-amber-900 flex items-center justify-center gap-3 flex-wrap">
      <span>A newer version of Tesserae is available. This page is running an older one.</span>
      <button
        onClick={() => window.location.reload(true)}
        className="px-3 py-1 rounded bg-amber-700 text-white text-xs font-medium hover:bg-amber-800"
      >
        Reload
      </button>
    </div>
  );
}
