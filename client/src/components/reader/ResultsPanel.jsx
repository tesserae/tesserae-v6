import { useState, useEffect } from 'react';
import { LoadingSpinner } from '../common';
import { ResultsInsight } from '../assistant';

const LANG_LABEL = { la: 'Latin', grc: 'Greek', he: 'Hebrew', en: 'English', cop: 'Coptic' };

/**
 * The Reader's side panel: what the corpus has to say about the current selection.
 *
 * Three tabs, one per kind of connection:
 *   Similar Passages  content-level matches from the scene index (cross-language)
 *   Verbal Parallels  word-level matches from the lexical engines
 *   Translation       the aligned public-domain English, where one exists
 *
 * Every result is a button that opens that passage in the Reader, which is what
 * makes the corpus browsable by association rather than by search alone.
 */
export default function ResultsPanel({ selection, language, work, units, onOpenPassage }) {
  const [tab, setTab] = useState('similar');
  const [similar, setSimilar] = useState(null);
  const [translation, setTranslation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!selection || tab !== 'similar') return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      work,
      ref_start: selection.refStart || '',
      ref_end: selection.refEnd || selection.refStart || '',
      limit: '15',
    });
    fetch(`/api/scene/similar?${params}`)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        if (d.error) setError(d.error);
        setSimilar(d);
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selection, work, tab]);

  useEffect(() => {
    if (!selection || tab !== 'translation') return;
    let cancelled = false;
    setLoading(true);
    const refs = (units || [])
      .slice(selection.startIdx, selection.endIdx + 1)
      .map((u) => u.ref)
      .join('|');
    fetch(`/api/translation?work=${encodeURIComponent(work)}&refs=${encodeURIComponent(refs)}`)
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setTranslation(d); })
      .catch(() => { if (!cancelled) setTranslation(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selection, work, units, tab]);

  if (!selection) {
    return (
      <aside className="w-full lg:w-96 border-t lg:border-t-0 lg:border-l border-gray-200 bg-gray-50 p-6">
        <p className="text-sm text-gray-500 leading-relaxed">
          Select a passage in the text to see what the corpus connects to it. Drag across
          several lines for content matches, or click a single line for word matches.
        </p>
      </aside>
    );
  }

  const tabs = [
    ['similar', 'Similar Passages'],
    ['verbal', 'Verbal Parallels'],
    ['translation', 'Translation'],
  ];

  return (
    <aside className="w-full lg:w-96 border-t lg:border-t-0 lg:border-l border-gray-200 bg-gray-50 flex flex-col">
      <div className="flex border-b border-gray-200 text-sm">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-3 py-2 font-semibold border-b-2 transition-colors ${
              tab === id
                ? 'text-red-700 border-red-700'
                : 'text-gray-500 border-transparent hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {tab === 'similar' && (
          <>
            {loading && <LoadingSpinner />}
            {error && <p className="text-sm text-red-700">{error}</p>}
            {!loading && similar?.results?.length === 0 && (
              <p className="text-sm text-gray-500">
                No passage in the corpus resembles this selection closely.
              </p>
            )}
            {!loading && similar?.results?.map((r) => (
              <button
                key={r.id}
                onClick={() => onOpenPassage?.(r)}
                className="w-full text-left bg-white border border-gray-200 rounded-lg p-3 hover:border-red-300 transition-colors"
              >
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="text-[10px] font-bold uppercase tracking-wide bg-gray-100 text-gray-600 rounded px-1">
                    {LANG_LABEL[r.language] || r.language}
                  </span>
                  <span className="font-bold text-sm text-gray-900">
                    {prettyWork(r.work)}
                  </span>
                  <span className="text-xs text-gray-500">{shortRef(r.ref_start)}</span>
                  {r.strong && (
                    <span className="ml-auto text-[11px] font-semibold text-green-700">strong</span>
                  )}
                </div>
                {r.gist && (
                  <p className="text-xs text-gray-600 mt-1 leading-snug">
                    {r.gist}
                    {/* The summary named someone the passage does not. Often that
                        is sound inference (Vergil writes virgo where the summary
                        says Sibyl), sometimes it is the wrong person, and a
                        served result cannot tell those apart. So it is marked
                        rather than asserted or hidden. */}
                    {r.names_in_text === false && (
                      <span
                        className="ml-1 text-[10px] text-amber-700 whitespace-nowrap"
                        title="This summary names people the passage itself does not name. It may be correct inference from context, or a misidentification. Check the text."
                      >
                        (names unconfirmed)
                      </span>
                    )}
                  </p>
                )}
                {/* One scriptural passage the corpus holds in several versions,
                    collapsed into a single result. Naming the other versions is
                    useful; giving each one its own row is not. */}
                {r.also_in?.length > 0 && (
                  <p className="text-[11px] text-gray-500 mt-1 leading-snug">
                    Also in{' '}
                    {r.also_in
                      .map((a) => LANG_LABEL[a.language] || a.language)
                      .filter((v, i, arr) => arr.indexOf(v) === i)
                      .join(', ')}
                  </p>
                )}
                {r.themes?.length > 0 && (
                  <div className="flex gap-1 flex-wrap mt-1">
                    {r.themes.slice(0, 4).map((t) => (
                      <span key={t} className="text-[10px] bg-gray-100 text-gray-600 rounded px-1">{t}</span>
                    ))}
                  </div>
                )}
              </button>
            ))}
            <p className="text-[11px] text-gray-400 pt-1 leading-snug">
              These passages match in content, not wording, so a match in another language
              usually shares no words with the selection. Summaries are machine-written.
            </p>
            {!loading && similar?.results?.length > 0 && (
              <ResultsInsight
                results={similar.results.map((r) => ({
                  // The scene index reports one passage per hit, so present the
                  // selection as the source side and the match as the target.
                  source: { ref: selection.refStart, text: '' },
                  target: { ref: `${r.work} ${r.ref_start}`, text: r.gist || '' },
                  channels: ['context'],
                  themes: r.themes || [],
                }))}
                source={work}
                target="the corpus"
                className="mt-2"
              />
            )}
          </>
        )}

        {tab === 'verbal' && (
          <p className="text-sm text-gray-500">
            Word-level matches for this selection come from the existing search engines.
            Wiring in progress.
          </p>
        )}

        {tab === 'translation' && (
          <>
            {loading && <LoadingSpinner />}
            {!loading && translation?.available === false && (
              <p className="text-sm text-gray-500">
                {translation.reason} Aligned public-domain translations currently cover
                about a fifth of the Greek corpus and a tenth of the Latin.
              </p>
            )}
            {!loading && translation?.available && (
              <div className="bg-white border border-gray-200 rounded-lg p-3">
                {/* A block-only warning goes ABOVE the text. Below it, a reader who
                    has already taken the English for a rendering of their lines
                    will never see it. */}
                {translation.block_only && (
                  <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1.5 mb-2 leading-snug">
                    {translation.note}
                  </p>
                )}
                <p className="text-sm text-gray-800 whitespace-pre-line leading-relaxed">
                  {translation.text}
                </p>
                {translation.note && !translation.block_only && (
                  <p className="text-[11px] text-amber-700 mt-2 leading-snug">{translation.note}</p>
                )}
                <p className="text-[11px] text-gray-500 mt-2 leading-snug">
                  {translation.translator}
                  {translation.year ? `, ${translation.year}` : ''}
                  {translation.attribution ? ` \u00b7 ${translation.attribution}` : ''}
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

/** Trailing book.line of a reference tag, which is what a reader recognises. */
function shortRef(ref) {
  if (!ref) return '';
  const m = String(ref).match(/(\d+[.:]\d+)\s*$/);
  return m ? m[1] : String(ref).split(/\s+/).pop();
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
