import { useState, useEffect, useCallback } from 'react';
import { LoadingSpinner } from '../common';
import TextPane from './TextPane';
import ConnectionGutter from './ConnectionGutter';
import ResultsPanel from './ResultsPanel';

const DEFAULT_WORK = 'vergil.aeneid.part.6.tess';
const DEFAULT_LANGUAGE = 'la';

/**
 * The Reader: read a text, select a passage, see what the corpus connects to it.
 *
 * This inverts the site's usual stance. The search pages serve a scholar who
 * already has a hypothesis ("compare these two works"); the Reader serves one
 * who is reading and wants to know what a passage touches. Results open in the
 * Reader in turn, so the corpus can be followed by association.
 */
export default function ReaderPage() {
  const [work, setWork] = useState(() => paramOr('work', DEFAULT_WORK));
  const [language, setLanguage] = useState(() => paramOr('lang', DEFAULT_LANGUAGE));
  const [units, setUnits] = useState([]);
  const [metadata, setMetadata] = useState(null);
  const [selection, setSelection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load the work's text.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSelection(null);
    fetch(`/api/text/${encodeURIComponent(work)}?language=${language}`)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        if (d.error) { setError(d.error); return; }
        setUnits(d.units || []);
        setMetadata(d.metadata || null);
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [work, language]);

  // Keep the URL in step, so any passage is linkable and Back works.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    p.set('work', work);
    p.set('lang', language);
    if (selection?.refStart) p.set('at', selection.refStart); else p.delete('at');
    window.history.replaceState({}, '', `${window.location.pathname}?${p}`);
  }, [work, language, selection]);

  /** Open a result in the Reader, which is what makes the corpus browsable. */
  const openPassage = useCallback((result) => {
    if (!result?.work) return;
    setWork(result.work.endsWith('.tess') ? result.work : `${result.work}.tess`);
    setLanguage(result.language || 'la');
    window.scrollTo({ top: 0 });
  }, []);

  const title = metadata
    ? `${metadata.author || ''} ${metadata.title || ''}`.trim()
    : prettyWork(work.replace('.tess', ''));

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 flex-wrap">
        <h2 className="font-semibold text-gray-900" style={{ fontFamily: '"Gentium Book Plus", Georgia, serif' }}>
          {title || 'Reader'}
        </h2>
        {selection && (
          <span className="text-sm text-gray-500">
            {selection.lineCount} line{selection.lineCount === 1 ? '' : 's'} selected
          </span>
        )}
        <button
          onClick={() => setSelection(null)}
          className={`ml-auto text-sm text-gray-500 hover:text-gray-700 ${selection ? '' : 'invisible'}`}
        >
          Clear selection
        </button>
      </div>

      {loading && <div className="p-10"><LoadingSpinner /></div>}
      {error && <p className="p-6 text-red-700">{error}</p>}

      {!loading && !error && (
        <div className="flex flex-col lg:flex-row" style={{ minHeight: '32rem' }}>
          <div className="flex flex-col flex-1 min-w-0">
            {/* The key for the gutter marks. The gutter itself is nine pixels
                wide per column and can only carry a letter, and its tooltip does
                not exist on a phone, so the words go here where there is room.
                Without this a reader saw two columns of coloured squares beside
                the poem and had no way to find out what they were. */}
            <p className="px-3 py-1.5 text-[11px] text-gray-600 border-b border-gray-200 bg-gray-50 flex flex-wrap gap-x-4 gap-y-1">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-[9px] h-[7px] rounded-sm bg-red-700" />
                <strong className="font-semibold text-gray-700">W</strong>
                shared wording
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-[9px] h-[7px] rounded-sm bg-amber-600" />
                <strong className="font-semibold text-gray-700">C</strong>
                similar content, wording need not match
              </span>
              <span className="text-gray-500">darker means more; select a line to see them</span>
            </p>
          <div className="flex flex-1 min-w-0">
            <ConnectionGutter
              work={work.replace('.tess', '')}
              units={units}
              onSelectLine={(u) => {
                const i = units.findIndex((x) => x.ref === u.ref);
                setSelection({ startIdx: i, endIdx: i, refStart: u.ref, refEnd: u.ref, lineCount: 1 });
              }}
            />
            <TextPane
              units={units}
              language={language}
              selection={selection}
              onSelect={setSelection}
            />
            </div>
          </div>
          <ResultsPanel
            selection={selection}
            language={language}
            work={work.replace('.tess', '')}
            units={units}
            onOpenPassage={openPassage}
          />
        </div>
      )}
    </div>
  );
}

function paramOr(name, fallback) {
  const v = new URLSearchParams(window.location.search).get(name);
  return v || fallback;
}

/** "vergil.aeneid.part.6" -> "Vergil, Aeneid 6", good enough for a result label. */
function prettyWork(work) {
  if (!work) return '';
  const parts = String(work).replace(/\.tess$/, '').split('.');
  const author = cap(parts[0] || '');
  const title = cap(parts[1] || '');
  const partIdx = parts.indexOf('part');
  const book = partIdx > -1 ? ` ${parts[partIdx + 1]}` : '';
  return title ? `${author}, ${title}${book}` : author;
}

function cap(s) {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
