import { useState, useEffect, useCallback } from 'react';
import { fetchCorpus, fetchAuthors, fetchTexts } from '../utils/api';

export const useCorpus = (language) => {
  const [corpus, setCorpus] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [hierarchy, setHierarchy] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!language) return;
    
    setLoading(true);
    setError(null);
    setCorpus([]);
    setAuthors([]);
    setHierarchy([]);
    
    Promise.all([
      fetchCorpus(language),
      fetchAuthors(language)
    ])
      .then(([corpusData, authorsData]) => {
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
        
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [language]);

  const getTextsForAuthor = useCallback(async (authorKey) => {
    return fetchTexts(authorKey);
  }, []);

  return {
    corpus,
    authors,
    hierarchy,
    loading,
    error,
    getTextsForAuthor
  };
};

export default useCorpus;
