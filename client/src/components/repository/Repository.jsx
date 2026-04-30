import { useState, useEffect, useCallback } from 'react';
import { LoadingSpinner, Modal } from '../common';

/**
 * Normalize Latin text for matching using platform standard (u/v equivalence).
 * Matches backend/matcher.py normalize_latin()
 */
function normalizeLatin(text) {
  return text.toLowerCase().replace(/v/g, 'u');
}

/**
 * Highlight matched words in text using expanded word forms.
 * Expanded forms include all inflected variants (rege/regem, fato/fata, virum/virorum).
 */
function highlightMatchedWords(text, expandedForms, language = 'la') {
  if (!text || !expandedForms || expandedForms.size === 0) {
    return text;
  }
  
  const isLatin = language === 'la' || language === 'latin';
  const words = text.split(/(\s+|[,.:;!?'"()-])/);
  
  return words.map((part, i) => {
    const w = part.toLowerCase().replace(/[,.:;!?'"()-]/g, '');
    if (!w || w.length < 2) return part;
    
    const wNorm = isLatin ? normalizeLatin(w) : w;
    const isMatch = expandedForms.has(w) || expandedForms.has(wNorm);
    
    if (isMatch && part.trim()) {
      return <span key={i} className="bg-amber-200 text-amber-900 font-medium px-0.5 rounded">{part}</span>;
    }
    return part;
  });
}

const AUTHOR_EXPANSIONS = {
  'verg': 'Vergil', 'vergil': 'Vergil',
  'luc': 'Lucan', 'lucan': 'Lucan',
  'ov': 'Ovid', 'ovid': 'Ovid',
  'quint': 'Quintilian', 'quintilian': 'Quintilian',
  'cic': 'Cicero', 'cicero': 'Cicero',
  'hor': 'Horace', 'horace': 'Horace',
  'sen': 'Seneca', 'seneca': 'Seneca',
  'stat': 'Statius', 'statius': 'Statius',
  'val': 'Valerius Flaccus', 'sil': 'Silius Italicus',
  'prop': 'Propertius', 'tib': 'Tibullus', 'cat': 'Catullus',
  'juv': 'Juvenal', 'pers': 'Persius', 'mart': 'Martial'
};

const WORK_EXPANSIONS = {
  'aen': 'Aeneid', 'aeneid': 'Aeneid',
  'met': 'Metamorphoses', 'georg': 'Georgics', 'ecl': 'Eclogues',
  'inst': 'Institutio Oratoria', 'theb': 'Thebaid',
  'phars': 'Pharsalia', 'pun': 'Punica', 'arg': 'Argonautica',
  'att': 'Letters to Atticus', 'fam': 'Letters to Friends'
};

const AUTHOR_DEFAULT_WORKS = {
  'luc': 'Bellum Civile', 'lucan': 'Bellum Civile'
};

/**
 * Format citation with full author and work names.
 * Expands abbreviated references like "verg. aen. 1.36" -> "Vergil, Aeneid 1.36"
 * Handles authors with single work like "luc. 3.697" -> "Lucan, Bellum Civile 3.697"
 */
function formatCitation(author, work, reference) {
  if (author && work) {
    return `${author}, ${work} ${reference || ''}`.trim();
  }
  
  if (reference) {
    const parts = reference.toLowerCase().split(/[\s.]+/).filter(p => p);
    if (parts.length >= 2) {
      const authorCode = parts[0];
      const expandedAuthor = AUTHOR_EXPANSIONS[authorCode] || authorCode;
      
      const isNumber = /^\d+$/.test(parts[1]);
      if (isNumber && AUTHOR_DEFAULT_WORKS[authorCode]) {
        const expandedWork = AUTHOR_DEFAULT_WORKS[authorCode];
        const lineRef = parts.slice(1).join('.');
        return `${expandedAuthor}, ${expandedWork} ${lineRef}`.trim();
      }
      
      const expandedWork = WORK_EXPANSIONS[parts[1]] || parts[1];
      const lineRef = parts.slice(2).join('.');
      return `${expandedAuthor}, ${expandedWork} ${lineRef}`.trim();
    }
  }
  
  return reference || '';
}

function normalizeRepositoryItem(item, { publicEntry = false } = {}) {
  const source = item.source || {};
  const target = item.target || {};
  const sourceLanguage = source.language || item.source_language || item.language || 'la';
  const targetLanguage = target.language || item.target_language || sourceLanguage;
  const derivedLanguage = item.language || sourceLanguage || targetLanguage || 'la';
  const isPublic = item.is_public ?? item.shared_to_public ?? publicEntry;

  return {
    ...item,
    source,
    target,
    language: derivedLanguage,
    source_locus: source.reference || item.source_locus || '',
    target_locus: target.reference || item.target_locus || '',
    source_text: source.snippet || item.source_text || '',
    target_text: target.snippet || item.target_text || '',
    score: item.score ?? item.tesserae_score ?? 0,
    scholar_score: item.scholar_score ?? item.intertext_score ?? item.user_score ?? 0,
    status: item.status || (isPublic ? 'shared' : 'private'),
    is_public: isPublic,
  };
}

export default function Repository({ user, isAdmin = false }) {
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ language: 'all', status: 'all' });
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [displayLimit, setDisplayLimit] = useState(50);
  const [viewMode, setViewMode] = useState(user ? 'my' : 'public');
  const [publicIntertexts, setPublicIntertexts] = useState([]);
  const [myIntertexts, setMyIntertexts] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [editingScope, setEditingScope] = useState('saved');
  const [itemToDelete, setItemToDelete] = useState(null);
  const [deleteError, setDeleteError] = useState('');
  const [newIntertext, setNewIntertext] = useState({
    source_locus: '',
    source_text: '',
    target_locus: '',
    target_text: '',
    language: 'la',
    notes: '',
    scholar_score: 0,
    is_public: false,
    matched_words: ''
  });
  const [expandedAuthors, setExpandedAuthors] = useState({});
  const [expandedWorks, setExpandedWorks] = useState({});
  const [expandedFormsCache, setExpandedFormsCache] = useState({});

  const loadExpandedFormsForItems = useCallback(async (items) => {
    const uniqueLemmaSets = new Map();
    
    items.forEach(item => {
      const lemmas = item.matched_lemmas || [];
      if (lemmas.length > 0) {
        const cacheKey = [...lemmas].sort().join(',');
        if (!uniqueLemmaSets.has(cacheKey)) {
          uniqueLemmaSets.set(cacheKey, lemmas);
        }
      }
    });
    
    const newCache = { ...expandedFormsCache };
    const keysToFetch = [...uniqueLemmaSets.keys()].filter(k => !newCache[k]);
    
    if (keysToFetch.length === 0) return;
    
    for (const cacheKey of keysToFetch) {
      try {
        const lemmas = uniqueLemmaSets.get(cacheKey);
        const res = await fetch('/api/intertexts/expand-lemmas', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lemmas })
        });
        if (res.ok) {
          const data = await res.json();
          newCache[cacheKey] = new Set(data.forms || []);
        }
      } catch (err) {
        console.error('Failed to expand lemmas:', err);
      }
    }
    
    setExpandedFormsCache(newCache);
  }, [expandedFormsCache]);

  const loadPublicIntertexts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/intertexts', { credentials: 'include' });
      if (!res.ok) {
        throw new Error('Failed to load public repository');
      }
      const data = await res.json();
      const items = (data.intertexts || []).map((item) => normalizeRepositoryItem(item, { publicEntry: true }));
      setPublicIntertexts(items);
      await loadExpandedFormsForItems(items);
    } catch (err) {
      console.error('Failed to load public intertexts:', err);
    } finally {
      setLoading(false);
    }
  }, [loadExpandedFormsForItems]);

  const loadMyIntertexts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/intertexts/my', { credentials: 'include' });
      if (!res.ok) {
        throw new Error('Failed to load repository');
      }
      const data = await res.json();
      const items = (data.intertexts || []).map((item) => normalizeRepositoryItem(item));
      setMyIntertexts(items);
      await loadExpandedFormsForItems(items);
    } catch (err) {
      console.error('Failed to load my intertexts:', err);
    } finally {
      setLoading(false);
    }
  }, [loadExpandedFormsForItems]);

  useEffect(() => {
    loadPublicIntertexts();
  }, [loadPublicIntertexts]);

  useEffect(() => {
    if (user) {
      loadMyIntertexts();
      return;
    }
    setMyIntertexts([]);
    if (viewMode !== 'public') {
      setViewMode('public');
    }
  }, [user, viewMode, loadMyIntertexts]);

  const getFormsForItem = (item) => {
    const lemmas = item.matched_lemmas || [];
    if (lemmas.length === 0) return new Set();
    const cacheKey = [...lemmas].sort().join(',');
    return expandedFormsCache[cacheKey] || new Set(lemmas);
  };

  const handleAddIntertext = async () => {
    if (!Number.isInteger(newIntertext.scholar_score) || newIntertext.scholar_score < 1 || newIntertext.scholar_score > 5) {
      alert('Please select a star rating before adding an intertext.');
      return;
    }
    try {
      const payload = {
        source: {
          text_id: newIntertext.source_locus.trim() || `manual-source-${Date.now()}`,
          reference: newIntertext.source_locus.trim(),
          snippet: newIntertext.source_text.trim(),
          language: newIntertext.language,
        },
        target: {
          text_id: newIntertext.target_locus.trim() || `manual-target-${Date.now()}`,
          reference: newIntertext.target_locus.trim(),
          snippet: newIntertext.target_text.trim(),
          language: newIntertext.language,
        },
        matched_tokens: newIntertext.matched_words
          ? newIntertext.matched_words.split(',').map((w) => w.trim()).filter(Boolean)
          : [],
        intertext_score: newIntertext.scholar_score,
        notes: newIntertext.notes.trim(),
        share_to_public: newIntertext.is_public,
      };

      const res = await fetch('/api/intertexts/my', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Failed to add intertext');
      setShowAddModal(false);
      setNewIntertext({
        source_locus: '', source_text: '', target_locus: '', target_text: '',
        language: 'la', notes: '', scholar_score: 0, is_public: false, matched_words: ''
      });
      loadMyIntertexts();
      loadPublicIntertexts();
    } catch (err) {
      alert('Failed to add intertext: ' + err.message);
    }
  };

  const handleUpdateIntertext = async (id, updates) => {
    try {
      const payload = { ...updates };
      if ('scholar_score' in payload) {
        payload.intertext_score = payload.scholar_score;
        delete payload.scholar_score;
      }
      if ('is_public' in payload) {
        payload.shared_to_public = payload.is_public;
        delete payload.is_public;
      }

      const res = await fetch(`/api/intertexts/my/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Failed to update');
      loadMyIntertexts();
      loadPublicIntertexts();
    } catch (err) {
      alert('Update failed: ' + err.message);
    }
  };

  const handleUpdatePublicIntertext = async (id, updates) => {
    try {
      const payload = {};
      if ('notes' in updates) {
        payload.notes = updates.notes;
      }
      if ('scholar_score' in updates) {
        payload.user_score = updates.scholar_score;
      }

      const res = await fetch(`/api/intertexts/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Failed to update');
      loadMyIntertexts();
      loadPublicIntertexts();
    } catch (err) {
      alert('Update failed: ' + err.message);
    }
  };

  const openEditModal = (item, scope = 'saved') => {
    setEditingScope(scope);
    setEditingItem({
      ...item,
      notes: item.notes || '',
      scholar_score: item.scholar_score || 0,
      is_public: item.is_public !== false,
    });
  };

  const handleSaveEditedIntertext = async () => {
    if (!editingItem) return;
    if (!Number.isInteger(editingItem.scholar_score) || editingItem.scholar_score < 1 || editingItem.scholar_score > 5) {
      alert('Please select a star rating before saving changes.');
      return;
    }

    if (editingScope === 'public') {
      await handleUpdatePublicIntertext(editingItem.id, {
        notes: editingItem.notes || '',
        scholar_score: editingItem.scholar_score,
      });
    } else {
      await handleUpdateIntertext(editingItem.id, {
        notes: editingItem.notes || '',
        scholar_score: editingItem.scholar_score,
        is_public: editingItem.is_public !== false,
      });
    }
    setEditingItem(null);
    setEditingScope('saved');
  };

  const handleDeleteIntertext = async (id) => {
    setDeleteError('');
    try {
      const res = await fetch(`/api/intertexts/my/${id}`, { 
        method: 'DELETE',
        credentials: 'include'
      });
      if (!res.ok) throw new Error('Failed to delete');
      loadMyIntertexts();
      loadPublicIntertexts();
      setItemToDelete(null);
    } catch (err) {
      setDeleteError('Delete failed. You may not have permission.');
    }
  };

  const handleDeletePublicIntertext = async (id) => {
    setDeleteError('');
    try {
      const res = await fetch(`/api/intertexts/${id}`, { 
        method: 'DELETE',
        credentials: 'include'
      });
      if (!res.ok) throw new Error('Failed to delete');
      loadMyIntertexts();
      loadPublicIntertexts();
      setItemToDelete(null);
    } catch (err) {
      setDeleteError('Delete failed. You may not have permission.');
    }
  };

  const isPublicView = viewMode === 'public';
  const repositoryItems = isPublicView ? publicIntertexts : myIntertexts;

  const filteredIntertexts = repositoryItems.filter(item => {
    if (filter.language !== 'all' && item.language !== filter.language) return false;
    if (!isPublicView) {
      if (filter.status === 'shared' && !item.is_public) return false;
      if (filter.status === 'private' && item.is_public) return false;
    }
    return true;
  });

  const sortedIntertexts = [...filteredIntertexts].sort((a, b) => {
    let cmp = 0;
    if (sortBy === 'created_at') {
      cmp = new Date(a.created_at || 0) - new Date(b.created_at || 0);
    } else if (sortBy === 'score') {
      cmp = (a.score || 0) - (b.score || 0);
    } else if (sortBy === 'scholar_score') {
      cmp = (a.scholar_score || 0) - (b.scholar_score || 0);
    }
    return sortOrder === 'desc' ? -cmp : cmp;
  });
  const personalStats = {
    total: myIntertexts.length,
    shared: myIntertexts.filter((item) => item.is_public).length,
  };

  const publicStats = {
    total: publicIntertexts.length,
    withNotes: publicIntertexts.filter((item) => item.notes).length,
  };

  const groupedByWork = (() => {
    const groups = {};
    filteredIntertexts.forEach(item => {
      const lang = item.language || 'la';
      const author = item.source?.author || item.source_author || item.source_locus?.split(',')[0]?.trim() || 'Unknown';
      const work = item.source?.work || item.source_work || item.source_locus?.split(',')[1]?.trim() || 'Unknown';
      
      if (!groups[lang]) groups[lang] = {};
      if (!groups[lang][author]) groups[lang][author] = {};
      if (!groups[lang][author][work]) groups[lang][author][work] = [];
      groups[lang][author][work].push(item);
    });
    return groups;
  })();

  const toggleAuthor = (lang, author) => {
    const key = `${lang}:${author}`;
    setExpandedAuthors(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleWork = (lang, author, work) => {
    const key = `${lang}:${author}:${work}`;
    setExpandedWorks(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const langNames = { la: 'Latin', grc: 'Greek', en: 'English', cross: 'Greek-Latin' };

  const exportCSV = useCallback(() => {
    const headers = ['Source', 'Target', 'Language', 'Match Score', 'Your Rating', 'Visibility', 'Notes', 'Created'];
    const rows = sortedIntertexts.map(item => [
      item.source_locus || '',
      item.target_locus || '',
      item.language || '',
      item.score || '',
      item.scholar_score || '',
      item.is_public ? 'shared' : 'private',
      (item.notes || '').replace(/"/g, '""'),
      item.created_at || ''
    ]);
    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'intertexts.csv';
    a.click();
    URL.revokeObjectURL(url);
  }, [sortedIntertexts]);

  const StarRating = ({ value, onChange, readOnly }) => (
    <div className="flex gap-0.5">
      {[1,2,3,4,5].map(star => (
        <button
          key={star}
          type="button"
          disabled={readOnly}
          onClick={() => onChange && onChange(star)}
          className={`text-lg ${star <= value ? 'text-yellow-500' : 'text-gray-300'} ${!readOnly && 'hover:text-yellow-400 cursor-pointer'}`}
        >
          ★
        </button>
      ))}
    </div>
  );

  if (loading) {
    return <LoadingSpinner text="Loading repository..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            {isPublicView ? 'Public Repository' : 'My Repository'}
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            {isPublicView
              ? 'Browse parallels that users chose to make publicly visible.'
              : 'Review and manage the parallels you have saved with your own comments and ratings'}
          </p>
        </div>
        {isPublicView ? (
          <div className="flex gap-4 text-sm">
            <div className="text-center">
              <div className="text-2xl font-bold text-red-700">{publicStats.total}</div>
              <div className="text-gray-500">Visible</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-amber-600">{publicStats.withNotes}</div>
              <div className="text-gray-500">With Notes</div>
            </div>
          </div>
        ) : (
          <div className="flex gap-4 text-sm">
            <div className="text-center">
              <div className="text-2xl font-bold text-red-700">{personalStats.total}</div>
              <div className="text-gray-500">Saved</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-amber-600">{personalStats.shared}</div>
              <div className="text-gray-500">Shared</div>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-wrap gap-4 items-center justify-between">
          <div className="flex gap-2">
            <button
              onClick={() => setViewMode('public')}
              className={`px-4 py-2 rounded text-sm ${viewMode === 'public' ? 'bg-red-700 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
            >
              Public Repository
            </button>
            {user && (
              <>
                <button
                  onClick={() => setViewMode('my')}
                  className={`px-4 py-2 rounded text-sm ${viewMode === 'my' ? 'bg-red-700 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                >
                  My Saved
                </button>
                <button
                  onClick={() => setViewMode('byWork')}
                  className={`px-4 py-2 rounded text-sm ${viewMode === 'byWork' ? 'bg-red-700 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                >
                  By Work
                </button>
              </>
            )}
          </div>
          <div className="flex gap-3 flex-wrap">
            <select
              value={filter.language}
              onChange={e => setFilter({ ...filter, language: e.target.value })}
              className="border rounded px-3 py-2 text-sm"
            >
              <option value="all">All Languages</option>
              <option value="la">Latin</option>
              <option value="grc">Greek</option>
              <option value="en">English</option>
              <option value="cross">Greek-Latin</option>
            </select>
            {!isPublicView && (
              <select
                value={filter.status}
                onChange={e => setFilter({ ...filter, status: e.target.value })}
                className="border rounded px-3 py-2 text-sm"
              >
                <option value="all">All Entries</option>
                <option value="private">Private Only</option>
                <option value="shared">Shared Publicly</option>
              </select>
            )}
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              className="border rounded px-3 py-2 text-sm"
            >
              <option value="created_at">Date</option>
              <option value="score">Match Score</option>
              <option value="scholar_score">Your Rating</option>
            </select>
            <button
              onClick={exportCSV}
              className="px-3 py-2 bg-gray-100 text-gray-700 border rounded hover:bg-gray-200 text-sm"
            >
              Export CSV
            </button>
            {!user && (
              <button
                onClick={() => window.dispatchEvent(new CustomEvent('open-public-auth-modal', { detail: { mode: 'login' } }))}
                className="px-3 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm"
              >
                Sign In To Save
              </button>
            )}
            {user && !isPublicView && (
              <button
                onClick={() => setShowAddModal(true)}
                className="px-3 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm"
              >
                + Add Intertext
              </button>
            )}
          </div>
        </div>
      </div>

      {filteredIntertexts.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          {isPublicView
            ? 'No public intertexts found matching your filters.'
            : viewMode === 'my'
            ? "You haven't saved any intertexts yet. Run a search and click 'Register' to save a parallel with your notes and rating."
            : "No intertexts found matching your filters."
          }
        </div>
      ) : viewMode === 'byWork' ? (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="p-4 border-b bg-gray-50">
            <span className="text-sm text-gray-600">
              {filteredIntertexts.length} intertexts organized by source work
            </span>
          </div>
          <div className="divide-y divide-gray-100">
            {Object.entries(groupedByWork).sort().map(([lang, authors]) => (
              <div key={lang} className="border-b">
                <div className="px-4 py-2 bg-gray-100 font-medium text-sm text-gray-700">
                  {langNames[lang] || lang} ({Object.values(authors).flatMap(w => Object.values(w)).flat().length})
                </div>
                {Object.entries(authors).sort().map(([author, works]) => {
                  const authorKey = `${lang}:${author}`;
                  const isAuthorExpanded = expandedAuthors[authorKey];
                  const authorCount = Object.values(works).flat().length;
                  return (
                    <div key={author} className="border-l-4 border-gray-200">
                      <button
                        onClick={() => toggleAuthor(lang, author)}
                        className="w-full text-left px-6 py-2 hover:bg-gray-50 flex items-center justify-between"
                      >
                        <span className="font-medium text-gray-800">{author}</span>
                        <span className="text-xs text-gray-500">
                          {authorCount} {authorCount === 1 ? 'intertext' : 'intertexts'} {isAuthorExpanded ? '▼' : '▶'}
                        </span>
                      </button>
                      {isAuthorExpanded && Object.entries(works).sort().map(([work, items]) => {
                        const workKey = `${lang}:${author}:${work}`;
                        const isWorkExpanded = expandedWorks[workKey];
                        return (
                          <div key={work} className="border-l-4 border-gray-100 ml-4">
                            <button
                              onClick={() => toggleWork(lang, author, work)}
                              className="w-full text-left px-6 py-2 hover:bg-gray-50 flex items-center justify-between text-sm"
                            >
                              <span className="text-gray-700 italic">{work}</span>
                              <span className="text-xs text-gray-500">
                                {items.length} {isWorkExpanded ? '▼' : '▶'}
                              </span>
                            </button>
                            {isWorkExpanded && (
                              <div className="ml-4 border-l border-gray-200">
                                {items.map((item, i) => (
                                  <div key={item.id || i} className="px-4 py-3 bg-white hover:bg-gray-50 border-b border-gray-100">
                                    <div className="flex items-start justify-between gap-2 mb-2">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <span className={`text-xs px-2 py-0.5 rounded ${item.is_public ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'}`}>
                                          {item.is_public ? 'shared' : 'private'}
                                        </span>
                                        <span className="text-xs text-gray-400">
                                          Score: {item.score?.toFixed?.(2) || item.score || '-'}
                                        </span>
                                        {item.scholar_score > 0 && (
                                          <span className="text-xs text-amber-600">{'★'.repeat(item.scholar_score)}</span>
                                        )}
                                        {(item.submitter?.name || item.submitter?.orcid || item.contributor_name) && (
                                          <span className="text-xs text-gray-500 border-l border-gray-300 pl-2 ml-1">
                                            Added by {item.submitter?.name && item.submitter?.orcid 
                                              ? `${item.submitter.name}`
                                              : item.submitter?.name || item.contributor_name || 'Anonymous'}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                                      <div className="bg-gray-50 p-2 rounded">
                                        <div className="text-xs text-red-600 font-medium mb-1">{formatCitation(item.source?.author, item.source?.work, item.source?.reference || item.source_locus)}</div>
                                        <div className="text-gray-700 max-h-32 overflow-y-auto">{highlightMatchedWords(item.source_text || item.source?.snippet || '', getFormsForItem(item), item.language || item.source?.language || 'la')}</div>
                                      </div>
                                      <div className="bg-gray-50 p-2 rounded">
                                        <div className="text-xs text-amber-600 font-medium mb-1">{formatCitation(item.target?.author, item.target?.work, item.target?.reference || item.target_locus)}</div>
                                        <div className="text-gray-700 max-h-32 overflow-y-auto">{highlightMatchedWords(item.target_text || item.target?.snippet || '', getFormsForItem(item), item.language || item.target?.language || 'la')}</div>
                                      </div>
                                    </div>
                                    {item.notes && <div className="mt-2 text-xs text-gray-500 italic">{item.notes}</div>}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="divide-y divide-gray-200">
            {sortedIntertexts.slice(0, displayLimit).map((item, i) => (
              <div key={item.id || i} className="p-4 hover:bg-gray-50">
                {(() => {
                  const canDeletePublicItem = isPublicView && user && (isAdmin || (item.submitter_id && String(item.submitter_id) === String(user.id)));
                  const canEditPublicItem = canDeletePublicItem;
                  const canEditSavedItem = viewMode === 'my' && user;
                  return (
                <div className="flex items-start justify-between gap-4 mb-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className={`text-xs px-2 py-0.5 rounded ${item.is_public ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'}`}>
                        {item.is_public ? 'shared' : 'private'}
                      </span>
                      <span className="text-xs text-gray-500">
                        {(() => {
                          const lang = item.language || item.source?.language || 'en';
                          if (lang === 'la') return 'Latin';
                          if (lang === 'grc') return 'Greek';
                          if (lang === 'cross') return 'Greek-Latin';
                          return 'English';
                        })()}
                      </span>
                      {item.score && (
                        <span className="text-xs text-gray-500">
                          Match: {item.score.toFixed(3)}
                        </span>
                      )}
                      {item.scholar_score > 0 && (
                        <StarRating value={item.scholar_score} readOnly />
                      )}
                      {(item.submitter?.name || item.submitter?.orcid || item.contributor_name) && (
                        <span className="text-xs text-gray-500 border-l border-gray-300 pl-2 ml-1 flex items-center">
                          Added by {item.submitter?.name && item.submitter?.orcid 
                            ? `${item.submitter.name}`
                            : item.submitter?.name || item.contributor_name || 'Anonymous'}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {item.created_at && (
                      <span className="text-xs text-gray-400">
                        {new Date(item.created_at).toLocaleDateString()}
                      </span>
                    )}
                    {isPublicView && (
                    <button
                      onClick={async () => {
                        try {
                          const newStatus = item.status === 'flagged' ? 'confirmed' : 'flagged';
                          const res = await fetch(`/api/intertexts/${item.id}`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'include',
                            body: JSON.stringify({ status: newStatus })
                          });
                          if (res.ok) loadPublicIntertexts();
                        } catch (err) { console.error('Flag failed:', err); }
                      }}
                      className={`text-xs px-2 py-1 rounded ${
                        item.status === 'flagged'
                          ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                          : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                      }`}
                      title={item.status === 'flagged' ? 'Remove flag' : 'Flag as problematic'}
                    >
                      {item.status === 'flagged' ? '⚑ Unflag' : '⚐ Flag'}
                    </button>
                    )}
                    {canEditSavedItem && (
                      <div className="flex gap-1">
                        <button
                          onClick={() => openEditModal(item, 'saved')}
                          className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => { setDeleteError(''); setItemToDelete({ id: item.id, type: 'saved' }); }}
                          className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                    {canEditPublicItem && (
                      <button
                        onClick={() => openEditModal(item, 'public')}
                        className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200"
                      >
                        Edit
                      </button>
                    )}
                    {canDeletePublicItem && (
                      <button
                        onClick={() => { setDeleteError(''); setItemToDelete({ id: item.id, type: 'public' }); }}
                        className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </div>
                  );
                })()}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="bg-gray-50 p-3 rounded">
                    <div className="text-xs text-red-600 mb-1 font-medium">
                      {formatCitation(item.source?.author, item.source?.work, item.source?.reference || item.source_locus)}
                    </div>
                    <div className="text-sm text-gray-700 max-h-32 overflow-y-auto">
                      {highlightMatchedWords(
                        item.source?.snippet || item.source_text || '',
                        getFormsForItem(item),
                        item.language || item.source?.language || 'la'
                      )}
                    </div>
                  </div>
                  <div className="bg-gray-50 p-3 rounded">
                    <div className="text-xs text-amber-600 mb-1 font-medium">
                      {formatCitation(item.target?.author, item.target?.work, item.target?.reference || item.target_locus)}
                    </div>
                    <div className="text-sm text-gray-700 max-h-32 overflow-y-auto">
                      {highlightMatchedWords(
                        item.target?.snippet || item.target_text || '',
                        getFormsForItem(item),
                        item.language || item.target?.language || 'la'
                      )}
                    </div>
                  </div>
                </div>
                {item.notes && (
                  <div className="mt-2 text-sm text-gray-600 italic">
                    Note: {item.notes}
                  </div>
                )}
              </div>
            ))}
          </div>
          {sortedIntertexts.length > displayLimit && (
            <div className="px-4 py-3 bg-gray-50 text-center">
              <button
                onClick={() => setDisplayLimit(displayLimit + 50)}
                className="text-amber-600 hover:text-amber-800 text-sm"
              >
                Show more ({displayLimit} of {sortedIntertexts.length})
              </button>
            </div>
          )}
        </div>
      )}

      {showAddModal && (
        <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)} title="Add Manual Intertext">
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Source Locus</label>
                <input
                  type="text"
                  value={newIntertext.source_locus}
                  onChange={e => setNewIntertext({...newIntertext, source_locus: e.target.value})}
                  placeholder="e.g., Vergil, Aeneid 1.1"
                  className="w-full border rounded px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Target Locus</label>
                <input
                  type="text"
                  value={newIntertext.target_locus}
                  onChange={e => setNewIntertext({...newIntertext, target_locus: e.target.value})}
                  placeholder="e.g., Homer, Iliad 1.1"
                  className="w-full border rounded px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Source Text</label>
              <textarea
                value={newIntertext.source_text}
                onChange={e => setNewIntertext({...newIntertext, source_text: e.target.value})}
                rows={2}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Target Text</label>
              <textarea
                value={newIntertext.target_text}
                onChange={e => setNewIntertext({...newIntertext, target_text: e.target.value})}
                rows={2}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
                <select
                  value={newIntertext.language}
                  onChange={e => setNewIntertext({...newIntertext, language: e.target.value})}
                  className="w-full border rounded px-3 py-2 text-sm"
                >
                  <option value="la">Latin</option>
                  <option value="grc">Greek</option>
                  <option value="en">English</option>
                  <option value="cross">Greek-Latin</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Your Rating</label>
                <StarRating 
                  value={newIntertext.scholar_score} 
                  onChange={score => setNewIntertext({...newIntertext, scholar_score: score})}
                />
                <p className="text-xs text-gray-400 mt-1">
                  {newIntertext.scholar_score > 0 ? `${newIntertext.scholar_score}/5 selected` : 'Required'}
                </p>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Matched Words (comma-separated)</label>
              <input
                type="text"
                value={newIntertext.matched_words || ''}
                onChange={e => setNewIntertext({...newIntertext, matched_words: e.target.value})}
                placeholder="e.g., arma, virum, fato"
                className="w-full border rounded px-3 py-2 text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">Words to highlight in both passages</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Notes <span className="text-gray-400">({(newIntertext.notes || '').length}/500)</span>
              </label>
              <textarea
                value={newIntertext.notes}
                onChange={e => {
                  if (e.target.value.length <= 500) {
                    setNewIntertext({...newIntertext, notes: e.target.value});
                  }
                }}
                placeholder="Scholarly commentary or observations..."
                rows={2}
                maxLength={500}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_public"
                checked={newIntertext.is_public}
                onChange={e => setNewIntertext({...newIntertext, is_public: e.target.checked})}
              />
              <label htmlFor="is_public" className="text-sm text-gray-700">Share this intertext publicly</label>
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleAddIntertext}
                disabled={!newIntertext.source_locus || !newIntertext.target_locus || newIntertext.scholar_score < 1}
                className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
              >
                Add Intertext
              </button>
            </div>
          </div>
        </Modal>
      )}

      {editingItem && (
        <Modal isOpen={Boolean(editingItem)} onClose={() => {
          setEditingItem(null);
          setEditingScope('saved');
        }} title="Edit Intertext">
          <div className="space-y-4">
            <div className="bg-gray-50 p-4 rounded">
              <div className="text-sm text-gray-500 mb-1">Source</div>
              <div className="font-medium text-red-700">{editingItem.source?.reference || editingItem.source_locus}</div>
              <div className="text-sm text-gray-700 mt-1">
                {(editingItem.source?.snippet || editingItem.source_text || '').substring(0, 140)}
                {(editingItem.source?.snippet || editingItem.source_text || '').length > 140 ? '...' : ''}
              </div>
              <div className="text-sm text-gray-500 mt-3 mb-1">Target</div>
              <div className="font-medium text-amber-600">{editingItem.target?.reference || editingItem.target_locus}</div>
              <div className="text-sm text-gray-700 mt-1">
                {(editingItem.target?.snippet || editingItem.target_text || '').substring(0, 140)}
                {(editingItem.target?.snippet || editingItem.target_text || '').length > 140 ? '...' : ''}
              </div>
            </div>
            {editingScope === 'saved' && (
              <div>
                <div className="text-sm text-gray-600 mb-2">Visibility:</div>
                <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
                  <button
                    type="button"
                    onClick={() => setEditingItem({ ...editingItem, is_public: false })}
                    className={`px-3 py-1.5 text-sm rounded ${
                      editingItem.is_public === false
                        ? 'bg-white text-gray-900 shadow-sm'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    Private
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingItem({ ...editingItem, is_public: true })}
                    className={`px-3 py-1.5 text-sm rounded ${
                      editingItem.is_public !== false
                        ? 'bg-white text-red-700 shadow-sm'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    Make Public
                  </button>
                </div>
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Your Rating</label>
              <StarRating 
                value={editingItem.scholar_score || 0} 
                onChange={score => {
                  setEditingItem({...editingItem, scholar_score: score});
                }}
              />
              <p className="text-xs text-gray-400 mt-1">
                {editingItem.scholar_score > 0 ? `${editingItem.scholar_score}/5 selected` : 'Required'}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Notes <span className="text-gray-400">({(editingItem.notes || '').length}/500)</span>
              </label>
              <textarea
                value={editingItem.notes || ''}
                onChange={e => {
                  if (e.target.value.length <= 500) {
                    setEditingItem({...editingItem, notes: e.target.value});
                  }
                }}
                rows={3}
                maxLength={500}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <button
                onClick={() => {
                  setEditingItem(null);
                  setEditingScope('saved');
                }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEditedIntertext}
                disabled={editingItem.scholar_score < 1}
                className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save Changes
              </button>
            </div>
          </div>
        </Modal>
      )}

      {itemToDelete && (
        <Modal isOpen={!!itemToDelete} onClose={() => setItemToDelete(null)} title="Confirm Deletion">
          <div className="p-4">
            <p className="text-gray-700">Are you sure you want to delete this intertext? This action cannot be undone.</p>
            {deleteError && <div className="mt-4 text-sm text-red-600 bg-red-50 p-2 rounded">{deleteError}</div>}
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setItemToDelete(null)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => itemToDelete.type === 'public' ? handleDeletePublicIntertext(itemToDelete.id) : handleDeleteIntertext(itemToDelete.id)}
                className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
