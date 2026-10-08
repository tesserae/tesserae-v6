import Pagination from '../common/Pagination';
import { getSessionValue, setSessionValue } from '../../utils/storage';
import { usePagination } from '../../hooks/usePagination';
import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { LoadingSpinner, SearchableSelect } from '../common';
import { normalizeGreek } from '../../utils/greekUtils';
import { dirFor } from '../../utils/rtl';
import { exportRowsToPDF } from '../../utils/exportResults';
import { languageName } from '../../utils/languageNames';
import CopticSearchInput from './CopticSearchInput';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { orderEras, ERA_COLORS } from '../../utils/eras';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

// Stage 3b-3: the "Hide stock formulas" checkbox's own fixed threshold --
// matches backend/app.py's DOCUMENTS_FORMULA_DEFAULT_N, measured against
// the real documents indexes (dis manibus/bene merenti/votum solvit
// libens merito/hic situs est, thousands of sharing documents each, vs.
// arma virumque/arma virumque cano, fewer than 20).
const DOCUMENTS_FORMULA_DEFAULT_N = 100;

// Hebrew and Coptic loci embed the full text id (e.g.
// "hebrew_bible.1_samuel.1.1"); strip that redundant stem so the citation
// reads "1.1". Loci without the stem (e.g. "verg. aen. 1.1") pass through.
function displayLocus(locus, textId) {
  const stem = (textId || '').replace(/\.tess$/, '');
  return stem && (locus || '').startsWith(stem + '.')
    ? locus.slice(stem.length + 1)
    : (locus || '');
}

export default function LineSearch({ language }) {
  const [mode, setMode] = useState('browse');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  // Documents-collection hits are shaped completely differently (credit/
  // date/place/labels, no author/work/era/year) and get their own card and
  // their own section below. Every existing literary derivation (dedup,
  // genre filter, timeline, pagination) stays on literatureResults so it is
  // byte-for-byte what it always was when no document hit is present
  // (collection='literature', the default, never returns one).
  const literatureResults = useMemo(() => results.filter(r => r.collection !== 'documents'), [results]);
  const documentResults = useMemo(() => results.filter(r => r.collection === 'documents'), [results]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchType, setSearchType] = useState('lemma');
  const [showTimeline, setShowTimeline] = useState(true);
  const [eraFilter, setEraFilter] = useState(null);
  const [authorFilter, setAuthorFilter] = useState(null);
  const [showPoetry, setShowPoetry] = useState(true);
  const [showProse, setShowProse] = useState(true);
  const [sortOrder, setSortOrder] = useState('chronological');
  // Set when a /?tab=line&q=... deep link should auto-run once its query is in state.
  const [pendingUrlSearch, setPendingUrlSearch] = useState(null);

  // Documents collection (stage 3b-2, behind TESSERAE_DOCUMENTS=1): the
  // documentary corpus (inscriptions, papyri) searchable alongside or
  // instead of literature. A trial, not yet shown to every reader:
  // ?documents=1 switches it on and remembers that for the rest of the
  // visit, as the Scholarship tab does, and the control appears only once
  // /api/languages also confirms the server has it on.
  const [documentsTrial] = useState(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('documents') === '1';
    if (fromUrl) setSessionValue('documents_trial', '1');
    return fromUrl || getSessionValue('documents_trial', '0') === '1';
  });
  const [documentsEnabled, setDocumentsEnabled] = useState(false);
  const [collection, setCollection] = useState('literature');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [docRegion, setDocRegion] = useState('');
  const [docTextType, setDocTextType] = useState('');
  const [docMaterial, setDocMaterial] = useState('');
  const [docSource, setDocSource] = useState('');
  // Stage 3b-3: leave out a hit whose match rests entirely on restored
  // text, and hide stock formulas (matched words shared by more documents
  // than DOCUMENTS_FORMULA_DEFAULT_N -- see the same constant's comment in
  // backend/app.py for how that default was measured).
  const [excludeRestored, setExcludeRestored] = useState(false);
  const [hideFormulas, setHideFormulas] = useState(false);

  useEffect(() => {
    fetch('/api/languages').then(r => r.json()).then(data => {
      setDocumentsEnabled(documentsTrial && !!data.documents_enabled);
    }).catch(() => {});
  }, []);
  const chartRef = useRef(null);
  const authorChartRef = useRef(null);
  
  const [texts, setTexts] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [works, setWorks] = useState([]);
  const [selectedAuthor, setSelectedAuthor] = useState('');
  const [selectedWork, setSelectedWork] = useState('');
  const [lineStart, setLineStart] = useState('');
  const [lineEnd, setLineEnd] = useState('');
  const [loadingTexts, setLoadingTexts] = useState(true);
  
  const [browseLines, setBrowseLines] = useState([]);
  const [browseLoading, setBrowseLoading] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (loading) {
      const startTime = Date.now();
      setElapsedTime(0);
      timerRef.current = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [loading]);
  const browsePagination = usePagination(browseLines, { initialPageSize: 100, resetKey: browseLines });

  const [sourceInfo, setSourceInfo] = useState(null);

  useEffect(() => {
    loadTexts();
    setSelectedAuthor('');
    setSelectedWork('');
    setBrowseLines([]);
    setQuery('');
    setResults([]);
    setError(null);
    setSourceInfo(null);
  }, [language]);

  useEffect(() => {
    const gotoQuery = sessionStorage.getItem('tesserae_goto_query');
    const gotoText = sessionStorage.getItem('tesserae_goto_text');
    
    if (gotoQuery || gotoText) {
      sessionStorage.removeItem('tesserae_goto_query');
      sessionStorage.removeItem('tesserae_goto_text');
      
      if (gotoQuery) {
        setQuery(gotoQuery);
        setMode('search');
      }
      
      if (gotoText && texts.length > 0) {
        const text = texts.find(t => t.id === gotoText);
        if (text) {
          setSelectedAuthor(text.author);
          setSelectedWork(text.id);
        }
      }
    }
  }, [texts]);

  useEffect(() => {
    if (selectedAuthor) {
      const authorTexts = texts
        .filter(t => t.author === selectedAuthor)
        .map(t => ({ 
          id: t.id, 
          label: t.title || t.work || t.display_name,
          display: t.display_name || `${t.author}, ${t.title || t.work}`
        }))
        .sort((a, b) => {
          const extractNum = (s) => {
            const match = s.match(/(\d+)/);
            return match ? parseInt(match[1], 10) : 0;
          };
          const aBase = a.label.replace(/,?\s*(Book|Part)?\s*\d+$/, '');
          const bBase = b.label.replace(/,?\s*(Book|Part)?\s*\d+$/, '');
          if (aBase !== bBase) return aBase.localeCompare(bBase);
          return extractNum(a.label) - extractNum(b.label);
        });
      setWorks(authorTexts);
      if (!authorTexts.find(w => w.id === selectedWork)) {
        setSelectedWork('');
      }
    } else {
      setWorks([]);
      setSelectedWork('');
    }
  }, [selectedAuthor, texts]);

  const loadTexts = async () => {
    setLoadingTexts(true);
    try {
      const res = await fetch(`/api/texts?language=${language}`);
      const data = await res.json();
      const textList = Array.isArray(data) ? data : (data.texts || []);
      setTexts(textList);
      
      const uniqueAuthors = [...new Set(textList.map(t => t.author))].filter(Boolean).sort();
      setAuthors(uniqueAuthors);
    } catch (err) {
      console.error('Failed to load texts:', err);
    }
    setLoadingTexts(false);
  };

  // Adds collection + the documents-only filters to a search params object,
  // only when the documents control is actually on and set away from plain
  // Literature. With the control untouched (or the server switch off) this
  // adds nothing, so a request is byte-for-byte what it always was.
  const addCollectionParams = (params) => {
    if (!documentsEnabled || collection === 'literature') return params;
    params.collection = collection;
    if (dateFrom.trim()) params.date_from = parseInt(dateFrom, 10);
    if (dateTo.trim()) params.date_to = parseInt(dateTo, 10);
    if (docRegion.trim()) params.region = docRegion.trim();
    if (docTextType.trim()) params.text_type = docTextType.trim();
    if (docMaterial.trim()) params.material = docMaterial.trim();
    if (docSource.trim()) params.source = docSource.trim();
    if (excludeRestored) params.exclude_restored = true;
    if (hideFormulas) params.hide_formulas = DOCUMENTS_FORMULA_DEFAULT_N;
    return params;
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setEraFilter(null);
    try {
      const searchParams = addCollectionParams({
        query: query.trim(),
        language,
        search_type: searchType
      });

      if (selectedAuthor) searchParams.author = selectedAuthor;
      if (selectedWork) searchParams.work = selectedWork;
      if (lineStart) searchParams.line_start = parseInt(lineStart);
      if (lineEnd) searchParams.line_end = parseInt(lineEnd);

      const res = await fetch('/api/line-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchParams)
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        setResults([]);
      } else {
        setResults(data.results || []);
      }
    } catch (err) {
      setError('Search failed. Please try again.');
      setResults([]);
    }
    setLoading(false);
  };

  // Deep link: /?tab=line&q=...&type=... opens Line Search pre-filled and runs it,
  // so an AI agent (or a shared link) can point straight at an interactive timeline.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const q = params.get('q');
    const type = params.get('type');
    if (q) {
      setQuery(q);
      if (type && ['lemma', 'exact', 'regex'].includes(type)) setSearchType(type);
      setMode('search');
      setPendingUrlSearch(q);
    }
    // Run once on mount for the initial URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (pendingUrlSearch != null && query === pendingUrlSearch) {
      setPendingUrlSearch(null);
      handleSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingUrlSearch, query]);

  const handleBrowseLines = async () => {
    if (!selectedAuthor || !selectedWork) return;
    setBrowseLoading(true);
    setBrowseLines([]);
    try {
      const res = await fetch(`/api/text/${selectedWork}/lines?language=${language}`);
      const data = await res.json();
      if (data.lines) {
        setBrowseLines(data.lines);
      }
    } catch (err) {
      console.error('Failed to load lines:', err);
    }
    setBrowseLoading(false);
  };

  const selectLineForSearch = async (line) => {
    const lineText = line.text || '';
    setQuery(lineText);
    setMode('search');
    
    // Track source info for display and exclusion
    const workInfo = works.find(w => w.id === selectedWork);
    const source = {
      author: selectedAuthor,
      work: workInfo?.label || selectedWork,
      text_id: selectedWork,
      locus: line.locus || line.ref || '',
      text: lineText
    };
    setSourceInfo(source);
    
    if (!lineText.trim()) return;
    setLoading(true);
    setError(null);
    setEraFilter(null);
    try {
      const searchParams = addCollectionParams({
        query: lineText.trim(),
        language,
        search_type: searchType,
        exclude_text_id: selectedWork,
        exclude_locus: line.locus || line.ref || ''
      });
      
      const res = await fetch('/api/line-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchParams)
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        setResults([]);
      } else {
        setResults(data.results || []);
      }
    } catch (err) {
      setError('Search failed. Please try again.');
      setResults([]);
    }
    setLoading(false);
  };

  const clearFilters = () => {
    setSelectedAuthor('');
    setSelectedWork('');
    setLineStart('');
    setLineEnd('');
  };

  const deduplicatedResults = useMemo(() => {
    return literatureResults.filter((r, index, self) => {
      if (query && r.text === query) {
        return false;
      }
      return index === self.findIndex(t => t.text === r.text && t.locus === r.locus);
    });
  }, [literatureResults, query]);

  const exportCSV = useCallback(() => {
    const headers = ['Author', 'Work', 'Locus', 'Text', 'Era'];
    const rows = literatureResults.map(r => [
      r.author || '',
      r.work || '',
      r.locus || '',
      r.text?.replace(/"/g, '""') || '',
      r.era || ''
    ]);
    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    // Prepend UTF-8 BOM so Excel reads non-Latin scripts (Coptic, Greek) as Unicode, not Windows-1252.
    const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `line_search_${query}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [literatureResults, query]);

  const exportTimelineChart = () => {
    if (!chartRef.current) return;
    const canvas = chartRef.current.canvas;
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `tesserae_timeline_${query}_${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const genreFilteredResults = useMemo(() => {
    if (showPoetry && showProse) return deduplicatedResults;
    return deduplicatedResults.filter(r => {
      const isPoetry = r.is_poetry === true;
      if (!showPoetry && isPoetry) return false;
      if (!showProse && !isPoetry) return false;
      return true;
    });
  }, [deduplicatedResults, showPoetry, showProse]);

  const poetryCount = useMemo(() => deduplicatedResults.filter(r => r.is_poetry === true).length, [deduplicatedResults]);
  const proseCount = useMemo(() => deduplicatedResults.filter(r => r.is_poetry !== true).length, [deduplicatedResults]);

  const timelineData = useMemo(() => {
    const data = genreFilteredResults;
    if (!data || data.length === 0) return { labels: [], datasets: [{ label: 'Matches', data: [], backgroundColor: [], borderColor: [], borderWidth: 1 }] };
    const eraCounts = {};
    data.forEach(r => {
      const era = r.era || 'Unknown';
      eraCounts[era] = (eraCounts[era] || 0) + 1;
    });
    const sortedEras = orderEras(language, eraCounts);
    return {
      labels: sortedEras,
      datasets: [{
        label: 'Matches',
        data: sortedEras.map(era => eraCounts[era]),
        backgroundColor: sortedEras.map(era => ERA_COLORS[era] || ERA_COLORS['Unknown']),
        borderColor: sortedEras.map(era => (ERA_COLORS[era] || ERA_COLORS['Unknown']).replace('0.7', '1')),
        borderWidth: 1
      }]
    };
  }, [genreFilteredResults]);

  const authorTimelineData = useMemo(() => {
    const data = genreFilteredResults;
    if (!data || data.length === 0) return { labels: [], datasets: [{ label: 'Matches', data: [], backgroundColor: 'rgba(120, 81, 169, 0.7)', borderColor: 'rgba(120, 81, 169, 1)', borderWidth: 1 }] };
    const authorCounts = {};
    data.forEach(r => {
      const author = r.author || 'Unknown';
      authorCounts[author] = (authorCounts[author] || 0) + 1;
    });
    const sortedAuthors = Object.keys(authorCounts).sort((a, b) => {
      const aResult = data.find(r => r.author === a);
      const bResult = data.find(r => r.author === b);
      const aYear = aResult?.year || 9999;
      const bYear = bResult?.year || 9999;
      if (aYear !== bYear) return aYear - bYear;
      return a.localeCompare(b);
    });
    return {
      labels: sortedAuthors,
      datasets: [{
        label: 'Matches',
        data: sortedAuthors.map(author => authorCounts[author]),
        backgroundColor: 'rgba(120, 81, 169, 0.7)',
        borderColor: 'rgba(120, 81, 169, 1)',
        borderWidth: 1
      }]
    };
  }, [genreFilteredResults]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      title: {
        display: true,
        text: eraFilter ? `Showing matches from ${eraFilter} (click to clear)` : 'Period Timeline (click bar to filter)'
      },
      tooltip: {
        callbacks: {
          label: (context) => `${context.parsed.y} match${context.parsed.y !== 1 ? 'es' : ''}`
        }
      }
    },
    scales: {
      y: { beginAtZero: true, ticks: { stepSize: 1 } }
    },
    onClick: (event, elements) => {
      if (elements.length > 0) {
        const idx = elements[0].index;
        const chartData = timelineData;
        if (chartData) {
          const clickedEra = chartData.labels[idx];
          setEraFilter(eraFilter === clickedEra ? null : clickedEra);
          setAuthorFilter(null);
        }
      }
    }
  };

  const authorChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      title: {
        display: true,
        text: authorFilter ? `Showing matches from ${authorFilter} (click to clear)` : 'Author Timeline (click bar to filter)'
      },
      tooltip: {
        callbacks: {
          label: (context) => `${context.parsed.y} match${context.parsed.y !== 1 ? 'es' : ''}`
        }
      }
    },
    scales: {
      y: { beginAtZero: true, ticks: { stepSize: 1 } },
      x: { ticks: { maxRotation: 45, minRotation: 45 } }
    },
    onClick: (event, elements) => {
      if (elements.length > 0) {
        const idx = elements[0].index;
        const chartData = authorTimelineData;
        if (chartData) {
          const clickedAuthor = chartData.labels[idx];
          setAuthorFilter(authorFilter === clickedAuthor ? null : clickedAuthor);
          setEraFilter(null);
        }
      }
    }
  };

  const extractLineNumber = (locus) => {
    if (!locus) return '';
    const match = locus.match(/[\d]+(?:[.\-:]+[\d\w]+)*$/);
    return match ? match[0] : locus.trim().split(/\s+/).pop() || locus;
  };

  const cleanWorkTitle = (work, locus) => {
    if (!work) return work;
    const lineNum = extractLineNumber(locus);
    if (!lineNum) return work;
    const match = work.match(/^(.+?)\s+(\d+)$/);
    if (match) {
      const [, baseName, bookNum] = match;
      if (lineNum.startsWith(bookNum + '.') || lineNum.startsWith(bookNum + ':')) {
        return baseName;
      }
    }
    return work;
  };

  // Some .tess sources encode editorial angle brackets as HTML entities
  // (&lt; &gt;); decode for display so readers see < > not the raw entity.
  const decodeEntities = (s) => (typeof s === 'string' ? s
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&') : s);

  const highlightMatches = (text, matchedWords) => {
    if (!text) return text;
    text = decodeEntities(text);
    if (!matchedWords || matchedWords.length === 0) return text;
    
    const normalizeWord = (s) => {
      if (!s) return '';
      let normalized = s.toLowerCase();
      if (language === 'la') {
        normalized = normalized.replace(/v/g, 'u').replace(/j/g, 'i');
      } else if (language === 'grc') {
        normalized = normalizeGreek(s);
      } else if (language === 'he') {
        // strip nikkud + cantillation (matched_words are unvocalized) and maqaf
        normalized = normalized.normalize('NFD').replace(/[֑-ֽֿ-ׇ]/g, '').replace(/־/g, '');
      }
      return normalized;
    };

    const matchSet = new Set(matchedWords.map(w => normalizeWord(w)));
    const words = text.split(language === 'he' ? /(\s+|־)/ : /(\s+)/);
    
    return words.map((word, i) => {
      if (/^\s+$/.test(word)) {
        return <span key={i}>{word}</span>;
      }
      
      let wordClean;
      if (language === 'grc') {
        const nfd = word.normalize('NFD');
        const noDiacritics = nfd.replace(/[\u0300-\u036f]/g, '');
        wordClean = noDiacritics.replace(/[^\u0370-\u03FF\u1F00-\u1FFFa-zA-Z]/g, '');
      } else {
        wordClean = word.replace(/[^a-zA-Z\u0370-\u03FF\u1F00-\u1FFF]/g, '');
      }
      
      const wordNorm = normalizeWord(wordClean);
      if (wordNorm && matchSet.has(wordNorm)) {
        return <mark key={i} className="bg-amber-200 px-0.5 rounded">{word}</mark>;
      }
      return <span key={i}>{word}</span>;
    });
  };

  const filteredResults = useMemo(() => {
    const filtered = deduplicatedResults.filter(r => {
      if (eraFilter && (r.era || 'Unknown') !== eraFilter) return false;
      if (authorFilter && r.author !== authorFilter) return false;
      const isPoetry = r.is_poetry === true;
      if (!showPoetry && isPoetry) return false;
      if (!showProse && !isPoetry) return false;
      return true;
    });
    
    if (sortOrder === 'alphabetical') {
      return [...filtered].sort((a, b) => {
        const authorCmp = (a.author || '').localeCompare(b.author || '');
        if (authorCmp !== 0) return authorCmp;
        return (a.work || '').localeCompare(b.work || '');
      });
    }
    return [...filtered].sort((a, b) => {
      const aYear = a.year || 9999;
      const bYear = b.year || 9999;
      if (aYear !== bYear) return aYear - bYear;
      return (a.author || '').localeCompare(b.author || '');
    });
  }, [deduplicatedResults, eraFilter, authorFilter, showPoetry, showProse, sortOrder]);

  // Result identity changes on completion, even when the same query is run again.
  const paginationResetKey = useMemo(() => ({}), [literatureResults, eraFilter, authorFilter, showPoetry, showProse, sortOrder]);
  const pagination = usePagination(filteredResults, { resetKey: paginationResetKey });
  const docPagination = usePagination(documentResults, { initialPageSize: 50, resetKey: documentResults });

  // Document hit text, rendered by TOKEN POSITION (not a whitespace re-split
  // of `text`) so restored-word marking lines up with restored_indices
  // exactly as the index stored it. Falls back to the plain literary
  // highlighter if a hit carries no token list.
  const renderDocumentText = (result) => {
    const tokens = result.tokens || [];
    if (!tokens.length) {
      return highlightMatches(result.text, result.matched_words || []);
    }
    const restoredSet = new Set(result.restored_indices || []);
    const fragmentSet = new Set(result.fragment_indices || []);
    const matchedSet = new Set((result.matched_words || []).map(w => (w || '').toLowerCase()));
    return tokens.map((tok, i) => {
      let el = <span>{tok}</span>;
      if (restoredSet.has(i)) {
        // Light dotted underline for an editorially restored word -- chosen
        // over scholarly square brackets because the matched-word highlight
        // below already uses <mark>, and the corpus's own angle-bracket
        // convention (decodeEntities above) is reserved for editorial
        // brackets carried IN the source text itself; an underline reads as
        // "mark on top of the word" without colliding with either.
        el = <span className="underline decoration-dotted decoration-2 decoration-sky-500" title="editorially restored">{tok}</span>;
      } else if (fragmentSet.has(i)) {
        el = <span className="italic text-gray-500" title="surviving fragment of a damaged word">{tok}</span>;
      }
      if (matchedSet.has((tok || '').toLowerCase())) {
        el = <mark className="bg-amber-200 px-0.5 rounded">{el}</mark>;
      }
      return <span key={i}>{el}{' '}</span>;
    });
  };

  const documentDateLabel = (result) => {
    const nb = result.date_not_before, na = result.date_not_after;
    if (nb == null && na == null) return null;
    const fmt = (y) => (y < 0 ? `${-y} BC` : `${y} AD`);
    if (nb != null && na != null && nb !== na) return `${fmt(nb)}–${fmt(na)}`;
    return fmt(nb != null ? nb : na);
  };

  // Stage 3b-3: the document Reader view, opened from a document hit's own
  // citation. Carries the originating query/type/language (and the
  // ?documents=1 trial flag, when it is what got this control shown at
  // all) so the view's own "back to results" link can return here with
  // the query intact, the same deep-link pattern Theme Search/Reader
  // already use for "back to results" (ReaderPage.jsx's `cameFrom`/`q`).
  const documentViewUrl = (docId) => {
    const params = new URLSearchParams({
      doc: docId, lang: language, q: query, type: searchType,
    });
    if (documentsTrial) params.set('documents', '1');
    return `/document?${params.toString()}`;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 bg-gray-100 p-1 rounded-lg inline-flex">
        <button
          onClick={() => setMode('browse')}
          className={`px-3 py-1.5 text-sm font-medium rounded ${
            mode === 'browse' ? 'bg-white shadow text-red-700' : 'text-gray-600 hover:text-gray-800'
          }`}
        >
          Find Text to Search
        </button>
        <button
          onClick={() => setMode('search')}
          className={`px-3 py-1.5 text-sm font-medium rounded ${
            mode === 'search' ? 'bg-white shadow text-red-700' : 'text-gray-600 hover:text-gray-800'
          }`}
        >
          Input Search Text
        </button>
      </div>

      {mode === 'search' ? (
        <>
          <div className="bg-white rounded-lg shadow p-4 sm:p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search Terms
              </label>
              <div className="flex flex-col sm:flex-row gap-3">
                {language === 'cop' ? (
                  <CopticSearchInput
                    className="flex-1"
                    value={query}
                    onChange={setQuery}
                    onEnter={handleSearch}
                  />
                ) : (
                  <input
                    type="text"
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSearch()}
                    placeholder="Enter word or phrase..."
                    className="flex-1 border rounded px-4 py-2"
                  />
                )}
                <select
                  value={searchType}
                  onChange={e => setSearchType(e.target.value)}
                  className="border rounded px-3 py-2 text-sm"
                >
                  <option value="lemma">Lemma (dictionary form)</option>
                  <option value="exact">Exact match</option>
                  <option value="regex">Regular expression (pattern)</option>
                </select>
              </div>
              {searchType === 'regex' && (
                <p className="mt-1 text-xs text-gray-500">
                  Pattern matching: use <code className="bg-gray-100 px-1 rounded">.</code> for any character, <code className="bg-gray-100 px-1 rounded">|</code> for OR, <code className="bg-gray-100 px-1 rounded">[aei]</code> for character sets,
                  {' '}<code className="bg-gray-100 px-1 rounded">.*</code> for any sequence. Example: <code className="bg-gray-100 px-1 rounded">amor|bellum</code> finds lines with either word. See Help & Support for more.
                </p>
              )}
              {sourceInfo && (
                <div className="mt-2 flex items-center justify-between text-sm text-gray-600 bg-gray-50 rounded px-3 py-2">
                  <span>
                    <span className="font-medium">{sourceInfo.author}</span>
                    {sourceInfo.work && <span className="italic">, {cleanWorkTitle(sourceInfo.work, sourceInfo.locus)}</span>}
                    {sourceInfo.locus && <span>, {extractLineNumber(sourceInfo.locus)}</span>}
                  </span>
                  <button
                    onClick={() => setSourceInfo(null)}
                    className="text-gray-500 hover:text-gray-600 ml-2"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>

            {documentsEnabled && (language === 'la' || language === 'grc') && (
              <div className="border-t pt-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Search in</label>
                <div className="flex items-center gap-2 bg-gray-100 p-1 rounded-lg inline-flex">
                  {[
                    { key: 'literature', label: 'Literature' },
                    { key: 'documents', label: 'Documents' },
                    { key: 'both', label: 'Both' },
                  ].map(opt => (
                    <button
                      key={opt.key}
                      onClick={() => setCollection(opt.key)}
                      className={`px-3 py-1.5 text-sm font-medium rounded ${
                        collection === opt.key ? 'bg-white shadow text-red-700' : 'text-gray-600 hover:text-gray-800'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {collection !== 'literature' && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Date from</label>
                      <input type="number" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                             placeholder="e.g., -100" className="w-full border rounded px-2 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Date to</label>
                      <input type="number" value={dateTo} onChange={e => setDateTo(e.target.value)}
                             placeholder="e.g., 200" className="w-full border rounded px-2 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Region</label>
                      <input type="text" value={docRegion} onChange={e => setDocRegion(e.target.value)}
                             placeholder="e.g., Latium" className="w-full border rounded px-2 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Text type</label>
                      <input type="text" value={docTextType} onChange={e => setDocTextType(e.target.value)}
                             placeholder="e.g., epitaph" className="w-full border rounded px-2 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Material</label>
                      <input type="text" value={docMaterial} onChange={e => setDocMaterial(e.target.value)}
                             placeholder="e.g., marble" className="w-full border rounded px-2 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Source</label>
                      <input type="text" value={docSource} onChange={e => setDocSource(e.target.value)}
                             placeholder="e.g., edh" className="w-full border rounded px-2 py-1.5 text-sm" />
                    </div>
                  </div>
                )}
                {collection !== 'literature' && (
                  <div className="flex flex-col sm:flex-row sm:items-center gap-3 mt-3">
                    <label className="flex items-center gap-2 text-sm text-gray-700">
                      <input type="checkbox" checked={excludeRestored}
                             onChange={e => setExcludeRestored(e.target.checked)} />
                      Leave out matches on restored words
                    </label>
                    <label className="flex items-center gap-2 text-sm text-gray-700">
                      <input type="checkbox" checked={hideFormulas}
                             onChange={e => setHideFormulas(e.target.checked)} />
                      Hide stock formulas
                    </label>
                  </div>
                )}
              </div>
            )}

            <div className="border-t pt-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700">Filter by Text (Optional)</span>
                {(selectedAuthor || selectedWork || lineStart || lineEnd) && (
                  <button
                    onClick={clearFilters}
                    className="text-xs text-red-600 hover:text-red-800"
                  >
                    Clear Filters
                  </button>
                )}
              </div>
              
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Author</label>
                  <SearchableSelect
                    ariaLabel="Author"
                    value={selectedAuthor}
                    onChange={setSelectedAuthor}
                    options={[{ value: '', label: 'All Authors' }, ...authors.map(author => ({ value: author, label: author }))]}
                    disabled={loadingTexts}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs text-gray-500 mb-1">Work</label>
                  <SearchableSelect
                    ariaLabel="Work"
                    value={selectedWork}
                    onChange={setSelectedWork}
                    options={[{ value: '', label: 'All Works' }, ...works.map(work => ({ value: work.id, label: work.label }))]}
                    disabled={!selectedAuthor || loadingTexts}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Line Start</label>
                  <input
                    type="number"
                    value={lineStart}
                    onChange={e => setLineStart(e.target.value)}
                    placeholder="e.g., 1"
                    className="w-full border rounded px-3 py-2 text-sm"
                    min="1"
                  />
                </div>
                
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Line End</label>
                  <input
                    type="number"
                    value={lineEnd}
                    onChange={e => setLineEnd(e.target.value)}
                    placeholder="e.g., 100"
                    className="w-full border rounded px-3 py-2 text-sm"
                    min="1"
                  />
                </div>
              </div>
            </div>

            <div className="border-t pt-4 flex justify-end">
              <button
                onClick={handleSearch}
                disabled={!query.trim() || loading}
                className="px-6 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
              >
                {loading ? 'Searching...' : 'Search Lines'}
              </button>
            </div>
          </div>

          {loading && <LoadingSpinner text="Searching corpus..." elapsedTime={elapsedTime} step="Finding matching lines" />}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {literatureResults.length > 0 && (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm text-gray-600">
                  Found {literatureResults.length} parallel lines
                  {filteredResults.length !== literatureResults.length && (
                    <span className="text-amber-600"> (showing {filteredResults.length} after filters)</span>
                  )}
                </span>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1 text-sm text-gray-600">
                    <input
                      type="checkbox"
                      checked={showPoetry}
                      onChange={e => setShowPoetry(e.target.checked)}
                      className="rounded"
                    />
                    Poetry ({poetryCount})
                  </label>
                  <label className="flex items-center gap-1 text-sm text-gray-600">
                    <input
                      type="checkbox"
                      checked={showProse}
                      onChange={e => setShowProse(e.target.checked)}
                      className="rounded"
                    />
                    Prose ({proseCount})
                  </label>
                  <select
                    value={sortOrder}
                    onChange={e => setSortOrder(e.target.value)}
                    className="text-sm border rounded px-2 py-1"
                  >
                    <option value="chronological">By Era</option>
                    <option value="alphabetical">A-Z</option>
                  </select>
                  <button
                    onClick={() => setShowTimeline(!showTimeline)}
                    className={`text-sm px-3 py-1 rounded ${showTimeline ? 'bg-amber-700 text-white' : 'bg-amber-100 text-amber-700 hover:bg-amber-200'}`}
                  >
                    {showTimeline ? 'Hide Timelines' : 'Show Timelines'}
                  </button>
                  <button
                    onClick={exportCSV}
                    className="text-sm text-amber-600 hover:text-amber-800"
                  >
                    Export CSV
                  </button>
                </div>
              </div>

              {showTimeline && deduplicatedResults.some(r => r.era) && (
                <div className="p-4 border-b bg-gray-50 space-y-6">
                  {timelineData.labels.length > 0 ? (
                    <>
                      <div>
                        <h4 className="text-sm font-medium text-gray-700 mb-2">Period Timeline</h4>
                        <div style={{ height: '180px' }}>
                          <Bar ref={chartRef} data={timelineData} options={chartOptions} />
                        </div>
                      </div>
                      <div>
                        <h4 className="text-sm font-medium text-gray-700 mb-2">Author Timeline</h4>
                        <div style={{ height: '180px' }}>
                          <Bar ref={authorChartRef} data={authorTimelineData} options={authorChartOptions} />
                        </div>
                      </div>
                      <div className="flex justify-end">
                        <button
                          onClick={exportTimelineChart}
                          className="text-xs text-gray-600 hover:text-gray-900"
                        >
                          Export PNG
                        </button>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-4">No results match the current genre filter.</p>
                  )}
                </div>
              )}

              {(eraFilter || authorFilter) && (
                <div className="px-4 py-2 bg-amber-50 border-b flex items-center justify-between">
                  <span className="text-sm text-amber-800">
                    Showing {filteredResults.length} matches from {eraFilter || authorFilter}
                  </span>
                  <button
                    onClick={() => { setEraFilter(null); setAuthorFilter(null); }}
                    className="text-xs text-amber-600 hover:text-amber-800 font-medium"
                  >
                    Clear Filter
                  </button>
                </div>
              )}

              <div className="divide-y divide-gray-200">
                {pagination.visibleItems.map((result, i) => {
                  const locus = displayLocus(result.locus, result.text_id);
                  return (
                  <div key={i} className="p-4 hover:bg-gray-50">
                    <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                      <span className="text-xs text-gray-500 min-w-[2.5rem] text-right shrink-0 leading-none" style={{paddingTop: '1px'}}>
                        {pagination.startIndex + i + 1}.
                      </span>
                      <div className="sm:w-48 flex-shrink-0 min-w-0 break-words">
                        <div className="text-sm font-medium text-gray-900">
                          {result.author}
                        </div>
                        <div className="text-xs text-gray-500">
                          {result.work}, {locus}
                        </div>
                        {result.era && (
                          <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded mt-1 inline-block">
                            {result.era}
                          </span>
                        )}
                      </div>
                      <div className="flex-1 min-w-0 break-words text-gray-700" dir={dirFor(language)}>
                        {highlightMatches(result.text, result.matched_words || query.split(/\s+/))}
                      </div>
                    </div>
                  </div>
                  );
                })}
              </div>
              <Pagination {...pagination} idPrefix="linesearch" />
            </div>
          )}

          {documentResults.length > 0 && (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 flex items-center justify-between">
                <span className="text-sm text-gray-600">
                  Found {documentResults.length} documents
                </span>
              </div>
              <div className="divide-y divide-gray-200">
                {docPagination.visibleItems.map((result, i) => {
                  const credit = result.credit || {};
                  const labels = [result.text_type_label, result.object_type_label, result.material_label]
                    .filter(Boolean);
                  const place = result.ancient_place || result.modern_place;
                  const dateLabel = documentDateLabel(result);
                  return (
                    <div key={i} className="p-4 hover:bg-gray-50">
                      <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                        <span className="text-xs text-gray-500 min-w-[2.5rem] text-right shrink-0 leading-none" style={{ paddingTop: '1px' }}>
                          {docPagination.startIndex + i + 1}.
                        </span>
                        <div className="sm:w-48 flex-shrink-0 min-w-0 break-words">
                          <div className="text-sm font-medium text-gray-900">
                            <a href={documentViewUrl(result.doc_id)} className="hover:underline">
                              {credit.principal_edition || result.doc_id}
                            </a>
                          </div>
                          <div className="text-xs text-gray-500">
                            {[dateLabel, place, result.region].filter(Boolean).join(' · ')}
                          </div>
                          {labels.length > 0 && (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {labels.map((lab, li) => (
                                <span key={li} className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded inline-block">
                                  {lab}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0 break-words text-gray-700" dir={dirFor(language)}>
                          {renderDocumentText(result)}
                          {result.matched_restored && (
                            <div className="mt-1 text-xs text-sky-700">match on restored text</div>
                          )}
                          {(credit.source_name || credit.source_url) && (
                            <div className="mt-1 text-xs text-gray-500">
                              Text:{' '}
                              {credit.source_url ? (
                                <a href={credit.source_url} target="_blank" rel="noopener noreferrer"
                                   className="text-amber-700 hover:text-amber-900 underline">
                                  {credit.source_name || 'source'}
                                </a>
                              ) : (credit.source_name)}
                              {credit.licence_name && <span>, {credit.licence_name}</span>}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <Pagination {...docPagination} idPrefix="docsearch" itemLabel="documents" />
            </div>
          )}
        </>
      ) : (
        <div className="bg-white rounded-lg shadow p-4 sm:p-6 space-y-4">
          <div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Find Text to Search</h3>
            <p className="text-sm text-gray-500 mb-4">
              Select an author and work to view all lines. Click any line to use it as a search term.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Author</label>
              <SearchableSelect
                ariaLabel="Author"
                value={selectedAuthor}
                onChange={(v) => { setSelectedAuthor(v); setSelectedWork(''); setBrowseLines([]); }}
                options={authors.map(author => ({ value: author, label: author }))}
                placeholder="Select author..."
                disabled={loadingTexts}
                className="w-full border rounded px-3 py-2"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Work</label>
              <SearchableSelect
                ariaLabel="Work"
                value={selectedWork}
                onChange={(v) => { setSelectedWork(v); setBrowseLines([]); }}
                options={works.map(work => ({ value: work.id, label: work.label }))}
                placeholder={selectedAuthor ? 'Select work...' : 'Select author first'}
                disabled={!selectedAuthor || loadingTexts}
                className="w-full border rounded px-3 py-2"
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-600">Match type:</label>
                <select
                  value={searchType}
                  onChange={e => setSearchType(e.target.value)}
                  className="border rounded px-2 py-1.5 text-sm"
                >
                  <option value="lemma">Lemma (dictionary form)</option>
                  <option value="exact">Exact match</option>
                  <option value="regex">Regular expression (pattern)</option>
                </select>
              </div>
              <button
                onClick={handleBrowseLines}
                disabled={!selectedAuthor || !selectedWork || browseLoading}
                className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
              >
                {browseLoading ? 'Loading...' : 'Load Lines'}
              </button>
            </div>
            {searchType === 'regex' && (
              <p className="text-xs text-gray-500">
                Pattern matching: use <code className="bg-gray-100 px-1 rounded">.</code> for any character, <code className="bg-gray-100 px-1 rounded">|</code> for OR, <code className="bg-gray-100 px-1 rounded">[aei]</code> for character sets,
                {' '}<code className="bg-gray-100 px-1 rounded">.*</code> for any sequence. Example: <code className="bg-gray-100 px-1 rounded">amor|bellum</code> finds lines with either word. See Help & Support for more.
              </p>
            )}
          </div>

          {browseLoading && <LoadingSpinner text="Loading lines..." />}

          {browseLines.length > 0 && (
            <div className="border rounded-lg overflow-hidden">
              <div className="px-4 py-2 bg-gray-50 border-b flex justify-between items-center">
                <span className="text-sm text-gray-600">
                  {browseLines.length} lines found
                </span>
              </div>
              <div className="max-h-96 overflow-y-auto divide-y">
                {browsePagination.visibleItems.map((line, i) => (
                  <div
                    key={i}
                    className="p-3 hover:bg-amber-50 cursor-pointer flex gap-3"
                    onClick={() => selectLineForSearch(line)}
                  >
                    <span className="text-xs text-gray-500 w-16 flex-shrink-0 text-right break-words">
                      {displayLocus(line.locus, selectedWork)}
                    </span>
                    <span className="text-sm text-gray-700 flex-1 min-w-0" dir="auto">{decodeEntities(line.text)}</span>
                  </div>
                ))}
              </div>
              <Pagination {...browsePagination} idPrefix="line-browse" itemLabel="lines" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
