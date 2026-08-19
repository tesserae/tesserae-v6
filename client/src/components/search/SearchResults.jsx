import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { Button, LoadingSpinner, Pagination } from '../common';
import { usePagination } from '../../hooks/usePagination';
import { formatReference, formatElapsedTime } from '../../utils/formatting';
import { displayGreekWithFinalSigma } from '../../utils/greekUtils';
import { dirFor, isRTL } from '../../utils/rtl';
import { normalizeCoptic } from '../../utils/copticUtils';
import { exportRowsToPDF } from '../../utils/exportResults';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import * as d3 from 'd3';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const SearchResults = ({
  results,
  loading,
  error,
  pageSize,
  onPageSizeChange,
  searchRunId,
  onRegister,
  onCorpusSearch,
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
  const [corpusGroupBy, setCorpusGroupBy] = useState('timeline'); // 'era' | 'author' | 'timeline'
  const [corpusHitIdx, setCorpusHitIdx] = useState(0);
  const [corpusData, setCorpusData] = useState(null);
  const [corpusLoading, setCorpusLoading] = useState(false);
  const [corpusSelectedAuthor, setCorpusSelectedAuthor] = useState(null);
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
  const timelineRef = useRef(null);
  const [pauseUpdates, setPauseUpdates] = useState(false);
  const [frozenResults, setFrozenResults] = useState(null);
  const fusionBatchTotal = fusionProgress?.batchTotal || fusionProgress?.channelsTotal || 0;
  const fusionBatchIndex = fusionProgress?.batchIndex || fusionProgress?.channelsDone?.length || 0;
  const fusionBatchPercent = fusionBatchTotal > 0
    ? Math.min(100, Math.round((fusionBatchIndex / fusionBatchTotal) * 100))
    : 0;
  const fusionPhaseLabel = fusionProgress?.phase === 'window' ? 'Window pass' : 'Line pass';

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

  const {
    visibleItems,
    startIndex,
    currentPage,
    totalPages,
    totalResults,
    pageSize: activePageSize,
    setPage,
    setPageSize,
  } = usePagination(filteredResults, {
    pageSize,
    onPageSizeChange,
    resetKey: paginationResetKey,
    // While fusion streams, the array grows on every intermediate event; hold
    // page 1 so the pointer can never trail a set that is still being built.
    pinToFirstPage: loading,
  });

  const paginationProps = {
    currentPage,
    totalPages,
    totalResults,
    pageSize: activePageSize,
    onPageChange: setPage,
    onPageSizeChange: setPageSize,
    disabled: loading,
  };

  const toggleExpand = (index) => {
    setExpandedResults(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const highlightMatchedWords = useCallback((text, matchedWords, side) => {
    if (!text || !matchedWords || matchedWords.length === 0) return text;
    const words = new Set();
    matchedWords.forEach(m => {
      const w = side === 'source' ? m.source_word : m.target_word;
      if (w) words.add(w.toLowerCase());
    });
    if (words.size === 0) return text;
    return text.replace(/\S+/g, token => {
      const stripped = token.toLowerCase().replace(/^[.,;:!?'"()\u2014\u2013-]+/, '').replace(/[.,;:!?'"()\u2014\u2013-]+$/, '');
      if (stripped && words.has(stripped)) {
        const start = token.toLowerCase().indexOf(stripped);
        return token.slice(0, start) + '**' + token.slice(start, start + stripped.length) + '**' + token.slice(start + stripped.length);
      }
      return token;
    });
  }, []);

  const exportCSV = useCallback(() => {
    if (!results || results.length === 0) return;

    // Sort by fused_score descending — the same score the on-screen list and
    // ranking show. Falls back to score / overall_score for legacy formats.
    // Without this explicit sort the CSV could appear unordered if the API
    // serializes results in some other internal order.
    const scoreOf = (r) => r.fused_score ?? r.score ?? r.overall_score ?? 0;
    const sorted = [...results].sort((a, b) => scoreOf(b) - scoreOf(a));
    const headers = ['Rank', 'Source Locus', 'Source Text', 'Target Locus', 'Target Text', 'Score', 'Matched Words', 'Channels'];
    const rows = sorted.map((r, idx) => {
      const mw = r.matched_words || [];
      const sourceText = (r.source_text || r.source_snippet || r.source?.text || '').replace(/<[^>]*>/g, '').replace(/"/g, '""');
      const targetText = (r.target_text || r.target_snippet || r.target?.text || '').replace(/<[^>]*>/g, '').replace(/"/g, '""');
      return [
        String(idx + 1),
        r.source_locus || r.source?.ref || '',
        highlightMatchedWords(sourceText, mw, 'source'),
        r.target_locus || r.target?.ref || '',
        highlightMatchedWords(targetText, mw, 'target'),
        scoreOf(r).toFixed(3),
        mw.map(w => typeof w === 'object' ? (w.lemma || w.word || '') : w).join('; '),
        (r.channels || []).join('; '),
      ];
    });

    const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n');
    // Prepend UTF-8 BOM so Excel reads non-Latin scripts (Coptic, Greek) as Unicode, not Windows-1252.
    const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tesserae_results_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [results]);

  const exportPDF = useCallback(() => {
    if (!results || results.length === 0) return;
    const headers = ['#', 'Source Locus', 'Source Text', 'Target Locus', 'Target Text', 'Score', 'Matched Words', 'Channels'];
    // Token-based renderer: split source/target text on whitespace, compare each
    // token against the matched-word set. Robust against any script and avoids
    // regex word-boundary issues with non-ASCII alphabets. For Coptic the
    // legacy/primary Unicode-block mismatch is normalised before comparing.
    const escHtml = (s) => String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const stripPunct = (s) => s.replace(/^[\s.,;:!?'"()—–·‧·\-]+/, '')
                              .replace(/[\s.,;:!?'"()—–·‧·\-]+$/, '');
    const isCop = language === 'cop';
    const norm = (s) => isCop ? normalizeCoptic(s) : s.toLowerCase();
    const renderHL = (text, mw, side) => {
      if (!text) return '';
      const targets = new Set();
      (mw || []).forEach(w => {
        const word = typeof w === 'object'
          ? (side === 'source' ? w.source_word : w.target_word) || w.word || w.lemma
          : w;
        if (!word) return;
        const s = String(word);
        if (s.includes('~') || s.includes('[')) return; // skip composite labels
        targets.add(norm(stripPunct(s)));
      });
      if (targets.size === 0) return escHtml(text);
      return String(text).split(/(\s+)/).map(part => {
        if (/^\s+$/.test(part) || part === '') return escHtml(part);
        const stripped = stripPunct(part);
        const cmp = norm(stripped);
        let hit = targets.has(cmp);
        if (!hit) {
          // Substring fallback: bound-group token containing a sub-word match.
          for (const t of targets) {
            if (t.length >= 3 && cmp.includes(t)) { hit = true; break; }
          }
        }
        return hit ? `<strong class="hl">${escHtml(part)}</strong>` : escHtml(part);
      }).join('');
    };
    // Sort by fused_score descending so the PDF order matches what's shown
    // on screen (which uses fused_score as the primary score). The API may
    // serialize results in a different internal order; without an explicit
    // sort the PDF could appear out of order.
    const scoreOf = (r) => r.fused_score ?? r.score ?? r.overall_score ?? 0;
    const sorted = [...results].sort((a, b) => scoreOf(b) - scoreOf(a));
    const rows = sorted.map((r, idx) => {
      const mw = r.matched_words || [];
      const sourceText = (r.source_text || r.source_snippet || r.source?.text || '').replace(/<[^>]*>/g, '');
      const targetText = (r.target_text || r.target_snippet || r.target?.text || '').replace(/<[^>]*>/g, '');
      return [
        String(idx + 1),
        r.source_locus || r.source?.ref || '',
        renderHL(sourceText, mw, 'source'),
        r.target_locus || r.target?.ref || '',
        renderHL(targetText, mw, 'target'),
        scoreOf(r).toFixed(3),
        mw.map(w => typeof w === 'object' ? (w.lemma || w.word || '') : w).join('; '),
        (r.channels || []).join('; '),
      ];
    });
    const sourceLabel = sourceTextInfo ? `${sourceTextInfo.author || ''} ${sourceTextInfo.title || sourceTextInfo.work || ''}`.trim() : '';
    const targetLabel = targetTextInfo ? `${targetTextInfo.author || ''} ${targetTextInfo.title || targetTextInfo.work || ''}`.trim() : '';
    const subtitle = sourceLabel && targetLabel ? `${sourceLabel} vs ${targetLabel}` : '';
    const rtl = isRTL(language);  // Persian/Arabic/Urdu/Hebrew are right-to-left
    // Headers are ['#', 'Source Locus', 'Source Text', 'Target Locus',
    // 'Target Text', 'Score', 'Matched Words', 'Channels']. Widths chosen
    // to minimise row height: each column gets width roughly proportional to
    // its typical content length, so every column wraps to a similar number
    // of lines instead of one column blowing up the row.
    const colWidths = ['3%', '8%', '25%', '8%', '25%', '4%', '17%', '10%'];
    exportRowsToPDF('Tesserae V6 — Search Results', subtitle, headers, rows, {
      htmlCells: true,
      dir: rtl ? 'rtl' : 'ltr',
      lang: language || '',
      colWidths,
    });
  }, [results, sourceTextInfo, targetTextInfo, language]);

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

  const getDistributionData = useCallback(() => {
    if (!results || results.length === 0) return null;
    const isSourceView = distributionChartView === 'source';
    // A locus like "1.469" -> book 1, line 469; a flat "469" -> line only.
    const parseLoc = (locus) => {
      const nums = (String(locus).match(/\d+/g) || []).map(Number);
      return { book: nums.length >= 2 ? nums[0] : null, line: nums.length ? nums[nums.length - 1] : null };
    };
    const pts = results.map(r => parseLoc(isSourceView
      ? (r.source_locus || r.source?.ref || '')
      : (r.target_locus || r.target?.ref || '')));
    const color = isSourceView ? 'rgba(185, 28, 28, 0.7)' : 'rgba(217, 119, 6, 0.7)';
    const border = isSourceView ? 'rgb(185, 28, 28)' : 'rgb(217, 119, 6)';
    const books = new Set(pts.map(p => p.book).filter(b => b != null));

    // Single book (e.g. Aeneid 1 vs Lucan 1): a by-book chart is one useless
    // column, so show WHERE ALONG THE BOOK the parallels fall — bin by line.
    if (books.size <= 1) {
      const lines = pts.map(p => p.line).filter(n => n != null);
      if (lines.length === 0) return null;
      const maxLine = Math.max(...lines);
      const band = [10, 25, 50, 100, 200, 500, 1000].find(b => Math.ceil(maxLine / b) <= 18) || 1000;
      const nBands = Math.max(1, Math.ceil(maxLine / band));
      const counts = new Array(nBands).fill(0);
      pts.forEach(p => { if (p.line != null) counts[Math.min(nBands - 1, Math.floor((p.line - 1) / band))]++; });
      return {
        _mode: 'line', _band: band,
        labels: counts.map((_, i) => `${i * band + 1}–${(i + 1) * band}`),
        datasets: [{ label: 'Parallels', data: counts, backgroundColor: color, borderColor: border, borderWidth: 1 }]
      };
    }

    // Multiple books: keep the by-book view.
    const bookData = {};
    pts.forEach(p => { const k = `Book ${p.book}`; (bookData[k] = bookData[k] || { count: 0 }).count++; });
    const sorted = Object.keys(bookData).sort((a, b) =>
      (parseInt(a.replace(/\D/g, '')) || 0) - (parseInt(b.replace(/\D/g, '')) || 0));
    return {
      _mode: 'book',
      labels: sorted,
      datasets: [{ label: 'Parallels', data: sorted.map(k => bookData[k].count), backgroundColor: color, borderColor: border, borderWidth: 1 }]
    };
  }, [results, distributionChartView]);

  const distributionData = getDistributionData();
  const distIsLine = distributionData?._mode === 'line';
  const distWork = distributionChartView === 'source'
    ? (sourceTextInfo?.title || 'Source')
    : (targetTextInfo?.title || 'Target');

  // ---- Corpus mode: where a parallel's shared words recur across the corpus ----
  const ERA_ORDER = { 'Archaic': 0, 'Early Greek': 1, 'Classical': 2, 'Hellenistic': 3, 'Republic': 4, 'Late Republican': 5, 'Late Republic': 5, 'Augustan': 6, 'Early Imperial': 7, 'Imperial': 8, 'Later Imperial': 9, 'Late Antique': 10, 'Patristic': 10, 'Carolingian': 11, 'Medieval': 12, 'Renaissance': 13, 'Early Modern': 14, 'Modern': 15, 'Unknown': 99 };
  const sharedLemmasOf = (r) => {
    const raw = (r?.matched_lemmas && r.matched_lemmas.length) ? r.matched_lemmas : (r?.matched_words || []);
    return raw
      .map(w => (typeof w === 'object' ? (w.lemma || w.word || '') : String(w)).trim())
      .filter(w => /^[\p{L}]+$/u.test(w));
  };
  const corpusHit = (results && results.length) ? results[Math.min(corpusHitIdx, results.length - 1)] : null;

  useEffect(() => {
    if (sidebarMode !== 'corpus' || !showDistributionChart || loading || !corpusHit) return;
    const words = sharedLemmasOf(corpusHit);
    const query = words.join(' ');
    if (words.length < 2) { setCorpusData({ query, loci: [], tooFew: true }); return; }
    let cancelled = false;
    setCorpusLoading(true);
    setCorpusSelectedAuthor(null);
    fetch('/api/line-search', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, language, search_type: 'lemma', max_results: 500 }),
    })
      .then(res => res.json())
      .then(d => { if (!cancelled) setCorpusData({ query, corpus_version: d.corpus_version,
        loci: (d.results || []).map(x => ({ era: x.era, year: x.year, author: x.author,
          work: x.work, locus: x.locus, text: x.text, matched_words: x.matched_words || [] })) }); })
      .catch(() => { if (!cancelled) setCorpusData({ query, loci: [], error: true }); })
      .finally(() => { if (!cancelled) setCorpusLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sidebarMode, corpusHitIdx, showDistributionChart, loading, language, results]);

  const CORPUS_COLOR = { backgroundColor: 'rgba(37, 99, 235, 0.7)', borderColor: 'rgb(37, 99, 235)', borderWidth: 1 };
  const getCorpusChartData = () => {
    if (!corpusData || !corpusData.loci || !corpusData.loci.length) return null;
    if (corpusGroupBy === 'author') {
      const datedYear = (l) => (l.year != null && l.year < 9999 ? l.year : null);
      const agg = {}; // author -> { count, year }
      corpusData.loci.forEach(l => {
        const a = l.author || 'Unknown';
        if (!agg[a]) agg[a] = { count: 0, year: datedYear(l) };
        agg[a].count++;
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
    corpusData.loci.forEach(l => { const e = l.era || 'Unknown'; byEra[e] = (byEra[e] || 0) + 1; });
    const eras = Object.keys(byEra).sort((a, b) => (ERA_ORDER[a] ?? 50) - (ERA_ORDER[b] ?? 50));
    return { labels: eras, datasets: [{ label: 'Occurrences', data: eras.map(e => byEra[e]), ...CORPUS_COLOR }] };
  };
  const corpusChartData = getCorpusChartData();
  const corpusIsAuthor = corpusGroupBy === 'author';
  const corpusIsTimeline = corpusGroupBy === 'timeline';
  const corpusChartOptions = {
    responsive: true, maintainAspectRatio: false,
    indexAxis: corpusIsAuthor ? 'y' : 'x',
    plugins: {
      legend: { display: false },
      title: { display: true, text: corpusIsAuthor
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

  // Vertical timeline (d3): the date axis runs top (latest) to bottom (earliest);
  // each author sits at its actual year, so time clusters and gaps are visible,
  // with a bar for how often the shared words occur in that author. Click an
  // author to list its actual instances below the chart.
  useEffect(() => {
    if (!(sidebarMode === 'corpus' && corpusGroupBy === 'timeline')) return;
    const host = timelineRef.current;
    if (!host) return;
    host.innerHTML = '';
    if (!corpusData || !corpusData.loci || !corpusData.loci.length) return;
    const datedYear = (l) => (l.year != null && l.year < 9999 ? l.year : null);
    const agg = {};
    corpusData.loci.forEach(l => {
      const a = l.author || 'Unknown';
      (agg[a] = agg[a] || { count: 0, year: datedYear(l) }).count++;
      if (agg[a].year == null) { const y = datedYear(l); if (y != null) agg[a].year = y; }
    });
    let data = Object.entries(agg).map(([author, v]) => ({ author, count: v.count, year: v.year }))
      .filter(d => d.year != null);
    if (!data.length) {
      d3.select(host).append('div').attr('class', 'text-xs text-gray-400 p-2')
        .text('No dated authors to place on a timeline.');
      return;
    }
    data = data.sort((a, b) => b.count - a.count).slice(0, 40).sort((a, b) => b.year - a.year);

    const rowH = 16, marginTop = 16, marginBottom = 8, axisW = 50, labelW = 175;
    const width = host.clientWidth || 340;
    const baseHeight = marginTop + marginBottom + data.length * rowH;

    const years = data.map(d => d.year);
    const yScale = d3.scaleLinear().domain([d3.min(years), d3.max(years)])
      .range([baseHeight - marginBottom, marginTop]).nice();
    let lastY = -Infinity;
    data.forEach(d => { d.trueY = yScale(d.year); d.y = Math.max(d.trueY, lastY + rowH); lastY = d.y; });
    // Greedy de-overlap can push the earliest author below baseHeight when dates
    // cluster or an outlier stretches the scale; grow the canvas so nothing clips.
    const height = Math.max(baseHeight, lastY + marginBottom + 6);
    const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)
      .attr('font-family', 'inherit');
    const dotR = 3, dotGap = 8;
    const dotCap = Math.max(1, Math.floor((width - axisW - labelW) / dotGap));
    const fmtYear = y => (y < 0 ? `${-y} BCE` : `${y} CE`);
    const trunc = s => (s.length > 15 ? s.slice(0, 14) + '…' : s);

    svg.append('line').attr('x1', axisW - 6).attr('x2', axisW - 6)
      .attr('y1', marginTop - 6).attr('y2', baseHeight - marginBottom).attr('stroke', '#e5e7eb');
    svg.append('g').selectAll('text.tick').data(yScale.ticks(6)).join('text')
      .attr('x', 2).attr('y', d => yScale(d)).attr('dy', '0.32em')
      .attr('font-size', 9).attr('fill', '#9ca3af').text(d => fmtYear(d));

    const rows = svg.append('g').selectAll('g.row').data(data).join('g')
      .style('cursor', 'pointer')
      .on('click', (event, d) => setCorpusSelectedAuthor(d.author))
      .on('mouseover', function () { d3.select(this).select('text.author-label').style('text-decoration', 'underline'); })
      .on('mouseout', function () { d3.select(this).select('text.author-label').style('text-decoration', null); });
    rows.append('line').attr('x1', axisW - 6).attr('x2', axisW)
      .attr('y1', d => d.trueY).attr('y2', d => d.y).attr('stroke', '#e5e7eb');
    // One dot per occurrence, so a single instance is a single dot rather than a
    // long bar. Beyond dotCap dots a "+" marks the overflow; the exact total is in
    // the label. dotCap is width-driven, so longer names simply leave room for fewer.
    rows.each(function (d) {
      const g = d3.select(this);
      const n = Math.min(d.count, dotCap);
      const fill = d.author === corpusSelectedAuthor ? 'rgba(37,99,235,1)' : 'rgba(37,99,235,0.75)';
      for (let i = 0; i < n; i++) {
        g.append('circle').attr('cx', axisW + dotR + i * dotGap).attr('cy', d.y)
          .attr('r', dotR).attr('fill', fill);
      }
      if (d.count > dotCap) {
        g.append('text').attr('x', axisW + n * dotGap + 1).attr('y', d.y).attr('dy', '0.32em')
          .attr('font-size', 10).attr('font-weight', 700).attr('fill', fill).text('+');
      }
    });
    rows.append('text').attr('class', 'author-label')
      .attr('x', d => axisW + Math.min(d.count, dotCap) * dotGap + (d.count > dotCap ? 9 : 0) + 6)
      .attr('y', d => d.y).attr('dy', '0.32em')
      .attr('font-size', 9)
      .attr('font-weight', d => d.author === corpusSelectedAuthor ? 700 : 400)
      .attr('fill', '#2563eb')
      .text(d => `${trunc(d.author.replace(/_/g, ' '))}, ${fmtYear(d.year)} (${d.count})`);
    rows.append('title').text(d => `${d.author.replace(/_/g, ' ')} — ${fmtYear(d.year)} — ${d.count} occurrence${d.count !== 1 ? 's' : ''}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sidebarMode, corpusGroupBy, corpusData, corpusSelectedAuthor]);

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

  const renderHighlightedText = (textData, language = null, matchedWords = [], isSource = true, otherTextData = null) => {
    if (!textData) return '';

    if (typeof textData === 'string') return textData;

    const { text, tokens, highlight_indices } = textData;

    if (!text) return '';

    // Build set of words to highlight from multiple sources
    const wordsToHighlight = new Set();
    // For sound matching: n-grams to search for within words
    const soundNgrams = new Set();

    // 1. From highlight_indices (if available)
    if (tokens && highlight_indices && highlight_indices.length > 0) {
      highlight_indices.forEach(i => {
        const token = tokens[i]?.toLowerCase();
        if (token) wordsToHighlight.add(token);
      });
    }

    // 2. From matched_words (for semantic and sound matches)
    if (matchedWords && matchedWords.length > 0) {
      matchedWords.forEach(m => {
        // Add the source or target word based on which side we're rendering
        const word = isSource ? m.source_word : m.target_word;
        if (word) wordsToHighlight.add(word.toLowerCase());
        // Also add the lemma (handles cases where lemma differs from token)
        if (m.lemma && !m.lemma.includes('\u2248') && m.lemma !== 'semantic') {
          // Check if this looks like a sound n-gram match (e.g., "[ngram]", "source~target")
          const lemmaStr = String(m.lemma);
          if (lemmaStr.includes('[') || lemmaStr.includes('~')) {
            // Extract n-grams from sound match format
            const ngrams = lemmaStr.split(/[\[\],~\s]+/).filter(s => s.length >= 2);
            ngrams.forEach(ng => soundNgrams.add(ng.toLowerCase()));
          } else {
            wordsToHighlight.add(lemmaStr.toLowerCase());
          }
        }
        // Handle display field for sound matches
        if (m.display) {
          const displayStr = String(m.display);
          if (displayStr.includes('[') || displayStr.includes('~')) {
            const ngrams = displayStr.split(/[\[\],~\s]+/).filter(s => s.length >= 2);
            ngrams.forEach(ng => soundNgrams.add(ng.toLowerCase()));
          }
        }
      });
    }

    // 3. Find common word stems between source and target (ONLY for semantic matches)
    // For exact/lemma matches, we trust the backend highlight_indices which respect the stoplist
    const isSemanticMatch = matchedWords?.some(m => m.similarity !== undefined || m.lemma === 'semantic');
    if (isSemanticMatch && otherTextData && otherTextData.tokens && tokens) {
      const thisTokens = new Set(tokens.map(t => t?.toLowerCase()).filter(Boolean));
      const otherTokens = new Set(otherTextData.tokens.map(t => t?.toLowerCase()).filter(Boolean));

      // Find tokens that share a common stem (first 4+ chars) - catches hasta/hastam
      thisTokens.forEach(token => {
        if (token.length >= 4) {
          const stem = token.slice(0, Math.min(token.length - 1, 5));
          otherTokens.forEach(otherToken => {
            if (otherToken.length >= 4 && otherToken.startsWith(stem)) {
              wordsToHighlight.add(token);
            }
          });
        }
      });
    }

    // Helper to check if a word matches any highlight word or contains sound n-grams
    const shouldHighlight = (word) => {
      const normalized = word.toLowerCase().replace(/[.,;:!?'"()\u2014\u2013-]+$/, '').replace(/^[.,;:!?'"()\u2014\u2013-]+/, '');
      if (wordsToHighlight.has(normalized)) return true;

      // For sound matching: check if word contains any of the matched n-grams
      if (soundNgrams.size > 0) {
        for (const ngram of soundNgrams) {
          if (normalized.includes(ngram)) return true;
          // Also check with Greek accent normalization (strip diacritics for matching)
          const normalizedNoAccents = normalized.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
          const ngramNoAccents = ngram.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
          if (normalizedNoAccents.includes(ngramNoAccents)) return true;
        }
      }

      // For Latin, also check u/v equivalence
      if (language === 'la') {
        const uvNormalized = normalized.replace(/[uv]/g, 'u');
        for (const hw of wordsToHighlight) {
          if (hw.replace(/[uv]/g, 'u') === uvNormalized) return true;
        }
      }
      // Coptic uses two equivalent Unicode blocks (U+03E2-03EF and
      // U+2CB2-2CBF) for the same seven letters. Backend tokens are
      // normalised to the latter; .tess display text uses the former.
      // Normalise both sides before comparing. Backend tokens are
      // sub-word morphemes (Scriptorium CoNLL-U) but the displayed text is
      // whitespace-split into bound groups, so a sub-word match must
      // highlight any bound group that contains it.
      if (language === 'cop') {
        const copNormalized = normalizeCoptic(normalized);
        for (const hw of wordsToHighlight) {
          const hwNorm = normalizeCoptic(hw);
          if (!hwNorm) continue;
          if (hwNorm === copNormalized) return true;
          if (copNormalized.includes(hwNorm)) return true;
        }
      }
      return false;
    };

    if (wordsToHighlight.size === 0 && soundNgrams.size === 0) {
      // Still need to handle line breaks in window results
      return text.includes('\n') ? text.replace(/\n/g, '<br class="verse-break" />') : text;
    }

    // Split text into verses (window results have \n between lines)
    const verses = text.split('\n');
    const highlightedVerses = verses.map(verse => {
      const parts = verse.split(/(\s+)/);
      return parts.map(part => {
        if (/^\s+$/.test(part)) return part; // whitespace
        if (shouldHighlight(part)) {
          return `<mark class="bg-yellow-200 px-0.5 rounded">${part}</mark>`;
        }
        return part;
      }).join('');
    });

    return highlightedVerses.join('<br class="verse-break" />');
  };

  // Bold the matched words inside a corpus-instance line. matched_words are the
  // actual surface tokens the line-search flagged, so normalize the same way the
  // main highlighter does (case, trailing punctuation, Latin u/v, Greek accents).
  const renderInstanceText = (text, matchedWords, lang) => {
    if (!text) return null;
    const strip = (w) => w.toLowerCase()
      .replace(/[.,;:!?'"()—–··-]+$/, '')
      .replace(/^[.,;:!?'"()—–··-]+/, '');
    const norm = (w) => {
      let n = strip(w);
      if (lang === 'la') n = n.replace(/[uv]/g, 'u').replace(/j/g, 'i');
      if (lang === 'grc') n = n.normalize('NFD').replace(/[̀-ͯ]/g, '');
      return n;
    };
    const wanted = new Set((matchedWords || []).map(norm).filter(Boolean));
    if (!wanted.size) return text;
    return text.split(/(\s+)/).map((part, i) => {
      if (/^\s+$/.test(part) || !part) return part;
      return wanted.has(norm(part))
        ? <strong key={i} className="font-semibold text-gray-900">{part}</strong>
        : <span key={i}>{part}</span>;
    });
  };

  const renderScansion = (scansion) => {
    if (!scansion || !scansion.raw) return null;
    const meterAbbr = {
      'hexameter': 'Hx',
      'pentameter': 'P',
      'hendecasyllable': 'Hn',
      'elegiac': 'E'
    };
    return (
      <div className="flex items-center gap-1 mt-1">
        <span className="font-mono text-xs text-gray-500">{scansion.raw}</span>
        <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-gray-100 text-gray-600" title={scansion.meter}>
          {meterAbbr[scansion.meter] || scansion.meter?.charAt(0).toUpperCase() || '?'}
        </span>
      </div>
    );
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
          {isQueued && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4 text-center max-w-md">
              <div className="text-amber-800 font-medium mb-1">Search queued</div>
              <div className="text-amber-600 text-sm">{queuedMessage}</div>
              <div className="text-amber-500 text-xs mt-2">Your search will start automatically when a slot opens.</div>
            </div>
          )}
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
        <div className={`${pauseUpdates ? 'bg-amber-50 border-amber-200' : 'bg-blue-50 border-blue-200'} border rounded-lg p-3`}>
          <div className="flex items-center gap-3">
            {!pauseUpdates && (
              <div className="w-5 h-5 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin flex-shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <div className={`text-sm font-medium ${pauseUpdates ? 'text-amber-800' : 'text-blue-800'}`}>
                {pauseUpdates ? 'Display paused, search continues in background' : (progressText || 'Searching...')}
              </div>
              <div className={`mt-1 text-xs ${pauseUpdates ? 'text-amber-600' : 'text-blue-600'}`}>
                {fusionPhaseLabel}
                {fusionBatchTotal > 0 && ` | batch ${fusionBatchIndex} of ${fusionBatchTotal}`}
                {fusionProgress.currentChannel && ` | ${fusionProgress.currentChannel}`}
                {fusionProgress.totalMatches > 0 && ` | ${fusionProgress.totalMatches.toLocaleString()} candidates`}
                {fusionProgress.resultCount > 0 && ` | showing ${fusionProgress.resultCount.toLocaleString()}`}
              </div>
            </div>
            <button
              onClick={handlePauseToggle}
              className={`text-xs px-3 py-1 rounded font-medium flex-shrink-0 ${
                pauseUpdates
                  ? 'bg-amber-600 text-white hover:bg-amber-700'
                  : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
              }`}
            >
              {pauseUpdates ? 'Resume' : 'Pause'}
            </button>
            <span className={`text-xs ${pauseUpdates ? 'text-amber-500' : 'text-blue-500'} tabular-nums flex-shrink-0`}>
              {elapsedTime > 0 && formatElapsedTime(elapsedTime)}
            </span>
          </div>
          {fusionBatchTotal > 0 && (
            <div className={`mt-3 h-1.5 rounded-full overflow-hidden ${pauseUpdates ? 'bg-amber-100' : 'bg-blue-100'}`}>
              <div
                className={`h-full transition-all duration-300 ${pauseUpdates ? 'bg-amber-500' : 'bg-blue-600'}`}
                style={{ width: `${fusionBatchPercent}%` }}
              />
            </div>
          )}
        </div>
      )}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {searchStats?.total_matches && searchStats.total_matches > activeResults.length
              ? `Top ${activeResults.length.toLocaleString()} of ${searchStats.total_matches.toLocaleString()} Parallels`
              : `${activeResults.length} Parallel${activeResults.length !== 1 ? 's' : ''} Found`}
            {loading && fusionProgress && (pauseUpdates ? ' (paused)' : ' (partial)')}
            {chartFilter && ` (${filteredResults.length} ${chartFilter.mode === 'line' ? `at lines ${chartFilter.label}` : `in ${chartFilter.book}`})`}
          </h3>
          {searchStats && (
            <p className="text-sm text-gray-500">
              {searchStats.elapsed_time && `Search completed in ${formatElapsedTime(searchStats.elapsed_time)}`}
              {searchStats.source_lines && ` | ${searchStats.source_lines} source lines`}
              {searchStats.target_lines && ` | ${searchStats.target_lines} target lines`}
            </p>
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
                Filtering to {chartFilter.mode === 'line' ? `lines ${chartFilter.label}` : chartFilter.book} ({filteredResults.length} result{filteredResults.length !== 1 ? 's' : ''})
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

          {sidebarMode === 'corpus' && (<>
          <div className="mb-2">
            <label className="text-xs text-gray-600 block mb-1">Parallel:</label>
            <select
              value={corpusHitIdx}
              onChange={(e) => setCorpusHitIdx(Number(e.target.value))}
              className="w-full border rounded px-2 py-1 text-xs"
            >
              {(results || []).map((r, i) => (
                <option key={i} value={i}>
                  #{i + 1} · {formatReference(r.source_locus || r.source?.ref, language)} ↔ {formatReference(r.target_locus || r.target?.ref, language)}
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
            <button
              onClick={() => setCorpusGroupBy('timeline')}
              className={`text-xs px-2.5 py-1 rounded ${corpusGroupBy === 'timeline' ? 'bg-blue-600 text-white' : 'bg-blue-100 text-blue-700 hover:bg-blue-200'}`}
            >Timeline</button>
            <button
              onClick={() => setCorpusGroupBy('era')}
              className={`text-xs px-2.5 py-1 rounded ${corpusGroupBy === 'era' ? 'bg-blue-600 text-white' : 'bg-blue-100 text-blue-700 hover:bg-blue-200'}`}
            >Era</button>
          </div>
          {corpusIsTimeline && corpusData && !corpusData.tooFew && !corpusLoading && (
            <p className="text-xs text-gray-500 mb-1.5">Click any author to see its lines.</p>
          )}
          <div>
            {corpusLoading ? (
              <div className="flex items-center justify-center h-[200px] text-sm text-gray-400">Searching the corpus…</div>
            ) : corpusData && corpusData.tooFew ? (
              <div className="flex items-center justify-center h-[200px] text-xs text-gray-400 text-center px-2">This parallel shares only one word, so there is no corpus-wide co-occurrence to map. Pick another.</div>
            ) : corpusIsTimeline ? (
              <div key="corpus-timeline" ref={timelineRef} className="w-full" />
            ) : corpusChartData ? (
              <div key="corpus-chart" style={{ height: corpusIsAuthor ? Math.max(180, corpusChartData.labels.length * 22) : 200 }}>
                <Bar data={corpusChartData} options={corpusChartOptions} />
              </div>
            ) : (
              <div className="flex items-center justify-center h-[200px] text-xs text-gray-400">No corpus occurrences found.</div>
            )}
          </div>
          {corpusIsAuthor && corpusChartData && corpusChartData._capped && (
            <p className="text-xs text-gray-400 mt-1">Showing the 30 most-cited authors, in chronological order.</p>
          )}
          {corpusSelectedAuthor && corpusData && corpusData.loci && (() => {
            const rows = corpusData.loci.filter(l => (l.author || 'Unknown') === corpusSelectedAuthor);
            return (
              <div className="mt-2 border-t pt-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-gray-700">
                    {corpusSelectedAuthor.replace(/_/g, ' ')} — {rows.length} instance{rows.length !== 1 ? 's' : ''}
                  </span>
                  <button
                    onClick={() => setCorpusSelectedAuthor(null)}
                    className="text-xs text-gray-400 hover:text-gray-700"
                  >Close</button>
                </div>
                <div className="space-y-1.5 overflow-y-auto" style={{ maxHeight: 200 }}>
                  {rows.map((l, i) => (
                    <div key={i} className="text-xs leading-snug">
                      <span className="text-gray-400">{i + 1}. </span>
                      <span className="text-gray-500">
                        {[l.work && l.work.replace(/_/g, ' '), l.locus].filter(Boolean).join(' ')}
                      </span>
                      {l.text && <span className="text-gray-700"> — {renderInstanceText(l.text, l.matched_words, language)}</span>}
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
          {corpusData && corpusData.loci && corpusData.loci.length > 0 && (
            <p className="text-xs text-gray-500 mt-2">
              These words co-occur in {corpusData.loci.length} corpus lines{corpusData.corpus_version ? ` (corpus version ${corpusData.corpus_version})` : ''}.
            </p>
          )}
          </>)}
        </aside>
      )}

      <div className="flex-1 min-w-0 w-full">
      <Pagination {...paginationProps} variant="full" idPrefix="parallels-top" />
      <div className="space-y-3">
        {visibleItems.map((r, i) => (
          <div
            key={startIndex + i}
            className="bg-white border rounded-lg p-3 sm:p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex gap-3">
              <span className="text-xs text-gray-400 min-w-[2.5rem] text-right shrink-0 leading-none" style={{paddingTop: '1px'}}>
                {startIndex + i + 1}.
              </span>
              <div className="flex-1">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-gray-500 mb-1 leading-none">Source</div>
                <div className="font-medium text-gray-900">{formatReference(r.source_locus || r.source?.ref, language)}</div>
                <div
                  className="text-gray-700 mt-1"
                  dir={dirFor(language)}
                  dangerouslySetInnerHTML={{ __html: r.source_text || r.source_snippet || renderHighlightedText(r.source, language, r.matched_words, true, r.target) }}
                />
                {r.features?.source_scansion && renderScansion(r.features.source_scansion)}
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Target</div>
                <div className="font-medium text-gray-900">{formatReference(r.target_locus || r.target?.ref, language)}</div>
                <div
                  className="text-gray-700 mt-1"
                  dir={dirFor(language)}
                  dangerouslySetInnerHTML={{ __html: r.target_text || r.target_snippet || renderHighlightedText(r.target, language, r.matched_words, false, r.source) }}
                />
                {r.features?.target_scansion && renderScansion(r.features.target_scansion)}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t">
              <span className="text-sm text-gray-600">
                Score: <span className="font-medium">{(r.fused_score ?? r.score ?? r.overall_score)?.toFixed(2) || '-'}</span>
              </span>
              {r.channels && r.channels.length > 0 && (
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                  {r.channels.length} channel{r.channels.length !== 1 ? 's' : ''}
                </span>
              )}
              {r.features?.meter_score > 0 && (
                <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">
                  Metrical: {(r.features.meter_score * 100).toFixed(0)}%
                </span>
              )}
              {r.matched_words && r.matched_words.length > 0 && (
                <span className="text-sm text-gray-600">
                  Matches: <span className="font-medium">
                    {r.matched_words.map(w => {
                      const word = typeof w === 'object' ? (w.lemma || w.word || w.display || JSON.stringify(w)) : w;
                      return displayGreekWithFinalSigma(word);
                    }).join(', ')}
                  </span>
                </span>
              )}
              {r.channels && r.channels.length > 0 && (
                <div className="flex flex-wrap gap-1 ml-1">
                  {r.channels.map(ch => (
                    <span key={ch} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                      {ch}
                    </span>
                  ))}
                </div>
              )}
              <div className="flex-1"></div>
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
