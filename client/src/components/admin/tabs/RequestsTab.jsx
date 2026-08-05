import { useMemo, useState } from 'react';
import { LANG_NAMES } from '../adminConstants';

export default function RequestsTab({ authHeaders, textRequests, onRefresh }) {
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [editingRequest, setEditingRequest] = useState(null);
  const [savingRequest, setSavingRequest] = useState(false);
  const [tessPreview, setTessPreview] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const normalizedStatus = (status) => (status || 'pending').toLowerCase();

  const filteredAndSortedRequests = useMemo(() => {
    const filtered = textRequests.filter((request) => {
      if (statusFilter === 'all') return true;
      return normalizedStatus(request.status) === statusFilter;
    });

    const statusWeight = (status) => {
      const s = normalizedStatus(status);
      if (s === 'pending') return 0;
      if (s === 'approved') return 2;
      return 1;
    };

    return [...filtered].sort((a, b) => {
      const byStatus = statusWeight(a.status) - statusWeight(b.status);
      if (byStatus !== 0) return byStatus;

      const aTime = new Date(a.created_at || 0).getTime();
      const bTime = new Date(b.created_at || 0).getTime();
      return bTime - aTime;
    });
  }, [textRequests, statusFilter]);

  const parseApiResponse = async (response, fallbackMessage) => {
    let data = null;
    try {
      data = await response.json();
    } catch (_ignored) {
      data = null;
    }
    if (!response.ok || data?.error) {
      const reason = data?.error || data?.message || response.statusText || fallbackMessage;
      const error = new Error(reason);
      error.status = response.status;
      throw error;
    }
    return data;
  };

  const deleteRequest = async (requestId) => {
    if (!window.confirm('Are you sure you want to delete this text request? This cannot be undone.')) {
      return;
    }
    try {
      const res = await fetch(`/api/admin/requests/${requestId}`, {
        method: 'DELETE',
        headers: authHeaders
      });
      await parseApiResponse(res, 'Failed to delete text request');
      onRefresh();
      setSelectedRequest(null);
    } catch (err) {
      window.alert(err.message || 'Failed to delete request');
      console.error('Failed to delete request:', err);
    }
  };

  const openRequestDetails = (request) => {
    setSelectedRequest(request);
    setEditingRequest({
      official_author: request.official_author || request.author || '',
      official_work: request.official_work || request.work || '',
      approved_filename: request.approved_filename || request.suggested_filename || '',
      text_date: request.text_date || '',
      admin_notes: request.admin_notes || '',
      content: request.content || '',
      author_era: request.author_era || '',
      author_year: request.author_year != null ? String(request.author_year) : '',
      e_source: request.e_source || '',
      e_source_url: request.e_source_url || '',
      print_source: request.print_source || '',
      added_by: request.added_by || ''
    });
    updateTessPreview(request.content || '', request.official_author || request.author, request.official_work || request.work);
  };

  const updateTessPreview = (rawContent, author, work) => {
    if (!rawContent || !author || !work) {
      setTessPreview('');
      return;
    }
    const safeAuthor = author.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
    const safeWork = work.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
    const lines = rawContent.split('\n').filter(l => l.trim());
    const formatted = lines.slice(0, 10).map((line, idx) => {
      return `<${safeAuthor}.${safeWork}.${idx + 1}> ${line.trim()}`;
    });
    if (lines.length > 10) {
      formatted.push(`... and ${lines.length - 10} more lines`);
    }
    setTessPreview(formatted.join('\n'));
  };

  const saveRequestChanges = async () => {
    if (!selectedRequest || !editingRequest) return;
    setSavingRequest(true);
    try {
      const normalize = (v) => (v === null || v === undefined ? '' : String(v));
      const hasChanges = [
        'official_author',
        'official_work',
        'approved_filename',
        'text_date',
        'admin_notes',
        'content',
        'author_era',
        'author_year',
        'e_source',
        'e_source_url',
        'print_source',
        'added_by'
      ].some((field) => normalize(editingRequest[field]) !== normalize(selectedRequest[field]));

      if (!hasChanges) {
        setSelectedRequest(null);
        return;
      }

      const res = await fetch(`/api/admin/requests/${selectedRequest.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify(editingRequest)
      });
      await parseApiResponse(res, 'Failed to save request changes');
      onRefresh();
      setSelectedRequest(null);
    } catch (err) {
      window.alert(err.message || 'Failed to save request changes');
      console.error('Failed to save request changes:', err);
    }
    setSavingRequest(false);
  };

  const approveWithEdits = async () => {
    if (!selectedRequest || !editingRequest) return;
    setSavingRequest(true);
    let saveCompleted = false;
    try {
      const normalize = (v) => (v === null || v === undefined ? '' : String(v));
      const hasChanges = [
        'official_author',
        'official_work',
        'approved_filename',
        'text_date',
        'admin_notes',
        'content',
        'author_era',
        'author_year',
        'e_source',
        'e_source_url',
        'print_source',
        'added_by'
      ].some((field) => normalize(editingRequest[field]) !== normalize(selectedRequest[field]));

      if (hasChanges) {
        const saveRes = await fetch(`/api/admin/requests/${selectedRequest.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...authHeaders },
          body: JSON.stringify(editingRequest)
        });
        await parseApiResponse(saveRes, 'Failed to save request before approval');
        saveCompleted = true;
      }

      const approveRequestInternal = async (overwrite = false) => {
        const approveRes = await fetch(`/api/admin/requests/${selectedRequest.id}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeaders },
          body: JSON.stringify({ content: editingRequest.content, overwrite })
        });
        return parseApiResponse(approveRes, 'Failed to approve and add text to corpus');
      };

      let approvalResult;
      try {
        approvalResult = await approveRequestInternal(false);
      } catch (err) {
        if (err?.status === 409) {
          const shouldOverwrite = window.confirm(
            `${err.message}\n\nA matching text already exists. Do you want to overwrite it?`
          );
          if (!shouldOverwrite) {
            window.alert('Approval cancelled. Existing corpus text was not overwritten.');
            return;
          }
          approvalResult = await approveRequestInternal(true);
        } else {
          throw err;
        }
      }

      await onRefresh();
      setSelectedRequest(null);
      if (approvalResult?.warnings?.length) {
        window.alert(
          `The text was added and marked approved, but ${approvalResult.warnings.length} maintenance task(s) need attention. Check the server logs for details.`
        );
      }
    } catch (err) {
      const message = saveCompleted
        ? `Approval failed after saving edits: ${err.message || 'Unknown error'}`
        : (err.message || 'Failed to approve request');
      window.alert(message);
      console.error('Failed to approve request:', err);
    } finally {
      setSavingRequest(false);
    }
  };

  const markRequestApproved = async () => {
    if (!selectedRequest) return;
    const confirmed = window.confirm(
      'Mark this pending request as approved? This only changes the request status and does not add, replace, or reprocess corpus content.'
    );
    if (!confirmed) return;

    setSavingRequest(true);
    try {
      const res = await fetch(`/api/admin/requests/${selectedRequest.id}/mark-approved`, {
        method: 'POST',
        headers: authHeaders
      });
      await parseApiResponse(res, 'Failed to mark request approved');
      await onRefresh();
      setSelectedRequest(null);
    } catch (err) {
      window.alert(err.message || 'Failed to mark request approved');
      console.error('Failed to mark request approved:', err);
    } finally {
      setSavingRequest(false);
    }
  };

  const generateFilename = () => {
    if (!editingRequest) return;
    const author = editingRequest.official_author || '';
    const work = editingRequest.official_work || '';
    const safeAuthor = author.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
    const safeWork = work.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
    setEditingRequest(prev => ({ ...prev, approved_filename: `${safeAuthor}.${safeWork}.tess` }));
  };

  return (
    <>
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h3 className="font-medium text-gray-900">Text Requests</h3>
          <div className="flex items-center gap-3">
            <div className="text-sm text-gray-500">
              {textRequests.filter(r => normalizedStatus(r.status) === 'pending').length} pending
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="request-status-filter" className="text-xs text-gray-500 uppercase">Filter</label>
              <select
                id="request-status-filter"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="border rounded px-2 py-1 text-sm"
              >
                <option value="all">All</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Author</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Work</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Language</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date Submitted</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Last Edit</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredAndSortedRequests.length === 0 ? (
                <tr>
                  <td colSpan="7" className="px-3 py-8 text-center text-sm text-gray-500">
                    No text requests for this filter
                  </td>
                </tr>
              ) : filteredAndSortedRequests.map(request => (
                <tr key={request.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => openRequestDetails(request)}>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <span className={`px-2 py-0.5 text-xs rounded ${
                      request.status === 'approved' ? 'bg-amber-100 text-amber-700' :
                      request.status === 'rejected' ? 'bg-red-100 text-red-700' :
                      'bg-amber-100 text-amber-700'
                    }`}>
                      {request.status || 'pending'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-sm text-gray-900">{request.author}</td>
                  <td className="px-3 py-2 text-sm text-gray-900">{request.work}</td>
                  <td className="px-3 py-2 text-sm text-gray-500">{LANG_NAMES[request.language] || request.language}</td>
                  <td className="px-3 py-2 text-sm text-gray-500">
                    {request.created_at ? new Date(request.created_at).toLocaleString() : '-'}
                  </td>
                  <td className="px-3 py-2 text-sm text-gray-500">
                    {request.admin_updated_at ? new Date(request.admin_updated_at).toLocaleString() : '-'}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <button
                      onClick={(e) => { e.stopPropagation(); openRequestDetails(request); }}
                      className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                    >
                      Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedRequest && editingRequest && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b bg-gray-50 flex justify-between items-center">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Review Text Request</h3>
                <p className="text-sm text-gray-500">
                  Submitted by {selectedRequest.name || 'Anonymous'}
                  {selectedRequest.email && ` (${selectedRequest.email})`}
                </p>
              </div>
              <button
                onClick={() => setSelectedRequest(null)}
                className="text-gray-400 hover:text-gray-600 text-2xl"
              >
                &times;
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Official Author Name</label>
                  <input
                    type="text"
                    value={editingRequest.official_author}
                    onChange={e => {
                      setEditingRequest(prev => ({ ...prev, official_author: e.target.value }));
                      updateTessPreview(editingRequest.content, e.target.value, editingRequest.official_work);
                    }}
                    className="w-full border rounded px-3 py-2 text-sm"
                    placeholder="e.g., Vergil"
                  />
                  <p className="text-xs text-gray-400 mt-1">Original: {selectedRequest.author}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Official Work Title</label>
                  <input
                    type="text"
                    value={editingRequest.official_work}
                    onChange={e => {
                      setEditingRequest(prev => ({ ...prev, official_work: e.target.value }));
                      updateTessPreview(editingRequest.content, editingRequest.official_author, e.target.value);
                    }}
                    className="w-full border rounded px-3 py-2 text-sm"
                    placeholder="e.g., Aeneid"
                  />
                  <p className="text-xs text-gray-400 mt-1">Original: {selectedRequest.work}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
                  <div className="px-3 py-2 bg-gray-100 rounded text-sm">
                    {LANG_NAMES[selectedRequest.language] || selectedRequest.language}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Era</label>
                  <select
                    value={editingRequest.author_era}
                    onChange={e => setEditingRequest(prev => ({ ...prev, author_era: e.target.value }))}
                    className="w-full border rounded px-3 py-2 text-sm"
                  >
                    <option value="">Select era...</option>
                    <option value="Archaic">Archaic</option>
                    <option value="Classical">Classical</option>
                    <option value="Hellenistic">Hellenistic</option>
                    <option value="Republic">Republic</option>
                    <option value="Augustan">Augustan</option>
                    <option value="Early Imperial">Early Imperial</option>
                    <option value="Later Imperial">Later Imperial</option>
                    <option value="Late Antique">Late Antique</option>
                    <option value="Early Medieval">Early Medieval</option>
                    <option value="Unknown">Unknown</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Year (negative = BCE)</label>
                  <input
                    type="number"
                    value={editingRequest.author_year}
                    onChange={e => setEditingRequest(prev => ({ ...prev, author_year: e.target.value }))}
                    className="w-full border rounded px-3 py-2 text-sm"
                    placeholder="e.g., -19 for 19 BCE"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">.tess Filename</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={editingRequest.approved_filename}
                      onChange={e => setEditingRequest(prev => ({ ...prev, approved_filename: e.target.value }))}
                      className="flex-1 border rounded px-3 py-2 text-sm font-mono"
                    />
                    <button
                      onClick={generateFilename}
                      className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs hover:bg-gray-200"
                      title="Auto-generate from author/work"
                    >
                      Auto
                    </button>
                  </div>
                </div>
              </div>

              <div className="border border-amber-200 rounded-lg p-4 bg-amber-50">
                <h4 className="text-sm font-semibold text-amber-900 mb-3">Sources Entry (for Sources page)</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">e-Source</label>
                    <select
                      value={editingRequest.e_source}
                      onChange={e => setEditingRequest(prev => ({ ...prev, e_source: e.target.value }))}
                      className="w-full border rounded px-3 py-2 text-sm"
                    >
                      <option value="">Select source...</option>
                      <option value="Perseus">Perseus</option>
                      <option value="The Latin Library">The Latin Library</option>
                      <option value="DigilibLT">DigilibLT</option>
                      <option value="Open Greek and Latin">Open Greek and Latin</option>
                      <option value="MQDQ">MQDQ (Musisque Deoque)</option>
                      <option value="Corpus Scriptorum Latinorum">Corpus Scriptorum Latinorum</option>
                      <option value="Bibliotheca Augustana">Bibliotheca Augustana</option>
                      <option value="Forum Romanum">Forum Romanum</option>
                      <option value="Divus Angelus">Divus Angelus</option>
                      <option value="Moby Shakespeare">Moby Shakespeare</option>
                      <option value="User Submission">User Submission</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">e-Source URL</label>
                    <input
                      type="url"
                      value={editingRequest.e_source_url}
                      onChange={e => setEditingRequest(prev => ({ ...prev, e_source_url: e.target.value }))}
                      className="w-full border rounded px-3 py-2 text-sm"
                      placeholder="https://..."
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-medium text-gray-700 mb-1">Print Source (citation)</label>
                    <input
                      type="text"
                      value={editingRequest.print_source}
                      onChange={e => setEditingRequest(prev => ({ ...prev, print_source: e.target.value }))}
                      className="w-full border rounded px-3 py-2 text-sm"
                      placeholder="e.g., Rudolf Hercher, Erotici Scriptores Graeci, Vol 1. Leipzig: Teubneri, 1858."
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Added by</label>
                    <input
                      type="text"
                      value={editingRequest.added_by}
                      onChange={e => setEditingRequest(prev => ({ ...prev, added_by: e.target.value }))}
                      className="w-full border rounded px-3 py-2 text-sm"
                      placeholder="Name of person who added this text"
                    />
                  </div>
                </div>
              </div>

              {selectedRequest.notes && (
                <div className="bg-amber-50 border border-amber-200 rounded p-3">
                  <div className="text-sm font-medium text-amber-800">Submitter Notes</div>
                  <p className="text-sm text-amber-700 mt-1">{selectedRequest.notes}</p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Admin Notes</label>
                <textarea
                  value={editingRequest.admin_notes}
                  onChange={e => setEditingRequest(prev => ({ ...prev, admin_notes: e.target.value }))}
                  className="w-full border rounded px-3 py-2 text-sm"
                  rows={2}
                  placeholder="Internal notes about this request..."
                />
              </div>

              <div className="border-t pt-4">
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-sm font-medium text-gray-700">Text Content (Raw)</label>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => {
                        if (!editingRequest.content || !editingRequest.official_author || !editingRequest.official_work) return;
                        const author = editingRequest.official_author.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
                        const work = editingRequest.official_work.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
                        const lines = editingRequest.content.split('\n').filter(l => l.trim());
                        const formatted = lines.map((line, idx) => {
                          const trimmed = line.trim();
                          if (trimmed.startsWith('<') && trimmed.includes('>')) return trimmed;
                          return `<${author}.${work}.${idx + 1}> ${trimmed}`;
                        }).join('\n');
                        setEditingRequest(prev => ({ ...prev, content: formatted }));
                        updateTessPreview(formatted, editingRequest.official_author, editingRequest.official_work);
                      }}
                      className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                      title="Add .tess tags to each line"
                    >
                      Add .tess Tags
                    </button>
                    <span className="text-xs text-gray-500">
                      {editingRequest.content ? editingRequest.content.split('\n').filter(l => l.trim()).length : 0} lines
                    </span>
                  </div>
                </div>
                <textarea
                  value={editingRequest.content}
                  onChange={e => {
                    setEditingRequest(prev => ({ ...prev, content: e.target.value }));
                    updateTessPreview(e.target.value, editingRequest.official_author, editingRequest.official_work);
                  }}
                  className="w-full border rounded px-3 py-2 text-sm font-mono"
                  rows={8}
                  placeholder="Paste or edit the text content here..."
                />
              </div>

              <div className="bg-gray-900 rounded p-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-medium text-gray-400 uppercase">.tess Preview</span>
                  <span className="text-xs text-gray-500">First 10 lines</span>
                </div>
                <pre className="text-amber-400 text-sm font-mono whitespace-pre-wrap overflow-x-auto">
                  {tessPreview || 'Enter author, work, and content to see preview...'}
                </pre>
              </div>
            </div>

            <div className="px-6 py-4 bg-gray-50 border-t flex justify-between">
              <div className="flex gap-2">
                <button
                  onClick={() => deleteRequest(selectedRequest.id)}
                  disabled={savingRequest}
                  className="px-4 py-2 bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
              <div className="flex gap-2">
                {normalizedStatus(selectedRequest.status) === 'pending' && (
                  <button
                    onClick={markRequestApproved}
                    disabled={savingRequest}
                    className="px-4 py-2 bg-amber-100 text-amber-800 rounded hover:bg-amber-200 disabled:opacity-50"
                    title="Use only when this request's text has already been added to the corpus"
                  >
                    Mark as Approved
                  </button>
                )}
                <button
                  onClick={() => setSelectedRequest(null)}
                  className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={saveRequestChanges}
                  disabled={savingRequest}
                  className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
                >
                  {savingRequest ? 'Saving...' : 'Save Changes'}
                </button>
                <button
                  onClick={approveWithEdits}
                  disabled={savingRequest || !editingRequest.content}
                  className="px-4 py-2 bg-red-800 text-white rounded hover:bg-red-900 disabled:opacity-50"
                >
                  {savingRequest ? 'Processing...' : 'Approve & Add to Corpus'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
