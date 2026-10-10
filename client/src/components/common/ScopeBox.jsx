import { useEffect, useState } from 'react';
import { SEARCH_SCOPE, liveCovers } from '../../data/searchScope';
import { LANGUAGE_NAMES } from '../../utils/languageNames';

// "What this search does": one grey line at the top of a search page that opens
// to its scope, the texts and collections it covers, its limits and its
// measured performance. The facts come from data/searchScope.js. Live counts
// come from /api/scope and are fetched the first time a box is opened, then
// shared by every box on the page.

let countsPromise = null;

export function resetScopeCounts() {
  countsPromise = null;
}

function loadCounts() {
  if (!countsPromise) {
    countsPromise = (typeof fetch === 'function'
      ? fetch('/api/scope').then((r) => (r.ok ? r.json() : null))
      : Promise.resolve(null)
    ).catch(() => null);
  }
  return countsPromise;
}

function storageKey(id) {
  return `tesserae_scope_${id}`;
}

function readOpen(id) {
  try {
    return window.localStorage.getItem(storageKey(id)) === '1';
  } catch (e) {
    return false;
  }
}

function writeOpen(id, open) {
  try {
    window.localStorage.setItem(storageKey(id), open ? '1' : '0');
  } catch (e) {
    // Storage may be blocked. The box still works for this visit.
  }
}

export default function ScopeBox({ id, className = '' }) {
  const entry = SEARCH_SCOPE[id];
  const [open, setOpen] = useState(() => readOpen(id));
  const [counts, setCounts] = useState(null);

  useEffect(() => {
    if (!open) return undefined;
    let dead = false;
    loadCounts().then((c) => { if (!dead) setCounts(c); });
    return () => { dead = true; };
  }, [open]);

  if (!entry) return null;

  const toggle = () => {
    const next = !open;
    setOpen(next);
    writeOpen(id, next);
  };
  const openHelp = () => {
    window.dispatchEvent(new CustomEvent('tesserae:open-help', { detail: { section: entry.helpSection } }));
  };
  const covers = liveCovers(id, counts, LANGUAGE_NAMES) || entry.covers;
  const panelId = `scope-panel-${id}`;

  return (
    <div className={`rounded border border-gray-200 bg-white text-xs text-gray-600 ${className}`}
         data-testid={`scope-box-${id}`}>
      <div className="flex items-center gap-2 px-3 py-1.5">
        <p className={`min-w-0 flex-1 ${open ? '' : 'truncate'}`} title={open ? undefined : entry.does}>
          <span className="font-semibold text-gray-700">What this search does.</span>{' '}
          {entry.does}
        </p>
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={panelId}
          className="shrink-0 text-red-700 hover:underline"
        >
          {open ? 'Hide' : 'Details'}
        </button>
      </div>
      {open && (
        <div id={panelId} className="border-t border-gray-100 px-3 py-2 space-y-2">
          <section>
            <h4 className="font-semibold uppercase tracking-wide text-gray-500">Scope</h4>
            <p>{entry.scope}</p>
          </section>
          <section>
            <h4 className="font-semibold uppercase tracking-wide text-gray-500">Texts and collections</h4>
            <p>{covers}</p>
          </section>
          <section>
            <h4 className="font-semibold uppercase tracking-wide text-gray-500">Limits</h4>
            <p>{entry.limits}</p>
          </section>
          <section>
            <h4 className="font-semibold uppercase tracking-wide text-gray-500">Measured performance</h4>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left">
                <thead className="text-gray-500">
                  <tr>
                    <th className="py-1 pr-3 font-medium">Language</th>
                    <th className="py-1 pr-3 font-medium">Measured against</th>
                    <th className="py-1 pr-3 font-medium">Result</th>
                    <th className="py-1 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 align-top">
                  {entry.measured.map((m, i) => (
                    <tr key={i}>
                      <td className="py-1 pr-3">{m.language}</td>
                      <td className="py-1 pr-3">{m.against}</td>
                      <td className="py-1 pr-3">{m.result}</td>
                      <td className="py-1">{m.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-1">
              Every figure was measured against a published list or a test set and is dated, because the corpus and the scoring change.
            </p>
          </section>
          <button type="button" onClick={openHelp} className="text-red-700 hover:underline">
            More in Help
          </button>
        </div>
      )}
    </div>
  );
}
