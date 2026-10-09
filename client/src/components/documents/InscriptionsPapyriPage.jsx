import { useState, useEffect } from 'react';
import { LoadingSpinner } from '../common';
import { dirFor } from '../../utils/rtl';
import useDocumentsTrial from '../../hooks/useDocumentsTrial';
import useDocumentsSearch from './useDocumentsSearch';
import { DOC_PAGE_SIZE, DOCUMENT_EXAMPLE_SEARCHES } from './documentsConstants';
import DocumentExampleButtons from './DocumentExampleButtons';
import DocumentsSearchFilters from './DocumentsSearchFilters';
import DocumentsResultsPanel from './DocumentsResultsPanel';
import DocumentsBrowser from '../corpus/DocumentsBrowser';

// Narrower than LineSearch.jsx's Literature/Documents/Both: this page's
// whole purpose is the documents collection, so Literature is not offered
// here (it already has a page -- Lines search). "Both" stays, since the
// example searches below use it to also surface a document's literary
// source alongside the inscriptions/papyri that echo it.
const COLLECTION_OPTIONS = [
  { key: 'documents', label: 'Documents' },
  { key: 'both', label: 'Both' },
];

const LANGUAGE_OPTIONS = [
  { code: 'la', label: 'Latin' },
  { code: 'grc', label: 'Greek' },
];

/**
 * A simple, language-agnostic highlight for the literature companion list
 * below a "Both" documents search (e.g. the "arma virumque cano" example,
 * which also surfaces Vergil's own opening). Deliberately not the full
 * LineSearch.jsx `highlightMatches` (per-language normalization, Coptic/
 * Hebrew diacritics): this page's focus is the documents collection, and
 * the literary hit here is a secondary companion to it, not its own
 * fully-featured result list -- that already exists at Lines search.
 */
function simpleHighlight(text, matchedWords) {
  if (!text) return text;
  const words = (matchedWords || []).filter(Boolean).map(w => w.toLowerCase());
  if (words.length === 0) return text;
  return text.split(/(\s+)/).map((part, i) => {
    const clean = part.replace(/[^\p{L}]/gu, '').toLowerCase();
    if (clean && words.includes(clean)) {
      return <mark key={i} className="bg-amber-200 px-0.5 rounded">{part}</mark>;
    }
    return <span key={i}>{part}</span>;
  });
}

/**
 * The Inscriptions & Papyri page (route /inscriptions-papyri): a search
 * over the documents collection (filters, restoration/formula options,
 * ranking, totals, paging, the century/region chart -- all shared with
 * LineSearch.jsx's "Documents"/"Both" option via useDocumentsSearch),
 * with the browse-by-facet view (DocumentsBrowser, kind -> region ->
 * findspot -> century) underneath it. A document's citation opens the
 * existing /document page and carries enough state in its own URL for
 * the "back to results" link to return here with the search intact.
 *
 * Shown in the main navigation only behind the documents trial
 * (Navigation.jsx), and redirects to the main search page itself when
 * the client's own ?documents=1 session flag was never set -- the route
 * is not a back door to a trial feature for a visitor who never opted
 * in, even if they land on it directly.
 */
export default function InscriptionsPapyriPage({ setPageType }) {
  const documentsTrial = useDocumentsTrial();
  const [documentsEnabled, setDocumentsEnabled] = useState(false);
  // Whether the /api/languages check above has settled (true or false).
  // A restored deep link (the back-link effect below) must not auto-run
  // its search until this resolves -- addCollectionParams reads
  // `documentsEnabled` to decide whether to add collection/filters at
  // all, and firing the search while it is still the initial `false`
  // would silently drop every one of them from the request.
  const [serverChecked, setServerChecked] = useState(false);

  useEffect(() => {
    fetch('/api/languages').then(r => r.json()).then(data => {
      setDocumentsEnabled(!!data.documents_enabled);
    }).catch(() => {}).finally(() => setServerChecked(true));
  }, []);

  // Not an opt-in: a bookmark or shared link to this route, without the
  // trial flag ever having been set in this session, lands on the main
  // search instead. Checked once -- a flag that turns on mid-visit (the
  // trial is only ever set, never cleared, by useDocumentsTrial) would
  // not need a second check.
  useEffect(() => {
    if (!documentsTrial && setPageType) {
      setPageType('search');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentsTrial]);

  const [language, setLanguage] = useState('la');
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState('lemma');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pendingUrlSearch, setPendingUrlSearch] = useState(null);
  // The literary companion to a "Both" search (e.g. Vergil's own opening
  // alongside the Pompeii graffito that echoes it) -- separate from the
  // documents collection's own result state, which useDocumentsSearch owns.
  const [literatureHits, setLiteratureHits] = useState([]);

  const {
    collection, setCollection,
    dateFrom, setDateFrom,
    dateTo, setDateTo,
    docRegion, setDocRegion,
    docTextType, setDocTextType,
    docMaterial, setDocMaterial,
    docSource, setDocSource,
    excludeRestored, setExcludeRestored,
    hideFormulas, setHideFormulas,
    documentPageResults,
    docTotal,
    docSort,
    docDistribution,
    docPageLoading,
    docPagination,
    addCollectionParams,
    applyDocumentsResponse,
    recordSearch,
    fetchDocumentsPage,
  } = useDocumentsSearch({ documentsEnabled, defaultCollection: 'documents', setError });

  // Deep link / "back to results" from the document view: restores the
  // query and every filter this page's own documentViewUrl encoded, then
  // runs the search once the query is in state (the same pendingUrlSearch
  // pattern LineSearch.jsx uses for its own /?tab=line&q=... deep link).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const lang = params.get('lang');
    const type = params.get('type');
    const col = params.get('collection');
    if (lang && LANGUAGE_OPTIONS.some(l => l.code === lang)) setLanguage(lang);
    if (type && ['lemma', 'exact', 'regex'].includes(type)) setSearchType(type);
    if (col && COLLECTION_OPTIONS.some(o => o.key === col)) setCollection(col);
    if (params.get('region')) setDocRegion(params.get('region'));
    if (params.get('date_from')) setDateFrom(params.get('date_from'));
    if (params.get('date_to')) setDateTo(params.get('date_to'));
    if (params.get('text_type')) setDocTextType(params.get('text_type'));
    if (params.get('material')) setDocMaterial(params.get('material'));
    if (params.get('source')) setDocSource(params.get('source'));
    if (params.get('exclude_restored') === '1') setExcludeRestored(true);
    if (params.get('hide_formulas') === '1') setHideFormulas(true);
    const q = params.get('q');
    if (q) {
      setQuery(q);
      setPendingUrlSearch(q);
    }
    // Run once on mount for the initial URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (serverChecked && pendingUrlSearch != null && query === pendingUrlSearch) {
      setPendingUrlSearch(null);
      handleSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingUrlSearch, query, serverChecked]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const searchParams = addCollectionParams({
        query: query.trim(),
        language,
        search_type: searchType,
      });
      recordSearch(searchParams);
      const res = await fetch('/api/line-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchParams),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        setLiteratureHits([]);
        applyDocumentsResponse({});
      } else {
        setLiteratureHits((data.results || []).filter(r => r.collection !== 'documents'));
        applyDocumentsResponse(data, { sortUsed: searchParams.sort });
      }
    } catch (err) {
      setError('Search failed. Please try again.');
      setLiteratureHits([]);
    }
    setLoading(false);
  };

  const runExampleSearch = async (example) => {
    setQuery(example.query);
    setCollection(example.collection);
    setSearchType(example.searchType);
    setError(null);
    setLoading(true);
    try {
      const searchParams = {
        query: example.query, language, search_type: example.searchType,
        collection: example.collection, offset: 0, limit: DOC_PAGE_SIZE, sort: docSort,
      };
      recordSearch(searchParams);
      const res = await fetch('/api/line-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchParams),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        setLiteratureHits([]);
      } else {
        setLiteratureHits((data.results || []).filter(r => r.collection !== 'documents'));
        applyDocumentsResponse(data, { collection: example.collection, force: true });
      }
    } catch (err) {
      setError('Search failed. Please try again.');
      setLiteratureHits([]);
    }
    setLoading(false);
  };

  // Opens the existing /document page, carrying this page's query, type,
  // collection, sort and every active filter so its own "back to results"
  // link (DocumentView.jsx's `from` param) returns here with the search
  // intact rather than to Lines search.
  const documentViewUrl = (docId) => {
    const params = new URLSearchParams({
      doc: docId, lang: language, q: query, type: searchType,
      collection, sort: docSort, from: 'inscriptions-papyri', documents: '1',
    });
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    if (docRegion) params.set('region', docRegion);
    if (docTextType) params.set('text_type', docTextType);
    if (docMaterial) params.set('material', docMaterial);
    if (docSource) params.set('source', docSource);
    if (excludeRestored) params.set('exclude_restored', '1');
    if (hideFormulas) params.set('hide_formulas', '1');
    return `/document?${params.toString()}`;
  };

  if (!documentsTrial) return null;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-4 sm:p-6 space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Inscriptions &amp; Papyri</h2>
          <p className="text-sm text-gray-500 mt-1">
            Search and browse the documentary corpus (Latin and Greek inscriptions and papyri)
            alongside the literature it quotes or echoes.{' '}
            <button
              type="button"
              onClick={() => window.dispatchEvent(new CustomEvent('tesserae:open-help', { detail: { section: 'documents' } }))}
              className="text-red-700 hover:underline"
            >
              About this page
            </button>
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Search Terms</label>
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="Enter word or phrase..."
                className="flex-1 border rounded px-4 py-2"
              />
              <select
                value={searchType}
                onChange={e => setSearchType(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              >
                <option value="lemma">Lemma (dictionary form)</option>
                <option value="exact">Exact match</option>
                <option value="regex">Regular expression (pattern)</option>
              </select>
              <select
                value={language}
                onChange={e => setLanguage(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              >
                {LANGUAGE_OPTIONS.map(l => (
                  <option key={l.code} value={l.code}>{l.label}</option>
                ))}
              </select>
            </div>
            <DocumentExampleButtons
              examples={DOCUMENT_EXAMPLE_SEARCHES[language]}
              onRun={runExampleSearch}
            />
          </div>

          <div className="border-t pt-4">
            <DocumentsSearchFilters
              options={COLLECTION_OPTIONS}
              collection={collection} setCollection={setCollection}
              dateFrom={dateFrom} setDateFrom={setDateFrom}
              dateTo={dateTo} setDateTo={setDateTo}
              docRegion={docRegion} setDocRegion={setDocRegion}
              docTextType={docTextType} setDocTextType={setDocTextType}
              docMaterial={docMaterial} setDocMaterial={setDocMaterial}
              docSource={docSource} setDocSource={setDocSource}
              excludeRestored={excludeRestored} setExcludeRestored={setExcludeRestored}
              hideFormulas={hideFormulas} setHideFormulas={setHideFormulas}
            />
          </div>

          <div className="border-t pt-4 flex justify-end">
            <button
              onClick={handleSearch}
              disabled={!query.trim() || loading}
              className="px-6 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>
        </div>
      </div>

      {loading && <LoadingSpinner text="Searching the documents collection..." />}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {collection === 'both' && literatureHits.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 text-sm text-gray-600">
            Also found in the literature ({literatureHits.length})
          </div>
          <div className="divide-y divide-gray-200">
            {literatureHits.map((result, i) => (
              <div key={i} className="p-4">
                <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                  <div className="sm:w-48 flex-shrink-0 min-w-0 break-words">
                    <div className="text-sm font-medium text-gray-900">{result.author}</div>
                    <div className="text-xs text-gray-500">{result.work}, {result.locus}</div>
                  </div>
                  <div className="flex-1 min-w-0 break-words text-gray-700" dir={dirFor(language)}>
                    {simpleHighlight(result.text, result.matched_words)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <DocumentsResultsPanel
        documentResults={documentPageResults}
        docTotal={docTotal}
        docSort={docSort}
        onSortChange={(sort) => fetchDocumentsPage({ offset: 0, sort })}
        docDistribution={docDistribution}
        docPagination={docPagination}
        docPageLoading={docPageLoading}
        documentViewUrl={documentViewUrl}
        language={language}
      />

      <div className="bg-white rounded-lg shadow p-4 sm:p-6">
        <DocumentsBrowser documentsTrial={documentsTrial} />
      </div>
    </div>
  );
}
