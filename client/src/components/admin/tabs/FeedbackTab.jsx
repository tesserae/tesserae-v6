import { useMemo, useState } from 'react';

const normalizeStatus = (status) => {
  const s = (status || '').toLowerCase();
  if (['responded', 'resolved', 'done', 'closed'].includes(s)) return 'responded';
  if (s === 'in_progress') return 'in_progress';
  return 'pending';
};

export default function FeedbackTab({ feedback, onRefresh }) {
  const [statusFilter, setStatusFilter] = useState('all');
  const [updatingId, setUpdatingId] = useState(null);
  const [actionError, setActionError] = useState('');

  const filteredFeedback = useMemo(() => {
    if (statusFilter === 'all') return feedback;
    return feedback.filter((item) => normalizeStatus(item.status) === statusFilter);
  }, [feedback, statusFilter]);

  const updateFeedbackStatus = async (feedbackId, nextStatus) => {
    setActionError('');
    setUpdatingId(feedbackId);
    try {
      const res = await fetch(`/api/admin/feedback/${feedbackId}`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || 'Failed to update feedback status');
      }
      if (onRefresh) {
        await onRefresh();
      }
    } catch (err) {
      setActionError(err.message || 'Failed to update feedback status');
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="font-medium text-gray-900">User Feedback</h3>

      <div className="flex flex-wrap items-center gap-2">
        {['all', 'pending', 'in_progress', 'responded'].map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-3 py-1 text-xs rounded border ${
              statusFilter === status
                ? 'bg-red-700 text-white border-red-700'
                : 'bg-white text-gray-700 border-gray-300'
            }`}
          >
            {status === 'all' ? 'All' : status === 'pending' ? 'Pending' : status === 'in_progress' ? 'In Progress' : 'Responded'}
          </button>
        ))}
      </div>

      {actionError && <div className="text-sm text-red-600">{actionError}</div>}

      {filteredFeedback.length === 0 ? (
        <p className="text-gray-500 text-sm">No feedback submissions for this filter</p>
      ) : (
        <div className="divide-y">
          {filteredFeedback.map((item) => {
            const normalizedStatus = normalizeStatus(item.status);
            const isResponded = normalizedStatus === 'responded';
            const isInProgress = normalizedStatus === 'in_progress';

            return (
              <div key={item.id} className="py-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 text-xs rounded ${
                          item.type === 'bug'
                            ? 'bg-red-100 text-red-700'
                            : item.type === 'feature'
                              ? 'bg-blue-100 text-blue-700'
                              : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {item.type || 'suggestion'}
                      </span>
                      <span
                        className={`px-2 py-0.5 text-xs rounded ${
                          isResponded ? 'bg-green-100 text-green-700' : isInProgress ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'
                        }`}
                      >
                        {isResponded ? 'responded' : isInProgress ? 'in progress' : 'pending'}
                      </span>
                    </div>
                    <div className="text-sm text-gray-600 mt-1">
                      From: {item.name || 'Anonymous'} {item.email && `<${item.email}>`}
                    </div>
                    <p className="text-gray-800 mt-2 whitespace-pre-wrap">{item.message}</p>
                    <div className="text-xs text-gray-500 mt-1">
                      {item.created_at && new Date(item.created_at).toLocaleString()}
                    </div>
                    {isResponded && (item.responded_by || item.responded_at) && (
                      <div className="text-xs text-gray-500 mt-1">
                        Responded by {item.responded_by || 'admin'}
                        {item.responded_at ? ` on ${new Date(item.responded_at).toLocaleString()}` : ''}
                      </div>
                    )}
                  </div>

                  <div className="shrink-0 flex flex-col gap-2">
                    <button
                      onClick={() => updateFeedbackStatus(item.id, 'pending')}
                      disabled={updatingId === item.id || normalizedStatus === 'pending'}
                      className="px-3 py-1 text-xs rounded border border-amber-300 text-amber-700 bg-amber-50 disabled:opacity-50"
                    >
                      Pending
                    </button>
                    <button
                      onClick={() => updateFeedbackStatus(item.id, 'in_progress')}
                      disabled={updatingId === item.id || isInProgress}
                      className="px-3 py-1 text-xs rounded border border-blue-300 text-blue-700 bg-blue-50 disabled:opacity-50"
                    >
                      In Progress
                    </button>
                    <button
                      onClick={() => updateFeedbackStatus(item.id, 'responded')}
                      disabled={updatingId === item.id || isResponded}
                      className="px-3 py-1 text-xs rounded border border-green-300 text-green-700 bg-green-50 disabled:opacity-50"
                    >
                      Responded
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
