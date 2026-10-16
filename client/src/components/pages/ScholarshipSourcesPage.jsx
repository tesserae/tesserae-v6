/**
 * Scholarship: sources and methods. One public page that says what the
 * scholarship results are made from: the commentaries held, the journal
 * citation indexes with their terms, the live services, and how each part of
 * the results is built. Everything comes from GET /api/scholarship/about.
 * Each scholarship box links here, opening at one of the section anchors
 * (commentaries, journals, online, methods).
 */
import { useEffect, useState } from 'react';
import { getJson } from '../../utils/api';

const dateOf = (secs) => (secs ? new Date(secs * 1000).toISOString().slice(0, 10) : 'unknown');
const yearsOf = (j) => (j.year_from === j.year_to ? String(j.year_from) : `${j.year_from} to ${j.year_to}`);
const num = (n) => Number(n || 0).toLocaleString('en-US');

function Heading({ id, children }) {
  return <h2 id={id} className="text-lg font-semibold text-gray-900 mt-8 mb-2 scroll-mt-20">{children}</h2>;
}

function Commentaries({ groups, updated }) {
  return (
    <section>
      <Heading id="commentaries">Commentaries held</Heading>
      <p className="text-gray-700 mb-3">
        Commentary notes are shown beside the passage they explain. They are grouped here by the language of the
        works they comment on. Last updated {dateOf(updated)}.
      </p>
      {groups.map((g) => (
        <div key={g.language} className="mb-5" data-testid={`commentaries-${g.language}`}>
          <h3 className="text-base font-semibold text-gray-800 mb-1">{g.language_name}</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm border border-gray-200">
              <thead className="bg-gray-50 text-left">
                <tr>
                  <th className="px-2 py-1">Commentator</th>
                  <th className="px-2 py-1">Title and edition</th>
                  <th className="px-2 py-1">Works</th>
                  <th className="px-2 py-1 text-right">Notes</th>
                  <th className="px-2 py-1">License</th>
                  <th className="px-2 py-1">Source</th>
                </tr>
              </thead>
              <tbody>
                {g.commentaries.map((r) => (
                  <tr key={`${r.commentator}|${r.edition}`} className="border-t border-gray-200 align-top">
                    <td className="px-2 py-1">{r.commentator}</td>
                    <td className="px-2 py-1">{r.title}{r.edition ? `. ${r.edition}` : ''}</td>
                    <td className="px-2 py-1">{(r.works || []).length}</td>
                    <td className="px-2 py-1 text-right">{num(r.notes)}</td>
                    <td className="px-2 py-1">{r.license || 'not stated'}</td>
                    <td className="px-2 py-1">
                      {r.source && /^https?:/.test(r.source)
                        ? <a href={r.source} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">link</a>
                        : (r.source || '')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </section>
  );
}

function Journals({ indexes, updated }) {
  return (
    <section>
      <Heading id="journals">Journal citation indexes</Heading>
      <p className="text-gray-700 mb-3">
        Each index lists the articles that cite a work held here, with the locus cited. Only articles whose text was
        read are counted.
      </p>
      {indexes.map((b) => (
        <div key={b.id} className="mb-6" data-testid={`index-${b.id}`}>
          <h3 className="text-base font-semibold text-gray-800">{b.name}</h3>
          <p className="text-gray-700">{b.description}</p>
          <p className="text-gray-700 mb-1"><span className="font-medium">Terms.</span> {b.terms}</p>
          <p className="text-xs text-gray-500 mb-2">Last updated {dateOf(updated?.[b.id])}.</p>
          {!b.available ? (
            <p className="text-sm text-gray-600">This index is not available on the server just now.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border border-gray-200">
                <thead className="bg-gray-50 text-left">
                  <tr>
                    <th className="px-2 py-1">Journal</th>
                    <th className="px-2 py-1">Years</th>
                    <th className="px-2 py-1 text-right">Articles</th>
                    <th className="px-2 py-1 text-right">With citations</th>
                    <th className="px-2 py-1 text-right">Citations</th>
                  </tr>
                </thead>
                <tbody>
                  {b.journals.map((j) => (
                    <tr key={j.journal} className="border-t border-gray-200">
                      <td className="px-2 py-1">{j.journal}</td>
                      <td className="px-2 py-1">{yearsOf(j)}</td>
                      <td className="px-2 py-1 text-right">{num(j.articles)}</td>
                      <td className="px-2 py-1 text-right">{num(j.articles_with_citations)}</td>
                      <td className="px-2 py-1 text-right">{num(j.citations)}</td>
                    </tr>
                  ))}
                  <tr className="border-t-2 border-gray-300 font-medium">
                    <td className="px-2 py-1">All {b.journals.length} journals</td>
                    <td className="px-2 py-1" />
                    <td className="px-2 py-1 text-right">{num(b.totals?.articles)}</td>
                    <td className="px-2 py-1 text-right">{num(b.totals?.articles_with_citations)}</td>
                    <td className="px-2 py-1 text-right">{num(b.totals?.citations)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
    </section>
  );
}

function Online({ online }) {
  return (
    <section>
      <Heading id="online">Online services consulted live</Heading>
      <p className="text-gray-700 mb-2">{online.note}</p>
      <ul className="space-y-2">
        {online.services.map((s) => (
          <li key={s.name} className="text-gray-700"><span className="font-medium text-gray-900">{s.name}.</span> {s.text}</li>
        ))}
      </ul>
    </section>
  );
}

function Methods({ methods }) {
  return (
    <section>
      <Heading id="methods">Methods</Heading>
      {methods.map((m) => (
        <div key={m.id} id={`method-${m.id}`} className="mb-3 scroll-mt-20">
          <h3 className="text-base font-semibold text-gray-800">{m.title}</h3>
          <p className="text-gray-700">{m.text}</p>
        </div>
      ))}
    </section>
  );
}

export default function ScholarshipSourcesPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let live = true;
    getJson('/api/scholarship/about')
      .then((j) => { if (live) setData(j); })
      .catch(() => { if (live) setError('The list of sources could not be loaded.'); });
    return () => { live = false; };
  }, []);

  // The sections arrive after the page opens, so a link's #anchor is applied
  // once they are in the page.
  useEffect(() => {
    if (!data) return;
    const id = window.location.hash.replace(/^#/, '');
    if (id) document.getElementById(id)?.scrollIntoView();
  }, [data]);

  return (
    <div className="bg-white rounded-lg shadow p-6 sm:p-8 max-w-4xl mx-auto" data-testid="scholarship-sources-page">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Scholarship: sources and methods</h1>
      <p className="text-gray-700">
        This page lists what the scholarship results on this site are made from, on what terms, and how each part is
        built, so that you can judge what was counted.
      </p>
      <nav className="mt-3 text-sm flex gap-4 flex-wrap" aria-label="Sections">
        <a href="#commentaries" className="text-red-700 hover:underline">Commentaries</a>
        <a href="#journals" className="text-red-700 hover:underline">Journals</a>
        <a href="#online" className="text-red-700 hover:underline">Online services</a>
        <a href="#methods" className="text-red-700 hover:underline">Methods</a>
      </nav>
      {error && <p className="mt-4 text-red-700">{error}</p>}
      {!data && !error && <p className="mt-4 text-gray-500">Loading...</p>}
      {data && (
        <>
          <Commentaries groups={data.commentaries || []} updated={data.updated?.commentaries} />
          <Journals indexes={data.journals || []} updated={data.updated?.indexes} />
          <Online online={data.online || { services: [], note: '' }} />
          <Methods methods={data.methods || []} />
        </>
      )}
    </div>
  );
}
