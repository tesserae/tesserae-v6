import { useEffect, useMemo, useState } from 'react';
import { LoadingSpinner, InfoBadge } from '../common';
import CiteRecordButton from '../common/CiteRecordButton';
import { recordFrom } from '../../utils/citations';
import { bareLocus } from '../reader/refId';
import { useCorpusTextMap } from '../../utils/textNames';
import EventMap from './EventMap';
import { dateLabel, kmLabel, placeLabel, readerLinkWithBack, shortPassageRef, workHeading } from './eventsFormat';
import AboutSourcesLink from '../scholarship/AboutSourcesLink';
import { expandEditions } from '../../utils/editionNames';

const LABEL_TEXT = {
  yes: ['Narrative', 'An offline language model judged that this passage is a narrative of the event itself.'],
  mention: ['Mention', 'An offline language model judged that this passage is a mention of the event, naming it without recounting it.'],
};

function WorkGroup({ work, items, event }) {
  const corpusMap = useCorpusTextMap(items[0]?.language);
  const eventNames = eventNameWords(event);
  return (
    <section className="mb-4">
      <h4 className="text-sm font-semibold text-gray-800 mb-1">{workHeading(work, corpusMap)}</h4>
      <ul className="space-y-2">
        {items.map((p, i) => (
          <li key={`${p.rank}-${i}`} id={`passage-${p.rank}`} className="bg-white border border-gray-200 rounded-lg p-3 scroll-mt-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium text-gray-800" title={p.ref_start}>
                {bareLocus(p.ref_start)}{p.ref_end && p.ref_end !== p.ref_start ? ` to ${bareLocus(p.ref_end)}` : ''}
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
            {p.snippet && (
              <p className="text-sm text-gray-700 mt-1">
                <HighlightedText text={p.snippet} forms={[...matchedForms(p.names_matched), ...(eventNames || [])]} stems />
              </p>
            )}
            {p.names_matched?.length > 0 && (
              <p className="text-xs text-gray-500 mt-1">Names found: {p.names_matched.join('; ')}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
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
        {` ${counts?.yes || 0} Narrative, ${counts?.mention || 0} Mention.`}
        {counts?.no ? ` ${counts.no} more were judged unrelated and are left out.` : ''}
      </p>
      {groups.map(([work, items]) => (
        <WorkGroup key={work} work={work} items={items} event={event} />
      ))}
    </div>
  );
}

const DOCUMENT_GROUPS = [
  ['names', 'Name a participant or the place'],
  ['dated', "Dated within the event's years, nearest first"],
];

/**
 * The words of the event's place and participants, five letters or more, marked in its
 * passages and documents with the case-insensitive stem rule of HighlightedText
 * (Agrippa, Antonius, Perusia where the place is given so).
 */
export function eventNameWords(event) {
  const raw = [event?.place, event?.place_ancient, ...(Array.isArray(event?.participants) ? event.participants : [])];
  const words = raw.filter(Boolean).flatMap((n) => String(n).split(/[\s,()]+/)).filter((w) => w.length >= 5);
  return [...new Set(words)];
}

/**
 * The word forms a passage was matched on, from its "Names found" entries
 * ("Perugia [place] = Περυσίας" gives Περυσίας), so the passage text can mark them
 * the way the document cards do (the project lead, 2026-10-20: "highlight all matching
 * terms").
 */
export function matchedForms(names) {
  return (names || []).flatMap((n) => {
    const i = String(n).lastIndexOf(' = ');
    return i < 0 ? [] : String(n).slice(i + 3).split(/[,;]\s*/).map((f) => f.trim()).filter(Boolean);
  });
}

/** A word as the Mentions store spells its forms: lower case, accents off, v as u, j as i. */
function foldForm(w) {
  return String(w || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/v/g, 'u').replace(/j/g, 'i').replace(/[^a-zα-ω]/g, '');
}

/**
 * The document's text with the words that name a participant or the place marked
 * (the project lead, 2026-10-20: "matching words should be highlighted"). The forms
 * come from the Mentions store, which records the word that matched in each document.
 */
export function HighlightedText({ text, forms, stems = false }) {
  const want = new Set((forms || []).map(foldForm).filter(Boolean));
  if (!want.size) return text;
  // With stems, a word also matches when it begins with a form less its last one or two
  // letters (at least four left), so another case of the same name is marked too
  // (Μαραθῶνα recorded, Μαραθῶνι in the passage).
  const roots = stems ? [...want].map((f) => (f.length >= 6 ? f.slice(0, -2) : f.length >= 5 ? f.slice(0, -1) : f)) : [];
  const hit = (w) => {
    const f = foldForm(w);
    if (!f) return false;
    return want.has(f) || roots.some((r) => r.length >= 4 && f.startsWith(r));
  };
  return String(text).split(/(\s+|[/·,.;:()[\]]+)/).map((part, k) => (
    hit(part)
      ? <mark key={k} className="bg-amber-100 text-gray-900 rounded px-0.5">{part}</mark>
      : part
  ));
}

function DocumentCard({ d, event }) {
  return (
    <li className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <a href={d.view_url} className="text-red-700 hover:underline font-medium">
          {expandEditions(d.edition) || d.text_type || 'Document'}
        </a>
        <span className="text-xs text-gray-500" title="The record number of this document in its database">
          Record {String(d.doc_id).replace(/^[a-z]+:/i, '')}
        </span>
        <span className="text-gray-600">
          {[d.place, dateLabel(d.date_start, d.date_end)].filter(Boolean).join(' · ')}
        </span>
        {d.sources && d.sources.length > 0 && (
          <span className="text-xs text-gray-500" title="The databases that record this document">
            {d.sources.join(' and ')}
          </span>
        )}
        {d.distance_km !== null && d.distance_km !== undefined && (
          <span className="ml-auto text-xs text-gray-500">{kmLabel(d.distance_km)} from {event.place || 'the event'}</span>
        )}
      </div>
      {d.text && (
        <p className="font-serif text-base text-gray-900 mt-1.5" lang={d.language === 'grc' ? 'grc' : 'la'}>
          <HighlightedText text={d.text} forms={[...(d.matched_forms || []), ...eventNameWords(event)]} stems />
        </p>
      )}
      {d.text_snippet && <p className="text-xs text-gray-500 mt-1">{d.text_snippet}</p>}
    </li>
  );
}

function DocumentsTab({ documents, event }) {
  if (documents.length === 0) {
    return (
      <p className="text-sm text-gray-600">
        No inscription or papyrus is dated to the years of this event, within fifty years of dating, and found near it.
      </p>
    );
  }
  const naming = documents.filter((d) => d.group === 'names');
  const dated = documents.filter((d) => (d.group || 'dated') === 'dated');
  /* HONEST EMPTY (2026-10-18): when no document names a participant or the
     place, the regional list is not evidence about the event (the project
     lead on the Sicilian Expedition: "loom weights?"), so the page says so
     and keeps the list behind a disclosure. The collection (EDR, EDH,
     papyri.info, I.Sicily) holds no Attic inscriptions, so Greek classical
     events usually land here. */
  if (naming.length === 0) {
    return (
      <div>
        <p className="text-sm text-gray-700">
          No inscription or papyrus in the collection names a participant or the place of this event
          within its years.
        </p>
        <details className="mt-2" data-testid="events-documents-regional">
          <summary className="text-sm text-gray-600 cursor-pointer">
            {dated.length} document{dated.length === 1 ? '' : 's'} from the region dated within the event's years,
            none naming a participant or the place
          </summary>
          <p className="text-xs text-gray-500 mt-2 mb-2">
            Dating span of no more than fifty years, the most tightly dated first, then the nearest to the event's place.
          </p>
          <ul className="space-y-2">
            {dated.map((d) => <DocumentCard key={d.doc_id} d={d} event={event} />)}
          </ul>
        </details>
      </div>
    );
  }
  return (
    <div>
      <p className="text-xs text-gray-500 mb-3">
        Documents dated within the years of the event, with a dating span of no more than fifty years.
        The first group names one of the event's participants or its place. The second group follows, the
        most tightly dated first, then the nearest to the event's place.
      </p>
      {DOCUMENT_GROUPS.map(([key, title]) => {
        const rows = documents.filter((d) => (d.group || 'dated') === key);
        if (rows.length === 0) return null;
        return (
          <section key={key} className="mb-4">
            <h4 className="text-sm font-semibold text-gray-800 mb-1">{title}</h4>
            <ul className="space-y-2">
              {rows.map((d) => <DocumentCard key={d.doc_id} d={d} event={event} />)}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function ScholarshipRow({ s, openPassage, ranks }) {
  return (
    <li className="bg-white border border-gray-200 rounded-lg p-3 text-sm">
      {s.url
        ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">{s.title}</a>
        : <span className="text-gray-800">{s.title}</span>}
      {s.relevance === 'partly' && (
        <span className="ml-2 text-xs bg-gray-100 text-gray-600 rounded px-1.5 py-0.5"
              title="Treats the passage or the work in a way that touches the event">partly</span>
      )}
      {s.page_ref && <span className="text-xs text-gray-500"> {' · '}{s.page_ref}</span>}
      {/* A commentary row the server could match to a held edition carries
          the fields the Reader's commentary notes cite from; without an
          edition there is nothing to cite and no control is shown. */}
      {s.kind === 'commentary' && s.edition && (
        <span className="ml-2"><CiteRecordButton record={recordFrom({ ...s, kind: 'commentary' }, 'cite')} /></span>
      )}
      {s.scope === 'span' && s.passage_ref && (
        <div className="text-xs mt-1 text-gray-600">within {shortPassageRef(s.passage_ref)}</div>
      )}
      {s.scope !== 'span' && s.passage_ref && ranks.has(s.passage_rank) && (
        <div className="text-xs mt-1">
          <a href={`#passage-${s.passage_rank}`} className="text-red-700 hover:underline"
             onClick={(e) => { e.preventDefault(); openPassage(s.passage_rank); }}>
            on {shortPassageRef(s.passage_ref)}
          </a>
        </div>
      )}
      {/* The model's one-line reason under every judged row, not only the
          rejected ones. A title alone ("The Origin of Plato's Cave") does not
          say why an article is listed for a battle (the project lead,
          2026-10-19: "I can't tell that any of the top hits ... have anything
          to do with it"). */}
      {s.relevance_reason && (
        <div className="text-xs mt-1 text-gray-500">{s.relevance_reason}</div>
      )}
    </li>
  );
}

/** The articles the model judged to cite the passage for another reason, under one line that opens on click. */
function OtherReasonRows({ rows, openPassage, ranks }) {
  const [open, setOpen] = useState(false);
  const n = rows.length;
  return (
    <div className="mt-2">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
              className="text-xs text-gray-600 hover:underline">
        {open ? '\u25BE' : '\u25B8'} {n} {n === 1 ? 'article cites' : 'articles cite'} the passage for another reason
      </button>
      {open && (
        <ul className="space-y-2 mt-2">
          {rows.map((s, i) => <ScholarshipRow key={i} s={s} openPassage={openPassage} ranks={ranks} />)}
        </ul>
      )}
    </div>
  );
}

function ScholarshipTab({ items, openPassage, ranks }) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-600">No article or commentary was found on the passages for this event.</p>;
  }
  const groups = [
    ['article', 'passage', 'Articles citing a leading passage'],
    ['article', 'span', 'Articles citing elsewhere within the span the leading passages cover'],
    ['commentary', null, 'Commentary on the passages'],
  ];
  return (
    <div>
      <p className="text-xs text-gray-500 mb-3">
        The first group holds the articles that cite one of the event's leading passages, each with the passage that brings it in. The second holds the articles that cite another place in the same works between the first and the last of those passages (for example another chapter of the same book), each with the span.
        Where an article was read for its bearing on the event, those that bear on it come first, a small tag marks those that touch it only in part, and those that cite the passage for another reason are kept under one line.{' '}
        <AboutSourcesLink anchor="journals" />
      </p>
      {groups.map(([kind, scope, title]) => {
        const rows = items.filter((s) => s.kind === kind && (scope === null || (s.scope || 'passage') === scope));
        if (rows.length === 0) return null;
        const shown = rows.filter((s) => s.relevance !== 'no');
        const other = rows.filter((s) => s.relevance === 'no');
        return (
          <section key={`${kind}-${scope}`} className="mb-4">
            <h4 className="text-sm font-semibold text-gray-800 mb-1">{title}</h4>
            <ul className="space-y-2">
              {shown.map((s, i) => <ScholarshipRow key={i} s={s} openPassage={openPassage} ranks={ranks} />)}
            </ul>
            {other.length > 0 && <OtherReasonRows rows={other} openPassage={openPassage} ranks={ranks} />}
          </section>
        );
      })}
    </div>
  );
}

/** One event: header, then Passages, Inscriptions & Papyri, Scholarship and Map tabs. */
export default function EventView({ id, goList }) {
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
    // Every tab shows in every view (the project lead, 2026-10-20): an event page is
    // opened on purpose, and with the Literature view's collections off it had kept
    // only its passages. The collection switches still decide what a search covers.
    ['documents', 'Inscriptions & Papyri', true],
    ['scholarship', 'Scholarship', true],
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
  // A response without one of the lists (an older server, a partial answer) shows
  // that tab empty rather than breaking the page.
  const passages = data.passages || [];
  const documents = data.documents || [];
  const scholarship = data.scholarship || [];
  const counts = { passages: passages.length, documents: documents.length, scholarship: scholarship.length };
  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      {back}
      <header className="mt-2 bg-white border border-gray-200 rounded-lg p-4">
        <h2 className="text-2xl font-bold text-gray-900">{ev.label}</h2>
        <p className="text-sm text-gray-600 mt-1">
          {[dateLabel(ev.date_start, ev.date_end), placeLabel(ev.place, ev.place_ancient), ev.type].filter(Boolean).join(' · ')}
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
        {tab === 'passages' && <PassagesTab passages={passages} counts={data.passage_counts} event={ev} focusRank={focusRank} />}
        {tab === 'documents' && <DocumentsTab documents={documents} event={ev} />}
        {tab === 'scholarship' && <ScholarshipTab items={scholarship} openPassage={openPassage} ranks={new Set(passages.map((p) => p.rank))} />}
        {tab === 'map' && <EventMap points={data.map || []} approximatePlace={ev.location_approximate ? (ev.place || 'the region') : null} />}
      </div>
    </div>
  );
}
