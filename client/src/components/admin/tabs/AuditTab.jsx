import { useState, useEffect } from 'react';
import { LoadingSpinner } from '../../common';

export default function AuditTab({ authHeaders }) {
  const [auditLog, setAuditLog] = useState([]);
  const [auditLogLoading, setAuditLogLoading] = useState(false);

  const loadAuditLog = async () => {
    setAuditLogLoading(true);
    try {
      const res = await fetch('/api/admin/audit-log?limit=100', { headers: authHeaders });
      if (res.ok) {
        const data = await res.json();
        setAuditLog(data.entries || []);
      }
    } catch (err) {
      console.error('Failed to load audit log:', err);
    }
    setAuditLogLoading(false);
  };

  useEffect(() => {
    loadAuditLog();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="font-medium text-gray-900">Admin Activity Log</h3>
        <button
          onClick={loadAuditLog}
          disabled={auditLogLoading}
          className="text-sm px-3 py-1 text-red-700 border border-red-700 rounded hover:bg-red-50 disabled:opacity-50"
        >
          {auditLogLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {auditLogLoading ? (
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      ) : auditLog.length === 0 ? (
        <div className="bg-gray-50 rounded p-8 text-center">
          <p className="text-gray-500">No admin activity recorded yet.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {(() => {
            const byPerson = {};
            auditLog.forEach(entry => {
              const name = entry.admin_username || 'unknown';
              if (!byPerson[name]) byPerson[name] = [];
              byPerson[name].push(entry);
            });

            return Object.keys(byPerson).sort().map(person => (
              <div key={person} className="bg-gray-50 rounded-lg overflow-hidden">
                <div className="bg-gray-100 px-4 py-2 border-b">
                  <h4 className="font-medium text-gray-800">{person}</h4>
                  <span className="text-sm text-gray-500">{byPerson[person].length} actions</span>
                </div>
                <div className="divide-y">
                  {byPerson[person].slice(0, 20).map(entry => (
                    <div key={entry.id} className="px-4 py-2 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                          entry.action === 'login' ? 'bg-blue-100 text-blue-700' :
                          entry.action === 'approve' ? 'bg-amber-100 text-amber-700' :
                          entry.action === 'delete' ? 'bg-red-100 text-red-700' :
                          entry.action === 'update' ? 'bg-amber-100 text-amber-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {entry.action}
                        </span>
                        {entry.target_type && (
                          <span className="text-sm text-gray-600">
                            {entry.target_type} #{entry.target_id}
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">
                        {entry.created_at ? new Date(entry.created_at).toLocaleString() : ''}
                      </span>
                    </div>
                  ))}
                  {byPerson[person].length > 20 && (
                    <div className="px-4 py-2 text-sm text-gray-500 text-center">
                      + {byPerson[person].length - 20} more actions
                    </div>
                  )}
                </div>
              </div>
            ));
          })()}
        </div>
      )}

      <div className="mt-6">
        <h4 className="font-medium text-gray-900 mb-3">Summary by Action Type</h4>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {(() => {
            const byType = {};
            auditLog.forEach(entry => {
              byType[entry.action] = (byType[entry.action] || 0) + 1;
            });
            return Object.entries(byType).sort((a, b) => b[1] - a[1]).map(([action, count]) => (
              <div key={action} className="bg-white border rounded p-3 text-center">
                <div className="text-2xl font-bold text-gray-800">{count}</div>
                <div className={`text-sm font-medium ${
                  action === 'login' ? 'text-blue-600' :
                  action === 'approve' ? 'text-amber-700' :
                  action === 'delete' ? 'text-red-600' :
                  action === 'update' ? 'text-amber-600' :
                  'text-gray-600'
                }`}>{action}</div>
              </div>
            ));
          })()}
        </div>
      </div>
    </div>
  );
}
