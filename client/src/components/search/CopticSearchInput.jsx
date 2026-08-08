import React, { useState, useEffect, useRef } from 'react';
import { transliterateToCoptic, COPTIC_ALPHABET } from '../../utils/copticUtils';

// Coptic search input with live Leipzig-Jerusalem transliteration and an
// optional clickable letter palette.
//
// There is no standard Coptic keyboard on macOS/Windows, so users type in
// Latin (e.g. "rOme", "shEre") and see the Coptic build up live; the Coptic is
// what gets searched. Pasting real Coptic also works, and clicking a letter in
// the palette inserts it at the cursor — the converter is a no-op on
// characters that are already Coptic, so typing and clicking mix freely.
//
// All Coptic glyphs shown here (the preview, the key hints, the palette) are
// COMPUTED / codepoint-generated, never hard-coded, so this source contains no
// non-Latin literals.

const HINT_KEYS = ['sh', 'E', 'O', 'h', 'c', 'j', '+'];

export default function CopticSearchInput({ value, onChange, onEnter, placeholder, className = '' }) {
  const [buffer, setBuffer] = useState('');
  const [paletteOpen, setPaletteOpen] = useState(false);
  const inputRef = useRef(null);

  // Reset the Latin buffer when the parent clears the query (e.g. on a
  // language switch), so a stale transliteration doesn't linger.
  useEffect(() => {
    if (value === '') setBuffer('');
  }, [value]);

  const commit = (next, caret) => {
    setBuffer(next);
    onChange(transliterateToCoptic(next));
    if (caret != null) {
      // Restore focus and caret after a palette insertion.
      requestAnimationFrame(() => {
        const el = inputRef.current;
        if (el) {
          el.focus();
          el.setSelectionRange(caret, caret);
        }
      });
    }
  };

  const handleChange = (e) => commit(e.target.value);

  const insertChar = (ch) => {
    const el = inputRef.current;
    const start = el ? el.selectionStart : buffer.length;
    const end = el ? el.selectionEnd : buffer.length;
    const next = buffer.slice(0, start) + ch + buffer.slice(end);
    commit(next, start + ch.length);
  };

  const coptic = transliterateToCoptic(buffer);
  const showPreview = buffer && coptic !== buffer;

  return (
    <div className={className}>
      <input
        ref={inputRef}
        type="text"
        value={buffer}
        onChange={handleChange}
        onKeyDown={(e) => e.key === 'Enter' && onEnter && onEnter()}
        placeholder={placeholder}
        className="w-full border rounded px-4 py-2"
      />

      {paletteOpen && (
        <div className="mt-2 p-2 border rounded bg-gray-50 flex flex-wrap gap-1">
          {COPTIC_ALPHABET.map(({ char, key }) => (
            <button
              key={char}
              type="button"
              onClick={() => insertChar(char)}
              title={`type: ${key}`}
              className="w-9 h-9 flex items-center justify-center text-lg leading-none border rounded bg-white text-gray-800 hover:bg-blue-50 hover:border-blue-300"
            >
              {char}
            </button>
          ))}
        </div>
      )}

      <div className="text-xs text-gray-500 mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {showPreview && (
          <span>
            Coptic: <span className="text-base text-gray-800">{coptic}</span>
          </span>
        )}
        <button
          type="button"
          onClick={() => setPaletteOpen((open) => !open)}
          className="text-blue-600 hover:underline"
          aria-expanded={paletteOpen}
        >
          {paletteOpen ? 'Hide letters' : 'Insert letters'}
        </button>
        <span className="text-gray-400">
          Type in Latin (Leipzig-Jerusalem):{' '}
          {HINT_KEYS.map((k) => `${k}→${transliterateToCoptic(k)}`).join('  ')}
        </span>
      </div>
    </div>
  );
}
