import { useState, useRef, useCallback, useEffect } from 'react';
import { searchTexts, searchTextsStream, searchFusionStream, searchHapax, searchBigrams, searchSemanticCross, createSearchId, requestSearchCancellation } from '../utils/api';

export const useSearch = () => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState('');
  const [elapsedTime, setElapsedTime] = useState(0);
  const [searchStats, setSearchStats] = useState(null);
  const [fusionProgress, setFusionProgress] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [isQueued, setIsQueued] = useState(false);
  const [queuedMessage, setQueuedMessage] = useState('');
  const abortController = useRef(null);
  const activeSearchId = useRef(null);
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

  useEffect(() => () => {
    requestSearchCancellation(activeSearchId.current);
    abortController.current?.abort();
    activeSearchId.current = null;
    abortController.current = null;
  }, []);

  const search = useCallback(async (params) => {
    if (abortController.current) {
      requestSearchCancellation(activeSearchId.current);
      abortController.current.abort();
    }
    activeSearchId.current = null;
    
    const controller = new AbortController();
    abortController.current = controller;
    const searchId = createSearchId();
    activeSearchId.current = searchId;
    setLoading(true);
    setError(null);
    setProgress(0);
    setProgressText('');
    setSearchStats(null);
    setFusionProgress(null);
    setIsQueued(false);
    setQueuedMessage('');

    const handleProgress = (step, detail, elapsed, meta = null) => {
      if (activeSearchId.current !== searchId) return;
      setIsQueued(false);
      setQueuedMessage('');
      setProgressText(detail ? `${step}: ${detail}` : step);
      setElapsedTime(Math.floor(elapsed));
      if (meta?.fusion_batch) {
        const batch = meta.fusion_batch;
        setFusionProgress(prev => ({
          channelsDone: prev?.channelsDone || [],
          channelsTotal: batch.total || prev?.channelsTotal || 0,
          phase: batch.phase || prev?.phase || 'line',
          currentChannel: batch.channel,
          batchIndex: batch.index || 0,
          batchTotal: batch.total || 0,
          batchStatus: batch.status || 'running',
          currentBatchResults: batch.result_count || 0,
          totalMatches: prev?.totalMatches || 0,
          resultCount: prev?.resultCount || 0,
        }));
      }
    };

    const handleQueued = (reason, waitTime) => {
      if (activeSearchId.current !== searchId) return;
      setIsQueued(true);
      setQueuedMessage(reason || 'Server is busy, your search is queued...');
    };

    try {
      const matchType = params.match_type || params.settings?.match_type;
      const isCrossLingual = matchType === 'semantic_cross' || matchType === 'dictionary_cross' || matchType === 'crosslingual_fusion';
      const isFusion = matchType === 'fusion';

      let data;
      if (isFusion) {
        const handleIntermediate = (intermediateData) => {
          if (activeSearchId.current !== searchId) return;
          setResults(intermediateData.results || []);
          const channelsDone = intermediateData.channels_done || [];
          const channelsTotal = intermediateData.channels_total || 9;
          setFusionProgress({
            channelsDone,
            channelsTotal,
            phase: intermediateData.phase || 'line',
            batchIndex: channelsDone.length,
            batchTotal: channelsTotal,
            batchStatus: 'done',
            currentChannel: channelsDone[channelsDone.length - 1] || '',
            currentBatchResults: 0,
            totalMatches: intermediateData.total_matches || 0,
            resultCount: (intermediateData.results || []).length,
          });
        };
        data = await searchFusionStream({ ...params, search_id: searchId }, handleProgress, controller.signal, handleIntermediate, handleQueued);
      } else if (isCrossLingual) {
        data = await searchTexts({ ...params, search_id: searchId }, controller.signal);
      } else {
        try {
          data = await searchTextsStream({ ...params, search_id: searchId }, handleProgress, controller.signal, handleQueued);
        } catch (streamErr) {
          if (streamErr.message && streamErr.message.includes('405')) {
            if (activeSearchId.current === searchId) {
              setProgressText('Streaming not available, using standard search...');
            }
            data = await searchTexts({ ...params, search_id: searchId }, controller.signal);
          } else {
            throw streamErr;
          }
        }
      }
      
      if (activeSearchId.current === searchId) {
        setResults(data.results || []);
        setSearchStats({
          elapsed_time: data.elapsed_time,
          source_lines: data.source_lines,
          target_lines: data.target_lines,
          total_matches: data.total_matches
        });
        setProgress(100);
        setProgressText('Complete');
        setFusionProgress(null);
      }
    } catch (err) {
      if (err.name !== 'AbortError' && activeSearchId.current === searchId) {
        setError(err.message || 'Search failed');
      }
    } finally {
      if (activeSearchId.current === searchId) {
        activeSearchId.current = null;
        abortController.current = null;
        setLoading(false);
        setFusionProgress(null);
        setHasSearched(true);
      }
    }
  }, []);

  const searchCrossLingual = useCallback(async (params) => {
    if (abortController.current) {
      requestSearchCancellation(activeSearchId.current);
      abortController.current.abort();
    }
    activeSearchId.current = null;
    
    const controller = new AbortController();
    abortController.current = controller;
    const searchId = createSearchId();
    activeSearchId.current = searchId;
    setLoading(true);
    setError(null);
    
    try {
      const data = await searchSemanticCross({ ...params, search_id: searchId }, controller.signal);
      if (activeSearchId.current === searchId) {
        setResults(data.results || []);
      }
      return data;
    } catch (err) {
      if (err.name !== 'AbortError' && activeSearchId.current === searchId) {
        setError(err.message || 'Search failed');
      }
    } finally {
      if (activeSearchId.current === searchId) {
        activeSearchId.current = null;
        abortController.current = null;
        setLoading(false);
        setHasSearched(true);
      }
    }
  }, []);

  const searchRareWords = useCallback(async (params) => {
    if (abortController.current) {
      requestSearchCancellation(activeSearchId.current);
      abortController.current.abort();
    }
    activeSearchId.current = null;
    
    const controller = new AbortController();
    abortController.current = controller;
    setLoading(true);
    setError(null);
    
    try {
      const data = await searchHapax(params, controller.signal);
      if (abortController.current === controller) {
        setResults(data.results || data.shared_words || []);
      }
      return data;
    } catch (err) {
      if (err.name !== 'AbortError' && abortController.current === controller) {
        setError(err.message || 'Search failed');
      }
    } finally {
      if (abortController.current === controller) {
        abortController.current = null;
        setLoading(false);
        setHasSearched(true);
      }
    }
  }, []);

  const searchWordPairs = useCallback(async (params) => {
    if (abortController.current) {
      requestSearchCancellation(activeSearchId.current);
      abortController.current.abort();
    }
    activeSearchId.current = null;

    const controller = new AbortController();
    abortController.current = controller;
    setLoading(true);
    setError(null);

    try {
      const data = await searchBigrams(params, controller.signal);
      if (abortController.current !== controller) return data;
      if (data.error) {
        setError(data.error);
        setResults([]);
        return data;
      }
      setResults(data.results || data.shared_bigrams || []);
      return data;
    } catch (err) {
      if (err.name !== 'AbortError' && abortController.current === controller) {
        setError(err.message || 'Search failed');
      }
    } finally {
      if (abortController.current === controller) {
        abortController.current = null;
        setLoading(false);
        setHasSearched(true);
      }
    }
  }, []);

  const cancel = useCallback(() => {
    if (abortController.current) {
      requestSearchCancellation(activeSearchId.current);
      abortController.current.abort();
      abortController.current = null;
      activeSearchId.current = null;
    }
    setLoading(false);
    setProgress(0);
    setProgressText('');
    setFusionProgress(null);
    setIsQueued(false);
    setQueuedMessage('');
  }, []);

  const clearResults = useCallback(() => {
    setResults([]);
    setError(null);
    setHasSearched(false);
  }, []);

  return {
    results,
    loading,
    error,
    progress,
    progressText,
    elapsedTime,
    searchStats,
    fusionProgress,
    hasSearched,
    isQueued,
    queuedMessage,
    search,
    searchCrossLingual,
    searchRareWords,
    searchWordPairs,
    cancel,
    clearResults
  };
};

export default useSearch;
