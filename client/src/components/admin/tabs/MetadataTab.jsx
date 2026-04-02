import { useState, useEffect } from 'react';
import { LoadingSpinner } from '../../common';

export default function MetadataTab({ authHeaders }) {
  const [corpusTexts, setCorpusTexts] = useState([]);
  const [corpusTextsLoading, setCorpusTextsLoading] = useState(false);
  const [corpusTextsFilter, setCorpusTextsFilter] = useState('');
  const [corpusTextsLang, setCorpusTextsLang] = useState('');
  const [corpusTextsTypeFilter, setCorpusTextsTypeFilter] = useState('');
  const [editingMetadata, setEditingMetadata] = useState(null);
  const [metadataSaving, setMetadataSaving] = useState(false);
  const [metadataMessage, setMetadataMessage] = useState(null);

  const loadCorpusTexts = async () => {
    setCorpusTextsLoading(true);
    try {
      const params = corpusTextsLang ? `?language=${corpusTextsLang}` : '';
      const res = await fetch(`/api/admin/corpus-texts${params}`, { headers: authHeaders });
      const data = await res.json();
      setCorpusTexts(data.texts || []);
    } catch (e) {
      console.error('Failed to load corpus texts:', e);
    }
    setCorpusTextsLoading(false);
  };

  const saveMetadataOverride = async (textId, fields) => {
    setMetadataSaving(true);
    setMetadataMessage(null);
    try {
      const res = await fetch(`/api/admin/text-metadata/${textId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify(fields)
      });
      if (res.ok) {
        setMetadataMessage({ type: 'success', text: `Metadata updated for ${textId}` });
        setEditingMetadata(null);
        loadCorpusTexts();
      } else {
        const err = await res.json();
        setMetadataMessage({ type: 'error', text: err.error || 'Failed to save' });
      }
    } catch (e) {
      setMetadataMessage({ type: 'error', text: e.message });
    }
    setMetadataSaving(false);
  };

  const clearMetadataOverride = async (textId) => {
    if (!window.confirm(`Remove all metadata overrides for ${textId}? It will revert to auto-detected values.`)) return;
    await saveMetadataOverride(textId, {});
  };

  const filteredCorpusTexts = corpusTexts.filter(t => {
    const q = corpusTextsFilter.toLowerCase();
    const matchesText = !q || t.author?.toLowerCase().includes(q) || t.title?.toLowerCase().includes(q) || t.id?.toLowerCase().includes(q);
    const matchesLang = !corpusTextsLang || t.language === corpusTextsLang;
    const matchesType = !corpusTextsTypeFilter || t.text_type === corpusTextsTypeFilter;
    return matchesText && matchesLang && matchesType;
  });

  useEffect(() => {
    loadCorpusTexts();
  }, [corpusTextsLang]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-between items-center gap-3">
        <h3 className="font-medium text-gray-900">Corpus Metadata</h3>
        <span className="text-sm text-gray-500">
          {filteredCorpusTexts.length} of {corpusTexts.length} texts
          {corpusTexts.filter(t => t.override).length > 0 && (
            <span className="ml-2 text-amber-600">
              ({corpusTexts.filter(t => t.override).length} with overrides)
            </span>
          )}
        </span>
      </div>

      <p className="text-sm text-gray-500">
        Edit text classification (poetry/prose), display names, dates, and eras.
        Changes are saved to a tracked overrides file and will persist across deployments.
      </p>

      {metadataMessage && (
        <div className={`text-sm p-2 rounded ${metadataMessage.type === 'success' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
          {metadataMessage.text}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="Filter by author, title, or filename..."
          value={corpusTextsFilter}
          onChange={e => setCorpusTextsFilter(e.target.value)}
          className="flex-1 min-w-[120px] sm:min-w-[200px] px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
        />
        <select
          value={corpusTextsLang}
          onChange={e => { setCorpusTextsLang(e.target.value); }}
          className="px-3 py-2 border border-gray-300 rounded text-sm"
        >
          <option value="">All Languages</option>
          <option value="la">Latin</option>
          <option value="grc">Greek</option>
          <option value="en">English</option>
        </select>
        <select
          value={corpusTextsTypeFilter}
          onChange={e => setCorpusTextsTypeFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded text-sm"
        >
          <option value="">All Types</option>
          <option value="poetry">Poetry</option>
          <option value="prose">Prose</option>
        </select>
      </div>

      {editingMetadata && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-3">
          <h4 className="font-medium text-amber-900">
            Edit Metadata: <span className="font-mono text-sm">{editingMetadata.id}</span>
          </h4>
          <p className="text-xs text-gray-500">
            Leave fields blank to use auto-detected values. Only fill in fields you want to override.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Text Type</label>
              <select
                value={editingMetadata.text_type || ''}
                onChange={e => setEditingMetadata(p => ({...p, text_type: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm"
              >
                <option value="">Auto-detect ({editingMetadata._auto_text_type || 'poetry'})</option>
                <option value="poetry">Poetry</option>
                <option value="prose">Prose</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Display Author</label>
              <input
                type="text"
                value={editingMetadata.display_author || ''}
                onChange={e => setEditingMetadata(p => ({...p, display_author: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm"
                placeholder={editingMetadata._auto_author || 'Auto-detected'}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Display Work Title</label>
              <input
                type="text"
                value={editingMetadata.display_work || ''}
                onChange={e => setEditingMetadata(p => ({...p, display_work: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm"
                placeholder={editingMetadata._auto_work || 'Auto-detected'}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Year</label>
              <input
                type="number"
                value={editingMetadata.year ?? ''}
                onChange={e => setEditingMetadata(p => ({...p, year: e.target.value === '' ? null : parseInt(e.target.value)}))}
                className="w-full border rounded px-2 py-1.5 text-sm"
                placeholder={editingMetadata._auto_year || 'From author_dates.json'}
              />
              <p className="text-xs text-gray-400 mt-0.5">Negative for BCE (e.g., -70 for 70 BCE)</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Era</label>
              <input
                type="text"
                value={editingMetadata.era || ''}
                onChange={e => setEditingMetadata(p => ({...p, era: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm"
                placeholder={editingMetadata._auto_era || 'From author_dates.json'}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
              <input
                type="text"
                value={editingMetadata.notes || ''}
                onChange={e => setEditingMetadata(p => ({...p, notes: e.target.value}))}
                className="w-full border rounded px-2 py-1.5 text-sm"
                placeholder="Optional notes about this override"
              />
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => saveMetadataOverride(editingMetadata.id, {
                text_type: editingMetadata.text_type || undefined,
                display_author: editingMetadata.display_author || undefined,
                display_work: editingMetadata.display_work || undefined,
                year: editingMetadata.year ?? undefined,
                era: editingMetadata.era || undefined,
                notes: editingMetadata.notes || undefined
              })}
              disabled={metadataSaving}
              className="px-3 py-1.5 bg-red-700 text-white rounded text-sm hover:bg-red-800 disabled:opacity-50"
            >
              {metadataSaving ? 'Saving...' : 'Save Override'}
            </button>
            <button
              onClick={() => { setEditingMetadata(null); setMetadataMessage(null); }}
              className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded text-sm hover:bg-gray-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {corpusTextsLoading ? (
        <div className="text-center py-8"><LoadingSpinner /></div>
      ) : (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="max-h-[600px] overflow-y-auto overflow-x-auto">
            <table className="w-full divide-y divide-gray-200 text-sm table-fixed min-w-[640px]">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="w-[14%] px-2 py-2 text-left font-semibold text-gray-700">Author</th>
                  <th className="w-[20%] px-2 py-2 text-left font-semibold text-gray-700">Work</th>
                  <th className="w-[6%] px-2 py-2 text-left font-semibold text-gray-700">Lang</th>
                  <th className="w-[8%] px-2 py-2 text-left font-semibold text-gray-700">Type</th>
                  <th className="w-[8%] px-2 py-2 text-left font-semibold text-gray-700">Year</th>
                  <th className="w-[10%] px-2 py-2 text-left font-semibold text-gray-700">Era</th>
                  <th className="w-[8%] px-2 py-2 text-left font-semibold text-gray-700">Status</th>
                  <th className="w-[10%] px-2 py-2 text-right font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredCorpusTexts.map(text => (
                  <tr key={text.id} className={`hover:bg-gray-50 ${text.has_override ? 'bg-amber-50' : ''}`}>
                    <td className="px-2 py-1.5 truncate" title={text.author}>{text.author}</td>
                    <td className="px-2 py-1.5 truncate" title={text.title}>{text.title}</td>
                    <td className="px-2 py-1.5">{text.language === 'la' ? 'Latin' : text.language === 'grc' ? 'Greek' : 'English'}</td>
                    <td className="px-2 py-1.5">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${text.text_type === 'prose' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                        {text.text_type}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-gray-600">{text.year != null ? (text.year < 0 ? `${Math.abs(text.year)} BCE` : `${text.year} CE`) : '—'}</td>
                    <td className="px-2 py-1.5 text-gray-600 truncate" title={text.era}>{text.era || '—'}</td>
                    <td className="px-2 py-1.5">
                      {text.has_override ? (
                        <span className="text-xs text-amber-600 font-medium">Overridden</span>
                      ) : (
                        <span className="text-xs text-gray-400">Auto</span>
                      )}
                    </td>
                    <td className="px-2 py-1.5 text-right whitespace-nowrap">
                      <button
                        onClick={() => {
                          const ovr = text.override || {};
                          setEditingMetadata({
                            id: text.id,
                            text_type: ovr.text_type || '',
                            display_author: ovr.display_author || '',
                            display_work: ovr.display_work || '',
                            year: ovr.year ?? null,
                            era: ovr.era || '',
                            notes: ovr.notes || '',
                            _auto_text_type: text.override ? undefined : text.text_type,
                            _auto_author: text.author,
                            _auto_work: text.work,
                            _auto_year: text.year?.toString(),
                            _auto_era: text.era
                          });
                          setMetadataMessage(null);
                        }}
                        className="text-red-700 hover:text-red-800 text-xs font-medium mr-2"
                      >
                        Edit
                      </button>
                      {text.has_override && (
                        <button
                          onClick={() => clearMetadataOverride(text.id)}
                          className="text-gray-500 hover:text-red-600 text-xs"
                        >
                          Clear
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {filteredCorpusTexts.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                      {corpusTexts.length === 0 ? 'No texts found in corpus' : 'No texts match the current filters'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
