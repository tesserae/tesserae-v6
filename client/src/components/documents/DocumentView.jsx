import { useState, useEffect } from 'react';
import { LoadingSpinner } from '../common';
import { dirFor } from '../../utils/rtl';
import { splitImageLinks } from './imageLinks';

function paramOr(name, fallback) {
  const v = new URLSearchParams(window.location.search).get(name);
  return v || fallback;
}

// One document's own text, by token position (same contract LineSearch's
// renderDocumentText uses for a document hit): a light dotted underline
// for a restored word, italic gray for a surviving fragment of a damaged
// one. No matched-word <mark> here -- this view has no query of its own
// to highlight, only the document itself.
function renderLineTokens(line, language) {
  const tokens = line.tokens || [];
  if (!tokens.length) {
    return <span>{line.text}</span>;
  }
  const restoredSet = new Set(line.restored_indices || []);
  const fragmentSet = new Set(line.fragment_indices || []);
  return tokens.map((tok, i) => {
    let el = <span>{tok}</span>;
    if (restoredSet.has(i)) {
      el = <span className="underline decoration-dotted decoration-2 decoration-sky-500" title="editorially restored">{tok}</span>;
    } else if (fragmentSet.has(i)) {
      el = <span className="italic text-gray-500" title="surviving fragment of a damaged word">{tok}</span>;
    }
    return <span key={i}>{el}{' '}</span>;
  });
}

function dateLabel(data) {
  const nb = data.date_not_before, na = data.date_not_after;
  if (nb == null && na == null) return null;
  const fmt = (y) => (y < 0 ? `${-y} BC` : `${y} AD`);
  if (nb != null && na != null && nb !== na) return `${fmt(nb)}–${fmt(na)}`;
  return fmt(nb != null ? nb : na);
}

export default function DocumentView() {
  const [docId] = useState(() => paramOr('doc', ''));
  const [language] = useState(() => paramOr('lang', 'la'));
  const [cameFromQuery] = useState(() => paramOr('q', ''));
  const [cameFromType] = useState(() => paramOr('type', 'lemma'));
  const [documentsTrial] = useState(() => paramOr('documents', ''));
  // Which page opened this view: 'line-search' (the default, every link
  // predating this field) or 'inscriptions-papyri' (that page's own
  // documentViewUrl). Determines where "back to results" returns to.
  const [cameFromPage] = useState(() => paramOr('from', 'line-search'));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [scholarship, setScholarship] = useState([]);

  // Journal sentences and commentary notes that cite this document. An
  // absent index, a 404 (documents switch off) or a failure leaves the
  // section out; it never blocks the document itself.
  useEffect(() => {
    setScholarship([]);
    if (!docId) return;
    let live = true;
    fetch(`/api/documents/${encodeURIComponent(docId)}/scholarship`)
      .then(r => (r.ok ? r.json() : null))
      .then(j => { if (live && j && Array.isArray(j.results)) setScholarship(j.results); })
      .catch(() => {});
    return () => { live = false; };
  }, [docId]);

  useEffect(() => {
    if (!docId) {
      setError('No document specified.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetch(`/api/documents/${encodeURIComponent(docId)}?language=${encodeURIComponent(language)}`)
      .then(r => {
        if (!r.ok) throw new Error(r.status === 404 ? 'Document not found.' : 'Failed to load document.');
        return r.json();
      })
      .then(setData)
      .catch(err => setError(err.message || 'Failed to load document.'))
      .finally(() => setLoading(false));
  }, [docId, language]);

  // The Inscriptions & Papyri page's own documentViewUrl carries its full
  // search state (collection, sort, filters) as query params alongside
  // doc/from -- copying the CURRENT address rather than re-listing every
  // field here means a filter added to that page later needs no matching
  // change on this side of the round trip. `doc` and `from` themselves
  // are the two fields specific to opening this view, so both are
  // stripped before the params are echoed back.
  const backParams = cameFromPage === 'inscriptions-papyri'
    ? new URLSearchParams(window.location.search)
    : new URLSearchParams({ lang: language, q: cameFromQuery, type: cameFromType });
  if (cameFromPage === 'inscriptions-papyri') {
    backParams.delete('doc');
    backParams.delete('from');
  }
  if (documentsTrial === '1') backParams.set('documents', '1');
  const backBase = cameFromPage === 'inscriptions-papyri' ? '/inscriptions-papyri' : '/line-search';
  const backUrl = `${backBase}?${backParams.toString()}`;

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <a href={backUrl} className="text-sm text-red-700 hover:underline inline-flex items-center gap-1">
        &larr; back to search results
      </a>

      {loading && (
        <div className="bg-white rounded-lg shadow p-8">
          <LoadingSpinner text="Loading document..." />
        </div>
      )}

      {!loading && error && (
        <div className="bg-white rounded-lg shadow p-6 text-gray-600">{error}</div>
      )}

      {!loading && !error && data && (() => {
        const credit = data.credit || {};
        const display = data.display || {};
        const labels = [data.text_type_label, data.object_type_label, data.material_label].filter(Boolean);
        const place = data.ancient_place || data.modern_place;
        const dLabel = dateLabel(data);
        const images = Array.isArray(display.image_url) ? display.image_url
          : (display.image_url ? [display.image_url] : []);
        const imageLinks = splitImageLinks(images);
        return (
          <div className="bg-white rounded-lg shadow p-4 sm:p-6 space-y-4">
            <div>
              <h1 className="text-lg font-semibold text-gray-900">
                {credit.principal_edition || data.doc_id}
              </h1>
              <div className="text-sm text-gray-600 mt-1">
                {[dLabel, place, data.region].filter(Boolean).join(' · ')}
                {data.pleiades_id && (
                  <>
                    {' '}&middot;{' '}
                    <a href={`https://pleiades.stoa.org/places/${encodeURIComponent(data.pleiades_id)}`}
                       target="_blank" rel="noopener noreferrer" className="text-amber-700 hover:underline">
                      Pleiades
                    </a>
                  </>
                )}
              </div>
              {labels.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {labels.map((lab, i) => (
                    <span key={i} className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded inline-block">
                      {lab}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="border-t pt-4 text-gray-800 leading-relaxed" dir={dirFor(language)}>
              {(data.lines || []).map((line, i) => (
                <p key={i} className="mb-1">{renderLineTokens(line, language)}</p>
              ))}
            </div>

            {(display.museum || display.inventory || display.dimensions) && (
              <div className="border-t pt-3 text-sm text-gray-600 space-y-0.5">
                {display.museum && <div><span className="font-medium">Museum:</span> {display.museum}</div>}
                {display.inventory && <div><span className="font-medium">Inventory:</span> {display.inventory}</div>}
                {display.dimensions && <div><span className="font-medium">Dimensions:</span> {display.dimensions}</div>}
              </div>
            )}

            {display.translation && (
              <div className="border-t pt-3">
                <div className="text-sm font-medium text-gray-700 mb-1">Translation</div>
                <p className="text-sm text-gray-700 italic">{display.translation}</p>
              </div>
            )}

            {display.apparatus && (
              <details className="border-t pt-3 text-sm text-gray-700">
                <summary className="cursor-pointer font-medium text-gray-800">Apparatus</summary>
                <p className="mt-2 whitespace-pre-wrap">{display.apparatus}</p>
              </details>
            )}

            {display.commentary && (
              <details className="border-t pt-3 text-sm text-gray-700">
                <summary className="cursor-pointer font-medium text-gray-800">Commentary</summary>
                <p className="mt-2 whitespace-pre-wrap">{display.commentary}</p>
              </details>
            )}

            {images.length > 0 && (
              <div className="border-t pt-3">
                <div className="text-sm font-medium text-gray-700 mb-1">Images</div>
                {imageLinks.shown.length > 0 && (
                  <ul className="text-sm list-disc list-inside">
                    {imageLinks.shown.map(({ url, label }, i) => (
                      <li key={i}>
                        <a href={url} title={url} target="_blank" rel="noopener noreferrer"
                           className="text-amber-700 hover:underline break-all">{label}</a>
                      </li>
                    ))}
                  </ul>
                )}
                {imageLinks.omitted > 0 && (
                  <p className="text-xs text-gray-500 mt-1">
                    {imageLinks.omitted} image link{imageLinks.omitted === 1 ? '' : 's'} omitted (the host no longer serves {imageLinks.omitted === 1 ? 'it' : 'them'}).
                  </p>
                )}
              </div>
            )}

            {scholarship.length > 0 && (
              <div className="border-t pt-3" data-testid="document-scholarship">
                <div className="text-sm font-medium text-gray-700 mb-1">Scholarship</div>
                <p className="text-[11px] text-gray-500 mb-2">
                  Sentences that cite this document in journals from before 1923 (JSTOR Early Journal
                  Content) and in the commentaries held here. The full list of sources is under{' '}
                  <a href="/text-credits" className="text-red-700 hover:underline">Sources and credits</a>.
                </p>
                <ul className="space-y-3">
                  {scholarship.map((r, i) => (
                    <li key={i} className="text-sm leading-snug">
                      <span className="inline-block bg-gray-100 text-gray-600 text-[10px] px-1.5 py-0.5 rounded mb-1">
                        {r.source === 'commentary' ? 'commentary' : 'journal article, JSTOR'}
                      </span>
                      <p className="text-gray-900">{r.citation}</p>
                      {r.excerpt && (
                        <p className="text-[12px] text-gray-700 mt-0.5 border-l-2 border-gray-200 pl-2">{r.excerpt}</p>
                      )}
                      <p className="text-[11px] text-gray-500 mt-0.5 flex flex-wrap gap-x-3">
                        {r.cites && <span>cites {r.cites}</span>}
                        {r.url && <a className="text-red-700 hover:underline" href={r.url} target="_blank" rel="noreferrer">on JSTOR</a>}
                        {r.commentary_file && <span>{r.commentary_file}{r.commentary_ref ? `, ${r.commentary_ref}` : ''}</span>}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {(credit.source_name || credit.source_url) && (
              <div className="border-t pt-3 text-xs text-gray-500">
                Text:{' '}
                {credit.source_url ? (
                  <a href={credit.source_url} target="_blank" rel="noopener noreferrer"
                     className="text-amber-700 hover:text-amber-900 underline">
                    {credit.source_name || 'source'}
                  </a>
                ) : credit.source_name}
                {credit.licence_name && (
                  <span>
                    , {credit.licence_url ? (
                      <a href={credit.licence_url} target="_blank" rel="noopener noreferrer" className="underline">
                        {credit.licence_name}
                      </a>
                    ) : credit.licence_name}
                  </span>
                )}
                {(credit.source_name_secondary || credit.source_url_secondary) && (
                  <span>
                    {'; '}
                    {credit.source_url_secondary ? (
                      <a href={credit.source_url_secondary} target="_blank" rel="noopener noreferrer"
                         className="text-amber-700 hover:text-amber-900 underline">
                        {credit.source_name_secondary || 'source'}
                      </a>
                    ) : credit.source_name_secondary}
                    {credit.licence_name_secondary && (
                      <span>
                        , {credit.licence_url_secondary ? (
                          <a href={credit.licence_url_secondary} target="_blank" rel="noopener noreferrer" className="underline">
                            {credit.licence_name_secondary}
                          </a>
                        ) : credit.licence_name_secondary}
                      </span>
                    )}
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}
