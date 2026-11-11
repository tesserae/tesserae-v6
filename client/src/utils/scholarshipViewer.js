// The address of the scholarship viewer page (/scholarship/view), built the same
// way from the Reader's tab, the Events pages and the Ask page, so the three
// entry links and the page agree on the parameter names.
import { bareLocus } from '../components/reader/refId';

export const VIEWER_PATH = '/scholarship/view';

/** The work id the citation indexes use: the Reader's file id without ".tess" or a ".part.N" suffix. */
export function viewerWorkId(work) {
  return String(work || '').replace(/\.tess$/, '').replace(/\.part\.\d+.*$/, '');
}

/** The viewer address for a work and, optionally, a passage ("1.1" to "1.33", or full refs). */
export function viewerHref({ work, lo, hi, scope } = {}) {
  const id = viewerWorkId(work);
  if (!id) return VIEWER_PATH;
  const p = new URLSearchParams({ work: id });
  const a = lo ? bareLocus(lo) : '';
  const b = hi ? bareLocus(hi) : a;
  if (a) { p.set('lo', a); if (b && b !== a) p.set('hi', b); }
  p.set('scope', scope || (a ? 'passage' : 'work'));
  return `${VIEWER_PATH}?${p.toString()}`;
}

// Compares two loci ("6.111.1" and "7.1.1") part by part, numbers as numbers.
export function compareLoci(a, b) {
  const x = String(a).split('.'); const y = String(b).split('.');
  for (let i = 0; i < Math.max(x.length, y.length); i += 1) {
    const m = parseInt(x[i], 10); const n = parseInt(y[i], 10);
    if (Number.isNaN(m) || Number.isNaN(n)) { if (x[i] !== y[i]) return String(x[i] ?? '').localeCompare(String(y[i] ?? '')); } else if (m !== n) return m - n;
  }
  return 0;
}
