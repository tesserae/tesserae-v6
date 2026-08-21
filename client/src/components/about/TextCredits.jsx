import { useState, useEffect, useRef } from 'react';

const SOURCE_LINKS = {
  'The Latin Library': 'http://thelatinlibrary.com/',
  'The Perseus Project': 'http://www.perseus.tufts.edu/',
  'DigilibLT': 'https://digiliblt.uniupo.it/',
  'Open Greek and Latin Project': 'https://opengreekandlatin.org/',
  'Musisque Deoque': 'http://www.mqdq.it/',
  'Corpus Scriptorum Latinorum': 'https://web.archive.org/web/20220305141011/http://www.forumromanum.org/literature/index.html',
  'Coptic Scriptorium': 'https://copticscriptorium.org/',
  'Sefaria': 'https://www.sefaria.org/',
  'Miqra according to the Masorah': 'https://he.wikisource.org/wiki/%D7%9E%D7%A9%D7%AA%D7%9E%D7%A9:Dovi/%D7%9E%D7%A7%D7%A8%D7%90_%D7%A2%D7%9C_%D7%A4%D7%99_%D7%94%D7%9E%D7%A1%D7%95%D7%A8%D7%94',
  'BHSA': 'https://etcbc.github.io/bhsa/',
  'MiqraBERT': 'https://huggingface.co/davidmsmiley/MiqraBERT',
  'OpenBible.info': 'https://www.openbible.info/labs/cross-references/',
  'CATSS': 'https://ccat.sas.upenn.edu/rak/catss.html',
};

function IntroLink({ name, url }) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline font-medium">
      {name}
    </a>
  );
}

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
        The texts used in this project were gathered from many electronic text databases. Latin and Greek
        texts come from{' '}
        <IntroLink name="The Latin Library" url={SOURCE_LINKS['The Latin Library']} />,{' '}
        <IntroLink name="The Perseus Project" url={SOURCE_LINKS['The Perseus Project']} />,{' '}
        <IntroLink name="DigilibLT" url={SOURCE_LINKS['DigilibLT']} />,{' '}
        <IntroLink name="Open Greek and Latin Project" url={SOURCE_LINKS['Open Greek and Latin Project']} />,{' '}
        <IntroLink name="Musisque Deoque" url={SOURCE_LINKS['Musisque Deoque']} />, and{' '}
        <IntroLink name="Corpus Scriptorum Latinorum" url={SOURCE_LINKS['Corpus Scriptorum Latinorum']} />.
        {' '}Coptic texts (Sahidic and Bohairic) come from{' '}
        <IntroLink name="Coptic Scriptorium" url={SOURCE_LINKS['Coptic Scriptorium']} /> (CC-BY 4.0; the
        Sahidica New Testament is additionally subject to its own academic-use license, ©2000–2006
        J. Warren Wells). The Hebrew Bible text is the{' '}
        <IntroLink name="Miqra according to the Masorah" url={SOURCE_LINKS['Miqra according to the Masorah']} />{' '}
        (MAM) edition, based on the Aleppo Codex, obtained through{' '}
        <IntroLink name="Sefaria" url={SOURCE_LINKS['Sefaria']} /> (CC-BY-SA); Hebrew morphological
        lemmatization draws on the <IntroLink name="ETCBC/BHSA" url={SOURCE_LINKS['BHSA']} /> dataset
        (Biblia Hebraica Stuttgartensia Amstelodamensis; CC-BY-NC 4.0, DOI 10.17026/dans-z6y-skyh)
        via Text-Fabric. The Hebrew semantic channel uses{' '}
        <IntroLink name="MiqraBERT" url={SOURCE_LINKS['MiqraBERT']} /> (D. M. Smiley), fine-tuned
        in-house on <IntroLink name="OpenBible.info" url={SOURCE_LINKS['OpenBible.info']} /> cross-references
        (CC-BY, from the Treasury of Scripture Knowledge); Hebrew-to-Greek Septuagint matching uses the{' '}
        <IntroLink name="CATSS" url={SOURCE_LINKS['CATSS']} /> Masoretic-Septuagint parallel (E. Tov),
        bridged through Greek to the Latin Vulgate for Hebrew-to-Latin matching.
        {' '}We have modified the texts by changing the markup, and may have made superficial changes to orthography.
        During our searches, all punctuation and capitalization are removed. Below we provide the electronic
        sources for each of our texts. To the best of our ability, we have looked for indications of the
        original provenance of these texts, and reproduce citation where possible. This is a work in progress.
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
