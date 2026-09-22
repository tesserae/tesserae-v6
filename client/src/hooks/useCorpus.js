import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchCorpus, fetchAuthors, fetchTexts } from '../utils/api';

export const useCorpus = (language) => {
  const [corpus, setCorpus] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [hierarchy, setHierarchy] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const retryCountRef = useRef(0);
  // WHICH LANGUAGE THE ANSWER HAS TO BE FOR.
  //
  // Clicking Latin, then Greek, then English leaves three requests in the
  // air at once, and whichever lands last used to win, not whichever was
  // asked for last. The pickers could then show one language's texts under
  // another language's tab, with nothing to say so. Every setter below is
  // now behind this check, and a late answer for a language nobody is
  // looking at any more is dropped, including the automatic retry, which
  // otherwise re-asked for the abandoned language two seconds later.
  const wantedLanguageRef = useRef(language);

  const loadCorpus = useCallback((lang) => {
    if (!lang) return;
    const stale = () => wantedLanguageRef.current !== lang;

    setLoading(true);
    setError(null);

    Promise.all([
      fetchCorpus(lang),
      fetchAuthors(lang)
    ])
      .then(([corpusData, authorsData]) => {
        if (stale()) return;
        const texts = Array.isArray(corpusData) ? corpusData : (corpusData.texts || []);
        setCorpus(texts);

        const authorsArray = Array.isArray(authorsData) ? authorsData : (authorsData.authors || []);

        const formattedAuthors = authorsArray.map(a => ({
          author: a.name || a.author,
          author_key: a.works?.[0]?.author_key || a.name?.toLowerCase().replace(/\s+/g, '_') || '',
          era: a.era,
          year: a.year,
          works: a.works || []
        }));
        setAuthors(formattedAuthors);

        const hierarchyData = authorsArray.map(a => {
          const authorKey = a.works?.[0]?.author_key || a.name?.toLowerCase().replace(/\s+/g, '_') || '';

          const worksMap = {};
          (a.works || []).forEach(w => {
            const workKey = w.work_key || w.work?.toLowerCase().replace(/\s+/g, '_') || '';
            if (!worksMap[workKey]) {
              worksMap[workKey] = {
                work_key: workKey,
                work: w.work || w.title,
                sections: []
              };
            }
            worksMap[workKey].sections.push({
              file: w.id,
              label: w.is_part ? (w.part || w.title) : w.title
            });
          });

          return {
            author: a.name || a.author,
            author_key: authorKey,
            works: Object.values(worksMap)
          };
        });
        setHierarchy(hierarchyData);

        retryCountRef.current = 0;
        setLoading(false);
      })
      .catch(err => {
        if (stale()) return;
        // One automatic retry: a transient authors-fetch failure used to
        // leave the Reader's dropdowns empty (placeholder Author/Work) until
        // a full reload, with no way to recover from the page.
        if (retryCountRef.current < 1) {
          retryCountRef.current += 1;
          setTimeout(() => { if (!stale()) loadCorpus(lang); }, 2000);
          return;
        }
        setError(err.message || 'Failed to load corpus data');
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    wantedLanguageRef.current = language;
    setCorpus([]);
    setAuthors([]);
    setHierarchy([]);
    retryCountRef.current = 0;   // each language gets its own retry budget
    loadCorpus(language);
  }, [language, loadCorpus]);

  const retry = useCallback(() => {
    retryCountRef.current += 1;
    loadCorpus(language);
  }, [language, loadCorpus]);

  const getTextsForAuthor = useCallback(async (authorKey) => {
    return fetchTexts(authorKey);
  }, []);

  return {
    corpus,
    authors,
    hierarchy,
    loading,
    error,
    retry,
    getTextsForAuthor
  };
};

export default useCorpus;
