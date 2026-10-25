import { useState, useEffect, useRef, useCallback } from 'react';
import AskAWorkPage from '../ask/AskAWorkPage';
import ThemeSearchPage from './ThemeSearchPage';
import { SCOPES, SCOPE_LABELS, scopeFromSearch } from '../../hooks/routePaths';

/**
 * Theme Search, one page with three scopes (2026-10-25): One text (the
 * passages of one work on a subject), Two texts (two works read against each
 * other) and Whole corpus (every indexed language at once). The scope is in
 * the address as ?scope=one|two|corpus, so a link reopens the right form.
 * Changing scope keeps the words typed in the query box where the two forms
 * share one (One text and Whole corpus), and starts the other parameters clean.
 */
export default function ThemeSearchScopes() {
  const [scope, setScope] = useState(() => scopeFromSearch(window.location.search));
  const [prefill, setPrefill] = useState('');
  const typed = useRef('');
  const onQueryChange = useCallback((q) => { typed.current = q; }, []);

  // The address always carries the scope, so it reads the same after a reload.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get('scope') !== scope) {
      p.set('scope', scope);
      window.history.replaceState({}, '', `/theme-search?${p.toString()}`);
    }
    document.title = `Theme Search: ${SCOPE_LABELS[scope].toLowerCase()} — Tesserae`;
  }, [scope]);

  const choose = (next) => {
    if (next === scope) return;
    const carry = (typed.current || '').trim();
    const p = new URLSearchParams({ scope: next });
    window.history.replaceState({}, '', `/theme-search?${p.toString()}`);
    setPrefill(next === 'two' ? '' : carry);
    setScope(next);
  };

  return (
    <div>
      <div className={`${scope === 'one' ? 'max-w-6xl' : 'max-w-4xl'} mx-auto px-6 pt-6`}>
        <div className="max-w-4xl">
        <h1 className="text-2xl font-semibold text-gray-900">
          Theme Search<span className="sr-only">: {SCOPE_LABELS[scope].toLowerCase()}</span>
        </h1>
        <div className="mt-3 inline-flex rounded border border-gray-300 overflow-hidden text-sm" role="group" aria-label="Scope of the search">
          {SCOPES.map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => choose(v)}
              aria-pressed={scope === v}
              data-testid={`scope-${v}`}
              className={`px-3 py-1.5 font-medium ${scope === v ? 'bg-red-700 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}
            >
              {SCOPE_LABELS[v]}
            </button>
          ))}
        </div>
        </div>
      </div>
      {scope === 'one'
        ? <AskAWorkPage key="one" prefill={prefill} onQueryChange={onQueryChange} />
        : <ThemeSearchPage key={scope} scopeName={scope} prefill={prefill} onQueryChange={onQueryChange} />}
    </div>
  );
}
