import { useCallback, useEffect, useState, useMemo } from 'react';

const GENRE_COLORS = {
  epic: 'bg-red-100 text-red-700',
  elegy: 'bg-amber-100 text-amber-700',
  lyric: 'bg-amber-100 text-amber-700',
  satire: 'bg-orange-100 text-orange-700',
  drama: 'bg-red-100 text-red-700',
  oratory: 'bg-gray-100 text-gray-700',
  rhetoric: 'bg-gray-100 text-gray-700',
  philosophy: 'bg-gray-100 text-gray-700',
  historiography: 'bg-gray-100 text-gray-700',
  epistolary: 'bg-gray-100 text-gray-700',
  pastoral: 'bg-amber-100 text-amber-700',
  theology: 'bg-gray-100 text-gray-600',
  scripture: 'bg-gray-100 text-gray-600',
  christian_poetry: 'bg-amber-100 text-amber-700',
  panegyric: 'bg-red-100 text-red-700',
  technical: 'bg-gray-100 text-gray-600',
  medieval: 'bg-gray-100 text-gray-600',
  unclassified: 'bg-red-50 text-red-500',
};

const ERA_COLORS = {
  'Republic': 'bg-emerald-100 text-emerald-700',
  'Augustan': 'bg-amber-100 text-amber-700',
  'Early Imperial': 'bg-orange-100 text-orange-700',
  'Later Imperial': 'bg-orange-100 text-orange-600',
  'Late Imperial': 'bg-orange-100 text-orange-600',
  'Late Antique': 'bg-gray-100 text-gray-700',
  'Carolingian': 'bg-gray-100 text-gray-600',
  'Early Medieval': 'bg-gray-100 text-gray-600',
  'Medieval': 'bg-gray-100 text-gray-600',
  'Renaissance': 'bg-violet-100 text-violet-700',
  'Modern': 'bg-violet-100 text-violet-600',
  'Unknown': 'bg-red-50 text-red-500',
  'unknown': 'bg-red-50 text-red-500',
};

const METER_COLORS = {
  'hexameter': 'bg-blue-100 text-blue-700',
  'elegiac': 'bg-amber-100 text-amber-700',
  'lyric': 'bg-purple-100 text-purple-700',
  'dramatic': 'bg-red-100 text-red-700',
  'prose': 'bg-gray-100 text-gray-600',
  'mixed': 'bg-orange-100 text-orange-700',
  'unknown': 'bg-red-50 text-red-500',
};

function formatGenre(genre) {
  return genre.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatAuthor(author) {
  return author.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatWork(work) {
  if (!work) return '';
  return work.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatLabel(value) {
  if (!value) return '';
  return value.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function GenreClassificationTab() {
  const [texts, setTexts] = useState([]);
  const [genres, setGenres] = useState([]);
  const [eras, setEras] = useState([]);
  const [meters, setMeters] = useState([]);
  const [counts, setCounts] = useState({});
  const [eraCounts, setEraCounts] = useState({});
  const [meterCounts, setMeterCounts] = useState({});
  const [total, setTotal] = useState(0);
  const [classified, setClassified] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Filters
  const [genreFilter, setGenreFilter] = useState('all');
  const [eraFilter, setEraFilter] = useState('all');
  const [meterFilter, setMeterFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [confidenceFilter, setConfidenceFilter] = useState('all');

  // Which filter section is expanded
  const [activeFilterSection, setActiveFilterSection] = useState('genre');

  // Sorting
  const [sortBy, setSortBy] = useState('author');
  const [sortDir, setSortDir] = useState('asc');

  // Pagination
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;

  // Pending edits: { filename: { genre?, era?, meter? } }
  const [pendingEdits, setPendingEdits] = useState({});
  const [saving, setSaving] = useState(false);

  // New genre input
  const [showNewGenre, setShowNewGenre] = useState(null);
  const [newGenreName, setNewGenreName] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/admin/text-genres', { credentials: 'include' });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || 'Failed to load');
      setTexts(data.texts || []);
      setGenres(data.genres || []);
      setEras(data.eras || []);
      setMeters(data.meters || []);
      setCounts(data.counts || {});
      setEraCounts(data.era_counts || {});
      setMeterCounts(data.meter_counts || {});
      setTotal(data.total || 0);
      setClassified(data.classified || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Filtered + sorted texts
  const filteredTexts = useMemo(() => {
    let result = texts;

    // Apply genre filter
    if (genreFilter !== 'all') {
      result = result.filter(t => {
        const effectiveGenre = pendingEdits[t.filename]?.genre || t.genre;
        return effectiveGenre === genreFilter;
      });
    }

    // Apply era filter
    if (eraFilter !== 'all') {
      result = result.filter(t => {
        const effectiveEra = pendingEdits[t.filename]?.era || t.era || 'unknown';
        return effectiveEra === eraFilter;
      });
    }

    // Apply meter filter
    if (meterFilter !== 'all') {
      result = result.filter(t => {
        const effectiveMeter = pendingEdits[t.filename]?.meter || t.meter || 'unknown';
        return effectiveMeter === meterFilter;
      });
    }

    // Apply confidence filter
    if (confidenceFilter !== 'all') {
      result = result.filter(t => t.confidence === confidenceFilter);
    }

    // Apply search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(t =>
        t.filename.toLowerCase().includes(q) ||
        t.author.toLowerCase().includes(q) ||
        (t.work && t.work.toLowerCase().includes(q))
      );
    }

    // Sort
    result = [...result].sort((a, b) => {
      let va, vb;
      if (sortBy === 'author') {
        va = a.author.toLowerCase();
        vb = b.author.toLowerCase();
      } else if (sortBy === 'work') {
        va = (a.work || '').toLowerCase();
        vb = (b.work || '').toLowerCase();
      } else if (sortBy === 'genre') {
        va = (pendingEdits[a.filename]?.genre || a.genre).toLowerCase();
        vb = (pendingEdits[b.filename]?.genre || b.genre).toLowerCase();
      } else if (sortBy === 'era') {
        va = (pendingEdits[a.filename]?.era || a.era || 'unknown').toLowerCase();
        vb = (pendingEdits[b.filename]?.era || b.era || 'unknown').toLowerCase();
      } else if (sortBy === 'meter') {
        va = (pendingEdits[a.filename]?.meter || a.meter || 'unknown').toLowerCase();
        vb = (pendingEdits[b.filename]?.meter || b.meter || 'unknown').toLowerCase();
      } else if (sortBy === 'confidence') {
        va = a.confidence;
        vb = b.confidence;
      } else {
        va = a.filename.toLowerCase();
        vb = b.filename.toLowerCase();
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  }, [texts, genreFilter, eraFilter, meterFilter, confidenceFilter, searchQuery, sortBy, sortDir, pendingEdits]);

  // Paginated slice
  const pageTexts = useMemo(() => {
    return filteredTexts.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  }, [filteredTexts, page]);

  const totalPages = Math.ceil(filteredTexts.length / PAGE_SIZE);

  const handleFieldChange = (filename, field, value) => {
    if (field === 'genre' && value === '__new__') {
      setShowNewGenre(filename);
      setNewGenreName('');
      return;
    }
    setPendingEdits(prev => {
      const next = { ...prev };
      const orig = texts.find(t => t.filename === filename);
      const origValue = orig ? (orig[field] || '') : '';

      if (!next[filename]) {
        next[filename] = {};
      }

      if (origValue === value) {
        delete next[filename][field];
        // Remove entry if no pending changes remain
        if (Object.keys(next[filename]).length === 0) {
          delete next[filename];
        }
      } else {
        next[filename][field] = value;
      }
      return next;
    });
  };

  const handleAddNewGenre = () => {
    const cleaned = newGenreName.trim().toLowerCase().replace(/\s+/g, '_');
    if (!cleaned) return;
    if (!genres.includes(cleaned)) {
      setGenres(prev => [...prev, cleaned].sort());
    }
    if (showNewGenre) {
      setPendingEdits(prev => ({
        ...prev,
        [showNewGenre]: { ...(prev[showNewGenre] || {}), genre: cleaned }
      }));
    }
    setShowNewGenre(null);
    setNewGenreName('');
  };

  const handleSave = async () => {
    const updates = Object.entries(pendingEdits).map(([filename, fields]) => ({
      filename, ...fields
    }));
    if (updates.length === 0) return;

    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const res = await fetch('/api/admin/text-genres', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates }),
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || 'Failed to save');
      setSuccess(`Saved ${data.updated} classification${data.updated !== 1 ? 's' : ''}.`);
      setPendingEdits({});
      setTimeout(() => setSuccess(''), 4000);
      loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSort = (col) => {
    if (sortBy === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortDir('asc');
    }
    setPage(0);
  };

  const sortArrow = (col) => {
    if (sortBy !== col) return '';
    return sortDir === 'asc' ? ' \u2191' : ' \u2193';
  };

  const pendingCount = Object.keys(pendingEdits).length;

  // All available values for dropdowns (including any from pending edits)
  const allGenres = useMemo(() => {
    const set = new Set(genres);
    Object.values(pendingEdits).forEach(fields => {
      if (fields.genre) set.add(fields.genre);
    });
    return [...set].sort();
  }, [genres, pendingEdits]);

  const allEras = useMemo(() => {
    const set = new Set(eras);
    Object.values(pendingEdits).forEach(fields => {
      if (fields.era) set.add(fields.era);
    });
    return [...set].sort();
  }, [eras, pendingEdits]);

  const allMeters = useMemo(() => {
    const set = new Set(meters);
    Object.values(pendingEdits).forEach(fields => {
      if (fields.meter) set.add(fields.meter);
    });
    return [...set].sort();
  }, [meters, pendingEdits]);

  // Active filter counts
  const activeFilterCount = (genreFilter !== 'all' ? 1 : 0)
    + (eraFilter !== 'all' ? 1 : 0)
    + (meterFilter !== 'all' ? 1 : 0);

  if (loading && texts.length === 0) {
    return <p className="text-gray-500 text-sm">Loading genre data...</p>;
  }

  if (!loading && texts.length === 0 && !error) {
    return (
      <div className="space-y-3">
        <h3 className="font-medium text-gray-900">Genre Classification</h3>
        <p className="text-gray-500 text-sm">
          No genre data found. Run <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">python scripts/classify_text_genres.py</code> to generate initial classifications.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium text-gray-900">Genre Classification</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {classified} of {total} texts classified ({total > 0 ? Math.round((classified / total) * 100) : 0}%)
            {activeFilterCount > 0 && (
              <span className="ml-2 text-red-600">
                {activeFilterCount} filter{activeFilterCount !== 1 ? 's' : ''} active
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {success && <span className="text-xs text-green-600">{success}</span>}
          {pendingCount > 0 && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1.5 text-xs bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
            >
              {saving ? 'Saving...' : `Save ${pendingCount} change${pendingCount !== 1 ? 's' : ''}`}
            </button>
          )}
          {pendingCount > 0 && (
            <button
              onClick={() => setPendingEdits({})}
              className="px-3 py-1.5 text-xs bg-gray-100 text-gray-700 rounded border border-gray-300 hover:bg-gray-200"
            >
              Discard
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <div className="space-y-1">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-red-600 h-2 rounded-full transition-all"
              style={{ width: `${(classified / total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Filter section tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {[
          { key: 'genre', label: 'Genre', filter: genreFilter, count: Object.keys(counts).length },
          { key: 'era', label: 'Era', filter: eraFilter, count: Object.keys(eraCounts).length },
          { key: 'meter', label: 'Meter', filter: meterFilter, count: Object.keys(meterCounts).length },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveFilterSection(tab.key)}
            className={`px-3 py-1.5 text-xs font-medium border-b-2 -mb-px transition-colors ${
              activeFilterSection === tab.key
                ? 'border-red-600 text-red-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
            {tab.filter !== 'all' && (
              <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-red-500" />
            )}
          </button>
        ))}
        {activeFilterCount > 0 && (
          <button
            onClick={() => { setGenreFilter('all'); setEraFilter('all'); setMeterFilter('all'); setPage(0); }}
            className="ml-auto px-2 py-1 text-xs text-gray-500 hover:text-red-600"
          >
            Clear all filters
          </button>
        )}
      </div>

      {/* Genre filter chips */}
      {activeFilterSection === 'genre' && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => { setGenreFilter('all'); setPage(0); }}
            className={`px-2 py-1 text-xs rounded border ${
              genreFilter === 'all'
                ? 'bg-red-700 text-white border-red-700'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            All ({total})
          </button>
          {allGenres.map(g => (
            <button
              key={g}
              onClick={() => { setGenreFilter(g); setPage(0); }}
              className={`px-2 py-1 text-xs rounded border ${
                genreFilter === g
                  ? 'bg-red-700 text-white border-red-700'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {formatGenre(g)} ({counts[g] || 0})
            </button>
          ))}
        </div>
      )}

      {/* Era filter chips */}
      {activeFilterSection === 'era' && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => { setEraFilter('all'); setPage(0); }}
            className={`px-2 py-1 text-xs rounded border ${
              eraFilter === 'all'
                ? 'bg-red-700 text-white border-red-700'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            All ({total})
          </button>
          {allEras.map(e => (
            <button
              key={e}
              onClick={() => { setEraFilter(e); setPage(0); }}
              className={`px-2 py-1 text-xs rounded border ${
                eraFilter === e
                  ? 'bg-red-700 text-white border-red-700'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {formatLabel(e)} ({eraCounts[e] || 0})
            </button>
          ))}
        </div>
      )}

      {/* Meter filter chips */}
      {activeFilterSection === 'meter' && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => { setMeterFilter('all'); setPage(0); }}
            className={`px-2 py-1 text-xs rounded border ${
              meterFilter === 'all'
                ? 'bg-red-700 text-white border-red-700'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            All ({total})
          </button>
          {allMeters.map(m => (
            <button
              key={m}
              onClick={() => { setMeterFilter(m); setPage(0); }}
              className={`px-2 py-1 text-xs rounded border ${
                meterFilter === m
                  ? 'bg-red-700 text-white border-red-700'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {formatLabel(m)} ({meterCounts[m] || 0})
            </button>
          ))}
        </div>
      )}

      {/* Search + confidence filter */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={searchQuery}
          onChange={e => { setSearchQuery(e.target.value); setPage(0); }}
          placeholder="Search by author, work, or filename..."
          className="flex-1 border rounded px-3 py-1.5 text-sm"
        />
        <select
          value={confidenceFilter}
          onChange={e => { setConfidenceFilter(e.target.value); setPage(0); }}
          className="border rounded px-2 py-1.5 text-sm text-gray-700"
        >
          <option value="all">All sources</option>
          <option value="auto">Auto-classified</option>
          <option value="manual">Manual</option>
        </select>
      </div>

      {error && <div className="text-sm text-red-600">{error}</div>}

      {/* Results count */}
      <div className="text-xs text-gray-500">
        Showing {Math.min(filteredTexts.length, PAGE_SIZE)} of {filteredTexts.length} texts
        {searchQuery && ` matching "${searchQuery}"`}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
              <th
                onClick={() => handleSort('author')}
                className="py-2 px-2 text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700 select-none"
              >
                Author{sortArrow('author')}
              </th>
              <th
                onClick={() => handleSort('work')}
                className="py-2 px-2 text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700 select-none"
              >
                Work{sortArrow('work')}
              </th>
              <th
                onClick={() => handleSort('era')}
                className="py-2 px-2 text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700 select-none"
              >
                Era{sortArrow('era')}
              </th>
              <th
                onClick={() => handleSort('meter')}
                className="py-2 px-2 text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700 select-none"
              >
                Meter{sortArrow('meter')}
              </th>
              <th
                onClick={() => handleSort('genre')}
                className="py-2 px-2 text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700 select-none"
              >
                Genre{sortArrow('genre')}
              </th>
              <th
                onClick={() => handleSort('confidence')}
                className="py-2 px-2 text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700 select-none w-20"
              >
                Source{sortArrow('confidence')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {pageTexts.map(t => {
              const edits = pendingEdits[t.filename] || {};
              const isEdited = t.filename in pendingEdits;
              const effectiveGenre = edits.genre || t.genre;
              const effectiveEra = edits.era || t.era || 'unknown';
              const effectiveMeter = edits.meter || t.meter || 'unknown';
              return (
                <tr
                  key={t.filename}
                  className={isEdited ? 'bg-amber-50' : 'hover:bg-gray-50'}
                >
                  <td className="py-1.5 px-2 text-gray-900">
                    <span title={t.filename}>{formatAuthor(t.author)}</span>
                  </td>
                  <td className="py-1.5 px-2 text-gray-600">
                    {formatWork(t.work)}
                  </td>
                  <td className="py-1.5 px-2">
                    <select
                      value={effectiveEra}
                      onChange={e => handleFieldChange(t.filename, 'era', e.target.value)}
                      className={`text-xs rounded px-2 py-0.5 border ${
                        edits.era
                          ? 'border-amber-400 bg-amber-100'
                          : 'border-gray-200 bg-white'
                      }`}
                    >
                      {allEras.map(e => (
                        <option key={e} value={e}>{formatLabel(e)}</option>
                      ))}
                    </select>
                    {!edits.era && (
                      <span className={`ml-1 inline-block px-1.5 py-0.5 text-xs rounded ${ERA_COLORS[effectiveEra] || 'bg-gray-100 text-gray-600'}`}>
                        {formatLabel(effectiveEra)}
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 px-2">
                    <select
                      value={effectiveMeter}
                      onChange={e => handleFieldChange(t.filename, 'meter', e.target.value)}
                      className={`text-xs rounded px-2 py-0.5 border ${
                        edits.meter
                          ? 'border-amber-400 bg-amber-100'
                          : 'border-gray-200 bg-white'
                      }`}
                    >
                      {allMeters.map(m => (
                        <option key={m} value={m}>{formatLabel(m)}</option>
                      ))}
                    </select>
                    {!edits.meter && (
                      <span className={`ml-1 inline-block px-1.5 py-0.5 text-xs rounded ${METER_COLORS[effectiveMeter] || 'bg-gray-100 text-gray-600'}`}>
                        {formatLabel(effectiveMeter)}
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 px-2">
                    <select
                      value={effectiveGenre}
                      onChange={e => handleFieldChange(t.filename, 'genre', e.target.value)}
                      className={`text-xs rounded px-2 py-0.5 border ${
                        edits.genre
                          ? 'border-amber-400 bg-amber-100'
                          : 'border-gray-200 bg-white'
                      }`}
                    >
                      {allGenres.map(g => (
                        <option key={g} value={g}>{formatGenre(g)}</option>
                      ))}
                      <option value="__new__">+ Add new genre...</option>
                    </select>
                    {!edits.genre && (
                      <span className={`ml-2 inline-block px-1.5 py-0.5 text-xs rounded ${GENRE_COLORS[effectiveGenre] || 'bg-gray-100 text-gray-600'}`}>
                        {formatGenre(effectiveGenre)}
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 px-2">
                    <span className={`text-xs ${
                      t.confidence === 'manual' ? 'text-green-600' : 'text-gray-500'
                    }`}>
                      {t.confidence}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-between items-center pt-2">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1 text-xs rounded border border-gray-300 text-gray-700 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-xs text-gray-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="px-3 py-1 text-xs rounded border border-gray-300 text-gray-700 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}

      {/* New genre modal */}
      {showNewGenre && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-sm w-full mx-4 p-5">
            <h4 className="text-sm font-semibold text-gray-900 mb-3">Add New Genre</h4>
            <input
              type="text"
              value={newGenreName}
              onChange={e => setNewGenreName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAddNewGenre()}
              placeholder="e.g. didactic, fable, hymn..."
              className="w-full border rounded px-3 py-2 text-sm mb-3"
              autoFocus
            />
            <p className="text-xs text-gray-500 mb-3">
              Use lowercase, underscores for spaces. This will be added to the genre list.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowNewGenre(null); setNewGenreName(''); }}
                className="px-3 py-1.5 text-xs border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAddNewGenre}
                disabled={!newGenreName.trim()}
                className="px-3 py-1.5 text-xs bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
              >
                Add
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
