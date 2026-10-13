// The side panel that shows a corpus-wide search for the words of one parallel
// (moved out of App.jsx, cleaning job H4, 2026-10-13, code unchanged): its
// state and the handler a result card's "Search Corpus" button calls.
import { useState, useCallback } from 'react';
import { postJsonTo } from '../utils/api';

export const useCorpusSearchPanel = ({ activeTab }) => {
  const [corpusSearchResults, setCorpusSearchResults] = useState(null);
  const [corpusSearchLoading, setCorpusSearchLoading] = useState(false);
  const [corpusSearchQuery, setCorpusSearchQuery] = useState(null);
  const [corpusSearchError, setCorpusSearchError] = useState(null);
  const [corpusSearchElapsed, setCorpusSearchElapsed] = useState(0);
  const [showCorpusSearch, setShowCorpusSearch] = useState(false);

  const handleCorpusSearch = useCallback(async (result) => {
    let lemmas;
    let queryInfo;
    // A cross-language card passes its own language explicitly (the source
    // and target sides of a cross-language pair are two different
    // languages, so there is no single activeTab to fall back to there);
    // every other caller still searches the one language on screen.
    const searchLanguage = (result && typeof result === 'object' && result.language) || activeTab;

    if (typeof result === 'string') {
      lemmas = result.split(/\s*\+\s*|\s+/).filter(Boolean);
      queryInfo = {
        source: { ref: 'Rare Word/Pair Search', text: result },
        target: { ref: '', text: '' },
        lemmas,
        language: searchLanguage
      };
    } else {
      // Prefer the clean matched_lemmas list (real content words, markup and
      // function words removed). Fall back to parsing matched_words for older
      // results that predate the field.
      lemmas = (Array.isArray(result.matched_lemmas) && result.matched_lemmas.length)
        ? result.matched_lemmas.slice()
        : (result.matched_words || []).map(w =>
            typeof w === 'object' ? (w.lemma || w.word || '') : w
          ).filter(Boolean);
      queryInfo = {
        // citation: the server's own "<Author>, <Work title> <locus>" string
        // (issue #566), carried through so the Source/Target header below
        // can show it instead of re-parsing ref client-side.
        source: { ref: result.source_locus || result.source?.ref, text: result.source_text || result.source?.text,
                  citation: result.source?.citation },
        target: { ref: result.target_locus || result.target?.ref, text: result.target_text || result.target?.text,
                  citation: result.target?.citation },
        lemmas,
        language: searchLanguage
      };
    }

    if (lemmas.length < 1) {
      alert('At least 1 word is required for corpus search');
      return;
    }

    setCorpusSearchQuery(queryInfo);
    setCorpusSearchResults(null);
    setCorpusSearchError(null);
    setCorpusSearchLoading(true);
    setShowCorpusSearch(true);
    setCorpusSearchElapsed(0);

    const startTime = Date.now();
    const timerInterval = setInterval(() => {
      setCorpusSearchElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    try {
      const data = await postJsonTo('/api/corpus-search', {
        lemmas,
        language: searchLanguage,
        // The two texts being compared used to be left out, so the corpus
        // map and its timeline never showed the very authors in question
        // (2026-09-07: Mir and Iqbal were missing). They are included and
        // the chart marks them.
        exclude_texts: []
      });
      clearInterval(timerInterval);
      if (data.error) {
        setCorpusSearchError(data.error);
      } else {
        setCorpusSearchResults(data.results || []);
      }
    } catch (err) {
      clearInterval(timerInterval);
      setCorpusSearchError('Corpus search failed. Please try again.');
    }
    setCorpusSearchLoading(false);
  }, [activeTab]);

  return {
    corpusSearchResults, setCorpusSearchResults, corpusSearchLoading, corpusSearchQuery, setCorpusSearchQuery,
    corpusSearchError, corpusSearchElapsed, setCorpusSearchElapsed, showCorpusSearch, setShowCorpusSearch,
    handleCorpusSearch,
  };
};

export default useCorpusSearchPanel;
