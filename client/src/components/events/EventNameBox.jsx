import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { dateLabel } from './eventsFormat';

const BLUR_DELAY_MS = 150;

// The names list is fetched once per page load and shared by every box.
let namesPromise = null;
export function __resetEventNamesForTests() { namesPromise = null; }

function loadNames() {
  if (!namesPromise) {
    namesPromise = fetch('/api/events/names')
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => (Array.isArray(d) ? d : []))
      .catch(() => { namesPromise = null; return []; });
  }
  return namesPromise;
}

/** Lower case with accents removed, so "Cannae" and "cánnae" meet. */
export function fold(s) {
  return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/**
 * The events the list shows. With nothing typed, every event that has passages or
 * documents, in alphabetical order, so the list can be browsed like a dropdown.
 * With text typed, the events whose label or place contains it: matches at the
 * start of the label first, then at the start of a word of the label, then the
 * rest, each group in the list's own order.
 */
export function suggestEvents(names, typed, limit = Infinity) {
  const t = fold(typed.trim());
  if (!t) {
    return names
      .filter((n) => (n.n_passages || 0) + (n.n_documents || 0) > 0)
      .slice()
      .sort((a, b) => String(a.label).localeCompare(String(b.label)))
      .slice(0, limit);
  }
  const groups = [[], [], []];
  for (const n of names) {
    const label = fold(n.label);
    const place = fold(n.place);
    if (!label.includes(t) && !place.includes(t)) continue;
    if (label.startsWith(t)) groups[0].push(n);
    else if (label.split(/[^a-z0-9]+/).some((w) => w.startsWith(t))) groups[1].push(n);
    else groups[2].push(n);
  }
  return groups.flat().slice(0, limit);
}

/**
 * The "Search by name or place" box of the Events page, a dropdown you can type
 * into. A click opens the list of every event with passages or documents, in
 * alphabetical order, and typing narrows it. The arrow button opens and closes
 * the list. Enter with nothing highlighted submits the surrounding form.
 */
export default function EventNameBox({ value, onChange, openEvent }) {
  const [names, setNames] = useState(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const boxRef = useRef(null);
  const blurTimer = useRef(null);
  const listId = useId();

  const suggestions = useMemo(() => (names ? suggestEvents(names, value) : []), [names, value]);
  const typed = value.trim().length > 0;
  const noMatch = open && typed && names !== null && suggestions.length === 0;
  const expanded = open && suggestions.length > 0;

  useEffect(() => {
    const away = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', away);
    return () => { document.removeEventListener('mousedown', away); clearTimeout(blurTimer.current); };
  }, []);

  const choose = (n) => { setOpen(false); setActive(-1); openEvent(n.id); };

  const onKeyDown = (e) => {
    if (e.key === 'Escape') { setOpen(false); setActive(-1); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!suggestions.length) return;
      e.preventDefault();
      setOpen(true);
      const step = e.key === 'ArrowDown' ? 1 : -1;
      setActive((a) => (a + step + suggestions.length + (a < 0 && step < 0 ? 1 : 0)) % suggestions.length);
      return;
    }
    if (e.key === 'Enter' && expanded && active >= 0 && suggestions[active]) {
      e.preventDefault();
      choose(suggestions[active]);
    }
  };

  return (
    <div ref={boxRef} className="relative">
      <label className="block text-xs text-gray-600">
        Search by name or place
        <span className="relative mt-1 block">
        <input value={value} placeholder="Choose an event or type a name" autoComplete="off"
               role="combobox" aria-autocomplete="list" aria-expanded={expanded}
               aria-controls={listId}
               aria-activedescendant={expanded && active >= 0 ? `${listId}-${active}` : undefined}
               onFocus={() => { setOpen(true); loadNames().then(setNames); }}
               onChange={(e) => { onChange(e.target.value); setOpen(true); setActive(-1); }}
               onKeyDown={onKeyDown}
               onBlur={() => { blurTimer.current = setTimeout(() => setOpen(false), BLUR_DELAY_MS); }}
               className="block w-full border border-gray-300 rounded pl-2 pr-8 py-1.5 text-sm text-gray-900" />
        <button type="button" tabIndex={-1} aria-label={expanded ? 'Close the list of events' : 'Show the list of events'}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => { loadNames().then(setNames); setOpen((o) => !o); setActive(-1); }}
                className="absolute inset-y-0 right-0 px-2 text-gray-500 hover:text-gray-800">
          <span aria-hidden="true">▾</span>
        </button>
        </span>
      </label>
      <ul id={listId} role="listbox" aria-label="Events" hidden={!expanded}
          className="absolute z-20 left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-96 overflow-auto">
        {expanded && suggestions.map((n, i) => (
          <li key={n.id} id={`${listId}-${i}`} role="option" aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(n)}
              onMouseEnter={() => setActive(i)}
              className={`px-3 py-2 cursor-pointer text-sm ${i === active ? 'bg-red-50' : ''}`}>
            <span className="font-bold text-gray-900">{n.label}</span>
            <span className="text-xs text-gray-500">
              {' '}{[dateLabel(n.year_start, n.year_end), n.place].filter(Boolean).join(' · ')}
            </span>
            {(n.n_passages || 0) + (n.n_documents || 0) === 0 && (
              <span className="ml-2 text-[10px] uppercase tracking-wide text-gray-400">no passages yet</span>
            )}
          </li>
        ))}
      </ul>
      {noMatch && (
        <p className="absolute z-20 left-0 right-0 mt-1 text-xs text-gray-500 bg-white border border-gray-200 rounded px-3 py-2">
          No event by that name. Press Search to look through places and descriptions.
        </p>
      )}
    </div>
  );
}
