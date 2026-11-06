import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { Button, LoadingSpinner, Pagination, CiteButton, InfoBadge } from '../common';
import { usePagination, useServerPagination, MAX_PAGE_SIZE } from '../../hooks/usePagination';
import { fetchResultPage, fetchAllResults, postJsonTo } from '../../utils/api';
import { formatReference, formatElapsedTime } from '../../utils/formatting';
import { languageName } from '../../utils/languageNames';
import {
  useCorpusTextMap,
  resolveDisplayCitation,
  siteIdFromRef,
  formatRefrainPopover,
  formatRhymeSummary,
} from '../../utils/textNames';
import { channelBadge } from '../../utils/channels';
import { displayGreekWithFinalSigma } from '../../utils/greekUtils';
import { dirFor } from '../../utils/rtl';
import { highlightResultHtml } from '../../utils/highlight';
import { ResultsInsight } from '../assistant';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { citationFor } from './citationFor';
import { exportSearchCSV, exportSearchPDF } from './exportHandlers';
import CorpusDistributionPanel, { useCorpusDistribution } from './CorpusDistributionPanel';
import FusionProgressBanner from './FusionProgressBanner';
import QueuedNotice from './QueuedNotice';
import ScansionLine from './ScansionLine';
import { buildDistributionData } from './distributionData';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

// Whether the "Matches:" line would say nothing the Refrain badge has not
// already shown (result card tidy, 2026-10-08): true once every matched
// word is one of the refrain's own words, so the matched-words line is
// omitted rather than repeating the yellow badge in plain text.
const matchedWordsAreRefrain = (r) => {
  const radif = String(r?.poetics?.radif || '').trim();
  if (!radif || !r.matched_words || r.matched_words.length === 0) return false;
  const radifWords = new Set(radif.split(/\s+/).filter(Boolean));
  return r.matched_words.every((w) => {
    const word = typeof w === 'object' ? (w.lemma || w.word || w.display || '') : w;
    return radifWords.has(String(word).trim());
  });
};

// Builds an InfoBadge `more` link to the matching label in the Help page's
// "Reading the results" section (result card tidy, second pass, 2026-10-08).
const helpMore = (onOpenHelp, anchor) => ({
  anchor,
  onClick: () => onOpenHelp && onOpenHelp('results', anchor),
});

const EMPTY = [];

const SearchResults = ({
  results,
  // {id, total, firstPage, pageSize, aggregates} when the server holds the
  // complete list and `results` is only its first page; null otherwise.
  resultSet = null,
  loading,
  error,
  pageSize,
  onPageSizeChange,
  searchRunId,
  onRegister,
  onCorpusSearch,
  onOpenHelp,
  onRerunFresh,
  sortBy,
  setSortBy,
  searchStats,
  language,
  sourceTextInfo,
  targetTextInfo,
  elapsedTime = 0,
  progressText = '',
  matchType = 'lemma',
  fusionProgress = null,
  isQueued = false,
  queuedMessage = ''
}) => {
  // Author/title lookup for citations that fall through the static Latin/
  // Greek/English tables (Persian, Urdu, ...): loads once per language and
  // re-renders this list when it arrives (result card tidy, 2026-10-08).
  const corpusMap = useCorpusTextMap(language);
  const [expandedResults, setExpandedResults] = useState({});
  // Standing chart sidebar: open by default (remembered per session), so a live
  // graph is on the comparison page with no extra clicks. Collapse toggles it.
  const [showDistributionChart, setShowDistributionChart] = useState(() => {
    try { return sessionStorage.getItem('tess_show_dist_chart') !== 'false'; }
    catch { return true; }
  });
  const toggleDistributionChart = () => {
    setShowDistributionChart(prev => {
      const next = !prev;
      try { sessionStorage.setItem('tess_show_dist_chart', String(next)); } catch {}
      return next;
    });
  };
  const [distributionChartView, setDistributionChartView] = useState('target');
  const [chartFilter, setChartFilter] = useState(null);
  // Sidebar has two modes: 'comparison' (where parallels fall in this pair) and
  // 'corpus' (where a chosen parallel's shared words recur across the corpus).
  const [sidebarMode, setSidebarMode] = useState('corpus');
  // Pin the sidebar via inline style (guaranteed to apply) only at the >=lg width
  // where the two-column layout is active; on narrow screens it flows normally.
  const [isWideLayout, setIsWideLayout] = useState(false);
  // The page has a sticky top nav (z-40); pin the sidebar just below it, measuring
  // the nav's real height so it never tucks underneath and gets its top clipped.
  const [stickyTop, setStickyTop] = useState(72);
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const measure = () => {
      setIsWideLayout(mq.matches);
      const nav = document.querySelector('nav.sticky');
      const h = nav ? nav.getBoundingClientRect().height : 56;
      setStickyTop(Math.round(h) + 12);
    };
    measure();
    mq.addEventListener('change', measure);
    window.addEventListener('resize', measure);
    return () => { mq.removeEventListener('change', measure); window.removeEventListener('resize', measure); };
  }, []);
  const stickyAsideStyle = isWideLayout
    ? { position: 'sticky', top: stickyTop, alignSelf: 'flex-start', maxHeight: `calc(100vh - ${stickyTop + 16}px)`, overflowY: 'auto' }
    : undefined;
  const chartRef = useRef(null);
  const [pauseUpdates, setPauseUpdates] = useState(false);
  const [frozenResults, setFrozenResults] = useState(null);

  // Auto-unpause when search completes
  useEffect(() => {
    if (!loading) {
      setPauseUpdates(false);
      setFrozenResults(null);
    }
  }, [loading]);

  // Freeze/unfreeze results on pause toggle
  const handlePauseToggle = useCallback(() => {
    setPauseUpdates(prev => {
      if (!prev) {
        // Pausing: snapshot current results
        setFrozenResults([...results]);
      } else {
        // Unpausing: show live results again
        setFrozenResults(null);
      }
      return !prev;
    });
  }, [results]);

  // Use frozen snapshot when paused, live results otherwise.
  const activeResults = useMemo(
    () => ((pauseUpdates && frozenResults) ? frozenResults : (results || [])),
    [pauseUpdates, frozenResults, results]
  );

  // Sort happens upstream in App; filtering happens here; pagination comes last.
  const filteredResults = useMemo(() => {
    if (!chartFilter) return activeResults;
    return activeResults.filter(r => {
      const locus = chartFilter.view === 'source'
        ? (r.source_locus || r.source?.ref || '')
        : (r.target_locus || r.target?.ref || '');
      const nums = (String(locus).match(/\d+/g) || []).map(Number);
      if (chartFilter.mode === 'line') {
        const line = nums.length ? nums[nums.length - 1] : null;
        return line != null && line >= chartFilter.lineMin && line <= chartFilter.lineMax;
      }
      const book = nums.length ? `Book ${nums[0]}` : 'Other';
      return book === chartFilter.book;
    });
  }, [activeResults, chartFilter]);

  // A new search, a sort change, or a filter change all return to page 1.
  // searchRunId covers the case where two searches return the same result count.
  const paginationResetKey = `${searchRunId ?? ''}|${sortBy ?? ''}|` +
    `${chartFilter ? `${chartFilter.mode || 'book'}:${chartFilter.view}:${chartFilter.book ?? chartFilter.label ?? ''}` : ''}`;

  // Server mode: the finished list lives on the server and every page, sort
  // and chart filter is a request to it. Client mode: fusion's streaming
  // previews, and any response without a result_id, paged in the browser.
  const serverMode = Boolean(resultSet) && !loading;
  const clientPagination = usePagination(serverMode ? EMPTY : filteredResults, {
    pageSize,
    onPageSizeChange,
    resetKey: paginationResetKey,
    // While fusion streams, the array grows on every intermediate event; hold
    // page 1 so the pointer can never trail a set that is still being built.
    pinToFirstPage: loading,
  });
  const serverPagination = useServerPagination(serverMode ? resultSet : null, {
    pageSize,
    onPageSizeChange,
    resetKey: paginationResetKey,
    sort: sortBy,
    filter: chartFilter,
  }, fetchResultPage);
  const {
    visibleItems,
    startIndex,
    currentPage,
    totalPages,
    totalResults,
    pageSize: activePageSize,
    setPage,
    setPageSize,
  } = serverMode ? serverPagination : clientPagination;
  // Count of the whole (unfiltered) list, and of the list after the chart filter.
  const allCount = serverMode ? resultSet.total : activeResults.length;
  const filteredCount = serverMode ? totalResults : filteredResults.length;
  // Exports and Tessa read rows the browser may not hold: fetch them on demand.
  const loadAllRows = useCallback(
    () => (serverMode ? fetchAllResults(resultSet.id) : Promise.resolve(results || [])),
    [serverMode, resultSet, results]
  );
  const loadTopRows = useCallback(
    (n) => {
      if (!serverMode) return Promise.resolve(activeResults.slice(0, n));
      // A page holds at most 100 rows; "all" beyond that comes from the export.
      if (n > MAX_PAGE_SIZE) return fetchAllResults(resultSet.id).then(rows => rows.slice(0, n));
      return fetchResultPage(resultSet.id, { offset: 0, limit: n, sort: sortBy }).then(d => d.results || []);
    },
    [serverMode, resultSet, sortBy, activeResults]
  );

  // Theme Comparison's reading of each visible word-level result: one POST
  // per page (not per row) to /api/passages/pair-lift, keyed by position in
  // visibleItems. Never blocks the page -- results fill in whenever they
  // arrive, and a failed or empty response just means no badges render.
  const [pairLifts, setPairLifts] = useState({});
  useEffect(() => {
    setPairLifts({});
    const workA = sourceTextInfo?.id;
    const workB = targetTextInfo?.id;
    const rows = (visibleItems || []).slice(0, 100);
    // Skip while fusion is still streaming: the visible set (held to page 1)
    // keeps growing underneath this effect, which would fire one request per
    // intermediate event instead of one per rendered page.
    if (loading || !workA || !workB || !rows.length) return undefined;
    let cancelled = false;
    const pairs = rows.map((r) => ({
      work_a: workA, ref_a: r.source_locus || r.source?.ref,
      work_b: workB, ref_b: r.target_locus || r.target?.ref,
    }));
    postJsonTo('/api/passages/pair-lift', { pairs })
      .then((data) => {
        if (cancelled) return;
        const map = {};
        (data?.results || []).forEach((r, idx) => { if (r && r.level) map[idx] = r; });
        setPairLifts(map);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [visibleItems, sourceTextInfo?.id, targetTextInfo?.id, loading]);

  const paginationProps = {
    currentPage,
    totalPages,
    totalResults,
    pageSize: activePageSize,
    onPageChange: setPage,
    onPageSizeChange: setPageSize,
    disabled: loading || serverPagination.pageLoading,
  };

  const toggleExpand = (index) => {
    setExpandedResults(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  // The locus as a citation names it: "verg. aen. 1.1" expanded by
  // formatReference. When a reference starts with the compared text's own id
  // (some corpora tag lines with the file id plus a locus), the author and
  // title come from the text record and the id is cut away. Anything still
  // raw after that (Persian, Urdu, ...) goes to the corpus list's own
  // author/title before this falls back to the bare id (result card tidy,
  // 2026-10-08).
  const displayLocus = useCallback((ref, info) => {
    const r = String(ref || '').replace(/<\/?.*?>/g, '').trim();
    const base = String(info?.id || '').replace(/\.tess$/, '');
    if (base && info?.author && r.startsWith(base + '.')) {
      const name = [info.author, info.title || info.work].filter(Boolean).join(', ');
      return `${name} ${r.slice(base.length + 1)}`;
    }
    return resolveDisplayCitation(formatReference(r, language), r, corpusMap).text;
  }, [language, corpusMap]);

  const exportCSV = useCallback(
    () => exportSearchCSV({ results, loadAllRows }),
    [results, loadAllRows]
  );

  const exportPDF = useCallback(
    () => exportSearchPDF({ results, loadAllRows, sourceTextInfo, targetTextInfo, language }),
    [results, loadAllRows, sourceTextInfo, targetTextInfo, language]
  );

  const exportDistributionChart = () => {
    if (!chartRef.current) return;
    const canvas = chartRef.current.canvas;
    if (!canvas) return;

    const link = document.createElement('a');
    const isSourceView = distributionChartView === 'source';
    const textInfo = isSourceView ? sourceTextInfo : targetTextInfo;
    const authorName = (textInfo?.author || 'author').replace(/[^a-zA-Z0-9]/g, '_');
    const workName = (textInfo?.title || 'work').replace(/[^a-zA-Z0-9]/g, '_');
    link.download = `tesserae_${authorName}_${workName}_${distributionChartView}_${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const distributionData = buildDistributionData({ results, distributionChartView, serverMode, resultSet });

  const distIsLine = distributionData?._mode === 'line';
  const distWork = distributionChartView === 'source'
    ? (sourceTextInfo?.title || 'Source')
    : (targetTextInfo?.title || 'Target');

  // The corpus half of the sidebar (where a parallel's shared words recur
  // across the corpus): state, requests and chart data live in the hook.
  const corpus = useCorpusDistribution({
    results, serverMode, visibleItems, startIndex, sidebarMode, showDistributionChart, loading, language,
  });

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false
      },
      title: {
        display: true,
        text: distIsLine ? `Where the parallels fall in ${distWork}` : 'Parallels by book'
      },
      tooltip: {
        callbacks: {
          label: (context) => `${context.parsed.y} parallel${context.parsed.y !== 1 ? 's' : ''}${distIsLine ? ` at lines ${context.label}` : ''}`
        }
      }
    },
    scales: {
      x: {
        title: {
          display: true,
          text: distIsLine ? `Line in ${distWork}` : distWork,
          font: { size: 12 }
        }
      },
      y: {
        beginAtZero: true,
        ticks: {
          stepSize: 1
        },
        title: {
          display: true,
          text: 'Parallels',
          font: { size: 12 }
        }
      }
    },
    onClick: (event, elements) => {
      if (elements.length > 0 && distributionData) {
        const idx = elements[0].index;
        const label = distributionData.labels[idx];
        if (distributionData._mode === 'line') {
          const m = String(label).match(/(\d+)\D+(\d+)/);
          if (m) setChartFilter({ mode: 'line', view: distributionChartView, lineMin: +m[1], lineMax: +m[2], label });
        } else {
          setChartFilter({ mode: 'book', view: distributionChartView, book: label, label });
        }
      }
    }
  };

  if (loading) {
    // Progressive streaming: if we have intermediate fusion results, show them
    // with a progress banner instead of just a spinner
    if (fusionProgress && results && results.length > 0) {
      // Fall through to render results below — the banner is added in the JSX
    } else {
      const isSlowSearch = matchType === 'sound' || matchType === 'edit_distance' || matchType === 'fusion';
      return (
        <div className="flex flex-col items-center justify-center py-12">
          {isQueued && <QueuedNotice message={queuedMessage} />}
          {isSlowSearch && !isQueued && (
            <div className="text-sm text-gray-600 mb-4 text-center">
              {matchType === 'fusion'
                ? 'Fusion search runs in batches. Results appear as each batch completes.'
                : 'Initial sound or edit distance searches on large texts typically take several minutes.'}
            </div>
          )}
          <LoadingSpinner
            size="lg"
            text={isQueued ? 'Waiting for server...' : (progressText || "Searching for parallels...")}
            elapsedTime={elapsedTime}
          />
        </div>
      );
    }
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        {error}
      </div>
    );
  }

  if ((!results || results.length === 0) && (!frozenResults || frozenResults.length === 0)) {
    return null;
  }

  return (
    <div className="space-y-4">
      {loading && fusionProgress && (
        <FusionProgressBanner
          fusionProgress={fusionProgress}
          pauseUpdates={pauseUpdates}
          progressText={progressText}
          elapsedTime={elapsedTime}
          onPauseToggle={handlePauseToggle}
        />
      )}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 mb-4">
        <div>
          {/* Announced to screen readers. A search can run for half a minute
              and then fill the page, and nothing said it had finished
              (2026-09-08). "polite" so it waits for a pause in speech. */}
          <h3 className="text-lg font-semibold text-gray-900" role="status" aria-live="polite">
            {searchStats?.total_matches && searchStats.total_matches > allCount
              ? `Top ${allCount.toLocaleString()} of ${searchStats.total_matches.toLocaleString()} Parallels`
              : `${allCount} Parallel${allCount !== 1 ? 's' : ''} Found`}
            {loading && fusionProgress && (pauseUpdates ? ' (paused)' : ' (partial)')}
            {chartFilter && ` (${filteredCount} ${chartFilter.mode === 'line' ? `at lines ${chartFilter.label}` : `in ${chartFilter.book}`})`}
          </h3>
          {searchStats && (
            <p className="text-sm text-gray-500">
              {searchStats.elapsed_time && `Search completed in ${formatElapsedTime(searchStats.elapsed_time)}`}
              {searchStats.source_lines && ` | ${searchStats.source_lines} source lines`}
              {searchStats.target_lines && ` | ${searchStats.target_lines} target lines`}
            </p>
          )}
          {!loading && (
            <ResultsInsight
              results={activeResults}
              total={allCount}
              loadResults={loadTopRows}
              source={sourceTextInfo?.display_name || sourceTextInfo?.name}
              target={targetTextInfo?.display_name || targetTextInfo?.name}
              className="mt-2"
            />
          )}
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={toggleDistributionChart}
              className={`text-xs px-3 py-2 rounded whitespace-nowrap ${showDistributionChart ? 'bg-amber-600 text-white' : 'bg-amber-100 text-amber-700 hover:bg-amber-200'}`}
            >
              {showDistributionChart ? 'Hide chart' : 'Show chart'}
            </button>
            <button
              onClick={exportCSV}
              className="text-xs bg-amber-600 text-white px-3 py-2 rounded hover:bg-amber-700 whitespace-nowrap"
            >
              Export CSV
            </button>
            <button
              onClick={exportPDF}
              className="text-xs bg-amber-600 text-white px-3 py-2 rounded hover:bg-amber-700 whitespace-nowrap"
              title="Open print-friendly view; choose 'Save as PDF' in the print dialog."
            >
              Export PDF
            </button>
            {onRerunFresh && !loading && (
              <button
                onClick={onRerunFresh}
                className="text-xs bg-gray-100 text-gray-600 px-3 py-2 rounded hover:bg-gray-200 whitespace-nowrap"
                title="Clear cached results and run the search again"
              >
                Refresh results
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs sm:text-sm text-gray-600">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="border rounded px-2 py-1.5 text-xs sm:text-sm"
            >
              <option value="score">Score</option>
              <option value="source_locus">Source Location</option>
              <option value="target_locus">Target Location</option>
            </select>
          </div>
        </div>
      </div>

      {/* Two-column layout: results on the left, standing chart sidebar on the right */}
      <div className="flex flex-col lg:flex-row-reverse gap-4 items-start">
      {showDistributionChart && results.length > 0 && (
        <aside style={stickyAsideStyle} className="w-full lg:w-96 shrink-0 bg-white border rounded-lg p-4">
          <div className="flex items-center gap-1 mb-3">
            <button
              onClick={() => setSidebarMode('corpus')}
              className={`text-xs px-3 py-1 rounded ${sidebarMode === 'corpus' ? 'bg-gray-700 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >Across the corpus</button>
            <button
              onClick={() => setSidebarMode('comparison')}
              className={`text-xs px-3 py-1 rounded ${sidebarMode === 'comparison' ? 'bg-gray-700 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >In this comparison</button>
          </div>

          {sidebarMode === 'comparison' && (<>
          <div className="flex flex-wrap items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-700">View:</span>
              <button
                onClick={() => { setDistributionChartView('source'); setChartFilter(null); }}
                className={`text-xs px-3 py-1 rounded ${distributionChartView === 'source' ? 'bg-red-700 text-white' : 'bg-red-100 text-red-600 hover:bg-red-200'}`}
              >
                Source
              </button>
              <button
                onClick={() => { setDistributionChartView('target'); setChartFilter(null); }}
                className={`text-xs px-3 py-1 rounded ${distributionChartView === 'target' ? 'bg-amber-600 text-white' : 'bg-amber-100 text-amber-600 hover:bg-amber-200'}`}
              >
                Target
              </button>
            </div>
            <button
              onClick={exportDistributionChart}
              className="text-xs text-gray-600 hover:text-gray-900"
              title="Export chart as PNG"
            >
              Export PNG
            </button>
          </div>
          <div className="h-[150px] sm:h-[200px]">
            <Bar ref={chartRef} data={distributionData || { labels: [], datasets: [] }} options={chartOptions} />
          </div>
          {chartFilter && (
            <div className="mt-3 flex items-center justify-between bg-amber-50 border border-amber-200 rounded px-3 py-2">
              <span className="text-sm text-amber-800">
                Filtering to {chartFilter.mode === 'line' ? `lines ${chartFilter.label}` : chartFilter.book} ({filteredCount} result{filteredCount !== 1 ? 's' : ''})
              </span>
              <button
                onClick={() => setChartFilter(null)}
                className="text-xs text-amber-600 hover:text-amber-800 font-medium"
              >
                Clear Filter
              </button>
            </div>
          )}
          <p className="text-xs text-gray-500 mt-2">Click a bar to filter the results list.</p>
          </>)}

          {sidebarMode === 'corpus' && (
            <CorpusDistributionPanel
              corpus={corpus}
              language={language}
              corpusMap={corpusMap}
              sourceTextInfo={sourceTextInfo}
              targetTextInfo={targetTextInfo}
            />
          )}
        </aside>
      )}

      <div className="flex-1 min-w-0 w-full">
      <Pagination {...paginationProps} variant="full" idPrefix="parallels-top" />
      {/* One legend line in place of the old "Colours" and "Badge colours"
          pair (result card tidy, second pass, 2026-10-08): the highlight
          colors when a poetic result is on screen, then a single hint that
          every label opens its own explanation, then a link to the fuller
          version in Help. */}
      {visibleItems.length > 0 && (
        <p className="text-xs text-gray-600 mb-2 flex flex-wrap items-center gap-x-1 gap-y-1">
          <span className="font-medium">Highlights:</span>
          {['fa', 'ur', 'ar'].includes(language) && visibleItems.some(r => r.poetics) ? (
            <>
              <span><mark className="bg-yellow-200 px-1 rounded">yellow</mark> shared word,</span>
              <span><mark className="bg-rose-200 px-1 rounded">rose</mark> rhyme word.</span>
            </>
          ) : (
            <span><mark className="bg-yellow-200 px-1 rounded">yellow</mark> shared word.</span>
          )}
          <span>Hover over or tap any label for its meaning.</span>
          <button
            type="button"
            onClick={() => onOpenHelp && onOpenHelp('results')}
            className="text-amber-700 hover:text-amber-900 underline"
          >
            Reading the results
          </button>
        </p>
      )}
      {serverMode && serverPagination.pageError && (
        <p className="text-sm text-red-700" role="alert">{serverPagination.pageError}</p>
      )}
      <div className="space-y-3">
        {visibleItems.map((r, i) => (
          <div
            key={startIndex + i}
            className="bg-white border rounded-lg p-3 sm:p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex gap-3">
              <span className="text-xs text-gray-500 min-w-[2.5rem] text-right shrink-0 leading-none" style={{paddingTop: '1px'}}>
                {startIndex + i + 1}.
              </span>
              <div className="flex-1">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-gray-500 mb-1 leading-none">Source</div>
                <div className="font-medium text-gray-900">{citationFor(r, 'source', language, corpusMap)}</div>
                <div
                  className="text-gray-700 mt-1"
                  dir={dirFor(language)}
                  dangerouslySetInnerHTML={{ __html: r.source_text || r.source_snippet || highlightResultHtml(r.source, language, r.matched_words, true, r.target, r.poetics) }}
                />
                {r.features?.source_scansion && <ScansionLine scansion={r.features.source_scansion} />}
                {/* Licensed for indexing and search only (data/restricted_texts.json):
                    the licence requires this line wherever the text's passages
                    are shown, so it follows the passage, not just the work's
                    own page. */}
                {sourceTextInfo?.restricted && (
                  <div className="text-[10px] text-gray-400 mt-1">{sourceTextInfo.credit}</div>
                )}
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Target</div>
                <div className="font-medium text-gray-900">{citationFor(r, 'target', language, corpusMap)}</div>
                <div
                  className="text-gray-700 mt-1"
                  dir={dirFor(language)}
                  dangerouslySetInnerHTML={{ __html: r.target_text || r.target_snippet || highlightResultHtml(r.target, language, r.matched_words, false, r.source, r.poetics) }}
                />
                {r.features?.target_scansion && <ScansionLine scansion={r.features.target_scansion} />}
                {targetTextInfo?.restricted && (
                  <div className="text-[10px] text-gray-400 mt-1">{targetTextInfo.credit}</div>
                )}
              </div>
            </div>

            {/* Row 1: the score, then the poem's-form badges (refrain, rhyme,
                meter, refrain lines) -- the group that shares the highlight
                legend's yellow/rose. Row 2: how-common, then the evidence
                badges (channels, theme), then the action buttons in their
                own non-wrapping group at the right, so they shrink the gaps
                around them before ever dropping to a third row at desktop
                widths (result card tidy, second pass, 2026-10-08). Every
                badge's popover is one short sentence with a "More" link into
                Help; InfoBadge carries no icon, so the badge itself is the
                trigger. */}
            <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t">
              <InfoBadge
                className="bg-white text-gray-600 px-0"
                explanation="How strong the match is overall; results are ranked by it."
                more={helpMore(onOpenHelp, 'score')}
              >
                Score: <span className="font-medium">{(r.fused_score ?? r.score ?? r.overall_score)?.toFixed(2) || '-'}</span>
              </InfoBadge>
              {r.poetics && r.poetics.radif && (
                <InfoBadge
                  className="bg-yellow-100 text-yellow-800"
                  explanation="The refrain (radif) both poems end on."
                  more={helpMore(onOpenHelp, 'refrain')}
                >
                  Refrain: <span dir="rtl">{r.poetics.radif}</span>
                </InfoBadge>
              )}
              {r.poetics && r.poetics.qafia && (
                <InfoBadge
                  className="bg-rose-100 text-rose-800"
                  explanation={r.poetics.rhyme_only
                    ? 'The rhyme letter (rawi) both poems share, weaker evidence than the full rhyme.'
                    : 'The ending the rhyme words of the two poems share, before the refrain.'}
                  extra={formatRhymeSummary(r.poetics, languageName(language)) && (
                    <div dir="auto">{formatRhymeSummary(r.poetics, languageName(language))}</div>
                  )}
                  more={helpMore(onOpenHelp, 'rhyme')}
                >
                  Rhyme: <span dir="rtl">{r.poetics.rhyme_only ? r.poetics.qafia : '…' + r.poetics.qafia}</span>
                  {r.poetics.rhyme_tier === 'partial' && ' (partial)'}
                </InfoBadge>
              )}
              {r.poetics && r.poetics.meter && (
                <InfoBadge
                  className="bg-purple-100 text-purple-700"
                  explanation="Both poems carry this meter label."
                  more={helpMore(onOpenHelp, 'meter')}
                >
                  Meter: <span dir="rtl">{r.poetics.meter}</span>
                </InfoBadge>
              )}
              {r.features?.meter_score > 0 && (
                <InfoBadge
                  className="bg-purple-100 text-purple-700"
                  explanation="How much the two lines' scansion agrees, checked independently of shared words."
                  more={helpMore(onOpenHelp, 'meter')}
                >
                  Metrical: {(r.features.meter_score * 100).toFixed(0)}%
                </InfoBadge>
              )}
              {r.poetics && r.poetics.radif && (r.poetics.source_lines || []).length + (r.poetics.target_lines || []).length > 2 && (() => {
                const refrainLines = formatRefrainPopover(r.poetics, corpusMap);
                return (
                  <InfoBadge
                    className="bg-yellow-50 text-yellow-800"
                    explanation="Every line where the two poems share this refrain; one result stands for the set."
                    extra={refrainLines.lines.map((line, idx) => <div key={idx}>{line}</div>)}
                    more={helpMore(onOpenHelp, 'refrain-lines')}
                  >
                    {(r.poetics.source_lines || []).length} + {(r.poetics.target_lines || []).length} refrain lines
                  </InfoBadge>
                );
              })()}
            </div>
            <div className="flex flex-wrap sm:flex-nowrap items-start sm:items-center gap-2 mt-2">
              <div className="flex flex-wrap items-center gap-2 flex-1 min-w-0">
                {(typeof r.formula_count === 'number' || r.poetics?.corpus_poems != null) && (
                  <span className="text-xs text-gray-500 font-medium">How common:</span>
                )}
                {typeof r.formula_count === 'number' && (
                  <InfoBadge
                    className="bg-gray-100 text-gray-600"
                    explanation="How many works in the corpus contain this shared wording; high means common."
                    more={helpMore(onOpenHelp, 'works-count')}
                  >
                    in {r.formula_count} work{r.formula_count !== 1 ? 's' : ''}
                  </InfoBadge>
                )}
                {r.poetics && r.poetics.corpus_poems != null && (
                  <InfoBadge
                    className="bg-gray-100 text-gray-600"
                    explanation="How many poems in the corpus end on this refrain and rhyme."
                    more={helpMore(onOpenHelp, 'form-count')}
                  >
                    form in {r.poetics.corpus_poems} poem{r.poetics.corpus_poems !== 1 ? 's' : ''}
                  </InfoBadge>
                )}
                {pairLifts[i] && typeof pairLifts[i].lift === 'number' && (
                  <InfoBadge
                    className={`bg-blue-100 text-blue-700 ${pairLifts[i].level === 'strong' ? 'font-semibold' : ''}`}
                    explanation="How much closer in content these lines are than the two works overall."
                    more={helpMore(onOpenHelp, 'theme')}
                  >
                    theme {pairLifts[i].lift >= 0 ? '+' : ''}{pairLifts[i].lift.toFixed(2)}
                  </InfoBadge>
                )}
                {r.channels && r.channels.length > 0 && (
                  <InfoBadge
                    className="bg-blue-100 text-blue-700"
                    explanation="Which kinds of evidence found this match."
                    more={helpMore(onOpenHelp, 'channels')}
                  >
                    {r.channels.map((ch) => channelBadge(ch)).join(' + ')}
                  </InfoBadge>
                )}
                {r.matched_words && r.matched_words.length > 0 && !matchedWordsAreRefrain(r) && (
                  <span className="text-sm text-gray-600">
                    Matches: <span className="font-medium">
                      {r.matched_words.map(w => {
                        const word = typeof w === 'object' ? (w.lemma || w.word || w.display || JSON.stringify(w)) : w;
                        return displayGreekWithFinalSigma(word);
                      }).join(', ')}
                    </span>
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {r.match_basis !== 'semantic' && onCorpusSearch && (
                  <Button
                    variant="tertiary"
                    size="sm"
                    onClick={() => onCorpusSearch(r)}
                    title="Find these words together in other texts"
                  >
                    Search Corpus
                  </Button>
                )}
                {onRegister && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => onRegister(r)}
                    title="Save this parallel to the Repository"
                  >
                    Register
                  </Button>
                )}
                {/* A parallel is the thing a scholar actually puts in a footnote,
                    so Cite belongs on the parallel and not only on the page
                    (interface audit, 2026-09-08). */}
                <CiteButton
                  showReportLink
                  finding={{
                    kind: 'fusion search',
                    source: displayLocus(r.source_locus || r.source?.ref, sourceTextInfo),
                    target: displayLocus(r.target_locus || r.target?.ref, targetTextInfo),
                    language: languageName(language),
                    score: r.fused_score ?? r.score ?? r.overall_score,
                    channels: Array.isArray(r.channels) ? r.channels.join(', ') : (r.channels || ''),
                    corpusVersion: searchStats?.corpus_version,
                    url: typeof window !== 'undefined' ? window.location.href : '',
                    siteId: [siteIdFromRef(r.source_locus || r.source?.ref),
                             siteIdFromRef(r.target_locus || r.target?.ref)]
                      .filter(Boolean).join(' ~ '),
                  }}
                />
              </div>
            </div>
            </div>{/* flex-1 */}
            </div>{/* flex row-number wrapper */}
          </div>
        ))}
      </div>

      <Pagination {...paginationProps} variant="nav" idPrefix="parallels-bottom" />
      </div>{/* flex-1 results column */}
      </div>{/* two-column flex wrapper */}
    </div>
  );
};

export default SearchResults;
