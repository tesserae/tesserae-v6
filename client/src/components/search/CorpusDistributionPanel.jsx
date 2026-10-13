// The corpus half of the chart sidebar: where the shared words of one chosen
// parallel recur across the whole corpus. Moved out of SearchResults.jsx
// (cleaning job H4, 2026-10-13), state, requests and markup unchanged except
// that the D3 timeline now lives in its own component, ResultsTimeline.
// The hook keeps its state in SearchResults, as before, so hiding the chart
// or switching to "In this comparison" does not lose the chosen parallel.
import { useState, useEffect, useRef } from 'react';
import { Bar } from 'react-chartjs-2';
import { postLineSearch } from '../../utils/api';
import { dirFor } from '../../utils/rtl';
import { renderInstanceText } from '../../utils/highlight';
import { citationFor } from './citationFor';
import ResultsTimeline from './ResultsTimeline';

const EMPTY = [];

export const useCorpusDistribution = ({ results, serverMode, visibleItems, startIndex, sidebarMode, showDistributionChart, loading, language }) => {
  const [corpusGroupBy, setCorpusGroupBy] = useState(language === 'he' ? 'work' : 'timeline'); // 'era' | 'author' | 'work' | 'timeline'
  const [corpusHitIdx, setCorpusHitIdx] = useState(0);
  const [corpusData, setCorpusData] = useState(null);
  const [corpusLoading, setCorpusLoading] = useState(false);
  const [corpusSelectedAuthor, setCorpusSelectedAuthor] = useState(null);
  // Lines fetched for a clicked author or work whose lines fell outside the
  // first 500 the chart's search returned: { key, loci } (2026-10-07).
  const [corpusExtraLoci, setCorpusExtraLoci] = useState(null);

  // ---- Corpus mode: where a parallel's shared words recur across the corpus ----
  const ERA_ORDER = { 'Archaic': 0, 'Early Greek': 1, 'Classical': 2, 'Hellenistic': 3, 'Republic': 4, 'Late Republican': 5, 'Late Republic': 5, 'Augustan': 6, 'Early Imperial': 7, 'Imperial': 8, 'Later Imperial': 9, 'Late Antique': 10, 'Patristic': 10, 'Carolingian': 11, 'Medieval': 12, 'Renaissance': 13, 'Early Modern': 14, 'Modern': 15, 'Unknown': 99 };
  const sharedLemmasOf = (r) => {
    const raw = (r?.matched_lemmas && r.matched_lemmas.length) ? r.matched_lemmas : (r?.matched_words || []);
    return raw
      .map(w => (typeof w === 'object' ? (w.lemma || w.word || '') : String(w)).trim())
      // Letters plus combining marks and the zero-width joiner, which Persian
      // and Urdu words carry (mi-gasht is written with one), and Greek accents.
      .filter(w => /^[\p{L}\p{M}\u200c]+$/u.test(w));
  };
  // The picker offers the rows on screen in server mode (the browser no longer
  // holds every row), numbered by their place in the whole list.
  const pickerRows = serverMode ? visibleItems : (results || EMPTY);
  const pickerOffset = serverMode ? startIndex : 0;
  const corpusHit = pickerRows.length ? pickerRows[Math.min(corpusHitIdx, pickerRows.length - 1)] : null;

  // OPEN ON A ROW THE CHART CAN DRAW (2026-10-07). The corpus chart needs two
  // shared words, and Persian and Urdu results lead with refrain-and-rhyme
  // rows that share one (the refrain), so the chart opened on "shares only one
  // word" and looked as if it never worked. When a new list arrives, pick the
  // first row with two or more shared words; the reader can still choose any.
  const pickerKey = `${pickerOffset}|${pickerRows.length}|${pickerRows[0]?.source_locus || pickerRows[0]?.source?.ref || ''}`;
  const lastPickerKey = useRef('');
  useEffect(() => {
    if (!pickerRows.length || lastPickerKey.current === pickerKey) return;
    lastPickerKey.current = pickerKey;
    const first = pickerRows.findIndex((r) => sharedLemmasOf(r).length >= 2);
    setCorpusHitIdx(first >= 0 ? first : 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickerKey]);

  useEffect(() => {
    if (sidebarMode !== 'corpus' || !showDistributionChart || loading || !corpusHit) return;
    const words = sharedLemmasOf(corpusHit);
    const query = words.join(' ');
    if (words.length < 2) { setCorpusData({ query, loci: [], tooFew: true }); return; }
    let cancelled = false;
    setCorpusLoading(true);
    setCorpusSelectedAuthor(null);
    postLineSearch({ query, language, search_type: 'lemma', max_results: 500 })
      .then(d => { if (!cancelled) setCorpusData({ query, corpus_version: d.corpus_version,
        // Every work's count (by_work_all), so the chart covers the whole corpus
        // even when the line list below stops at 500 (2026-10-07).
        byWork: d.by_work_all || null, linesAll: d.lines_all ?? null,
        loci: (d.results || []).map(x => ({ era: x.era, year: x.year, author: x.author,
          work: x.work, locus: x.locus, text: x.text, matched_words: x.matched_words || [] })) }); })
      .catch(() => { if (!cancelled) setCorpusData({ query, loci: [], error: true }); })
      .finally(() => { if (!cancelled) setCorpusLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sidebarMode, corpusHitIdx, showDistributionChart, loading, language, pickerRows]);

  // The rows the corpus chart counts: one per work with its full count when the
  // server sent them, else one per loaded line. A common pair (Persian "man ast")
  // filled the 500-line list from two or three poets, and the chart left out
  // the authors being compared.
  const corpusCountRows = (cd) => (cd?.byWork?.length
    ? cd.byWork.map(w => ({ author: w.author, work: w.work, era: w.era, year: w.year, n: w.count }))
    : (cd?.loci || []).map(l => ({ author: l.author, work: l.work, era: l.era, year: l.year, n: 1 })));
  // A clicked author or work with no line among the 500 loaded: fetch its own
  // lines, so the list under the chart is never empty for a bar that is drawn.
  useEffect(() => {
    if (!corpusSelectedAuthor || !corpusData?.byWork?.length) return;
    const byWork = corpusGroupBy === 'work';
    const has = (corpusData.loci || []).some(l => ((byWork ? l.work : l.author) || 'Unknown') === corpusSelectedAuthor);
    if (has) return;
    const key = `${byWork ? 'w' : 'a'}|${corpusSelectedAuthor}`;
    let cancelled = false;
    postLineSearch({ query: corpusData.query, language, search_type: 'lemma', max_results: 200,
        ...(byWork ? { work: corpusSelectedAuthor } : { author: corpusSelectedAuthor }) })
      .then(d => { if (!cancelled) setCorpusExtraLoci({ key, loci: (d.results || []).map(x => ({ era: x.era, year: x.year,
        author: x.author, work: x.work, locus: x.locus, text: x.text, matched_words: x.matched_words || [] })) }); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [corpusSelectedAuthor, corpusData, corpusGroupBy, language]);

  const CORPUS_COLOR = { backgroundColor: 'rgba(37, 99, 235, 0.7)', borderColor: 'rgb(37, 99, 235)', borderWidth: 1 };
  const getCorpusChartData = () => {
    const countRows = corpusCountRows(corpusData);
    if (!countRows.length) return null;
    if (corpusGroupBy === 'author' || corpusGroupBy === 'work') {
      const datedYear = (l) => (l.year != null && l.year < 9999 ? l.year : null);
      const agg = {}; // author (or work) -> { count, year }
      countRows.forEach(l => {
        const a = (corpusGroupBy === 'work' ? l.work : l.author) || 'Unknown';
        if (!agg[a]) agg[a] = { count: 0, year: datedYear(l) };
        agg[a].count += l.n;
        if (agg[a].year == null) { const y = datedYear(l); if (y != null) agg[a].year = y; }
      });
      let authors = Object.keys(agg);
      // Cap to the top 30 contributors, then order THOSE chronologically.
      authors.sort((a, b) => agg[b].count - agg[a].count);
      const capped = authors.length > 30;
      authors = authors.slice(0, 30);
      const yr = (a) => (agg[a].year != null ? agg[a].year : 9999);
      authors.sort((a, b) => yr(a) - yr(b) || a.localeCompare(b));
      return { _capped: capped, labels: authors,
        datasets: [{ label: 'Occurrences', data: authors.map(a => agg[a].count), ...CORPUS_COLOR }] };
    }
    const byEra = {};
    countRows.forEach(l => { const e = l.era || 'Unknown'; byEra[e] = (byEra[e] || 0) + l.n; });
    const eras = Object.keys(byEra).sort((a, b) => (ERA_ORDER[a] ?? 50) - (ERA_ORDER[b] ?? 50));
    return { labels: eras, datasets: [{ label: 'Occurrences', data: eras.map(e => byEra[e]), ...CORPUS_COLOR }] };
  };
  const corpusChartData = getCorpusChartData();
  const corpusIsWork = corpusGroupBy === 'work';
  // 'work' reuses the horizontal clickable-bar rendering of 'author', keyed on the
  // book instead. Used for Hebrew, whose books share one author and carry no dates.
  const corpusIsAuthor = corpusGroupBy === 'author' || corpusIsWork;
  const corpusIsTimeline = corpusGroupBy === 'timeline';
  const corpusChartOptions = {
    responsive: true, maintainAspectRatio: false,
    indexAxis: corpusIsAuthor ? 'y' : 'x',
    plugins: {
      legend: { display: false },
      title: { display: true, text: corpusIsWork
        ? 'Which works these words recur in'
        : corpusIsAuthor
        ? 'Where these words recur, by author (earliest → latest)'
        : 'Where these words recur across the corpus' },
      tooltip: { callbacks: { label: (c) => {
        const v = corpusIsAuthor ? c.parsed.x : c.parsed.y;
        return `${v} occurrence${v !== 1 ? 's' : ''}`;
      } } },
    },
    onClick: (evt, elements) => {
      if (corpusIsAuthor && elements && elements.length && corpusChartData) {
        setCorpusSelectedAuthor(corpusChartData.labels[elements[0].index]);
      }
    },
    scales: corpusIsAuthor ? {
      x: { beginAtZero: true, ticks: { stepSize: 1 }, title: { display: true, text: 'Occurrences', font: { size: 12 } } },
      y: { ticks: { autoSkip: false, font: { size: 10 } } },
    } : {
      x: { title: { display: true, text: 'Era (earliest → latest)', font: { size: 12 } } },
      y: { beginAtZero: true, ticks: { stepSize: 1 }, title: { display: true, text: 'Occurrences', font: { size: 12 } } },
    },
  };

  return {
    pickerRows, pickerOffset, corpusHit, sharedLemmasOf,
    corpusGroupBy, setCorpusGroupBy, corpusHitIdx, setCorpusHitIdx,
    corpusData, corpusLoading, corpusSelectedAuthor, setCorpusSelectedAuthor, corpusExtraLoci,
    corpusCountRows, corpusChartData, corpusChartOptions,
    corpusIsWork, corpusIsAuthor, corpusIsTimeline,
  };
};

const CorpusDistributionPanel = ({ corpus, language, corpusMap, sourceTextInfo, targetTextInfo }) => {
  const {
    pickerRows, pickerOffset, corpusHit, sharedLemmasOf,
    corpusGroupBy, setCorpusGroupBy, corpusHitIdx, setCorpusHitIdx,
    corpusData, corpusLoading, corpusSelectedAuthor, setCorpusSelectedAuthor, corpusExtraLoci,
    corpusCountRows, corpusChartData, corpusChartOptions,
    corpusIsWork, corpusIsAuthor, corpusIsTimeline,
  } = corpus;
  return (
    <>
      <div className="mb-2">
        <label className="text-xs text-gray-600 block mb-1">Parallel:</label>
        <select
          value={corpusHitIdx}
          onChange={(e) => setCorpusHitIdx(Number(e.target.value))}
          className="w-full border rounded px-2 py-1 text-xs"
        >
          {pickerRows.map((r, i) => (
            <option key={i} value={i}>
              #{pickerOffset + i + 1} · {citationFor(r, 'source', language, corpusMap)} ↔ {citationFor(r, 'target', language, corpusMap)}
              {sharedLemmasOf(r).length < 2 ? ' (one word, no chart)' : ''}
            </option>
          ))}
        </select>
      </div>
      {corpusHit && (
        <p className="text-xs text-gray-500 mb-2">
          Shared words: <span className="font-medium">{sharedLemmasOf(corpusHit).join(', ') || '—'}</span>
        </p>
      )}
      <div className="flex items-center gap-1 mb-2">
        <span className="text-xs text-gray-600 mr-1">Group by:</span>
        {language !== 'he' && (
          <button
            onClick={() => setCorpusGroupBy('timeline')}
            className={`text-xs px-2.5 py-1 rounded ${corpusGroupBy === 'timeline' ? 'bg-blue-600 text-white' : 'bg-blue-100 text-blue-700 hover:bg-blue-200'}`}
          >Timeline</button>
        )}
        {language !== 'he' && (
          <button
            onClick={() => setCorpusGroupBy('era')}
            className={`text-xs px-2.5 py-1 rounded ${corpusGroupBy === 'era' ? 'bg-blue-600 text-white' : 'bg-blue-100 text-blue-700 hover:bg-blue-200'}`}
          >Era</button>
        )}
        <button
          onClick={() => setCorpusGroupBy('work')}
          className={`text-xs px-2.5 py-1 rounded ${corpusGroupBy === 'work' ? 'bg-blue-600 text-white' : 'bg-blue-100 text-blue-700 hover:bg-blue-200'}`}
        >Work</button>
      </div>
      {(corpusIsTimeline || corpusIsWork) && corpusData && !corpusData.tooFew && !corpusLoading && (
        <p className="text-xs text-gray-500 mb-1.5">Click any {corpusIsWork ? 'work' : 'author'} to see its lines.</p>
      )}
      <div>
        {corpusLoading ? (
          <div className="flex items-center justify-center h-[200px] text-sm text-gray-500">Searching the corpus…</div>
        ) : corpusData && corpusData.tooFew ? (
          <div className="flex items-center justify-center h-[200px] text-xs text-gray-400 text-center px-2">This parallel shares only one word, so there is no corpus-wide co-occurrence to map. Pick another.</div>
        ) : corpusIsTimeline ? (
          <ResultsTimeline
            key="corpus-timeline"
            rows={corpusCountRows(corpusData)}
            selectedAuthor={corpusSelectedAuthor}
            onSelectAuthor={setCorpusSelectedAuthor}
            comparedAuthors={[sourceTextInfo?.author, targetTextInfo?.author]}
          />
        ) : corpusChartData ? (
          <div key="corpus-chart" style={{ height: corpusIsAuthor ? Math.max(180, corpusChartData.labels.length * 22) : 200 }}>
            <Bar data={corpusChartData} options={corpusChartOptions} />
          </div>
        ) : (
          <div className="flex items-center justify-center h-[200px] text-xs text-gray-500">No corpus occurrences found.</div>
        )}
      </div>
      {corpusIsAuthor && corpusChartData && corpusChartData._capped && (
        <p className="text-xs text-gray-500 mt-1">Showing the 30 most-cited {corpusIsWork ? 'works' : 'authors, in chronological order'}.</p>
      )}
      {corpusSelectedAuthor && corpusData && corpusData.loci && (() => {
        const loaded = corpusData.loci.filter(l => ((corpusIsWork ? l.work : l.author) || 'Unknown') === corpusSelectedAuthor);
        const extra = corpusExtraLoci && corpusExtraLoci.key === `${corpusIsWork ? 'w' : 'a'}|${corpusSelectedAuthor}` ? corpusExtraLoci.loci : null;
        const rows = loaded.length ? loaded : (extra || []);
        return (
          <div className="mt-2 border-t pt-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-gray-700">
                {corpusSelectedAuthor.replace(/_/g, ' ')} — {rows.length} instance{rows.length !== 1 ? 's' : ''}
              </span>
              <button
                onClick={() => setCorpusSelectedAuthor(null)}
                className="text-xs text-gray-500 hover:text-gray-700"
              >Close</button>
            </div>
            <div className="space-y-1.5 overflow-y-auto" style={{ maxHeight: 200 }}>
              {rows.map((l, i) => (
                <div key={i} className="text-xs leading-snug">
                  <span className="text-gray-500">{i + 1}. </span>
                  <span className="text-gray-500">
                    {[l.work && l.work.replace(/_/g, ' '), l.locus].filter(Boolean).join(' ')}
                  </span>
                  {l.text && <span className="text-gray-700" dir={dirFor(language)}> — {renderInstanceText(l.text, l.matched_words, language)}</span>}
                </div>
              ))}
            </div>
          </div>
        );
      })()}
      {corpusData && corpusData.loci && corpusData.loci.length > 0 && (
        <p className="text-xs text-gray-500 mt-2">
          {corpusData.linesAll != null && corpusData.byWork?.length
            ? `These words occur together in ${corpusData.linesAll.toLocaleString()} corpus lines across ${corpusData.byWork.length} works; the chart counts them all.`
            : `These words co-occur in ${corpusData.loci.length} corpus lines.`}
          {corpusData.corpus_version ? ` Corpus version ${corpusData.corpus_version}.` : ''}
        </p>
      )}
    </>
  );
};

export default CorpusDistributionPanel;
