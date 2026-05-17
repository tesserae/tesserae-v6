import { useState, useEffect, useMemo } from 'react';

const SOURCE_LINKS = {
  'The Latin Library': 'http://thelatinlibrary.com/',
  'The Perseus Project': 'http://www.perseus.tufts.edu/',
  'DigilibLT': 'http://digiliblt.lett.unipmn.it/',
  'Open Greek and Latin Project': 'http://www.dh.uni-leipzig.de/wo/projects/open-greek-and-latin-project/',
  'Musisque Deoque': 'http://www.mqdq.it/',
  'Corpus Scriptorum Latinorum': 'http://www.forumromanum.org/literature/index.html',
  'Coptic Scriptorium': 'https://copticscriptorium.org/',
  'BHSA': 'https://etcbc.github.io/bhsa/',
  'Tanzil': 'https://tanzil.net/',
  'Ganjoor': 'https://ganjoor.net/',
  'Frances Pritchett': 'https://franpritchett.com/00ghalib/',
  'Iqbal Demystified': 'https://github.com/iqbal-demystified',
  'Project Gutenberg': 'https://www.gutenberg.org/',
  'eBible.org': 'https://ebible.org/web/',
  'Moby Shakespeare': 'https://shakespeare.mit.edu/',
};

function IntroLink({ name, url }) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline font-medium">
      {name}
    </a>
  );
}

export default function TextCredits() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    fetch('/api/text-credits')
      .then(res => res.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(err => { setError(err.message); setLoading(false); });
  }, []);

  const filteredData = useMemo(() => {
    if (!data) return [];
    if (!filter.trim()) return data;
    const q = filter.toLowerCase();
    return data.filter(entry =>
      entry.author.toLowerCase().includes(q) ||
      entry.work.toLowerCase().includes(q)
    );
  }, [data, filter]);

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-700 mx-auto mb-4"></div>
        <p className="text-gray-600">Loading sources...</p>
      </div>
    );
  }

  if (error) {
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
        J. Warren Wells). The Hebrew Bible is extracted from the{' '}
        <IntroLink name="ETCBC/BHSA" url={SOURCE_LINKS['BHSA']} /> dataset (Biblia Hebraica Stuttgartensia
        Amstelodamensis). Quranic Arabic is from{' '}
        <IntroLink name="Tanzil" url={SOURCE_LINKS['Tanzil']} />; pre-Islamic Arabic poetry from
        public-domain Mu‘allaqāt editions. Classical Persian poetry comes from{' '}
        <IntroLink name="Ganjoor" url={SOURCE_LINKS['Ganjoor']} />, the Chronological Persian Poetry
        Dataset built on Ganjoor's SQLite distribution. Urdu Ghalib from{' '}
        <IntroLink name="Frances Pritchett's A Desertful of Roses" url={SOURCE_LINKS['Frances Pritchett']} />{' '}
        and Urdu Wikisource; Allama Iqbal's Urdu and Persian works from the{' '}
        <IntroLink name="Iqbal Demystified Dataset" url={SOURCE_LINKS['Iqbal Demystified']} />. English
        literary texts from{' '}
        <IntroLink name="Project Gutenberg" url={SOURCE_LINKS['Project Gutenberg']} /> and{' '}
        <IntroLink name="Moby Shakespeare" url={SOURCE_LINKS['Moby Shakespeare']} />, with the
        World English Bible from{' '}
        <IntroLink name="eBible.org" url={SOURCE_LINKS['eBible.org']} />. We have modified the texts by
        changing the markup, and may have made superficial changes to orthography. During our searches,
        all punctuation and capitalization are removed. Below we provide the electronic sources for each
        of our texts. To the best of our ability, we have looked for indications of the original
        provenance of these texts, and reproduce citation where possible. This is a work in progress.
      </p>

      <div className="mb-4">
        <input
          type="text"
          placeholder="Filter by author or work..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full sm:w-80 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
        />
        <span className="ml-3 text-sm text-gray-500">
          {filteredData.length} {filteredData.length === 1 ? 'entry' : 'entries'}
        </span>
      </div>

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
            {filteredData.map((entry, idx) => (
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
            {filteredData.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  No entries found matching your filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
