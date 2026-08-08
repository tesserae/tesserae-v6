import React, { useState, useEffect } from 'react';
import { transliterateToCoptic } from '../../utils/copticUtils';

// Coptic search input with live Leipzig-Jerusalem transliteration.
//
// There is no standard Coptic keyboard on macOS/Windows, so users type in
// Latin (e.g. "rOme", "shEre") and see the Coptic build up live; the Coptic
// is what gets searched. Pasting real Coptic also works (the converter is a
// no-op on characters that are already Coptic). The Latin buffer is kept
// separate from the emitted value so digraphs like "sh" resolve correctly
// while typing.
//
// All Coptic glyphs shown here (the preview and the key hints) are COMPUTED
// from the transliterator, never hard-coded, so the source contains no
// non-Latin literals.

const HINT_KEYS = ['sh', 'E', 'O', 'h', 'c', 'j', '+'];

export default function CopticSearchInput({ value, onChange, onEnter, placeholder, className = '' }) {
  const [buffer, setBuffer] = useState('');

  // Reset the Latin buffer when the parent clears the query (e.g. on a
  // language switch), so a stale transliteration doesn't linger.
  useEffect(() => {
    if (value === '') setBuffer('');
  }, [value]);

  const handleChange = (e) => {
    const raw = e.target.value;
    setBuffer(raw);
    onChange(transliterateToCoptic(raw));
  };

  const coptic = transliterateToCoptic(buffer);
  const showPreview = buffer && coptic !== buffer;

  return (
    <div className={className}>
      <input
        type="text"
        value={buffer}
        onChange={handleChange}
        onKeyDown={(e) => e.key === 'Enter' && onEnter && onEnter()}
        placeholder={placeholder}
        className="w-full border rounded px-4 py-2"
      />
      <div className="text-xs text-gray-500 mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {showPreview && (
          <span>
            Coptic: <span className="text-base text-gray-800">{coptic}</span>
          </span>
        )}
        <span className="text-gray-400">
          Type in Latin (Leipzig-Jerusalem):{' '}
          {HINT_KEYS.map((k) => `${k}→${transliterateToCoptic(k)}`).join('  ')}
        </span>
      </div>
    </div>
  );
}
