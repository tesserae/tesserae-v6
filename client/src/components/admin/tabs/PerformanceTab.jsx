import { useState, useEffect } from 'react';
import { Activity, Cpu, Clock, AlertTriangle, RotateCcw, Settings, Zap, CheckCircle, Search, Trash2 } from 'lucide-react';

export default function PerformanceTab() {
  const [status, setStatus] = useState(null);
  const [activeSearches, setActiveSearches] = useState([]);
  const [killingSlots, setKillingSlots] = useState({});
  const [loading, setLoading] = useState(true);
  const [maxSearches, setMaxSearches] = useState(2);
  const [memThreshold, setMemThreshold] = useState(8);
  const [emergencyFloor, setEmergencyFloor] = useState(3.0);
  const [queueTimeout, setQueueTimeout] = useState(300);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null); // {type: 'success'|'error', text: '...'}
  const [stressTestToggling, setStressTestToggling] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);

  const fetchStatus = async () => {
    try {
      const [statusRes, activeRes] = await Promise.all([
        fetch('/api/admin/concurrency', { credentials: 'include' }),
        fetch('/api/admin/concurrency/active', { credentials: 'include' })
      ]);

      if (statusRes.ok) {
        setStatus(await statusRes.json());
      }
      if (activeRes.ok) {
        const activeData = await activeRes.json();
        setActiveSearches(activeData.active_searches || []);
      }
    } catch (err) {
      console.error('Failed to fetch concurrency status:', err);
    } finally {
      setLoading(false);
    }
  };

  const killSearch = async (slotId) => {
    setKillingSlots(prev => ({ ...prev, [slotId]: true }));
    setMessage(null);
    try {
      const res = await fetch(`/api/admin/concurrency/active/${slotId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      const data = await res.json();
      if (res.ok) {
        setMessage({ type: 'success', text: `Search termination signal sent.` });
        fetchStatus();
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to kill search' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to kill search: ' + err.message });
    } finally {
      setKillingSlots(prev => ({ ...prev, [slotId]: false }));
    }
  };

  useEffect(() => {
    if (status && !initialLoaded) {
      setMaxSearches(status.max_searches);
      setMemThreshold(status.memory_threshold_gb);
      setQueueTimeout(status.queue_timeout);
      setEmergencyFloor(status.emergency_ram_floor_gb);
      setInitialLoaded(true);
    }
  }, [status, initialLoaded]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const updateConfig = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch('/api/admin/concurrency', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          max_searches: maxSearches,
          memory_threshold_gb: memThreshold,
          queue_timeout: queueTimeout,
          emergency_ram_floor_gb: emergencyFloor
        })
      });
      const data = await res.json();
      if (res.ok) {
        setMessage({ type: 'success', text: 'Concurrency settings updated successfully.' });
        if (data.max_searches) setMaxSearches(data.max_searches);
        if (data.memory_threshold_gb) setMemThreshold(data.memory_threshold_gb);
        if (data.queue_timeout) setQueueTimeout(data.queue_timeout);
        if (data.emergency_ram_floor_gb) setEmergencyFloor(data.emergency_ram_floor_gb);
        fetchStatus();
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to update settings' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to update settings: ' + err.message });
    }
    setSaving(false);
  };

  const toggleStressTest = async (enabled) => {
    setStressTestToggling(true);
    setMessage(null);
    try {
      const res = await fetch('/api/admin/concurrency/stress-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ enabled })
      });
      const data = await res.json();
      if (res.ok) {
        setMessage({ type: 'success', text: enabled ? 'Stress test mode enabled.' : 'Stress test mode disabled.' });
        fetchStatus();
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to toggle stress test mode' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to toggle stress test mode: ' + err.message });
    }
    setStressTestToggling(false);
  };

  const resetConfig = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch('/api/admin/concurrency/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (res.ok) {
        setMessage({ type: 'success', text: 'Settings reset to defaults.' });
        if (data.max_searches) setMaxSearches(data.max_searches);
        if (data.memory_threshold_gb) setMemThreshold(data.memory_threshold_gb);
        if (data.queue_timeout) setQueueTimeout(data.queue_timeout);
        if (data.emergency_ram_floor_gb) setEmergencyFloor(data.emergency_ram_floor_gb);
        fetchStatus();
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to reset settings' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to reset settings: ' + err.message });
    }
    setSaving(false);
  };

  const [killingAll, setKillingAll] = useState(false);

  const killAllSearches = async () => {
    if (!window.confirm('Are you sure you want to terminate ALL active searches?')) return;
    setKillingAll(true);
    try {
      const res = await fetch('/api/admin/concurrency/active/all', {
        method: 'DELETE',
        credentials: 'include'
      });
      if (res.ok) {
        setMessage({ type: 'success', text: 'Termination signal sent to all active searches.' });
        fetchStatus();
      } else {
        const data = await res.json();
        setMessage({ type: 'error', text: data.error || 'Failed to kill all searches' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Error killing all searches: ' + err.message });
    }
    setKillingAll(false);
  };

  const getCapacityColor = (active, max) => {
    const pct = max > 0 ? (active / max) * 100 : 0;
    if (pct > 80) return 'bg-red-500';
    if (pct >= 50) return 'bg-amber-500';
    return 'bg-green-500';
  };

  const getMemoryColor = (available, threshold) => {
    if (available <= threshold) return 'text-red-600';
    if (available > threshold * 1.5) return 'text-green-600';
    return 'text-amber-600';
  };

  const formatMemory = (val) => {
    if (val > 9999) return '∞';
    return val;
  };

  const formatRuntime = (seconds) => {
    if (!seconds || seconds < 0) return '0s';
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-500">
        <Activity className="w-5 h-5 animate-spin mr-2" />
        Loading performance data...
      </div>
    );
  }

  const capacityPct = status ? Math.min((status.active_searches / status.max_searches) * 100, 100) : 0;

  return (
    <div className="space-y-6">
      {/* Section A: Live Status Cards */}
      <div>
        <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4" />
          Live Status
          <span className="text-xs text-gray-400 font-normal">(auto-refresh every 5s)</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Active Searches Card */}
          <div className="bg-gray-50 border border-gray-200 p-4 rounded">
            <div className="flex items-center gap-2 mb-1">
              <Zap className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-600">Active Searches</span>
            </div>
            <div className="text-2xl font-bold text-gray-900">
              {status?.active_searches ?? 0} / {status?.max_searches ?? '?'}
            </div>
            <div className="mt-2 w-full bg-gray-200 rounded-full h-2.5">
              <div
                className={`h-2.5 rounded-full transition-all ${status ? getCapacityColor(status.active_searches, status.max_searches) : 'bg-gray-300'}`}
                style={{ width: `${capacityPct}%` }}
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">{capacityPct.toFixed(0)}% capacity</p>
          </div>

          {/* Queue Settings Card */}
          <div className="bg-gray-50 border border-gray-200 p-4 rounded">
            <div className="flex items-center gap-2 mb-1">
              <Clock className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-600">Queue Settings</span>
            </div>
            <div className="text-lg font-bold text-gray-900 mt-1">
              Timeout: {status?.queue_timeout ?? '?'}s
            </div>
            <div className="text-sm text-gray-600 mt-1">
              Poll interval: <span className="text-gray-900 font-medium">
                {status?.queue_poll_interval !== undefined ? `${status.queue_poll_interval}s` : '?'}
              </span>
            </div>
          </div>

          {/* Memory Card */}
          <div className="bg-gray-50 border border-gray-200 p-4 rounded">
            <div className="flex items-center gap-2 mb-1">
              <Cpu className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-600">Available Memory</span>
            </div>
            <div className={`text-2xl font-bold ${status ? getMemoryColor(status.available_memory_gb, status.memory_threshold_gb) : 'text-gray-900'}`}>
              {status ? formatMemory(status.available_memory_gb) : '?'} GB
              {status?.emergency_active && (
                <span className="ml-2 px-2 py-0.5 text-xs font-bold bg-red-600 text-white rounded animate-pulse">
                  EMERGENCY
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Threshold: {status?.memory_threshold_gb ?? '?'} GB · Emergency Floor: {status?.emergency_ram_floor_gb ?? '?'} GB
            </p>
          </div>
        </div>
      </div>

      {/* Section A2: Active Search Inspector Table */}
      <div className="border-t pt-6">
        <h3 className="font-medium text-gray-900 mb-4 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Search className="w-4 h-4 text-red-600" />
            Active Search Inspector
            <span className="text-xs text-gray-400 font-normal">
              ({activeSearches.length} running)
            </span>
          </span>
          {activeSearches.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded font-medium animate-pulse">
                Live Active
              </span>
              <button
                onClick={killAllSearches}
                disabled={killingAll}
                className="px-2.5 py-1 bg-red-600 hover:bg-red-700 text-white text-xs font-medium rounded flex items-center gap-1 transition-colors disabled:opacity-50"
              >
                <Trash2 className="w-3.5 h-3.5" />
                {killingAll ? 'Terminating All...' : 'Terminate All Searches'}
              </button>
            </div>
          )}
        </h3>

        {activeSearches.length === 0 ? (
          <div className="bg-gray-50 border border-gray-200 rounded p-6 text-center text-gray-500">
            <CheckCircle className="w-6 h-6 text-green-500 mx-auto mb-2" />
            <p className="text-sm font-medium text-gray-700">No Active Searches</p>
            <p className="text-xs text-gray-400 mt-1">
              All search slots are currently idle.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto border border-gray-200 rounded">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-gray-600 border-b border-gray-200 text-xs uppercase font-medium">
                <tr>
                  <th className="px-4 py-3">Source Text</th>
                  <th className="px-4 py-3">Target Text</th>
                  <th className="px-4 py-3">Language</th>
                  <th className="px-4 py-3">Match Type</th>
                  <th className="px-4 py-3">RAM Usage</th>
                  <th className="px-4 py-3">Runtime</th>
                  <th className="px-4 py-3">PID</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {activeSearches.map(search => (
                  <tr key={search.slot_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-gray-800 max-w-[180px] truncate" title={search.source_id}>
                      {search.source_id.replace('.tess', '')}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-800 max-w-[180px] truncate" title={search.target_id}>
                      {search.target_id.replace('.tess', '')}
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 text-xs font-semibold uppercase bg-gray-100 text-gray-700 rounded">
                        {search.language}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 text-xs font-medium bg-blue-50 text-blue-700 rounded border border-blue-100">
                        {search.match_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-gray-700">
                      {search.memory_mb ? `${search.memory_mb} MB` : '—'}
                    </td>
                    <td className="px-4 py-3 font-medium text-gray-700">
                      {formatRuntime(search.runtime_seconds)}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">
                      {search.pid || '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => killSearch(search.slot_id)}
                        disabled={killingSlots[search.slot_id] || search.is_cancelling}
                        className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white text-xs font-medium rounded flex items-center gap-1 ml-auto disabled:opacity-50 transition-colors"
                      >
                        {killingSlots[search.slot_id] ? (
                          <Activity className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="w-3.5 h-3.5" />
                        )}
                        {search.is_cancelling ? 'Terminating...' : killingSlots[search.slot_id] ? 'Killing...' : 'Kill Search'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Section B: Concurrency Controls */}
      <div className="border-t pt-6">
        <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Settings className="w-4 h-4" />
          Concurrency Controls
        </h3>
        <div className="bg-gray-50 p-4 rounded space-y-4">
          {/* Max Simultaneous Searches */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Simultaneous Searches
              <span className="ml-2 inline-block px-2 py-0.5 text-xs font-bold bg-red-100 text-red-700 rounded">
                {maxSearches}
              </span>
            </label>
            <input
              type="range"
              min="1"
              max="50"
              step="1"
              value={maxSearches}
              onChange={e => setMaxSearches(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>1</span>
              <span>25</span>
              <span>50</span>
            </div>
          </div>

          {/* Memory Threshold */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Memory Threshold (GB)
            </label>
            <input
              type="number"
              min={0.5}
              max={128}
              step={0.5}
              value={memThreshold}
              onChange={e => setMemThreshold(Number(e.target.value))}
              className="w-32 border rounded px-3 py-2 text-sm"
            />
          </div>

          {/* Emergency RAM Floor */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Emergency RAM Floor (GB)
              <span className="ml-1 text-xs text-red-500 font-normal">unbypassable</span>
            </label>
            <input
              type="number"
              min={1.0}
              max={16.0}
              step={0.5}
              value={emergencyFloor}
              onChange={e => setEmergencyFloor(Number(e.target.value))}
              className="w-32 border rounded px-3 py-2 text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">Blocks ALL new searches below this, even in Stress Test Mode</p>
          </div>

          {/* Queue Timeout */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Queue Timeout (seconds)
            </label>
            <input
              type="number"
              min={30}
              max={3600}
              step={30}
              value={queueTimeout}
              onChange={e => setQueueTimeout(Number(e.target.value))}
              className="w-32 border rounded px-3 py-2 text-sm"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={updateConfig}
              disabled={saving}
              className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
            >
              {saving ? 'Applying...' : 'Apply Changes'}
            </button>
            <button
              onClick={resetConfig}
              disabled={saving}
              className="px-4 py-2 border border-gray-300 text-gray-600 rounded hover:bg-gray-50"
            >
              <RotateCcw className="w-4 h-4 inline mr-1" />
              Reset to Defaults
            </button>
          </div>

          {/* Message */}
          {message && (
            <div className={`text-sm mt-2 flex items-center gap-1 ${
              message.type === 'success' ? 'text-green-600' : 'text-red-600'
            }`}>
              {message.type === 'success' && <CheckCircle className="w-4 h-4" />}
              {message.type === 'error' && <AlertTriangle className="w-4 h-4" />}
              {message.text}
            </div>
          )}
        </div>
      </div>

      {/* Section C: Stress Test Mode */}
      <div className="border-t pt-6">
        <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Zap className="w-4 h-4" />
          Stress Test Mode
        </h3>
        <div className="flex items-center gap-3 mb-3">
          <button
            onClick={() => toggleStressTest(!status?.stress_test_mode)}
            disabled={stressTestToggling}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              status?.stress_test_mode ? 'bg-amber-500' : 'bg-gray-300'
            } ${stressTestToggling ? 'opacity-50 cursor-wait' : 'cursor-pointer'}`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                status?.stress_test_mode ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
          <span className="text-sm text-gray-700">
            {status?.stress_test_mode ? 'Enabled' : 'Disabled'}
          </span>
        </div>
        {status?.stress_test_mode && (
          <div className="bg-amber-50 border border-amber-300 rounded p-3 flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-medium text-amber-800">Warning: Stress Test Mode Active</div>
              <p className="text-sm text-amber-700 mt-1">
                Memory safety checks are bypassed. The Emergency RAM Floor ({status?.emergency_ram_floor_gb ?? 3.0} GB) still applies and cannot be bypassed. This mode auto-expires after 1 hour.
                Only use for controlled load testing.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Section C2: Memory Reaper Status */}
      {status?.reaper_status?.reap_count > 0 && (
        <div className="border-t pt-6">
          <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-500" />
            Memory Reaper Activity
          </h3>
          <div className="bg-red-50 border border-red-200 rounded p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-2 h-2 rounded-full ${status.reaper_status.active ? 'bg-green-500' : 'bg-gray-400'}`} />
              <span className="text-sm font-medium text-gray-800">
                Reaper {status.reaper_status.active ? 'Active' : 'Inactive'}
              </span>
              <span className="text-xs text-gray-500">•</span>
              <span className="text-sm text-red-700 font-semibold">
                {status.reaper_status.reap_count} search{status.reaper_status.reap_count !== 1 ? 'es' : ''} auto-terminated
              </span>
            </div>
            {status.reaper_status.last_reap_reason && (
              <p className="text-xs text-red-600 font-mono break-all">
                Last: {status.reaper_status.last_reap_reason}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Section D: Defaults Reference */}
      {status?.defaults && (
        <div className="border-t pt-6">
          <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
            <Settings className="w-4 h-4" />
            Defaults Reference
          </h3>
          <div className="bg-blue-50 border border-blue-200 rounded p-4 text-sm text-blue-800">
            <div className="font-medium mb-2">Environment Variable Defaults</div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <div>
                <span className="text-blue-600">MAX_SEARCHES:</span>{' '}
                <span className="font-mono">{status.defaults.max_searches}</span>
              </div>
              <div>
                <span className="text-blue-600">MEMORY_THRESHOLD_GB:</span>{' '}
                <span className="font-mono">{status.defaults.memory_threshold_gb}</span>
              </div>
              <div>
                <span className="text-blue-600">QUEUE_TIMEOUT:</span>{' '}
                <span className="font-mono">{status.defaults.queue_timeout}</span>
              </div>
              <div>
                <span className="text-blue-600">EMERGENCY_RAM_FLOOR_GB:</span>{' '}
                <span className="font-mono">{status.defaults.emergency_ram_floor_gb}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
