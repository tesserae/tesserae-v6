// The Place control of the documents search: a text box with suggestions.
// There are about 6,600 findspots, too many for a drop-down, so the reader
// types two letters and sees up to twelve matching places with their
// document counts (/api/documents/places). What is in the box is what the
// search sends (`value`), whether it was typed or chosen from the list; the
// server matches it against the ancient and the modern name of a findspot.
import { useEffect, useRef, useState } from 'react';

const MIN_CHARS = 2;
const MAX_SUGGESTIONS = 12;
const DELAY_MS = 200;

export default function PlaceFilter({ value, onChange, language = '' }) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  // The text the list was last asked for, so choosing a suggestion (which
  // changes `value`) closes the list instead of asking for it again.
  const chosen = useRef('');

  useEffect(() => {
    const text = (value || '').trim();
    if (text.length < MIN_CHARS || text === chosen.current) {
      setSuggestions([]);
      return undefined;
    }
    let dead = false;
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ q: text, limit: String(MAX_SUGGESTIONS) });
      if (language) params.set('language', language);
      fetch(`/api/documents/places?${params.toString()}`)
        .then(r => (r.ok ? r.json() : null))
        .then(data => { if (!dead && data) setSuggestions(data.places || []); })
        .catch(() => {});
    }, DELAY_MS);
    return () => { dead = true; clearTimeout(timer); };
  }, [value, language]);

  const choose = (place) => {
    chosen.current = place.value;
    setSuggestions([]);
    setOpen(false);
    onChange(place.value);
  };

  return (
    <div className="relative">
      <label htmlFor="doc-filter-place" className="block text-xs text-gray-500 mb-1">Place</label>
      <input
        id="doc-filter-place"
        type="text"
        role="combobox"
        aria-expanded={open && suggestions.length > 0}
        aria-controls="doc-filter-place-list"
        autoComplete="off"
        value={value}
        placeholder="e.g., Rusellae"
        onChange={e => { chosen.current = ''; setOpen(true); onChange(e.target.value); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={e => { if (e.key === 'Escape') setOpen(false); }}
        className="w-full border rounded px-2 py-1.5 text-sm bg-white"
      />
      {open && suggestions.length > 0 && (
        <ul id="doc-filter-place-list" role="listbox"
            className="absolute z-20 left-0 mt-1 w-72 max-w-[90vw] bg-white border rounded shadow-lg text-sm max-h-72 overflow-auto">
          {suggestions.map(p => (
            <li key={p.value} role="option" aria-selected={p.value === value}>
              {/* mouse down, not click: the box loses focus (and closes the list) before a click lands */}
              <button type="button"
                      onMouseDown={e => { e.preventDefault(); choose(p); }}
                      className="w-full text-left px-2 py-1.5 hover:bg-gray-100 flex justify-between gap-2">
                <span>{p.label}</span>
                <span className="text-gray-500">{p.count.toLocaleString('en-US')}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
