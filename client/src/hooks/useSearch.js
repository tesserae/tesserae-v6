import { useState, useRef, useCallback, useEffect } from 'react';
import { searchTexts, searchTextsStream, searchHapax, searchBigrams, searchSemanticCross } from '../utils/api';

export const useSearch = () => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState('');
  const [elapsedTime, setElapsedTime] = useState(0);
  const [searchStats, setSearchStats] = useState(null);
  const abortController = useRef(null);
  const timerRef = useRef(null);
  const startTimeRef = useRef(null);

  useEffect(() => {
    if (loading) {
      startTimeRef.current = Date.now();
      setElapsedTime(0);
      timerRef.current = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - startTimeRef.current) / 1000));
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

  const search = useCallback(async (params) => {
    if (abortController.current) {
      abortController.current.abort();
    }
    
    abortController.current = new AbortController();
    setLoading(true);
    setError(null);
    setProgress(0);
    setProgressText('');
    setSearchStats(null);
    
    const handleProgress = (step, detail, elapsed) => {
      setProgressText(detail ? `${step}: ${detail}` : step);
      setElapsedTime(Math.floor(elapsed));
    };
    
    try {
      const matchType = params.match_type || params.settings?.match_type;
      const isCrossLingual = matchType === 'semantic_cross' || matchType === 'dictionary_cross';
      
      let data;
      if (isCrossLingual) {
        data = await searchTexts(params, abortController.current.signal);
      } else {
        data = await searchTextsStream(params, handleProgress, abortController.current.signal);
      }
      
      setResults(data.results || []);
      setSearchStats({
        elapsed_time: data.elapsed_time,
        source_lines: data.source_lines,
        target_lines: data.target_lines
      });
      setProgress(100);
      setProgressText('Complete');
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Search failed');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const searchCrossLingual = useCallback(async (params) => {
    if (abortController.current) {
      abortController.current.abort();
    }
    
    abortController.current = new AbortController();
    setLoading(true);
    setError(null);
    
    try {
      const data = await searchSemanticCross(params, abortController.current.signal);
      setResults(data.results || []);
      return data;
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Search failed');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const searchRareWords = useCallback(async (params) => {
    if (abortController.current) {
      abortController.current.abort();
    }
    
    abortController.current = new AbortController();
    setLoading(true);
    setError(null);
    
    try {
      const data = await searchHapax(params, abortController.current.signal);
      setResults(data.results || data.shared_words || []);
      return data;
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Search failed');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const searchWordPairs = useCallback(async (params) => {
    if (abortController.current) {
      abortController.current.abort();
    }
    
    abortController.current = new AbortController();
    setLoading(true);
    setError(null);
    
    try {
      const data = await searchBigrams(params, abortController.current.signal);
      if (data.error) {
        setError(data.error);
        setResults([]);
        return data;
      }
      setResults(data.results || data.shared_bigrams || []);
      return data;
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Search failed');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const cancel = useCallback(() => {
    if (abortController.current) {
      abortController.current.abort();
      abortController.current = null;
    }
    setLoading(false);
    setProgress(0);
    setProgressText('');
  }, []);

  const clearResults = useCallback(() => {
    setResults([]);
    setError(null);
  }, []);

  return {
    results,
    loading,
    error,
    progress,
    progressText,
    elapsedTime,
    searchStats,
    search,
    searchCrossLingual,
    searchRareWords,
    searchWordPairs,
    cancel,
    clearResults
  };
};

export default useSearch;
