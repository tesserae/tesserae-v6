import Pagination from '../common/Pagination';
import useIncrementalPagination, { BATCH_PAGE_SIZE_OPTIONS } from '../../hooks/useIncrementalPagination';
import { useState, useEffect, useCallback } from 'react';
import { languageName } from '../../utils/languageNames';
import SourcesCredits from './SourcesCredits';

// A deep link from the Reader's About panel ("Full credits"), filtered to
// the work's author: /text-credits?author=Name. Read once at mount, same
// as any other page's own query-string params; the filter box then behaves
// exactly as if the visitor had typed it.
function authorFromUrl() {
  try {
    return new URLSearchParams(window.location.search).get('author') || '';
  } catch {
    return '';
  }
}

export default function TextCredits() {
  const [filter, setFilter] = useState(authorFromUrl);
  const [query, setQuery] = useState(authorFromUrl);
  // Translators (2026-09-20): Kline was named only where his translation
  // appeared; the credits page named no translator at all. Every aligned
  // translation is now listed here as well, per language.
  const [translations, setTranslations] = useState(null);
  const [showTranslations, setShowTranslations] = useState(false);
  useEffect(() => {
    let dead = false;
    Promise.all(['la', 'grc'].map((lang) =>
      fetch(`/api/passages/translations?language=${lang}`)
        .then((r) => (r.ok ? r.json() : { works: {} }))
        .then((d) => [lang, d.works || {}])
        .catch(() => [lang, {}])))
      .then((pairs) => { if (!dead) setTranslations(Object.fromEntries(pairs)); });
    return () => { dead = true; };
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(filter), 250);
    return () => clearTimeout(timer);
  }, [filter]);

  const fetchPage = useCallback(async ({ page, pageSize, signal }) => {
    const params = new URLSearchParams({ query, offset: String((page - 1) * pageSize), limit: String(pageSize) });
    const res = await fetch(`/api/text-credits?${params}`, { signal });
    if (!res.ok) throw new Error('Failed to load sources. Please try again.');
    const data = await res.json();
    return { items: data.entries || [], total: data.total || 0 };
  }, [query]);
  const pagination = useIncrementalPagination({ fetchPage });
  const { visibleItems: entries, loading: fetching, pageError: error } = pagination;
  const loading = fetching && entries.length === 0;

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-700 mx-auto mb-4"></div>
        <p className="text-gray-600">Loading sources...</p>
      </div>
    );
  }

  if (error && entries.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-8">
        <p className="text-red-600">Failed to load sources: {error}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-4 sm:p-8">
      <SourcesCredits />
      <h2 className="text-2xl font-semibold text-gray-900 mb-4">Sources of the literary texts</h2>

      <p className="text-gray-700 leading-relaxed mb-6">
        Below we provide the electronic sources for each of our texts. To the best of our ability, we have
        looked for indications of the original provenance of these texts, and reproduce citation where
        possible. The full account of where our texts, models, and licenses come from is on the About page.
        This is a work in progress.
      </p>

      <TranslationCredits translations={translations} open={showTranslations}
                          onToggle={() => setShowTranslations((v) => !v)} />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          type="text"
          placeholder="Filter by author or work..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full sm:w-80 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
        />
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-x-auto border border-gray-200 rounded-lg">
        <table className="w-full text-sm min-w-[600px]">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-2 sm:px-4 py-2 sm:py-3 font-semibold text-gray-700">Author</th>
              <th className="text-left px-2 sm:px-4 py-2 sm:py-3 font-semibold text-gray-700">Work</th>
              <th className="text-left px-2 sm:px-4 py-2 sm:py-3 font-semibold text-gray-700">e-Source</th>
              <th className="text-left px-2 sm:px-4 py-2 sm:py-3 font-semibold text-gray-700">Print Source</th>
              <th className="text-left px-2 sm:px-4 py-2 sm:py-3 font-semibold text-gray-700">Added by</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {entries.map((entry, idx) => (
              <tr key={idx} className="hover:bg-gray-50">
                <td className="px-2 sm:px-4 py-2 text-gray-900 font-medium whitespace-nowrap">{entry.author}</td>
                <td className="px-2 sm:px-4 py-2 text-gray-700">{entry.work}</td>
                <td className="px-2 sm:px-4 py-2 whitespace-nowrap">
                  {/* Licensed for indexing and search only
                      (data/restricted_texts.json): there is no e-text or
                      print source to credit here, only the fixed credit line
                      and licence words the holder's terms require. */}
                  {entry.restricted ? (
                    <span className="text-gray-500 text-xs italic">{entry.credit}</span>
                  ) : entry.e_source_url ? (
                    <a
                      href={entry.e_source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-red-700 hover:underline"
                    >
                      {entry.e_source}
                    </a>
                  ) : (
                    <span className="text-gray-700">{entry.e_source}</span>
                  )}
                </td>
                <td className="px-2 sm:px-4 py-2 text-gray-600 text-xs">
                  {entry.restricted ? entry.license : entry.print_source}
                </td>
                <td className="px-2 sm:px-4 py-2 text-gray-600 whitespace-nowrap">{entry.added_by}</td>
              </tr>
            ))}
            {!loading && entries.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  No entries found matching your filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Pagination {...pagination} variant="more" pageSizeOptions={BATCH_PAGE_SIZE_OPTIONS}
        idPrefix="text-credits" itemLabel="entries" />
    </div>
  );
}


/** A work's file slug as a readable name: "silius_italicus.punica" ->
 *  "Silius Italicus, Punica". */
function workLabel(slug) {
  const [author, ...rest] = String(slug).split('.');
  const cap = (s) => s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  return rest.length ? `${cap(author)}, ${cap(rest.join(' '))}` : cap(author);
}

/** The translators behind the Reader's Translation tab, listed per language.
 *  The list comes from the aligned translation files themselves, so it is
 *  exactly what the Reader credits under each passage. */
export function TranslationCredits({ translations, open, onToggle }) {
  const total = translations
    ? Object.values(translations).reduce((n, works) => n + Object.keys(works).length, 0)
    : 0;
  return (
    <div className="mb-6 border border-gray-200 rounded-lg p-4 bg-gray-50">
      <h3 className="text-lg font-semibold text-gray-900 mb-2">Translations</h3>
      <p className="text-sm text-gray-700 leading-relaxed mb-2">
        The Reader's Translation tab shows English aligned to the original, and names the translator
        under each passage. We use public-domain translations first (Loeb volumes now out of copyright,
        Perseus, older editions). Where none exists we use an open translation whose author permits
        free non-commercial reproduction with attribution, as A. S. Kline does for Silius Italicus,
        Punica books 9 to 17; such translations are credited on every passage and are not included in
        our downloadable data releases.
      </p>
      {translations && (
        <button type="button" onClick={onToggle}
                className="text-sm text-red-700 hover:underline">
          {open ? 'Hide the list' : `List the ${total} translated works and their translators`}
        </button>
      )}
      {open && translations && (
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          {Object.entries(translations).map(([lang, works]) => (
            <div key={lang}>
              <h4 className="font-medium text-gray-900 mb-1">{languageName(lang) || lang}</h4>
              <ul className="text-sm text-gray-700 space-y-0.5">
                {Object.entries(works).sort(([a], [b]) => a.localeCompare(b)).map(([slug, info]) => (
                  <li key={slug}>
                    <span className="text-gray-900">{workLabel(slug)}</span>
                    {info.attribution ? <span className="text-gray-600">: {info.attribution}</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
