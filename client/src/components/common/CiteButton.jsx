import { useEffect, useRef, useState } from 'react';
import { CITATION_STYLES, buildCitation } from '../../utils/citation';
import RequestDialog from './RequestDialog';

/** The same finding the citation is built from, reshaped into the context
 * block the requests-workflow dialog shows and files (requests workflow,
 * 2026-10-08). Putting the link here, rather than in each result-card
 * component, means every result that already offers Cite gets it for free. */
function contextFromFinding(finding) {
  return {
    page_url: typeof window !== 'undefined' ? window.location.href : undefined,
    language: finding?.language,
    search_type: finding?.kind,
    settings: finding?.ranking,
    source: finding?.source,
    target: finding?.target,
    score: typeof finding?.score === 'number' ? finding.score.toFixed(3) : finding?.score,
    channels: finding?.channels,
  };
}

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
export default function CiteButton({ finding, label = 'Cite', className = '', showReportLink = false }) {
  const [open, setOpen] = useState(false);
  const [style, setStyle] = useState('reproducible');
  const [copied, setCopied] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  // Open the popup toward whichever side has room: a Cite button near the
  // left edge of the page (the cross-language cards) opened it off-screen.
  const [alignLeft, setAlignLeft] = useState(false);
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
        onClick={() => {
          const r = btnRef.current?.getBoundingClientRect();
          if (r) setAlignLeft(r.right < Math.min(352, window.innerWidth * 0.85) + 16);
          setOpen((v) => !v);
        }}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="text-xs px-2 py-1 rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
      >
        {label}
      </button>
      {showReportLink && (
        // A marked link on the card itself: readers do not think to look
        // inside Cite to report a problem.
        <button
          type="button"
          onClick={() => setReportOpen(true)}
          className="ml-2 inline-flex items-center gap-1 text-xs text-red-700 hover:underline align-middle"
        >
          <svg aria-hidden="true" viewBox="0 0 16 16" width="12" height="12" fill="none" className="shrink-0"><path d="M11 2.5l2.5 2.5L6 12.5H3.5V10L11 2.5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>
          Report a problem
        </button>
      )}
      {open && (
        <div
          ref={boxRef}
          role="dialog"
          aria-label="Cite this finding"
          className={`absolute ${alignLeft ? 'left-0' : 'right-0'} z-50 mt-1 w-[22rem] max-w-[85vw] rounded border border-gray-300
                     bg-white shadow-lg p-3 text-left`}
        >
          {/* One citation of the project covers a whole publication; the
              citation built below is for a reader who wants to point to
              this specific parallel, and stays available underneath (owner's
              review, 2026-10-08). */}
          <p className="text-[11px] text-gray-600 mb-2 pb-2 border-b border-gray-100 leading-snug">
            One citation of Tesserae per publication is enough. Individual parallels do
            not need their own.{' '}
            <button
              type="button"
              onClick={() => window.dispatchEvent(new CustomEvent('tesserae:open-how-to-cite'))}
              className="text-red-700 hover:underline font-medium"
            >
              How to cite Tesserae
            </button>
          </p>
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
          {/* The display citation above is a name ("Hafez, Diwan 5097"); the
              id Tesserae actually stores it under stays available here, the
              same way a DOI or a shelf number rides along with a readable
              title (result card tidy, 2026-10-08). */}
          {finding.siteId && (
            <p className="text-[11px] text-gray-500 mt-2 pt-1.5 border-t border-gray-100">
              Site ID: {finding.siteId}
            </p>
          )}
          {/* Requests workflow (2026-10-08): living here, rather than on each
              result-card component, means every card that already shows
              Cite gets this link with no change of its own. */}
          <p className="mt-2 pt-1.5 border-t border-gray-100">
            <button
              type="button"
              onClick={() => { setOpen(false); setReportOpen(true); }}
              className="inline-flex items-center gap-1 text-[11px] text-red-700 hover:underline"
            >
              <svg aria-hidden="true" viewBox="0 0 16 16" width="12" height="12" fill="none" className="shrink-0"><path d="M11 2.5l2.5 2.5L6 12.5H3.5V10L11 2.5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>
              Report a problem with this result
            </button>
          </p>
        </div>
      )}
      <RequestDialog
        isOpen={reportOpen}
        onClose={() => setReportOpen(false)}
        type="result-problem"
        context={contextFromFinding(finding)}
      />
    </span>
  );
}
