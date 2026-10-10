import { useEffect, useMemo, useState } from 'react';
import { LoadingSpinner, InfoBadge } from '../common';
import useCollections from '../../hooks/useCollections';
import { displayRef } from '../reader/refId';
import EventMap from './EventMap';
import { dateLabel, kmLabel, yearLabel, readerLinkWithBack } from './eventsFormat';

const LABEL_TEXT = {
  yes: ['Tells of it', 'An offline language model judged that this passage tells of the event itself.'],
  mention: ['Mentions it', 'An offline language model judged that this passage mentions the event without telling of it.'],
};

function workTitle(work) {
  return String(work || '').replace(/\.tess$/, '').replace(/\.part\.\d+.*$/, '').split('.')
    .map((s) => s.replace(/_/g, ' ')).join(': ');
}

function PassagesTab({ passages, counts, event, focusRank }) {
  const groups = useMemo(() => {
    const by = new Map();
    passages.forEach((p) => {
      if (!by.has(p.work)) by.set(p.work, []);
      by.get(p.work).push(p);
    });
    return [...by.entries()];
  }, [passages]);
  useEffect(() => {
    if (focusRank === null || focusRank === undefined) return;
    const el = document.getElementById(`passage-${focusRank}`);
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'center' });
  }, [focusRank]);
  if (passages.length === 0) {
    return <p className="text-sm text-gray-600">No passage has been matched to this event.</p>;
  }
  return (
    <div>
      <p className="text-xs text-gray-500 mb-3">
        {passages.length} passages in {groups.length} {groups.length === 1 ? 'work' : 'works'}.
        {counts?.no ? ` ${counts.no} more were judged unrelated and are left out.` : ''}
      </p>
      {groups.map(([work, items]) => (
        <section key={work} className="mb-4">
          <h4 className="text-sm font-semibold text-gray-800 mb-1">{workTitle(work)}</h4>
          <ul className="space-y-2">
            {items.map((p, i) => (
              <li key={`${p.rank}-${i}`} id={`passage-${p.rank}`} className="bg-white border border-gray-200 rounded-lg p-3 scroll-mt-4">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium text-gray-800">
                    {displayRef(p.ref_start)}{p.ref_end && p.ref_end !== p.ref_start ? ` to ${displayRef(p.ref_end)}` : ''}
                  </span>
                  {LABEL_TEXT[p.llm_label] && (
                    <InfoBadge className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600"
                               explanation={LABEL_TEXT[p.llm_label][1]}>
                      {LABEL_TEXT[p.llm_label][0]}
                    </InfoBadge>
                  )}
                  <a href={readerLinkWithBack(p.reader_url, event.id, event.label)}
                     className="ml-auto text-red-700 hover:underline text-xs">
                    Open in the Reader
                  </a>
                </div>
                {p.snippet && <p className="text-sm text-gray-700 mt-1">{p.snippet}</p>}
                {p.names_matched?.length > 0 && (
                  <p className="text-xs text-gray-500 mt-1">Names found: {p.names_matched.join('; ')}</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function DocumentsTab({ documents, event }) {
  if (documents.length === 0) {
    return (
      <p className="text-sm text-gray-600">
        No inscription or papyrus is dated to the years of this event and found near it.
      </p>
    );
  }
  return (
    <div>
      <p className="text-xs text-gray-500 mb-3">
        Documents dated within the years of the event, nearest first, with the distance from the event's place.
      </p>
      <ul className="space-y-2">
        {documents.map((d) => (
          <li key={d.doc_id} className="bg-white border border-gray-200 rounded-lg p-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <a href={d.view_url} className="text-red-700 hover:underline font-medium">{d.doc_id}</a>
              <span className="text-gray-600">
                {[d.place, dateLabel(d.date_start, d.date_end)].filter(Boolean).join(' · ')}
              </span>
              {d.distance_km !== null && d.distance_km !== undefined && (
                <span className="ml-auto text-xs text-gray-500">{kmLabel(d.distance_km)} from {event.place || 'the event'}</span>
              )}
            </div>
            {d.text_snippet && <p className="text-sm text-gray-700 mt-1">{d.text_snippet}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ScholarshipTab({ items, openPassage, ranks }) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-600">No article or commentary was found on the passages for this event.</p>;
  }
  const kinds = [['article', 'Articles citing the passages'], ['commentary', 'Commentary on the passages']];
  return (
    <div>
      <p className="text-xs text-gray-500 mb-3">
        These are the articles that cite the event's leading passages. Each shows the passage that brings it in.
      </p>
      {kinds.map(([kind, title]) => {
        const rows = items.filter((s) => s.kind === kind);
        if (rows.length === 0) return null;
        return (
          <section key={kind} className="mb-4">
            <h4 className="text-sm font-semibold text-gray-800 mb-1">{title}</h4>
            <ul className="space-y-2">
              {rows.map((s, i) => (
                <li key={i} className="bg-white border border-gray-200 rounded-lg p-3 text-sm">
                  {s.url
                    ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">{s.title}</a>
                    : <span className="text-gray-800">{s.title}</span>}
                  {s.page_ref && <span className="text-xs text-gray-500"> {' · '}{s.page_ref}</span>}
                  {s.passage_ref && ranks.has(s.passage_rank) && (
                    <div className="text-xs mt-1">
                      <a href={`#passage-${s.passage_rank}`} className="text-red-700 hover:underline"
                         onClick={(e) => { e.preventDefault(); openPassage(s.passage_rank); }}>
                        on {displayRef(s.passage_ref)}
                      </a>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

/** One event: header, then Passages, Inscriptions & Papyri, Scholarship and Map tabs. */
export default function EventView({ id, goList }) {
  const { anyOn } = useCollections();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('passages');
  const [focusRank, setFocusRank] = useState(null);

  useEffect(() => {
    let dead = false;
    setData(null);
    setError(null);
    fetch(`/api/events/${encodeURIComponent(id)}`)
      .then(async (r) => {
        if (r.status === 404) throw new Error('This event is not in the dossiers.');
        if (!r.ok) throw new Error(`Server answered ${r.status}`);
        return r.json();
      })
      .then((d) => { if (!dead) setData(d); })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [id]);

  const tabs = [
    ['passages', 'Passages', true],
    ['documents', 'Inscriptions & Papyri', anyOn(['inscriptions', 'papyri'])],
    ['scholarship', 'Scholarship', anyOn(['scholarship'])],
    ['map', 'Map', true],
  ].filter((t) => t[2]);

  const openPassage = (rank) => { setFocusRank(rank); setTab('passages'); };

  const back = (
    <a href="/events" onClick={(e) => { e.preventDefault(); goList(); }}
       className="text-sm text-red-700 hover:underline">
      All events
    </a>
  );

  if (error) {
    return <div className="max-w-4xl mx-auto px-4 py-6">{back}<p className="mt-3 text-sm text-red-700">{error}</p></div>;
  }
  if (!data) {
    return <div className="max-w-4xl mx-auto px-4 py-10"><LoadingSpinner text="Loading event..." /></div>;
  }

  const ev = data.event;
  const counts = { passages: data.passages.length, documents: data.documents.length, scholarship: data.scholarship.length };
  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      {back}
      <header className="mt-2 bg-white border border-gray-200 rounded-lg p-4">
        <h2 className="text-2xl font-bold text-gray-900">{ev.label}</h2>
        <p className="text-sm text-gray-600 mt-1">
          {[dateLabel(ev.date_start, ev.date_end), ev.place, ev.type].filter(Boolean).join(' · ')}
        </p>
        {ev.participants?.length > 0 && (
          <p className="text-sm text-gray-700 mt-2"><span className="text-gray-500">Participants:</span> {ev.participants.join(', ')}</p>
        )}
        {ev.summary ? (
          <>
            <p className="text-base text-gray-800 mt-2">{ev.summary}</p>
            <p className="text-xs text-gray-500 mt-1">
              From <a href={ev.summary_url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">{ev.summary_source || 'Wikipedia'}</a>, {ev.summary_licence}
            </p>
          </>
        ) : ev.description && <p className="text-sm text-gray-800 mt-2">{ev.description}</p>}
        <p className="text-sm mt-2 flex gap-4">
          {ev.wikipedia_url && <a href={ev.wikipedia_url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">Wikipedia</a>}
          {ev.pleiades_url && <a href={ev.pleiades_url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">Pleiades</a>}
        </p>
      </header>

      <div role="tablist" className="flex gap-3 border-b border-gray-200 mt-4 text-sm overflow-x-auto">
        {tabs.map(([tid, label]) => (
          <button key={tid} role="tab" aria-selected={tab === tid} onClick={() => setTab(tid)}
                  className={`px-2 py-2 font-semibold border-b-2 whitespace-nowrap ${
                    tab === tid ? 'text-red-700 border-red-700' : 'text-gray-500 border-transparent hover:text-gray-700'}`}>
            {label}{counts[tid] !== undefined ? ` (${counts[tid]})` : ''}
          </button>
        ))}
      </div>
      <div className="mt-4">
        {tab === 'passages' && <PassagesTab passages={data.passages} counts={data.passage_counts} event={ev} focusRank={focusRank} />}
        {tab === 'documents' && <DocumentsTab documents={data.documents} event={ev} />}
        {tab === 'scholarship' && <ScholarshipTab items={data.scholarship} openPassage={openPassage} ranks={new Set(data.passages.map((p) => p.rank))} />}
        {tab === 'map' && <EventMap points={data.map} />}
      </div>
    </div>
  );
}
