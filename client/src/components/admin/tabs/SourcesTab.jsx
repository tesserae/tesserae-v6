import { useState, useEffect } from 'react';
import { LoadingSpinner } from '../../common';
import { fetchAdminSources, updateAdminSource, deleteAdminSource, addAdminSource } from '../../../utils/api';

export default function SourcesTab({ authHeaders }) {
  const [sourcesData, setSourcesData] = useState([]);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [sourcesFilter, setSourcesFilter] = useState('');
  const [editingSource, setEditingSource] = useState(null);
  const [addingSource, setAddingSource] = useState(false);
  const [newSource, setNewSource] = useState({ author: '', work: '', e_source: '', e_source_url: '', print_source: '', added_by: '' });
  const [sourcesSaving, setSourcesSaving] = useState(false);
  const [sourcesMessage, setSourcesMessage] = useState(null);

  const loadSources = async () => {
    setSourcesLoading(true);
    try {
      const res = await fetchAdminSources(authHeaders);
      const data = res.data;
      setSourcesData(data.sources || []);
    } catch (e) {
      console.error('Failed to load sources:', e);
    }
    setSourcesLoading(false);
  };

  const saveSource = async (id, updates) => {
    setSourcesSaving(true);
    setSourcesMessage(null);
    try {
      const res = await updateAdminSource(authHeaders, id, updates);
      if (res.ok) {
        setSourcesMessage({ type: 'success', text: 'Source updated successfully' });
        setEditingSource(null);
        loadSources();
      } else {
        const err = res.data;
        setSourcesMessage({ type: 'error', text: err.error || 'Failed to update' });
      }
    } catch (e) {
      setSourcesMessage({ type: 'error', text: e.message });
    }
    setSourcesSaving(false);
  };

  const deleteSource = async (id, author, work) => {
    if (!window.confirm(`Delete source entry for "${author} - ${work}"?`)) return;
    try {
      const res = await deleteAdminSource(authHeaders, id);
      if (res.ok) {
        setSourcesMessage({ type: 'success', text: 'Source deleted' });
        loadSources();
      }
    } catch (e) {
      setSourcesMessage({ type: 'error', text: e.message });
    }
  };

  const addNewSource = async () => {
    if (!newSource.author && !newSource.work) return;
    setSourcesSaving(true);
    setSourcesMessage(null);
    try {
      const res = await addAdminSource(authHeaders, newSource);
      if (res.ok) {
        setSourcesMessage({ type: 'success', text: 'Source added successfully' });
        setNewSource({ author: '', work: '', e_source: '', e_source_url: '', print_source: '', added_by: '' });
        setAddingSource(false);
        loadSources();
      } else {
        const err = res.data;
        setSourcesMessage({ type: 'error', text: err.error || 'Failed to add' });
      }
    } catch (e) {
      setSourcesMessage({ type: 'error', text: e.message });
    }
    setSourcesSaving(false);
  };

  const filteredSources = sourcesData.filter(s => {
    if (!sourcesFilter.trim()) return true;
    const q = sourcesFilter.toLowerCase();
    return (s.author || '').toLowerCase().includes(q) ||
           (s.work || '').toLowerCase().includes(q) ||
           (s.e_source || '').toLowerCase().includes(q);
  });

  useEffect(() => {
    loadSources();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-between items-center gap-3">
        <h3 className="font-medium text-gray-900">Text Sources (Sources Page)</h3>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{filteredSources.length} of {sourcesData.length} entries</span>
          <button
            onClick={() => { setAddingSource(true); setSourcesMessage(null); }}
            className="px-3 py-1.5 bg-red-700 text-white rounded text-sm hover:bg-red-800"
          >
            + Add Source
          </button>
        </div>
      </div>

      {sourcesMessage && (
        <div className={`text-sm p-2 rounded ${sourcesMessage.type === 'success' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
          {sourcesMessage.text}
        </div>
      )}

      <input
        type="text"
        placeholder="Filter by author, work, or source..."
        value={sourcesFilter}
        onChange={e => setSourcesFilter(e.target.value)}
        className="w-full sm:w-80 px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
      />

      {addingSource && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-3">
          <h4 className="font-medium text-amber-900">Add New Source Entry</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Author</label>
              <input type="text" value={newSource.author} onChange={e => setNewSource(p => ({...p, author: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="e.g., Vergil" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Work</label>
              <input type="text" value={newSource.work} onChange={e => setNewSource(p => ({...p, work: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="e.g., Aeneid" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">e-Source</label>
              <input type="text" value={newSource.e_source} onChange={e => setNewSource(p => ({...p, e_source: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="e.g., The Latin Library" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">e-Source URL</label>
              <input type="text" value={newSource.e_source_url} onChange={e => setNewSource(p => ({...p, e_source_url: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="https://..." />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Print Source (citation)</label>
              <input type="text" value={newSource.print_source} onChange={e => setNewSource(p => ({...p, print_source: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="e.g., R. Mynors, OCT, 1969" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Added by</label>
              <input type="text" value={newSource.added_by} onChange={e => setNewSource(p => ({...p, added_by: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="Name" />
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={addNewSource} disabled={sourcesSaving || (!newSource.author && !newSource.work)} className="px-3 py-1.5 bg-red-700 text-white rounded text-sm hover:bg-red-800 disabled:opacity-50">
              {sourcesSaving ? 'Adding...' : 'Add'}
            </button>
            <button onClick={() => setAddingSource(false)} className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded text-sm hover:bg-gray-300">
              Cancel
            </button>
          </div>
        </div>
      )}

      {sourcesLoading ? (
        <div className="text-center py-8"><LoadingSpinner /></div>
      ) : (
        <div className="border border-gray-200 rounded-lg overflow-hidden overflow-x-auto">
          <table className="w-full divide-y divide-gray-200 text-sm table-fixed min-w-[640px]">
            <thead className="bg-gray-50">
              <tr>
                <th className="w-[14%] px-2 py-2 text-left font-semibold text-gray-700">Author</th>
                <th className="w-[16%] px-2 py-2 text-left font-semibold text-gray-700">Work</th>
                <th className="w-[10%] px-2 py-2 text-left font-semibold text-gray-700">e-Source</th>
                <th className="w-[30%] px-2 py-2 text-left font-semibold text-gray-700">Print Source</th>
                <th className="w-[14%] px-2 py-2 text-left font-semibold text-gray-700">Added by</th>
                <th className="w-[16%] px-2 py-2 text-right font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredSources.map(entry => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  {editingSource && editingSource.id === entry.id ? (
                    <>
                      <td className="px-2 py-1.5"><input type="text" value={editingSource.author} onChange={e => setEditingSource(p => ({...p, author: e.target.value}))} className="w-full border rounded px-2 py-1 text-sm" /></td>
                      <td className="px-2 py-1.5"><input type="text" value={editingSource.work} onChange={e => setEditingSource(p => ({...p, work: e.target.value}))} className="w-full border rounded px-2 py-1 text-sm" /></td>
                      <td className="px-2 py-1.5">
                        <input type="text" value={editingSource.e_source} onChange={e => setEditingSource(p => ({...p, e_source: e.target.value}))} className="w-full border rounded px-2 py-1 text-sm mb-1" placeholder="Source name" />
                        <input type="text" value={editingSource.e_source_url} onChange={e => setEditingSource(p => ({...p, e_source_url: e.target.value}))} className="w-full border rounded px-2 py-1 text-xs text-gray-500" placeholder="URL" />
                      </td>
                      <td className="px-2 py-1.5"><input type="text" value={editingSource.print_source} onChange={e => setEditingSource(p => ({...p, print_source: e.target.value}))} className="w-full border rounded px-2 py-1 text-sm" /></td>
                      <td className="px-2 py-1.5"><input type="text" value={editingSource.added_by} onChange={e => setEditingSource(p => ({...p, added_by: e.target.value}))} className="w-full border rounded px-2 py-1 text-sm" /></td>
                      <td className="px-2 py-1.5 text-right whitespace-nowrap">
                        <button onClick={() => saveSource(editingSource.id, editingSource)} disabled={sourcesSaving} className="text-red-700 hover:text-red-900 text-xs font-medium mr-2">
                          {sourcesSaving ? 'Saving...' : 'Save'}
                        </button>
                        <button onClick={() => setEditingSource(null)} className="text-gray-500 hover:text-gray-700 text-xs">
                          Cancel
                        </button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-2 py-2 text-gray-900 font-medium truncate" title={entry.author}>{entry.author}</td>
                      <td className="px-2 py-2 text-gray-700 truncate" title={entry.work}>{entry.work}</td>
                      <td className="px-2 py-2 truncate">
                        {entry.e_source_url ? (
                          <a href={entry.e_source_url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline text-xs">{entry.e_source}</a>
                        ) : (
                          <span className="text-gray-700 text-xs">{entry.e_source}</span>
                        )}
                      </td>
                      <td className="px-2 py-2 text-gray-600 text-xs truncate" title={entry.print_source}>{entry.print_source}</td>
                      <td className="px-2 py-2 text-gray-600 text-xs truncate" title={entry.added_by}>{entry.added_by}</td>
                      <td className="px-2 py-2 text-right whitespace-nowrap">
                        <button onClick={() => setEditingSource({...entry})} className="text-blue-600 hover:text-blue-800 text-xs font-medium mr-2">
                          Edit
                        </button>
                        <button onClick={() => deleteSource(entry.id, entry.author, entry.work)} className="text-red-600 hover:text-red-800 text-xs font-medium">
                          Delete
                        </button>
                      </td>
                    </>
                  )}
                </tr>
              ))}
              {filteredSources.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">No entries found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
