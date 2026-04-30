import { useState, useEffect, useCallback } from 'react';
import { LoadingSpinner } from '../common';
import StatsTab from './tabs/StatsTab';
import FeedbackTab from './tabs/FeedbackTab';
import SettingsTab from './tabs/SettingsTab';
import AuditTab from './tabs/AuditTab';
import AnalyticsTab from './tabs/AnalyticsTab';
import CacheTab from './tabs/CacheTab';
import SourcesTab from './tabs/SourcesTab';
import MetadataTab from './tabs/MetadataTab';
import RequestsTab from './tabs/RequestsTab';
import UsersTab from './tabs/UsersTab';
import GenreClassificationTab from './tabs/GenreClassificationTab';
import DictionaryReviewTab from './tabs/DictionaryReviewTab';
import Repository from '../repository/Repository';

const normalizeRole = (role) => (role || '').toString().trim().toUpperCase();

export default function AdminPanel() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [adminEmail, setAdminEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState('');
  const [activeTab, setActiveTab] = useState('requests');
  const [loading, setLoading] = useState(false);
  const [adminRoles, setAdminRoles] = useState([]);
  const [adminUserId, setAdminUserId] = useState(null);
  const [mustResetPassword, setMustResetPassword] = useState(false);
  const [resetCurrent, setResetCurrent] = useState('');
  const [resetNext, setResetNext] = useState('');
  const [resetConfirm, setResetConfirm] = useState('');
  const [resetError, setResetError] = useState('');
  const [resetSuccess, setResetSuccess] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);

  const [textRequests, setTextRequests] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [corpusStats, setCorpusStats] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [cacheInfo, setCacheInfo] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [bigramStats, setBigramStats] = useState({});

  useEffect(() => {
    const checkSession = async () => {
      try {
        const meRes = await fetch('/api/admin/me', { credentials: 'include' });
        if (meRes.ok) {
          const meData = await meRes.json();
          const meRoles = Array.isArray(meData.roles)
            ? meData.roles.map(normalizeRole).filter(Boolean)
            : [];
          
          if (meRoles.length > 0) {
            setIsAuthenticated(true);
            setAdminRoles(meRoles);
            setAdminUserId(meData.user_id || null);
            setMustResetPassword(Boolean(meData.must_reset_password));
            window.dispatchEvent(new Event('admin-auth-changed'));
            
            if (!meData.must_reset_password) {
              loadAdminData();
            }
          }
        }
      } catch (err) {
        console.error('Session check failed', err);
      }
    };
    checkSession();
  }, []);

  useEffect(() => {
    let interval;
    if (isAuthenticated && !mustResetPassword && activeTab === 'analytics') {
      interval = setInterval(async () => {
        try {
          const res = await fetch('/api/admin/analytics', { credentials: 'include' });
          if (res.ok) {
            const data = await res.json();
            setAnalytics(data);
          }
        } catch (err) {
          console.error('Failed to poll analytics:', err);
        }
      }, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isAuthenticated, mustResetPassword, activeTab]);

  const handleLogin = async () => {
    setAuthError('');
    if (!adminEmail.trim()) {
      setAuthError('Please enter your email');
      return;
    }
    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password, email: adminEmail }),
        credentials: 'include'
      });
      const data = await res.json();
      if (data.success) {
        const normalizedRoles = Array.isArray(data.roles)
          ? data.roles.map(normalizeRole).filter(Boolean)
          : [];
        setIsAuthenticated(true);
        setAdminRoles(normalizedRoles);
        setMustResetPassword(Boolean(data.must_reset_password));
        setResetError('');
        setResetSuccess('');
        window.dispatchEvent(new Event('admin-auth-changed'));
        try {
          const meRes = await fetch('/api/admin/me', { credentials: 'include' });
          if (meRes.ok) {
            const meData = await meRes.json();
            setAdminUserId(meData.user_id || null);
            const meRoles = Array.isArray(meData.roles)
              ? meData.roles.map(normalizeRole).filter(Boolean)
              : [];
            if (meRoles.length > 0) {
              setAdminRoles(meRoles);
            }
          }
        } catch (_ignored) {}
        if (!data.must_reset_password) {
          loadAdminData();
        }
      } else {
        setAuthError(data.error || 'Authentication failed');
      }
    } catch (err) {
      setAuthError('Authentication failed');
    }
  };

  const handleResetPassword = async () => {
    setResetError('');
    setResetSuccess('');
    if (!resetCurrent || !resetNext || !resetConfirm) {
      setResetError('Current password and new password are required');
      return;
    }
    if (resetNext !== resetConfirm) {
      setResetError('Passwords do not match');
      return;
    }
    if (resetNext.length < 8) {
      setResetError('Password must be at least 8 characters');
      return;
    }
    setResetLoading(true);
    try {
      const res = await fetch('/api/admin/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          current_password: resetCurrent,
          new_password: resetNext,
          confirm_password: resetConfirm
        })
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || 'Failed to reset password');
      }
      setResetSuccess('Password reset successfully.');
      setMustResetPassword(false);
      setResetCurrent('');
      setResetNext('');
      setResetConfirm('');
      setShowChangePassword(false);
      loadAdminData();
    } catch (err) {
      setResetError(err.message || 'Failed to reset password');
    } finally {
      setResetLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/admin/logout', {
        method: 'POST',
        credentials: 'include',
      });
    } catch (_ignored) {}
    setIsAuthenticated(false);
    setAdminRoles([]);
    setAdminUserId(null);
    setMustResetPassword(false);
    setResetCurrent('');
    setResetNext('');
    setResetConfirm('');
    setResetError('');
    setResetSuccess('');
    setShowChangePassword(false);
    window.dispatchEvent(new Event('admin-auth-changed'));
  };

  const loadAdminData = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [requestsRes, feedbackRes, corpusRes, analyticsRes, lemmaCacheRes, searchCacheRes, frequencyCacheRes, bigramRes] = await Promise.all([
        fetch('/api/admin/requests', { credentials: 'include' }),
        fetch('/api/admin/feedback', { credentials: 'include' }),
        fetch('/api/corpus-status'),
        fetch('/api/admin/analytics', { credentials: 'include' }),
        fetch('/api/admin/lemma-cache/stats', { credentials: 'include' }),
        fetch('/api/admin/search-cache/stats', { credentials: 'include' }),
        fetch('/api/admin/frequency-cache/stats', { credentials: 'include' }),
        fetch('/api/admin/bigram-cache/stats', { credentials: 'include' })
      ]);

      const requests = await requestsRes.json();
      const feedbackData = feedbackRes.ok ? await feedbackRes.json() : [];
      const corpus = corpusRes.ok ? await corpusRes.json() : null;
      const analyticsData = analyticsRes.ok ? await analyticsRes.json() : null;
      const lemmaCache = lemmaCacheRes.ok ? await lemmaCacheRes.json() : {};
      const searchCache = searchCacheRes.ok ? await searchCacheRes.json() : {};
      const frequencyCache = frequencyCacheRes.ok ? await frequencyCacheRes.json() : {};
      const bigramData = bigramRes.ok ? await bigramRes.json() : {};

      setTextRequests(requests.requests || []);
      setFeedback(Array.isArray(feedbackData) ? feedbackData : []);
      setCorpusStats(corpus?.summary?.total_texts || null);
      setAnalytics(analyticsData);
      setCacheInfo({
        lemma_cache_size: lemmaCache.total_count || 0,
        search_cache_size: searchCache.cached_searches || 0,
        frequency_cache_size: frequencyCache.total_entries || 0
      });
      setBigramStats(bigramData);
    } catch (err) {
      console.error('Failed to load admin data:', err);
      setLoadError('Failed to load some admin data. Some statistics may be unavailable.');
    }
    setLoading(false);
  };

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto mt-12">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Admin Login</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Email</label>
              <input
                type="email"
                value={adminEmail}
                onChange={e => setAdminEmail(e.target.value)}
                className="w-full border rounded px-3 py-2"
                placeholder="Enter your admin email"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  className="w-full border rounded px-3 py-2 pr-10"
                  placeholder="Enter admin password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 text-sm"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>
            {authError && (
              <div className="text-red-600 text-sm">{authError}</div>
            )}
            <button
              onClick={handleLogin}
              className="w-full px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800"
            >
              Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return <LoadingSpinner text="Loading admin data..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Admin Panel</h2>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setResetError('');
              setResetSuccess('');
              setShowChangePassword(true);
            }}
            className="text-sm text-blue-600 hover:text-blue-700"
          >
            Change Password
          </button>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Logout
          </button>
        </div>
      </div>

      {loadError && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 flex items-start gap-3">
          <span className="text-amber-600">!</span>
          <div>
            <div className="font-medium text-amber-800">Warning</div>
            <p className="text-sm text-amber-700">{loadError}</p>
          </div>
        </div>
      )}

      {mustResetPassword && (
        <div className="bg-white rounded-lg shadow p-6 max-w-lg">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Reset Admin Password</h3>
          <p className="text-sm text-gray-600 mb-4">
            Your account requires a password reset before using the admin panel.
          </p>
          <div className="space-y-3">
            <input
              type="password"
              className="w-full border rounded px-3 py-2"
              placeholder="Current password"
              value={resetCurrent}
              onChange={(e) => setResetCurrent(e.target.value)}
            />
            <input
              type="password"
              className="w-full border rounded px-3 py-2"
              placeholder="New password"
              value={resetNext}
              onChange={(e) => setResetNext(e.target.value)}
            />
            <input
              type="password"
              className="w-full border rounded px-3 py-2"
              placeholder="Confirm new password"
              value={resetConfirm}
              onChange={(e) => setResetConfirm(e.target.value)}
            />
            {resetError && <div className="text-sm text-red-600">{resetError}</div>}
            {resetSuccess && <div className="text-sm text-green-600">{resetSuccess}</div>}
            <button
              onClick={handleResetPassword}
              disabled={resetLoading}
              className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800"
            >
              {resetLoading ? 'Updating...' : 'Update Password'}
            </button>
          </div>
        </div>
      )}

      {!mustResetPassword && (
        <div className="bg-white rounded-lg shadow">
          <div className="border-b">
            <nav className="flex overflow-x-auto">
              {['requests', 'feedback', 'users', 'sources', 'metadata', 'dictionary', 'cache', 'stats', 'analytics', 'audit', 'repository', 'settings', 'genres'].map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-3 text-xs font-medium border-b-2 whitespace-nowrap ${
                    activeTab === tab
                      ? 'border-red-700 text-red-700'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {tab === 'requests' ? 'Requests' :
                   tab === 'feedback' ? 'Feedback' :
                   tab === 'genres' ? 'Genres' :
                   tab === 'dictionary' ? 'Dictionary' :
                   tab === 'users' ? 'Users' :
                   tab === 'sources' ? 'Sources' :
                   tab === 'metadata' ? 'Metadata' :
                   tab === 'cache' ? 'Cache' :
                   tab === 'stats' ? 'Stats' :
                   tab === 'analytics' ? 'Analytics' :
                   tab === 'audit' ? 'Audit' :
                   tab === 'repository' ? 'Repository' : 'Settings'}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-4">
            {activeTab === 'requests' && (
              <RequestsTab
                authHeaders={{}}
                textRequests={textRequests}
                onRefresh={loadAdminData}
              />
            )}

          {activeTab === 'feedback' && (
            <FeedbackTab feedback={feedback} onRefresh={loadAdminData} />
          )}

            {activeTab === 'dictionary' && (
              <DictionaryReviewTab />
            )}

            {activeTab === 'genres' && (
              <GenreClassificationTab />
            )}

            {activeTab === 'users' && (
              <UsersTab
                authHeaders={{}}
                isAdmin={adminRoles.map(normalizeRole).some((r) => r === 'ADMIN' || r === 'SUPER_ADMIN')}
                isSuperAdmin={adminRoles.map(normalizeRole).includes('SUPER_ADMIN')}
                currentAdminUserId={adminUserId}
              />
            )}

            {activeTab === 'sources' && (
              <SourcesTab authHeaders={{}} />
            )}

            {activeTab === 'metadata' && (
              <MetadataTab authHeaders={{}} />
            )}

            {activeTab === 'cache' && (
              <CacheTab
                authHeaders={{}}
                cacheInfo={cacheInfo}
                bigramStats={bigramStats}
                onRefresh={loadAdminData}
                onBigramStatsUpdate={setBigramStats}
              />
            )}

            {activeTab === 'stats' && (
              <StatsTab corpusStats={corpusStats} />
            )}

            {activeTab === 'analytics' && (
              <AnalyticsTab analytics={analytics} />
            )}

            {activeTab === 'audit' && (
              <AuditTab authHeaders={{}} />
            )}

            {activeTab === 'repository' && (
              <div className="p-4 bg-gray-50 min-h-[600px] rounded-lg">
                <Repository 
                  user={{ id: adminUserId, role: adminRoles.includes('SUPER_ADMIN') ? 'SUPER_ADMIN' : 'ADMIN' }} 
                  isAdmin={true} 
                />
              </div>
            )}

            {activeTab === 'settings' && (
              <SettingsTab authHeaders={{}} />
            )}
          </div>
        </div>
      )}

      {showChangePassword && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6">
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-lg font-semibold text-gray-900">Change Admin Password</h3>
              <button
                onClick={() => setShowChangePassword(false)}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                &times;
              </button>
            </div>
            <div className="space-y-3">
              <input
                type="password"
                className="w-full border rounded px-3 py-2"
                placeholder="Current password"
                value={resetCurrent}
                onChange={(e) => setResetCurrent(e.target.value)}
              />
              <input
                type="password"
                className="w-full border rounded px-3 py-2"
                placeholder="New password"
                value={resetNext}
                onChange={(e) => setResetNext(e.target.value)}
              />
              <input
                type="password"
                className="w-full border rounded px-3 py-2"
                placeholder="Confirm new password"
                value={resetConfirm}
                onChange={(e) => setResetConfirm(e.target.value)}
              />
              {resetError && <div className="text-sm text-red-600">{resetError}</div>}
              {resetSuccess && <div className="text-sm text-green-600">{resetSuccess}</div>}
              <button
                onClick={handleResetPassword}
                disabled={resetLoading}
                className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800"
              >
                {resetLoading ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
