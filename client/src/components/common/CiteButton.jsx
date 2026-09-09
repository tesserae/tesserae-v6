import { useEffect, useRef, useState } from 'react';
import { CITATION_STYLES, buildCitation } from '../../utils/citation';

/**
 * "Cite" for a finding: a small control that opens the reference in three
 * styles and copies the chosen one.
 *
 * The reproducible style leads because it is the one that does work a
 * bibliography reference cannot: it names the corpus version and the search,
 * so a reader can rerun it. The other two are there because journals ask for
 * them (interface audit, 2026-09-08).
 *
 * @param {object} finding fields described in utils/citation.js
 * @param {string} [label] the button's text
 */
export default function CiteButton({ finding, label = 'Cite', className = '' }) {
  const [open, setOpen] = useState(false);
  const [style, setStyle] = useState('reproducible');
  const [copied, setCopied] = useState(false);
  const boxRef = useRef(null);
  const btnRef = useRef(null);

  // Closes on a click elsewhere or on Escape, and hands focus back to the
  // button, so the control can be used and left without a mouse.
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)
          && btnRef.current && !btnRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { setOpen(false); btnRef.current?.focus(); }
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const text = buildCitation(style, finding);

  const copy = () => {
    if (!navigator.clipboard?.writeText) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }).catch(() => {});
  };

  return (
    <span className={`relative inline-block ${className}`}>
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="text-xs px-2 py-1 rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
      >
        {label}
      </button>
      {open && (
        <div
          ref={boxRef}
          role="dialog"
          aria-label="Cite this finding"
          className="absolute right-0 z-50 mt-1 w-[22rem] max-w-[85vw] rounded border border-gray-300
                     bg-white shadow-lg p-3 text-left"
        >
          <div className="flex rounded border border-gray-300 overflow-hidden mb-2">
            {CITATION_STYLES.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => setStyle(s.key)}
                aria-pressed={style === s.key}
                className={`flex-1 px-2 py-1 text-xs font-medium ${
                  style === s.key ? 'bg-gray-100 text-gray-900' : 'bg-white text-gray-600 hover:text-gray-900'}`}
              >
                {s.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-gray-600 mb-2 leading-snug">
            {CITATION_STYLES.find((s) => s.key === style)?.note}
          </p>
          <textarea
            readOnly
            value={text}
            rows={5}
            aria-label="Citation text"
            onFocus={(e) => e.target.select()}
            className="w-full text-xs font-mono border border-gray-200 rounded p-2 bg-gray-50
                       text-gray-800 resize-none"
          />
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              onClick={copy}
              className="text-xs font-semibold px-3 py-1.5 rounded bg-red-700 text-white hover:bg-red-800"
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
            <button
              type="button"
              onClick={() => { setOpen(false); btnRef.current?.focus(); }}
              className="text-xs px-3 py-1.5 rounded border border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              Close
            </button>
            {!finding.corpusVersion && (
              <span className="text-[11px] text-gray-500">
                No corpus version for this search
              </span>
            )}
          </div>
        </div>
      )}
    </span>
  );
}
