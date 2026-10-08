import Pagination from '../common/Pagination';
import { usePagination } from '../../hooks/usePagination';
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { LoadingSpinner, SearchableAuthorSelect, SearchableSelect, InfoBadge } from '../common';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { createSearchId, requestSearchCancellation } from '../../utils/api';
import { dirFor } from '../../utils/rtl';
import { exportRowsToPDF } from '../../utils/exportResults';
import { ResultsInsight } from '../assistant';
import { useCorpusTextMap, resolveDisplayCitation } from '../../utils/textNames';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

// rose highlights one word (the rhyme, right before the refrain), same as
// the single-language Persian/Urdu cards (owner's review of the live
// Persian to Urdu page, result card tidy, second pass, 2026-10-08).
const highlightTokens = (tokens, highlightIndices, roseIndex = -1) => {
  if (!tokens || tokens.length === 0) return '';
  const indexSet = new Set(highlightIndices || []);
  return tokens.map((token, i) => {
    if (i === roseIndex) return `<mark class="bg-rose-200 px-0.5 rounded">${token}</mark>`;
    return indexSet.has(i)
      ? `<mark class="bg-yellow-200 px-0.5 rounded">${token}</mark>`
      : token;
  }).join(' ');
};

// The rhyme word sits one token before the refrain's own highlighted range,
// the same position the single-language card derives it from when no named
// rhyme word is stored (SearchResults.jsx's renderHighlightedText).
const rhymeWordIndex = (highlightIndices) => {
  if (!highlightIndices || highlightIndices.length === 0) return -1;
  return Math.min(...highlightIndices) - 1;
};

// The channel badge's own names, in the same style as the main card's
// "lemma + sound" (result card tidy, second pass, 2026-10-08).
const CHANNEL_SCORE_LABELS = [
  ['semantic_score', 'semantic'],
  ['dict_score', 'vocabulary'],
  ['syntax_score', 'syntax'],
  ['phonetic_score', 'sound'],
  ['form_score', 'form'],
];
const channelNames = (features) => CHANNEL_SCORE_LABELS
  .filter(([key]) => features?.[key] > 0)
  .map(([, label]) => label);

const LANG_PAIRS = [
  { key: 'grc-la', source: 'grc', target: 'la', label: 'Greek → Latin' },
  { key: 'la-en', source: 'la', target: 'en', label: 'Latin → English' },
  { key: 'grc-en', source: 'grc', target: 'en', label: 'Greek → English' },
  { key: 'he-grc', source: 'he', target: 'grc', label: 'Hebrew → Greek' },
  { key: 'he-la', source: 'he', target: 'la', label: 'Hebrew → Latin' },
  { key: 'fa-ur', source: 'fa', target: 'ur', label: 'Persian → Urdu' },
  { key: 'ar-fa', source: 'ar', target: 'fa', label: 'Arabic → Persian' },
  { key: 'ar-ur', source: 'ar', target: 'ur', label: 'Arabic → Urdu' },
];

const LANG_LABELS = {
  grc: { name: 'Greek', color: 'amber', bgClass: 'bg-amber-50', textClass: 'text-amber-700', refClass: 'text-amber-600', btnClass: 'bg-amber-600 text-white' },
  la: { name: 'Latin', color: 'red', bgClass: 'bg-red-50', textClass: 'text-red-700', refClass: 'text-red-600', btnClass: 'bg-red-700 text-white' },
  en: { name: 'English', color: 'red', bgClass: 'bg-red-50', textClass: 'text-red-700', refClass: 'text-red-600', btnClass: 'bg-red-700 text-white' },
  he: { name: 'Hebrew', color: 'red', bgClass: 'bg-red-50', textClass: 'text-red-700', refClass: 'text-red-600', btnClass: 'bg-red-700 text-white' },
  fa: { name: 'Persian', color: 'red', bgClass: 'bg-red-50', textClass: 'text-red-700', refClass: 'text-red-600', btnClass: 'bg-red-700 text-white' },
  ur: { name: 'Urdu', color: 'red', bgClass: 'bg-red-50', textClass: 'text-red-700', refClass: 'text-red-600', btnClass: 'bg-red-700 text-white' },
  ar: { name: 'Arabic', color: 'red', bgClass: 'bg-red-50', textClass: 'text-red-700', refClass: 'text-red-600', btnClass: 'bg-red-700 text-white' },
};

const LANG_DEFAULTS = {
  grc: { author: 'homer', work: 'iliad', part: '.part.1.' },
  la: { author: 'vergil', work: 'aeneid', part: '.part.1.' },
  en: { author: 'milton', work: 'paradise_lost', part: null },
  he: { author: 'hebrew_bible', work: 'ruth', part: null },
  fa: { author: 'hafez', work: 'diwan', part: null },
  ur: { author: 'ghalib', work: 'diwan_wikisource', part: null },
  // Al-Baqara, the longest sura: 158 parallels to Hafez and 22 to Ghalib in
  // about two seconds. Al-Fatiha's seven verses gave eight and one.
  ar: { author: 'quran', work: 'al_baqara', part: null },
};

export default function CrossLingualSearch({ onOpenHelp }) {
  // Builds an InfoBadge `more` link to the matching label in the Help
  // page's "Reading the results" section (result card tidy, second pass,
  // 2026-10-08).
  const helpMore = (anchor) => ({
    anchor,
    onClick: () => onOpenHelp && onOpenHelp('reading-results', anchor),
  });
  const [hierarchy, setHierarchy] = useState({ grc: [], la: [], en: [] });
  const [loading, setLoading] = useState(true);
  const [searchLoading, setSearchLoading] = useState(false);
  const [results, setResults] = useState([]);
  // Set when the server answered a Hebrew-Greek search through the Septuagint
  // (via_septuagint in the response). Shown above the results, because a
  // reader must know the match was found in Greek and mapped to the Hebrew.
  const [pivotNote, setPivotNote] = useState(null);
  const [error, setError] = useState(null);

  const [langPair, setLangPair] = useState('grc-la');
  // The pairs this server can actually search, from /api/languages. A
  // preview serving only Persian, Urdu and Arabic used to open on Greek ->
  // Latin with empty menus, and the text lists were fetched for a fixed four
  // languages, so the Persian and Urdu menus were empty everywhere
  // (2026-09-06). Falls back to the full list if the request fails.
  const [pairs, setPairs] = useState(LANG_PAIRS);
  const [sourceAuthor, setSourceAuthor] = useState('');
  const [sourceWork, setSourceWork] = useState('');
  const [sourceSection, setSourceSection] = useState('');
  const [targetAuthor, setTargetAuthor] = useState('');
  const [targetWork, setTargetWork] = useState('');
  const [targetSection, setTargetSection] = useState('');

  const [minMatches, setMinMatches] = useState(2);
  // Hebrew -> Greek only: how a biblical search is answered (see
  // backend/lxx_pivot.py). 'septuagint' (default) pivots through the LXX
  // text when the Hebrew book has one; 'direct' always uses the dictionary
  // route; 'both' runs both and merges, labelling each result's route.
  const [hebrewGreekRoute, setHebrewGreekRoute] = useState('septuagint');
  const [sortBy, setSortBy] = useState('score');
  const [showDistributionChart, setShowDistributionChart] = useState(false);
  const [distributionChartView, setDistributionChartView] = useState('target');
  const [elapsedTime, setElapsedTime] = useState(0);
  const timerRef = useRef(null);
  const [chartFilter, setChartFilter] = useState(null);
  const chartRef = useRef(null);
  const hasSearchedRef = useRef(false);
  const abortRef = useRef(null);
  const activeSearchId = useRef(null);

  const currentPair = pairs.find(p => p.key === langPair) || pairs[0];
  const srcLang = LANG_LABELS[currentPair.source];
  const tgtLang = LANG_LABELS[currentPair.target];
  // Author/title lookup for a raw locus the fixed-author naming below does
  // not cover (result card tidy, 2026-10-08): the source side has never
  // carried a name, and the target side only does once a search has run.
  const srcCorpusMap = useCorpusTextMap(currentPair.source);
  const tgtCorpusMap = useCorpusTextMap(currentPair.target);

  // Persian, Urdu and Arabic pairs match on a different footing from the
  // classical ones, and the page used to describe every pair as SPhilBERTa
  // plus a translation dictionary, which was not true for every pair.
  // Describe each pair's own channels instead.
  const sharedScript = ['fa', 'ur', 'ar'].includes(currentPair.source)
    && ['fa', 'ur', 'ar'].includes(currentPair.target);
  // The per-pair description for the settings bar, kept to one plain
  // sentence (owner's review of the live Persian to Urdu page, result card
  // tidy, second pass, 2026-10-08): the channel badge on each result card
  // now carries its own evidence, so this line does not need to repeat it.
  const channelNoteShort = sharedScript
    ? 'Combines AI semantic matching (multilingual-e5) with shared-vocabulary matching across the two scripts.'
    : ['he', 'cop'].includes(currentPair.source) || ['he', 'cop'].includes(currentPair.target)
      ? 'Combines AI semantic matching with a cross-lingual dictionary built from aligned texts.'
      : 'Combines AI semantic matching (SPhilBERTa) with cross-lingual dictionary lookup.';

  // "Hafez, Diwan" for the chosen text, so a result reads "Hafez, Diwan 1626"
  // rather than a bare line number. The Persian, Urdu and Arabic reference tags
  // carry no author abbreviation, unlike "verg. aen. 1.1", so the locus alone
  // named nothing.
  const textName = (lang, authorKey, workKey) => {
    const author = (hierarchy[lang] || []).find(a => a.author_key === authorKey);
    const work = author?.works?.find(w => w.work_key === workKey);
    return [author?.author, work?.work].filter(Boolean).join(', ');
  };
  const srcName = textName(currentPair.source, sourceAuthor, sourceWork);
  const tgtName = textName(currentPair.target, targetAuthor, targetWork);
  const withName = (name, ref) => (name ? `${name} ${ref || ''}`.trim() : (ref || ''));
  // Names are fixed when the search runs, so changing the menus afterwards
  // does not relabel results that came from the earlier choice.
  const namesRef = useRef({ src: '', tgt: '' });
  namesRef.current = { src: srcName, tgt: tgtName };
  const [resultNames, setResultNames] = useState({ src: '', tgt: '' });

  const doSearch = useCallback(async () => {
    if (!sourceSection || !targetSection) {
      setError('Please select both source and target texts');
      return;
    }
    if (abortRef.current) {
      requestSearchCancellation(activeSearchId.current);
      abortRef.current.abort();
    }
    const controller = new AbortController();
    const searchId = createSearchId();
    abortRef.current = controller;
    activeSearchId.current = searchId;
    setSearchLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: sourceSection,
          target: targetSection,
          source_language: currentPair.source,
          target_language: currentPair.target,
          match_type: 'crosslingual_fusion',
          min_matches: minMatches,
          hebrew_greek_route: hebrewGreekRoute,
          search_id: searchId,
        }),
        signal: controller.signal
      });
      const data = await res.json();
      if (activeSearchId.current === searchId) {
        if (data.error) {
          setError(data.error);
          setResults([]);
    setPivotNote(null);
        } else {
          setResults(data.results || []);
          setPivotNote(data.via_septuagint ? (data.note || '') : null);
          // Freeze the chosen texts' names for these results (owner's review
          // of the live Persian to Urdu page, result card tidy, second pass,
          // 2026-10-08): this call was missing, so resultNames stayed empty
          // and every citation fell back to a bare ref with no author or
          // work ("1693" rather than "Hafez, Diwan 1693").
          setResultNames(namesRef.current);
        }
      }
    } catch (err) {
      if (err.name === 'AbortError' && activeSearchId.current === searchId) {
        setError(null);
      } else if (activeSearchId.current === searchId) {
        setError('Search failed. Please try again.');
      }
    }
    if (activeSearchId.current === searchId) {
      activeSearchId.current = null;
      abortRef.current = null;
      setSearchLoading(false);
    }
  }, [sourceSection, targetSection, minMatches, hebrewGreekRoute, currentPair]);

  const cancelSearch = useCallback(() => {
    if (abortRef.current) {
      requestSearchCancellation(activeSearchId.current);
      abortRef.current.abort();
      abortRef.current = null;
      activeSearchId.current = null;
      setSearchLoading(false);
    }
  }, []);

  useEffect(() => () => {
    requestSearchCancellation(activeSearchId.current);
    abortRef.current?.abort();
    activeSearchId.current = null;
    abortRef.current = null;
  }, []);

  useEffect(() => {
    loadHierarchies();
  }, []);

  const prevMinMatchesRef = useRef(minMatches);
  useEffect(() => {
    if (prevMinMatchesRef.current !== minMatches) {
      prevMinMatchesRef.current = minMatches;
      if (hasSearchedRef.current && sourceSection && targetSection && !searchLoading) {
        doSearch();
      }
    }
  }, [minMatches, sourceSection, targetSection, searchLoading, doSearch]);

  const prevHebrewGreekRouteRef = useRef(hebrewGreekRoute);
  useEffect(() => {
    if (prevHebrewGreekRouteRef.current !== hebrewGreekRoute) {
      prevHebrewGreekRouteRef.current = hebrewGreekRoute;
      if (hasSearchedRef.current && sourceSection && targetSection && !searchLoading) {
        doSearch();
      }
    }
  }, [hebrewGreekRoute, sourceSection, targetSection, searchLoading, doSearch]);

  useEffect(() => {
    if (searchLoading) {
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
  }, [searchLoading]);

  const setDefaultsForLang = useCallback((authors, lang, setSA, setSW, setSS) => {
    if (!authors?.length) return;
    const defaults = LANG_DEFAULTS[lang];
    const author = (defaults && authors.find(a => a.author_key === defaults.author)) || authors[0];
    setSA(author.author_key);
    if (author.works?.length > 0) {
      const work = (defaults && author.works.find(w => w.work_key === defaults.work)) || author.works[0];
      setSW(work.work_key);
      const part = defaults?.part
        ? work.parts?.find(p => p.id?.includes(defaults.part) || p.id?.endsWith('.1.tess'))
        : null;
      setSS(part?.id || work.whole_text || work.parts?.[0]?.id || '');
    }
  }, []);

  const loadHierarchies = async () => {
    setLoading(true);
    try {
      // The text lists for every language in a pair this server serves (not
      // a fixed four: Persian and Urdu had no lists, so choosing Persian ->
      // Urdu crashed the page).
      let served = LANG_PAIRS;
      try {
        const lr = await fetch('/api/languages');
        const ld = await lr.json();
        const keys = new Set((ld.crosslingual_pairs || []).map(p => p.key || `${p.source}-${p.target}`));
        if (keys.size) served = LANG_PAIRS.filter(p => keys.has(p.key));
      } catch (e) { /* keep the full list if the request fails */ }
      if (served.length) {
        setPairs(served);
        if (!served.some(p => p.key === langPair)) setLangPair(served[0].key);
      }
      const langs = [...new Set(served.flatMap(p => [p.source, p.target]))];
      const lists = await Promise.all(langs.map(lang =>
        fetch(`/api/texts/hierarchy?language=${lang}`)
          .then(r => r.json()).then(d => d.authors || []).catch(() => [])));
      const h = Object.fromEntries(langs.map((lang, i) => [lang, lists[i]]));
      const pair = served.find(p => p.key === langPair) || served[0] || currentPair;
      setHierarchy(h);
      setDefaultsForLang(h[pair.source] || [], pair.source, setSourceAuthor, setSourceWork, setSourceSection);
      setDefaultsForLang(h[pair.target] || [], pair.target, setTargetAuthor, setTargetWork, setTargetSection);
    } catch (err) {
      console.error('Failed to load text hierarchies:', err);
    }
    setLoading(false);
  };

  const getAuthorWorks = (authors, authorKey) => {
    const author = (authors || []).find(a => a.author_key === authorKey);
    return author ? author.works : [];
  };

  const getWorkParts = (authors, authorKey, workKey) => {
    const works = getAuthorWorks(authors, authorKey);
    const work = works.find(w => w.work_key === workKey);
    if (!work) return { wholeText: null, parts: [], workName: '' };
    return { wholeText: work.whole_text, parts: work.parts || [], workName: work.work };
  };

  const handleLangPairChange = useCallback((newKey) => {
    setLangPair(newKey);
    setResults([]);
    setPivotNote(null);
    setChartFilter(null);
    setHebrewGreekRoute('septuagint');
    hasSearchedRef.current = false;
    const pair = pairs.find(p => p.key === newKey) || pairs[0];
    setDefaultsForLang(hierarchy[pair.source] || [], pair.source, setSourceAuthor, setSourceWork, setSourceSection);
    setDefaultsForLang(hierarchy[pair.target] || [], pair.target, setTargetAuthor, setTargetWork, setTargetSection);
  }, [hierarchy, pairs, setDefaultsForLang]);

  const handleSearch = () => {
    hasSearchedRef.current = true;
    doSearch();
  };

  const exportCSV = useCallback(() => {
    const headers = ['Score', 'Channels', `${srcLang.name} Locus`, `${srcLang.name} Text`, `${tgtLang.name} Locus`, `${tgtLang.name} Text`, 'Semantic', 'Matched Words'];
    const rows = results.map(r => [
      (r.overall_score || r.score)?.toFixed(3) || '',
      (r.channels || ''),
      (r.source?.ref || r.source_locus || ''),
      (r.source?.text || r.source_text || '').replace(/"/g, '""'),
      (r.target?.ref || r.target_locus || ''),
      (r.target?.text || r.target_text || '').replace(/"/g, '""'),
      r.features?.semantic_score ? (r.features.semantic_score * 100).toFixed(0) + '%' : '',
      (r.matched_words || []).map(m => m.display || `${m.source_word || m.greek_word}→${m.target_word || m.latin_word}`).join('; ')
    ]);
    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cross_lingual_${langPair}_results.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [results, srcLang, tgtLang, langPair]);

  const sortedResults = useMemo(() => {
    if (!results || results.length === 0) return [];
    let filtered = chartFilter 
      ? results.filter(r => {
          const locus = chartFilter.view === 'source' 
            ? (r.source?.ref || r.source_locus || '') 
            : (r.target?.ref || r.target_locus || '');
          const bookMatch = locus.match(/(\d+)\.\d+/) || locus.match(/book\s*(\d+)/i);
          const book = bookMatch ? `Book ${bookMatch[1]}` : 'Other';
          return book === chartFilter.book;
        })
      : results;
    
    if (sortBy === 'score') {
      return [...filtered].sort((a, b) => (b.overall_score || b.score || 0) - (a.overall_score || a.score || 0));
    } else if (sortBy === 'source') {
      return [...filtered].sort((a, b) => (a.source?.ref || a.source_locus || '').localeCompare(b.source?.ref || b.source_locus || ''));
    } else {
      return [...filtered].sort((a, b) => (a.target?.ref || a.target_locus || '').localeCompare(b.target?.ref || b.target_locus || ''));
    }
  }, [results, sortBy, chartFilter]);

  const getDistributionData = useCallback(() => {
    if (!results || results.length === 0) return null;
    
    const bookData = {};
    const isSourceView = distributionChartView === 'source';
    
    results.forEach(r => {
      const locus = isSourceView 
        ? (r.source?.ref || r.source_locus || '') 
        : (r.target?.ref || r.target_locus || '');
      
      const bookMatch = locus.match(/(\d+)\.\d+/) || locus.match(/book\s*(\d+)/i);
      const book = bookMatch ? bookMatch[1] : 'Other';
      const bookLabel = `Book ${book}`;
      
      if (!bookData[bookLabel]) {
        bookData[bookLabel] = { count: 0, totalScore: 0 };
      }
      bookData[bookLabel].count++;
      bookData[bookLabel].totalScore += (r.overall_score || r.score || 0);
    });
    
    const sortedBooks = Object.keys(bookData).sort((a, b) => {
      const numA = parseInt(a.replace('Book ', '')) || 999;
      const numB = parseInt(b.replace('Book ', '')) || 999;
      return numA - numB;
    });
    
    return {
      labels: sortedBooks,
      datasets: [{
        label: 'Parallels',
        data: sortedBooks.map(b => bookData[b].count),
        backgroundColor: isSourceView
          ? { amber: 'rgba(217, 119, 6, 0.7)', red: 'rgba(185, 28, 28, 0.7)', blue: 'rgba(37, 99, 235, 0.7)' }[srcLang.color]
          : { amber: 'rgba(217, 119, 6, 0.7)', red: 'rgba(185, 28, 28, 0.7)', blue: 'rgba(37, 99, 235, 0.7)' }[tgtLang.color]
      }]
    };
  }, [results, distributionChartView, langPair]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { title: { display: true, text: distributionChartView === 'source' ? `${srcLang.name} Source` : `${tgtLang.name} Target` } },
      y: { beginAtZero: true, ticks: { precision: 0 } }
    },
    onClick: (event, elements) => {
      if (elements.length > 0) {
        const chartData = getDistributionData();
        if (chartData) {
          const clickedBook = chartData.labels[elements[0].index];
          setChartFilter(chartFilter?.book === clickedBook ? null : { book: clickedBook, view: distributionChartView });
        }
      }
    }
  };

  // Result identity changes on completion, even when the same query is run again.
  const paginationResetKey = useMemo(() => ({}), [results, sortBy, chartFilter]);
  const pagination = usePagination(sortedResults, { resetKey: paginationResetKey });

  if (loading) {
    return <LoadingSpinner text="Loading text data..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Cross-Lingual Search
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Find parallels across languages using AI semantic + dictionary fusion
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pairs.map(p => (
            <button
              key={p.key}
              onClick={() => handleLangPairChange(p.key)}
              className={`text-xs px-2 sm:px-3 py-1.5 rounded border transition-colors ${
                langPair === p.key
                  ? 'bg-gray-800 text-white border-gray-800'
                  : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className={`text-lg font-medium ${srcLang.textClass} mb-4`}>{srcLang.name} Source</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Author</label>
              <SearchableAuthorSelect
                value={sourceAuthor}
                onChange={(key) => {
                  setSourceAuthor(key);
                  setSourceWork('');
                  setSourceSection('');
                }}
                authors={hierarchy[currentPair.source] || []}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Work</label>
              <SearchableSelect
                ariaLabel="Source Work"
                value={sourceWork}
                onChange={(v) => {
                  setSourceWork(v);
                  if (v) {
                    const { wholeText, parts } = getWorkParts(hierarchy[currentPair.source], sourceAuthor, v);
                    setSourceSection(wholeText || parts[0]?.id || '');
                  } else {
                    setSourceSection('');
                  }
                }}
                options={getAuthorWorks(hierarchy[currentPair.source], sourceAuthor).map(w => ({ value: w.work_key, label: w.work }))}
                placeholder="Select a work..."
                className="w-full border rounded px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Section</label>
              <SearchableSelect
                ariaLabel="Source Section"
                value={sourceSection}
                onChange={setSourceSection}
                options={(() => {
                  const { wholeText, parts, workName } = getWorkParts(hierarchy[currentPair.source], sourceAuthor, sourceWork);
                  const opts = [];
                  if (wholeText) opts.push({ value: wholeText, label: `${workName} (Complete)` });
                  for (const p of parts) opts.push({ value: p.id, label: p.display });
                  return opts;
                })()}
                className="w-full border rounded px-3 py-2"
              />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <h3 className={`text-lg font-medium ${tgtLang.textClass} mb-4`}>{tgtLang.name} Target</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Author</label>
              <SearchableAuthorSelect
                value={targetAuthor}
                onChange={(key) => {
                  setTargetAuthor(key);
                  setTargetWork('');
                  setTargetSection('');
                }}
                authors={hierarchy[currentPair.target] || []}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Work</label>
              <SearchableSelect
                ariaLabel="Target Work"
                value={targetWork}
                onChange={(v) => {
                  setTargetWork(v);
                  if (v) {
                    const { wholeText, parts } = getWorkParts(hierarchy[currentPair.target], targetAuthor, v);
                    setTargetSection(wholeText || parts[0]?.id || '');
                  } else {
                    setTargetSection('');
                  }
                }}
                options={getAuthorWorks(hierarchy[currentPair.target], targetAuthor).map(w => ({ value: w.work_key, label: w.work }))}
                placeholder="Select a work..."
                className="w-full border rounded px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Section</label>
              <SearchableSelect
                ariaLabel="Target Section"
                value={targetSection}
                onChange={setTargetSection}
                options={(() => {
                  const { wholeText, parts, workName } = getWorkParts(hierarchy[currentPair.target], targetAuthor, targetWork);
                  const opts = [];
                  if (wholeText) opts.push({ value: wholeText, label: `${workName} (Complete)` });
                  for (const p of parts) opts.push({ value: p.id, label: p.display });
                  return opts;
                })()}
                className="w-full border rounded px-3 py-2"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-4 space-y-3 sm:space-y-0 sm:flex sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="space-y-2 sm:space-y-0 sm:flex sm:items-center sm:gap-4">
          {/* The per-pair description computed above (channelNoteShort), not a
              fixed sentence: Persian/Urdu/Arabic pairs run on multilingual-e5
              plus shared-vocabulary matching, not SPhilBERTa plus a
              cross-lingual dictionary (owner's review of the live Persian to
              Urdu page, result card tidy, second pass, 2026-10-08). */}
          <span className="text-sm text-gray-500 block">{channelNoteShort}</span>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600 whitespace-nowrap">Min Matches:</label>
            <select
              value={minMatches}
              onChange={(e) => setMinMatches(parseInt(e.target.value))}
              className="px-2 py-1.5 border rounded text-sm"
            >
              <option value={1}>Any (include semantic-only)</option>
              <option value={2}>2+ words (default)</option>
              <option value={3}>3+ words</option>
              <option value={4}>4+ words</option>
            </select>
          </div>
          {currentPair.key === 'he-grc' && (
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600 whitespace-nowrap">Route:</label>
              <select
                value={hebrewGreekRoute}
                onChange={(e) => setHebrewGreekRoute(e.target.value)}
                className="px-2 py-1.5 border rounded text-sm"
                title="How to answer a Hebrew to Greek search"
              >
                <option value="septuagint">Through the Septuagint (default)</option>
                <option value="direct">Directly</option>
                <option value="both">Both</option>
              </select>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSearch}
            disabled={searchLoading || !sourceSection || !targetSection}
            className="px-4 py-2 text-sm bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
          >
            {searchLoading ? 'Searching...' : 'Search'}
          </button>
          {searchLoading && (
            <button
              onClick={cancelSearch}
              className="px-3 py-2 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {searchLoading && <LoadingSpinner text="Searching for cross-lingual parallels..." elapsedTime={elapsedTime} />}

      {results.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {pivotNote && (
            <div className="px-4 py-2 bg-amber-50 border-b border-amber-200 text-xs text-amber-800">
              {pivotNote}
            </div>
          )}
          <div className="px-4 py-3 bg-gray-50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <span className="text-sm text-gray-600">
              Found {results.length} cross-lingual parallels
              {chartFilter && ` (${sortedResults.length} in ${chartFilter.book})`}
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setShowDistributionChart(!showDistributionChart)}
                className={`text-xs px-3 py-1.5 rounded ${showDistributionChart ? 'bg-amber-600 text-white' : 'bg-amber-100 text-amber-700 hover:bg-amber-200'}`}
              >
                {showDistributionChart ? 'Hide Chart' : 'Distribution'}
              </button>
              <button
                onClick={exportCSV}
                className="text-xs bg-red-700 text-white px-3 py-1.5 rounded hover:bg-red-800"
              >
                Export CSV
              </button>
              <span className="text-xs text-gray-500">Sort:</span>
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                className="text-xs border rounded px-2 py-1"
              >
                <option value="score">Score</option>
                <option value="source">{srcLang.name} Locus</option>
                <option value="target">{tgtLang.name} Locus</option>
              </select>
            </div>
          </div>
          
          {showDistributionChart && (
            <div className="p-4 border-b bg-gray-50">
              <div className="flex items-center gap-4 mb-3">
                <span className="text-sm text-gray-600">View:</span>
                <button
                  onClick={() => { setDistributionChartView('source'); setChartFilter(null); }}
                  className={`text-xs px-3 py-1 rounded ${distributionChartView === 'source' ? srcLang.btnClass : 'bg-gray-200'}`}
                >
                  {srcLang.name} Source
                </button>
                <button
                  onClick={() => { setDistributionChartView('target'); setChartFilter(null); }}
                  className={`text-xs px-3 py-1 rounded ${distributionChartView === 'target' ? tgtLang.btnClass : 'bg-gray-200'}`}
                >
                  {tgtLang.name} Target
                </button>
                {chartFilter && (
                  <button
                    onClick={() => setChartFilter(null)}
                    className="text-xs text-red-600 hover:text-red-800"
                  >
                    Clear Filter
                  </button>
                )}
              </div>
              <div style={{ height: '200px' }}>
                <Bar ref={chartRef} data={getDistributionData() || { labels: [], datasets: [] }} options={chartOptions} />
              </div>
            </div>
          )}
          
          <div className="divide-y divide-gray-200">
            {pagination.visibleItems.map((result, i) => (
              <div key={i} className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs text-gray-500 min-w-[2.5rem] text-right shrink-0 leading-none">
                    {pagination.startIndex + i + 1}.
                  </span>
                  {/* Every badge's popover is one short sentence, with a "More"
                      link into Help where a label has its own section there
                      (result card tidy, second pass, 2026-10-08). InfoBadge
                      carries no icon; the badge itself is the trigger. */}
                  <InfoBadge
                    className="bg-white text-gray-600 px-0"
                    explanation="How strong the match is overall; results are ranked by it."
                    more={helpMore('score')}
                  >
                    Score: {(result.overall_score || result.score)?.toFixed(3)}
                  </InfoBadge>
                  {result.poetics?.radif && (
                    <InfoBadge
                      className="bg-yellow-100 text-yellow-800"
                      explanation="The refrain (radif) both poems end on."
                      more={helpMore('refrain')}
                    >
                      Refrain: <span dir="rtl">{result.poetics.radif}</span>
                    </InfoBadge>
                  )}
                  {result.poetics?.qafia && (
                    <InfoBadge
                      className="bg-rose-100 text-rose-800"
                      explanation="The rhyme (qafiya) both poems share, before the refrain."
                      more={helpMore('rhyme')}
                    >
                      Rhyme: <span dir="rtl">-{result.poetics.qafia}</span>
                    </InfoBadge>
                  )}
                  {/* Evidence group, channel count/names first and the
                      semantic percentage after it, since semantic is one of
                      those channels (owner's review of the live Persian to
                      Urdu page, result card tidy, second pass, 2026-10-08).
                      Blue is the evidence color; yellow stays reserved for
                      the refrain and shared words. */}
                  {result.features?.n_channels > 0 && (
                    <InfoBadge
                      className="bg-blue-100 text-blue-700"
                      explanation="Which kinds of evidence found this match."
                      more={helpMore('channels')}
                    >
                      {result.features.n_channels} channel{result.features.n_channels !== 1 ? 's' : ''}: {channelNames(result.features).join(' + ')}
                    </InfoBadge>
                  )}
                  {result.features?.semantic_score > 0 && (
                    <InfoBadge
                      className="bg-blue-100 text-blue-700"
                      explanation="How closely an AI model judges the two lines' meaning to match, apart from shared vocabulary."
                    >
                      Semantic: {(result.features.semantic_score * 100).toFixed(0)}%
                    </InfoBadge>
                  )}
                  {result.route && (
                    <InfoBadge
                      className="bg-gray-100 text-gray-600"
                      explanation={result.route === 'septuagint'
                        ? 'This match runs through the Greek Septuagint rather than directly between the languages.'
                        : 'This match runs directly between the two languages, with no translation in between.'}
                    >
                      {result.route === 'septuagint' ? 'Via Septuagint' : 'Direct'}
                    </InfoBadge>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Source</div>
                    <div className="font-medium text-gray-900">
                      {(() => {
                        const raw = result.source?.ref || result.source_locus;
                        return resolveDisplayCitation(withName(resultNames.src, raw), raw, srcCorpusMap).text;
                      })()}
                    </div>
                    {(result.source?.hebrew_ref || result.target?.hebrew_ref) && (
                      <div className="text-xs text-gray-600 mt-0.5">
                        Hebrew: {result.source?.hebrew_ref || result.target?.hebrew_ref}
                        {(result.source?.hebrew_text || result.target?.hebrew_text) && (
                          <div className="text-gray-700 mt-0.5" dir="rtl">{result.source?.hebrew_text || result.target?.hebrew_text}</div>
                        )}
                      </div>
                    )}
                    {result.source?.tokens && result.source?.highlight_indices?.length > 0 ? (
                      <div className="text-gray-700 mt-1" dir={dirFor(currentPair.source)} dangerouslySetInnerHTML={{ __html: highlightTokens(result.source.tokens, result.source.highlight_indices, result.poetics?.qafia ? rhymeWordIndex(result.source.highlight_indices) : -1) }} />
                    ) : (
                      <div className="text-gray-700 mt-1" dir={dirFor(currentPair.source)}>{result.source?.text || result.source_text || ''}</div>
                    )}
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Target</div>
                    <div className="font-medium text-gray-900">
                      {(() => {
                        const raw = result.target?.ref || result.target_locus;
                        return resolveDisplayCitation(withName(resultNames.tgt, raw), raw, tgtCorpusMap).text;
                      })()}
                    </div>
                    {result.target?.tokens && result.target?.highlight_indices?.length > 0 ? (
                      <div className="text-gray-700 mt-1" dir={dirFor(currentPair.target)} dangerouslySetInnerHTML={{ __html: highlightTokens(result.target.tokens, result.target.highlight_indices, result.poetics?.qafia ? rhymeWordIndex(result.target.highlight_indices) : -1) }} />
                    ) : (
                      <div className="text-gray-700 mt-1" dir={dirFor(currentPair.target)}>{result.target?.text || result.target_text || ''}</div>
                    )}
                  </div>
                </div>
                {result.matched_words?.length > 0 && (
                  <div className="mt-2 text-xs text-gray-500">
                    Matched: {result.matched_words.map(m => m.display || `${m.source_word || m.greek_word} → ${m.target_word || m.latin_word}`).join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
          <Pagination {...pagination} idPrefix="crosslingualsearch" />
        </div>
      )}
    </div>
  );
}
