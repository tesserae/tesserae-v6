import { useCallback, useEffect, useState } from 'react';

export default function DictionaryReviewTab() {
  const [entries, setEntries] = useState([]);
  const [counts, setCounts] = useState({ pending: 0, accepted: 0, rejected: 0, skipped: 0 });
  const [statusFilter, setStatusFilter] = useState('pending');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;

  const loadEntries = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(
        `/api/admin/dictionary-review?status=${statusFilter}&limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`,
        { credentials: 'include' }
      );
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || 'Failed to load');
      setEntries(data.entries || []);
      setCounts(data.counts || { pending: 0, accepted: 0, rejected: 0 });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const updateEntry = async (id, status) => {
    try {
      const res = await fetch(`/api/admin/dictionary-review/${id}`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || 'Failed to update');
      setEntries(prev => prev.filter(e => e.id !== id));
      setCounts(prev => {
        const next = { ...prev };
        const oldStatus = entries.find(e => e.id === id)?.status || 'pending';
        if (oldStatus in next) next[oldStatus] = Math.max(0, next[oldStatus] - 1);
        if (status in next) next[status] = (next[status] || 0) + 1;
        return next;
      });
    } catch (err) {
      setError(err.message);
    }
  };

  const [reloadMsg, setReloadMsg] = useState('');

  const reloadDictionary = async () => {
    setReloadMsg('Reloading...');
    try {
      const res = await fetch('/api/admin/dictionary-review/reload', {
        method: 'POST',
        credentials: 'include',
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || 'Reload failed');
      setReloadMsg(`Loaded ${data.loaded} entries into dictionary`);
      setTimeout(() => setReloadMsg(''), 4000);
    } catch (err) {
      setReloadMsg(`Error: ${err.message}`);
    }
  };

  const exportAccepted = async () => {
    try {
      const res = await fetch('/api/admin/dictionary-review/export', { credentials: 'include' });
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'accepted_dictionary_entries.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  };

  const total = counts.pending + counts.accepted + counts.rejected + counts.skipped;
  const reviewed = counts.accepted + counts.rejected;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium text-gray-900">Dictionary Review</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Greek-Latin synonym candidates from Perseus Dynamic Lexicon
          </p>
        </div>
        <div className="flex items-center gap-2">
          {reloadMsg && <span className="text-xs text-gray-500">{reloadMsg}</span>}
          {counts.accepted > 0 && (
            <>
              <button
                onClick={reloadDictionary}
                className="px-3 py-1.5 text-xs bg-green-50 text-green-700 rounded border border-green-300 hover:bg-green-100"
              >
                Load into search
              </button>
              <button
                onClick={exportAccepted}
                className="px-3 py-1.5 text-xs bg-gray-100 text-gray-700 rounded border border-gray-300 hover:bg-gray-200"
              >
                Export CSV ({counts.accepted})
              </button>
            </>
          )}
        </div>
      </div>

      {total > 0 && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-gray-500">
            <span>{reviewed} of {total} reviewed</span>
            <span>{Math.round((reviewed / total) * 100)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div className="flex h-2.5 rounded-full overflow-hidden">
              <div
                className="bg-green-500"
                style={{ width: `${(counts.accepted / total) * 100}%` }}
              />
              <div
                className="bg-red-400"
                style={{ width: `${(counts.rejected / total) * 100}%` }}
              />
              <div
                className="bg-yellow-300"
                style={{ width: `${(counts.skipped / total) * 100}%` }}
              />
            </div>
          </div>
          <div className="flex gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
              {counts.accepted} accepted
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
              {counts.rejected} rejected
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-yellow-300 inline-block" />
              {counts.skipped} skipped
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-gray-300 inline-block" />
              {counts.pending} pending
            </span>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {['pending', 'accepted', 'rejected', 'skipped', 'all'].map(s => (
          <button
            key={s}
            onClick={() => { setStatusFilter(s); setPage(0); }}
            className={`px-3 py-1 text-xs rounded border ${
              statusFilter === s
                ? 'bg-red-700 text-white border-red-700'
                : 'bg-white text-gray-700 border-gray-300'
            }`}
          >
            {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            {s !== 'all' && counts[s] != null ? ` (${counts[s]})` : ''}
          </button>
        ))}
      </div>

      {error && <div className="text-sm text-red-600">{error}</div>}

      {loading ? (
        <p className="text-gray-500 text-sm">Loading...</p>
      ) : entries.length === 0 ? (
        <p className="text-gray-500 text-sm">
          {statusFilter === 'pending' ? 'No pending entries to review.' : 'No entries for this filter.'}
        </p>
      ) : (
        <div className="divide-y">
          {entries.map(entry => (
            <div key={entry.id} className="py-3 flex items-center justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="font-medium text-gray-900">{entry.greek_lemma}</span>
                  <span className="text-gray-400">↔</span>
                  <span className="font-medium text-gray-900">{entry.latin_lemma}</span>
                  {entry.shared_senses && (
                    <span className="text-sm text-gray-500">({entry.shared_senses})</span>
                  )}
                </div>
                <div className="flex items-center gap-3 mt-0.5">
                  {entry.greek_pos && (
                    <span className="text-xs text-gray-400">{entry.greek_pos}/{entry.latin_pos}</span>
                  )}
                  <span className="text-xs text-gray-400">score: {Math.round(entry.score)}</span>
                  {entry.reviewed_by && (
                    <span className="text-xs text-gray-400">
                      by {entry.reviewed_by}
                    </span>
                  )}
                </div>
              </div>
              <div className="shrink-0 flex gap-2">
                {(statusFilter === 'pending' || statusFilter === 'all') && entry.status === 'pending' ? (
                  <>
                    <button
                      onClick={() => updateEntry(entry.id, 'accepted')}
                      className="px-3 py-1 text-xs rounded border border-green-300 text-green-700 bg-green-50 hover:bg-green-100"
                    >
                      Accept
                    </button>
                    <button
                      onClick={() => updateEntry(entry.id, 'rejected')}
                      className="px-3 py-1 text-xs rounded border border-red-300 text-red-700 bg-red-50 hover:bg-red-100"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => updateEntry(entry.id, 'skipped')}
                      className="px-3 py-1 text-xs rounded border border-gray-300 text-gray-500 bg-gray-50 hover:bg-gray-100"
                    >
                      Skip
                    </button>
                  </>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 text-xs rounded ${
                      entry.status === 'accepted' ? 'bg-green-100 text-green-700' :
                      entry.status === 'rejected' ? 'bg-red-100 text-red-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {entry.status}
                    </span>
                    {entry.status === 'accepted' && (
                      <button
                        onClick={() => updateEntry(entry.id, 'rejected')}
                        className="px-2 py-0.5 text-xs rounded border border-red-200 text-red-500 hover:bg-red-50"
                      >
                        Reject
                      </button>
                    )}
                    {entry.status === 'rejected' && (
                      <button
                        onClick={() => updateEntry(entry.id, 'accepted')}
                        className="px-2 py-0.5 text-xs rounded border border-green-200 text-green-500 hover:bg-green-50"
                      >
                        Accept
                      </button>
                    )}
                    {(entry.status === 'accepted' || entry.status === 'rejected') && (
                      <button
                        onClick={() => updateEntry(entry.id, 'pending')}
                        className="px-2 py-0.5 text-xs rounded border border-gray-200 text-gray-400 hover:bg-gray-50"
                      >
                        Undo
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {entries.length >= PAGE_SIZE && (
        <div className="flex justify-between items-center pt-2">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1 text-xs rounded border border-gray-300 text-gray-700 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-xs text-gray-500">Page {page + 1}</span>
          <button
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 text-xs rounded border border-gray-300 text-gray-700"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
