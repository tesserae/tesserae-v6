import { useEffect, useState } from 'react';

const roleLabel = (role) => {
  if (!role) return '';
  const value = typeof role === 'string' ? role : role.name;
  if (!value) return '';
  return value.replace(/_/g, ' ');
};

export default function UsersTab({ authHeaders, isAdmin = false, isSuperAdmin = false, currentAdminUserId = null }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  const [busyUserId, setBusyUserId] = useState(null);
  const [createEmail, setCreateEmail] = useState('');
  const [createFirstName, setCreateFirstName] = useState('');
  const [createLastName, setCreateLastName] = useState('');
  const [createPassword, setCreatePassword] = useState('');
  const [createRole, setCreateRole] = useState('USER');
  const [createError, setCreateError] = useState(null);
  const [createSuccess, setCreateSuccess] = useState(null);

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    setActionError(null);
    setActionSuccess(null);

    try {
      const [usersRes, rolesRes] = await Promise.all([
        fetch('/api/admin/users', { headers: authHeaders, credentials: 'include' }),
        fetch('/api/admin/roles', { headers: authHeaders, credentials: 'include' })
      ]);

      if (!usersRes.ok) {
        throw new Error('Unable to load users. Backend endpoint not available yet.');
      }

      const usersPayload = await usersRes.json();
      const rolesPayload = rolesRes.ok ? await rolesRes.json() : null;

      setUsers(usersPayload.users || []);
      setRoles(Array.isArray(rolesPayload?.roles) ? rolesPayload.roles : []);
    } catch (err) {
      setError(err.message || 'Failed to load users.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setCreateError(null);
    setCreateSuccess(null);

    try {
      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders
        },
        credentials: 'include',
        body: JSON.stringify({
          email: createEmail.trim(),
          first_name: createFirstName.trim(),
          last_name: createLastName.trim(),
          password: createPassword,
          role: createRole
        })
      });

      const payload = await res.json();
      if (!res.ok || payload.error) {
        throw new Error(payload.error || 'Failed to create user.');
      }

      setCreateSuccess(`User created with role ${payload.role}. They must reset their password on first login.`);
      setCreateEmail('');
      setCreateFirstName('');
      setCreateLastName('');
      setCreatePassword('');
      setCreateRole('USER');
      await loadUsers();
    } catch (err) {
      setCreateError(err.message || 'Failed to create user.');
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const submitRoleChange = async (userId, roleName, action) => {
    setActionError(null);
    setActionSuccess(null);
    setBusyUserId(userId);

    try {
      const res = await fetch(`/api/admin/users/${userId}/roles`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders
        },
        credentials: 'include',
        body: JSON.stringify({ role: roleName, action })
      });

      const payload = await res.json();
      if (!res.ok || payload.error) {
        throw new Error(payload.error || 'Role update failed.');
      }

      setActionSuccess(payload.message || 'Role updated successfully.');
      setUsers((prev) =>
        prev.map((user) => {
          if (user.id !== userId) {
            return user;
          }
          const currentRoles = Array.isArray(user.roles)
            ? user.roles.map((r) => (typeof r === 'string' ? r : r.name)).filter(Boolean)
            : [];
          let nextRoles = currentRoles.slice();
          if (action === 'add' && !nextRoles.includes(roleName)) {
            nextRoles.push(roleName);
          }
          if (action === 'remove') {
            nextRoles = nextRoles.filter((role) => role !== roleName);
          }
          return {
            ...user,
            roles: nextRoles
          };
        })
      );
    } catch (err) {
      setActionError(err.message || 'Role update failed.');
    } finally {
      setBusyUserId(null);
    }
  };

  const deleteUser = async (userId, email) => {
    setActionError(null);
    setActionSuccess(null);
    if (!window.confirm(`Delete user ${email || userId}? This cannot be undone.`)) {
      return;
    }
    setBusyUserId(userId);
    try {
      const res = await fetch(`/api/admin/users/${userId}`, {
        method: 'DELETE',
        headers: {
          ...authHeaders
        },
        credentials: 'include'
      });
      const payload = await res.json();
      if (!res.ok || payload.error) {
        throw new Error(payload.error || 'Failed to delete user.');
      }
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      setActionSuccess(payload.message || 'User deleted.');
    } catch (err) {
      setActionError(err.message || 'Failed to delete user.');
    } finally {
      setBusyUserId(null);
    }
  };

  if (loading) {
    return (
      <div className="text-sm text-gray-500">Loading users...</div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Users & Roles</h3>
          <p className="text-sm text-gray-500">
            Manage user accounts. Admin role changes remain restricted.
          </p>
        </div>
        <button
          onClick={loadUsers}
          className="text-sm text-gray-600 hover:text-gray-800"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {actionError && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
          {actionError}
        </div>
      )}

      {actionSuccess && (
        <div className="bg-green-50 border border-green-200 rounded p-3 text-sm text-green-700">
          {actionSuccess}
        </div>
      )}

      {isAdmin && (
        <div className="bg-gray-50 border border-gray-200 rounded p-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-2">Create User</h4>
          <p className="text-xs text-gray-500 mb-3">
            Required fields: first name, last name, email, and password.
          </p>
          <form onSubmit={handleCreateUser} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input
              type="text"
              className="border rounded px-3 py-2 text-sm"
              placeholder="First name"
              value={createFirstName}
              onChange={(e) => setCreateFirstName(e.target.value)}
              required
            />
            <input
              type="text"
              className="border rounded px-3 py-2 text-sm"
              placeholder="Last name"
              value={createLastName}
              onChange={(e) => setCreateLastName(e.target.value)}
              required
            />
            <input
              type="email"
              className="border rounded px-3 py-2 text-sm"
              placeholder="Email"
              value={createEmail}
              onChange={(e) => setCreateEmail(e.target.value)}
              required
            />
            <input
              type="password"
              className="border rounded px-3 py-2 text-sm"
              placeholder="Temporary password"
              value={createPassword}
              onChange={(e) => setCreatePassword(e.target.value)}
              minLength={8}
              required
            />
            <select
              className="border rounded px-3 py-2 text-sm"
              value={createRole}
              onChange={(e) => setCreateRole(e.target.value)}
            >
              <option value="USER">USER</option>
              {isSuperAdmin && <option value="ADMIN">ADMIN</option>}
              {isSuperAdmin && <option value="SUPER_ADMIN">SUPER_ADMIN</option>}
            </select>
            <button
              type="submit"
              className="bg-red-700 text-white rounded px-3 py-2 text-sm hover:bg-red-800"
            >
              Create User
            </button>
          </form>
          {createError && (
            <div className="mt-3 text-xs text-red-600">{createError}</div>
          )}
          {createSuccess && (
            <div className="mt-3 text-xs text-green-600">{createSuccess}</div>
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="py-2 pr-4">User</th>
              <th className="py-2 pr-4">Email</th>
              <th className="py-2 pr-4">Roles</th>
              <th className="py-2 pr-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 && (
              <tr>
                <td className="py-3 text-gray-500" colSpan={4}>
                  No users returned yet.
                </td>
              </tr>
            )}
            {users.map(user => {
              const userRoles = Array.isArray(user.roles) ? user.roles : [];
              const normalizedRoles = userRoles.map(r => (typeof r === 'string' ? r : r.name)).filter(Boolean);
              const effectiveRoles = normalizedRoles.length > 0 ? normalizedRoles : ['USER'];
              const hasRole = (roleName) => effectiveRoles.includes(roleName);
              const isUserOnly = effectiveRoles.length === 1 && effectiveRoles[0] === 'USER';

              return (
                <tr key={user.id} className="border-b">
                  <td className="py-3 pr-4 text-gray-900">
                    {user.name || '-'}
                  </td>
                  <td className="py-3 pr-4 text-gray-700">{user.email}</td>
                  <td className="py-3 pr-4 text-gray-700">
                    {effectiveRoles.map(roleLabel).join(', ')}
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex flex-wrap gap-2 items-center">
                      {isSuperAdmin ? (
                        isUserOnly ? (
                          <span className="text-xs text-gray-500">
                            Role changes restricted for USER accounts
                          </span>
                        ) : (
                          <>
                            <button
                              disabled={busyUserId === user.id || hasRole('ADMIN')}
                              onClick={() => submitRoleChange(user.id, 'ADMIN', 'add')}
                              className="text-xs px-2 py-1 rounded bg-blue-50 text-blue-700 border border-blue-200 disabled:opacity-50"
                            >
                              Promote to ADMIN
                            </button>
                            <button
                              disabled={busyUserId === user.id || hasRole('SUPER_ADMIN')}
                              onClick={() => submitRoleChange(user.id, 'SUPER_ADMIN', 'add')}
                              className="text-xs px-2 py-1 rounded bg-purple-50 text-purple-700 border border-purple-200 disabled:opacity-50"
                            >
                              Promote to SUPER_ADMIN
                            </button>
                            <button
                              disabled={busyUserId === user.id || !hasRole('ADMIN')}
                              onClick={() => submitRoleChange(user.id, 'ADMIN', 'remove')}
                              className="text-xs px-2 py-1 rounded bg-amber-50 text-amber-700 border border-amber-200 disabled:opacity-50"
                            >
                              Demote ADMIN
                            </button>
                            <button
                              disabled={busyUserId === user.id || !hasRole('SUPER_ADMIN')}
                              onClick={() => submitRoleChange(user.id, 'SUPER_ADMIN', 'remove')}
                              className="text-xs px-2 py-1 rounded bg-red-50 text-red-700 border border-red-200 disabled:opacity-50"
                            >
                              Demote SUPER_ADMIN
                            </button>
                          </>
                        )
                      ) : (
                        <span className="text-xs text-gray-500">
                          Role updates require SUPER_ADMIN
                        </span>
                      )}
                      <button
                        disabled={busyUserId === user.id || String(currentAdminUserId || '') === String(user.id)}
                        onClick={() => deleteUser(user.id, user.email)}
                        className="text-xs px-2 py-1 rounded bg-red-50 text-red-700 border border-red-200 disabled:opacity-50"
                      >
                        {String(currentAdminUserId || '') === String(user.id) ? 'Current account' : 'Delete User'}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {roles.length > 0 && (
        <div className="text-xs text-gray-400">
          Available roles: {roles.map(roleLabel).join(', ')}
        </div>
      )}
    </div>
  );
}
