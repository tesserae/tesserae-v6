// Which pair of texts the pickers hold: a new tab or a new view clears the
// old pair and results, and once the corpus has loaded the language's default
// pair is filled in (moved out of App.jsx, cleaning job H4, 2026-10-13, code
// unchanged).
import { useEffect, useRef } from 'react';
import { viewById } from '../collections/collectionsConfig';

export const useDefaultTexts = ({
  activeTab, corpus, corpusLoading, sourceAuthor, sourceText, targetAuthor, targetText, view, clearResults,
  setSourceAuthor, setSourceText, setTargetAuthor, setTargetText,
  setCorpusSearchResults, setCorpusSearchQuery, setCorpusSearchElapsed, setShowCorpusSearch,
}) => {
  // Track previous activeTab and corpus loading state to detect when to apply defaults
  const prevActiveTabRef = useRef(null);
  const corpusLoadedForTabRef = useRef(null);
  // The view last seen, and the pair last set as defaults: when the view
  // changes, a pair the visitor never picked is replaced by the new view's.
  const prevViewRef = useRef(null);
  const lastDefaultsRef = useRef({ source: '', target: '' });
  
  useEffect(() => {
    const tabChanged = prevActiveTabRef.current !== null && prevActiveTabRef.current !== activeTab;
    prevActiveTabRef.current = activeTab;
    const viewChanged = prevViewRef.current !== null && prevViewRef.current !== view;
    prevViewRef.current = view;
    const notPicked = (!sourceText && !targetText)
      || (sourceText === lastDefaultsRef.current.source && targetText === lastDefaultsRef.current.target);
    const viewReset = viewChanged && notPicked;
    if (viewReset && !tabChanged && !sourceText && !targetText) {
      // Nothing to clear: let the defaults below apply for the new view.
      corpusLoadedForTabRef.current = null;
    }
    
    // Clear results AND text selections when tab changes
    if (tabChanged || (viewReset && (sourceText || targetText))) {
      clearResults();
      setCorpusSearchResults(null);
      setCorpusSearchQuery(null);
      setCorpusSearchElapsed(0);
      setShowCorpusSearch(false);
      // Clear text selections so defaults can be applied for new language
      setSourceAuthor('');
      setSourceText('');
      setTargetAuthor('');
      setTargetText('');
      // Reset corpus tracking so defaults will be applied when new corpus loads
      corpusLoadedForTabRef.current = null;
      // Exit early - let the next render cycle apply defaults with new corpus data
      return;
    }
    
    // Corpus is ready when not loading, has data, AND belongs to the active
    // tab. Right after a tab change the previous language's list is still in
    // hand for a render or two; treating it as ready set the new tab's
    // defaults from the wrong corpus (Urdu opened with Persian ids and so
    // with empty fields, 2026-09-06).
    const corpusReady = !corpusLoading && corpus.length > 0
      && (!corpus[0]?.language || corpus[0].language === activeTab);
    const corpusJustLoaded = corpusReady && corpusLoadedForTabRef.current !== activeTab;
    
    if (corpusJustLoaded) {
      corpusLoadedForTabRef.current = activeTab;
    }
    
    // Preserve transferred selections from Browse if they exist in this corpus.
    const sourceExists = Boolean(sourceText) && corpus.some(t => t.id === sourceText);
    const targetExists = Boolean(targetText) && corpus.some(t => t.id === targetText);
    const hasValidSelection = sourceExists && targetExists;

    // Set defaults only when we do not already have valid selections.
    // Defaults apply when the corpus has just loaded, when nothing is chosen,
    // or when a remembered id is STALE (not in this corpus: an earlier session's
    // pair, or a text since retired). The stale case is new (2026-09-19): a
    // stale remembered English pair left the page with no texts at all. A
    // pair mid-edit, with one side chosen and valid and the other still empty,
    // is none of these and is left alone.
    const sourceStale = Boolean(sourceText) && !sourceExists;
    const targetStale = Boolean(targetText) && !targetExists;
    const nothingChosen = !sourceAuthor && !sourceText && !targetAuthor && !targetText;
    const shouldSetDefaults = corpusReady && !hasValidSelection
      && (corpusJustLoaded || nothingChosen || sourceStale || targetStale);
    
    if (shouldSetDefaults) {
      let defaultSourceId, defaultTargetId;
      const viewPair = viewById(view).searchDefaults?.[activeTab];
      if (viewPair) {
        defaultSourceId = viewPair.source;
        defaultTargetId = viewPair.target;
      } else if (activeTab === 'grc') {
        defaultSourceId = 'homer.iliad.part.1.tess';
        defaultTargetId = 'apollonius_rhodius.argonautica.part.1.tess';
      } else if (activeTab === 'en') {
        defaultSourceId = 'milton.paradise_lost.part.1.tess';
        defaultTargetId = 'keats.hyperion.tess';
      } else if (activeTab === 'cop') {
        defaultSourceId = 'sahidic.bible.tess';
        defaultTargetId = 'shenoute.abraham.tess';
      } else if (activeTab === 'he') {
        defaultSourceId = 'hebrew_bible.ruth.tess';
        defaultTargetId = 'hebrew_bible.1_samuel.tess';
      } else if (activeTab === 'fa') {
        // Hafez against Zabur-e Ajam (the owner's choice, 2026-10-26): the
        // answer-poem pair, where seven known responses by Iqbal to Hafez
        // sit in the top ten and the Rhyme badge shows on the default page.
        // It is 12 million line pairs, so it depends on its cached answer:
        // keep the pair cached, and never clear the whole search cache
        // (clear one language, or re-run the default pairs after). Without
        // a fixed pair the fallback below picked the first two Persian
        // texts alphabetically, Anvari against Attar, five billion pairs.
        defaultSourceId = 'hafez.diwan.tess';
        defaultTargetId = 'iqbal.zabur_e_ajam.tess';
      } else if (activeTab === 'ur') {
        // Wali against Mir (2026-10-26): one part, and its first result is
        // a poetic response found by refrain and rhyme, so the Rhyme badge
        // with its shared rhyme words shows on the default page. Ghalib
        // against Bang-e Dra (the earlier choice) is 8 million pairs and
        // runs in parts.
        defaultSourceId = 'wali.diwan_wikisource.tess';
        defaultTargetId = 'mir.kulliyat_wikisource.tess';
      } else if (activeTab === 'ar') {
        defaultSourceId = 'quran.al_waqia.tess';
        defaultTargetId = 'busiri.burda.tess';
      } else {
        defaultSourceId = 'vergil.aeneid.part.1.tess';
        defaultTargetId = 'lucan.bellum_civile.part.1.tess';
      }
      
      const defaultSource = corpus.find(t => t.id === defaultSourceId) || corpus[0];
      const defaultTarget = corpus.find(t => t.id === defaultTargetId) || corpus[1] || corpus[0];
      
      lastDefaultsRef.current = { source: defaultSource?.id || '', target: defaultTarget?.id || '' };
      if (defaultSource) {
        setSourceAuthor(defaultSource.author_key || defaultSource.author?.toLowerCase().replace(/\s+/g, '_') || '');
        setSourceText(defaultSource.id);
      }
      if (defaultTarget) {
        setTargetAuthor(defaultTarget.author_key || defaultTarget.author?.toLowerCase().replace(/\s+/g, '_') || '');
        setTargetText(defaultTarget.id);
      }
    }
  }, [activeTab, corpus, corpusLoading, sourceText, targetText, clearResults, view,
    setSourceAuthor, setSourceText, setTargetAuthor, setTargetText,
    setCorpusSearchResults, setCorpusSearchQuery, setCorpusSearchElapsed, setShowCorpusSearch]);
};

export default useDefaultTexts;
