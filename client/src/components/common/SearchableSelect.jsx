import { useState, useEffect, useMemo, useRef, useId } from 'react';

/**
 * A type-to-find dropdown: a regular menu you can also filter by typing.
 *
 * Generalises SearchableAuthorSelect (which now wraps this) so every menu
 * that lists names long enough to scroll through -- authors, works, books,
 * sections -- gets the same behaviour: click it open like an ordinary
 * dropdown, or type the first letters and the matching name comes up. Below
 * the `sm` breakpoint it falls back to a native `<select>`, which is what a
 * phone keyboard and screen reader already know how to drive.
 *
 * Matching ignores case and diacritics, and ranks a name whose label (or any
 * word in it) STARTS with what was typed above one that merely contains it,
 * so "cur" finds "Curtius Rufus" before "Securus", and "theo" finds
 * "Theocritus" the same way "θεο" finds "Θεόκριτος".
 */

// NFD-decompose then drop the combining marks that decomposition splits off
// (accents, breathings, iota subscripts), so comparison runs on bare letters.
const DIACRITICS = /[̀-ͯ]/g;
function normalize(s) {
  return String(s || '').normalize('NFD').replace(DIACRITICS, '').toLowerCase();
}

// Splits a label into words for the "starts with" test, so "Curtius Rufus"
// matches on "Rufus" too, not only from the first letter of the whole label.
const WORD_SPLIT = /[\s,;:()/-]+/;

function filterOptions(options, filter) {
  if (!filter) return options;
  const nf = normalize(filter);
  if (!nf) return options;
  const starts = [];
  const contains = [];
  for (const o of options) {
    const label = normalize(o.label);
    if (label.startsWith(nf) || label.split(WORD_SPLIT).some((w) => w.startsWith(nf))) {
      starts.push(o);
    } else if (label.includes(nf)) {
      contains.push(o);
    }
  }
  return [...starts, ...contains];
}

const SearchableSelect = ({
  value,
  onChange,
  options,
  ariaLabel,
  placeholder,
  disabled,
  className,
}) => {
  const uid = useId();
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const listRef = useRef(null);

  const safeOptions = Array.isArray(options) ? options : [];

  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const [editing, setEditing] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  // What to fall back to if the user escapes without choosing -- the value
  // as of the moment this open/type session began, not necessarily `value`
  // itself at every instant (onChange only ever fires on commit, so in
  // practice `value` never moves while a session is open; kept anyway as
  // the one place that invariant is documented and could be leaned on).
  const previousValueRef = useRef(value);

  const filteredOptions = useMemo(
    () => filterOptions(safeOptions, filter),
    [safeOptions, filter]
  );

  const selectedOption = safeOptions.find((o) => o.value === value);
  const displayValue = editing ? filter : (selectedOption ? selectedOption.label : '');

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
        setEditing(false);
        setFilter('');
        setHighlight(-1);
      }
    };
    document.addEventListener('pointerdown', handleClickOutside);
    return () => document.removeEventListener('pointerdown', handleClickOutside);
  }, []);

  // Scroll the highlighted option into view, including the initial one when
  // the list opens on the current choice.
  useEffect(() => {
    if (!open || highlight < 0) return;
    const el = listRef.current?.querySelector(`[data-index="${highlight}"]`);
    if (el) el.scrollIntoView({ block: 'nearest' });
  }, [open, highlight]);

  const openFullList = () => {
    previousValueRef.current = value;
    setFilter('');
    setEditing(true);
    setOpen(true);
    const idx = safeOptions.findIndex((o) => o.value === value);
    setHighlight(idx >= 0 ? idx : (safeOptions.length ? 0 : -1));
  };

  const commit = (option) => {
    if (!option) return;
    onChange(option.value);
    setFilter('');
    setEditing(false);
    setOpen(false);
    setHighlight(-1);
  };

  const cancel = () => {
    setFilter('');
    setEditing(false);
    setOpen(false);
    setHighlight(-1);
    // `value` was never changed mid-session (onChange only fires on commit),
    // so there is nothing to restore beyond closing the display back to it.
    void previousValueRef.current;
  };

  const handleInputChange = (e) => {
    const text = e.target.value;
    setFilter(text);
    setEditing(true);
    setOpen(true);
    const next = filterOptions(safeOptions, text);
    setHighlight(next.length ? 0 : -1);
  };

  const handleKeyDown = (e) => {
    if (disabled) return;
    switch (e.key) {
      case 'ArrowDown': {
        e.preventDefault();
        if (!open) { openFullList(); return; }
        setHighlight((h) => {
          const n = filteredOptions.length;
          if (!n) return -1;
          return h < n - 1 ? h + 1 : h;
        });
        return;
      }
      case 'ArrowUp': {
        e.preventDefault();
        if (!open) { openFullList(); return; }
        setHighlight((h) => (h > 0 ? h - 1 : 0));
        return;
      }
      case 'Home': {
        if (!open) return;
        e.preventDefault();
        setHighlight(filteredOptions.length ? 0 : -1);
        return;
      }
      case 'End': {
        if (!open) return;
        e.preventDefault();
        setHighlight(filteredOptions.length ? filteredOptions.length - 1 : -1);
        return;
      }
      case 'Enter': {
        if (!open) return;
        e.preventDefault();
        commit(filteredOptions[highlight]);
        return;
      }
      case 'Escape': {
        if (!open) return;
        e.preventDefault();
        cancel();
        return;
      }
      case 'Tab': {
        // Leaves focus to move on (no preventDefault); just closes cleanly
        // behind it rather than relying on blur timing.
        if (open) cancel();
        return;
      }
      default:
        return;
    }
  };

  const listboxId = `${uid}-listbox`;
  const activeId = open && highlight >= 0 ? `${uid}-option-${highlight}` : undefined;

  const defaultClasses = 'w-full border rounded px-2 py-2 text-sm';
  const inputClasses = className || defaultClasses;

  return (
    <>
      {/* Phones: a native select, same options, same behaviour a screen
          reader or a phone keyboard already knows. No aria-label here: the
          desktop input below carries it, and both render at once in a test
          environment that does not evaluate the sm: breakpoint, so only one
          of the two may claim the accessible name (matches
          SearchableAuthorSelect, which this generalises). */}
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={`sm:hidden ${inputClasses}`}
      >
        {(!value || !selectedOption) && <option value="">{placeholder || ''}</option>}
        {safeOptions.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* Desktop: the type-to-find combobox. */}
      <div ref={containerRef} className="relative hidden sm:block">
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-label={ariaLabel}
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={activeId}
          placeholder={placeholder}
          disabled={disabled}
          value={displayValue}
          onChange={handleInputChange}
          onFocus={() => { if (!disabled) openFullList(); }}
          onClick={() => { if (!disabled && !open) openFullList(); }}
          onKeyDown={handleKeyDown}
          onBlur={() => { if (!open) { setEditing(false); setFilter(''); } }}
          className={`${inputClasses} pr-7 focus:outline-none focus:ring-1 focus:ring-red-600`}
        />
        <button
          type="button"
          tabIndex={-1}
          disabled={disabled}
          onPointerDown={(e) => {
            e.preventDefault();
            if (disabled) return;
            if (open) { cancel(); } else { inputRef.current?.focus(); }
          }}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-auto"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path d="M2.5 4.5L6 8l3.5-3.5" stroke="currentColor" strokeWidth="1.5"
                  strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        {open && (
          <div
            ref={listRef}
            id={listboxId}
            role="listbox"
            aria-label={ariaLabel}
            className="absolute z-50 w-full mt-1 bg-white border rounded shadow-lg max-h-56 overflow-y-auto"
          >
            {filteredOptions.length > 0 ? filteredOptions.map((o, i) => (
              <button
                key={o.value}
                type="button"
                id={`${uid}-option-${i}`}
                data-index={i}
                data-value={o.value}
                role="option"
                aria-selected={o.value === value}
                onPointerDown={(e) => { e.preventDefault(); commit(o); }}
                onMouseEnter={() => setHighlight(i)}
                className={`w-full text-left px-3 py-1.5 text-sm cursor-pointer ${
                  i === highlight ? 'bg-gray-100' : ''
                } ${o.value === value ? 'font-medium' : ''}`}
              >
                {o.label}
              </button>
            )) : <div className="px-3 py-2 text-sm text-gray-500">No matches</div>}
          </div>
        )}
      </div>
    </>
  );
};

export default SearchableSelect;
