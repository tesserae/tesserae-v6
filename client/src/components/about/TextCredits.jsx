import { useState, useEffect, useRef } from 'react';

export default function TextCredits() {
  const [entries, setEntries] = useState([]);
  const [totalEntries, setTotalEntries] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('');
  const [query, setQuery] = useState('');
  const [pageSize, setPageSize] = useState(50);
  const queryVersionRef = useRef(0);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(filter), 250);
    return () => clearTimeout(timer);
  }, [filter]);

  useEffect(() => {
    const controller = new AbortController();
    const queryVersion = queryVersionRef.current + 1;
    queryVersionRef.current = queryVersion;
    setLoading(true);
    setLoadingMore(false);
    setError('');

    const params = new URLSearchParams({
      query,
      offset: '0',
      limit: String(pageSize),
    });

    fetch(`/api/text-credits?${params.toString()}`, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load sources');
        return res.json();
      })
      .then((data) => {
        if (queryVersionRef.current !== queryVersion) return;
        setEntries(data.entries || []);
        setTotalEntries(data.total || 0);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError' || queryVersionRef.current !== queryVersion) return;
        setError('Failed to load sources. Please try again.');
        setLoading(false);
      });

    return () => controller.abort();
  }, [query, pageSize]);

  const loadMore = async () => {
    if (loading || loadingMore || entries.length >= totalEntries) return;

    const queryVersion = queryVersionRef.current;
    setLoadingMore(true);
    setError('');
    try {
      const params = new URLSearchParams({
        query,
        offset: String(entries.length),
        limit: String(pageSize),
      });
      const res = await fetch(`/api/text-credits?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to load more sources');
      const data = await res.json();
      if (queryVersionRef.current === queryVersion) {
        setEntries(previousEntries => [...previousEntries, ...(data.entries || [])]);
        setTotalEntries(data.total || 0);
      }
    } catch (err) {
      if (queryVersionRef.current === queryVersion) {
        setError('Failed to load more sources. Please try again.');
      }
    }
    if (queryVersionRef.current === queryVersion) setLoadingMore(false);
  };

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
      <h2 className="text-2xl font-semibold text-gray-900 mb-4">Sources</h2>

      <p className="text-gray-700 leading-relaxed mb-6">
        Below we provide the electronic sources for each of our texts. To the best of our ability, we have
        looked for indications of the original provenance of these texts, and reproduce citation where
        possible. The full account of where our texts, models, and licenses come from is on the About page.
        This is a work in progress.
      </p>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          type="text"
          placeholder="Filter by author or work..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full sm:w-80 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
        />
        <select
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
          aria-label="Entries at a time"
          className="w-fit border border-gray-300 rounded-lg px-3 py-2 text-sm"
        >
          <option value="25">25 entries at a time</option>
          <option value="50">50 entries at a time</option>
          <option value="100">100 entries at a time</option>
          <option value="500">500 entries at a time</option>
        </select>
        <span className="text-sm text-gray-500">
          Showing {entries.length} of {totalEntries} {totalEntries === 1 ? 'entry' : 'entries'}
        </span>
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
                  {entry.e_source_url ? (
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
                <td className="px-2 sm:px-4 py-2 text-gray-600 text-xs">{entry.print_source}</td>
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
      <ScholarshipCredits />
      {entries.length < totalEntries && (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="rounded border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loadingMore ? 'Loading…' : `Show More (${totalEntries - entries.length} remaining)`}
          </button>
        </div>
      )}
    </div>
  );
}

// The commentaries and the scholarship services behind the Reader's
// Scholarship tab, credited where they came from. The list of commentaries
// is read from the server so it always matches what is installed.
function ScholarshipCredits() {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetch('/api/scholarship/sources').then((r) => (r.ok ? r.json() : { commentaries: [] }))
      .then((d) => { if (!cancelled) setRows(d.commentaries || []); })
      .catch(() => { if (!cancelled) setRows([]); });
    return () => { cancelled = true; };
  }, []);
  const [open, setOpen] = useState(false);
  if (!rows || rows.length === 0) return null;
  const notes = rows.reduce((n, r) => n + (r.notes || 0), 0);
  const workCount = new Set(rows.flatMap((r) => r.works)).size;
  const works = (r) => r.works.map((w) => w.replace(/_/g, ' ').replace(/\./g, ', ')).join('; ');
  return (
    <div className="mt-10">
      <h3 className="text-xl font-semibold text-gray-900 mb-3">Commentaries and scholarship</h3>
      <p className="text-gray-700 leading-relaxed mb-4">
        The Reader&rsquo;s Scholarship tab shows the commentaries below, note by note, with their
        edition, source and licence. Those from the Perseus Digital Library are CC BY-SA 3.0; those
        from Sefaria carry the licence Sefaria states for each text; Matthew Henry comes from the
        Christian Classics Ethereal Library; the rest were taken from Internet Archive scans of
        public-domain editions and carry scanning errors we have only partly repaired.
      </p>
      <p className="text-gray-700 mb-3">
        {rows.length} commentaries on {workCount} works, {notes.toLocaleString()} notes in all.{' '}
        <button type="button" onClick={() => setOpen((v) => !v)} className="text-red-700 hover:underline">
          {open ? 'hide the list' : 'show the list'}
        </button>
      </p>
      {open && (
      <div className="overflow-x-auto border border-gray-200 rounded-lg">
        <table className="w-full text-sm min-w-[600px]">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-3 py-2 font-semibold text-gray-700">Commentator</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-700">Works</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-700">Edition</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-700">Source and licence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((r) => (
              <tr key={r.commentator + r.edition} className="hover:bg-gray-50">
                <td className="px-3 py-2 text-gray-900 font-medium whitespace-nowrap">{r.commentator}</td>
                <td className="px-3 py-2 text-gray-700 text-xs">{works(r)} ({r.notes.toLocaleString()} notes)</td>
                <td className="px-3 py-2 text-gray-600 text-xs">{r.edition}</td>
                <td className="px-3 py-2 text-gray-600 text-xs">
                  {/^https?:/.test(r.source) ? <a href={r.source} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">source</a> : r.source}
                  {r.license ? `; ${r.license}` : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
      <p className="text-gray-700 leading-relaxed mt-4">
        Articles and chapters found by title and abstract, from OpenAlex, Crossref and Unpaywall, are
        tagged &ldquo;article record&rdquo; in the list; the full text of open-access papers, through
        CORE and Semantic Scholar, is tagged &ldquo;open-access article&rdquo;; and book pages, through
        HathiTrust and Google Books, are tagged &ldquo;book page, Google Books&rdquo;. Journal articles
        from before 1923 are held separately and searched in full text: JSTOR&rsquo;s Early Journal
        Content, free on the Internet Archive, tagged &ldquo;journal article, before 1923, JSTOR&rdquo;.
        Recognising a citation of an ancient text in running prose (&ldquo;Aen. 1.1&rdquo;,
        &ldquo;Verg. A. I 1&rdquo;) follows Matteo Romanello&rsquo;s work: the rules of his CitationParser
        grammar, reimplemented here, and the table of author and work abbreviations built from his
        hucitlib knowledge base together with the Perseus catalogue. His Cited Loci of the Aeneid,
        made with JSTOR Labs, served as the answer key for measuring how much of the literature the
        tab finds. Scripture passages link to Sefaria.
      </p>
    </div>
  );
}
