import { useState } from 'react';

const API_BASE = '/api';

export default function RegisterUserTestPage({ setUser }) {
  const [mode, setMode] = useState('register');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);

    if (mode === 'register' && password !== confirmPassword) {
      setResult({
        ok: false,
        data: { error: 'Passwords do not match' },
      });
      setLoading(false);
      return;
    }

    try {
      const endpoint = mode === 'register' ? '/auth/register' : '/auth/login';
      const payload =
        mode === 'register'
          ? {
              email: email.trim(),
              password,
              first_name: firstName.trim(),
              last_name: lastName.trim(),
            }
          : {
              email: email.trim(),
              password,
            };

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data?.success && data?.user) {
        const userData = data.user;
        userData.name =
          userData.orcid_name ||
          `${userData.first_name || ''} ${userData.last_name || ''}`.trim() ||
          'Account';
        if (setUser) setUser(userData);
      }
      setResult({ ok: res.ok && Boolean(data?.success), data });
    } catch (err) {
      setResult({
        ok: false,
        data: { error: err?.message || `Failed to reach /api/auth/${mode}` },
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-2">Auth User Test</h2>
      <p className="text-sm text-gray-600 mb-5">
        Hidden test route for Marvin password auth (register + sign in). Not linked in navigation.
      </p>

      <div className="mb-5 flex gap-2">
        <button
          type="button"
          onClick={() => {
            setMode('register');
            setResult(null);
          }}
          className={`px-3 py-1.5 rounded text-sm ${
            mode === 'register' ? 'bg-red-700 text-white' : 'bg-gray-100 text-gray-700'
          }`}
        >
          Register
        </button>
        <button
          type="button"
          onClick={() => {
            setMode('login');
            setResult(null);
          }}
          className={`px-3 py-1.5 rounded text-sm ${
            mode === 'login' ? 'bg-red-700 text-white' : 'bg-gray-100 text-gray-700'
          }`}
        >
          Sign In
        </button>
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
            placeholder="user@example.com"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
          <input
            type="password"
            minLength={8}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
            placeholder={mode === 'register' ? 'Min 8, upper/lower/number/special' : 'Your password'}
          />
          {mode === 'register' && (
            <p className="text-xs text-gray-500 mt-1">
              Must include at least one uppercase letter, one lowercase letter, one number, and one special character.
            </p>
          )}
        </div>

        {mode === 'register' && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
              <input
                type="password"
                minLength={8}
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="Confirm your password"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="w-full border rounded px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="w-full border rounded px-3 py-2 text-sm"
                />
              </div>
            </div>
          </>
        )}

        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
        >
          {loading ? (mode === 'register' ? 'Registering...' : 'Signing in...') : (mode === 'register' ? 'Test Register' : 'Test Sign In')}
        </button>
      </form>

      {result && (
        <div
          className={`mt-5 p-3 rounded text-sm ${
            result.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
          }`}
        >
          <div className="font-medium mb-1">{result.ok ? 'Success' : 'Failed'}</div>
          <pre className="whitespace-pre-wrap break-words">
            {JSON.stringify(result.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
