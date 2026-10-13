// Whether an administrator is signed in on this browser: asked at load, on
// window focus and when the admin panel says the session changed (moved out
// of App.jsx, cleaning job H4, 2026-10-13, code unchanged).
import { useState, useEffect } from 'react';

export const useAdminSession = () => {
  const [adminSessionActive, setAdminSessionActive] = useState(false);
  const [adminSessionChecked, setAdminSessionChecked] = useState(false);
  useEffect(() => {
    let mounted = true;

    const checkAdminSession = async () => {
      try {
        const res = await fetch('/api/admin/me', { credentials: 'include' });
        if (mounted) {
          setAdminSessionActive(res.ok);
          setAdminSessionChecked(true);
        }
      } catch (_err) {
        if (mounted) {
          setAdminSessionActive(false);
          setAdminSessionChecked(true);
        }
      }
    };

    const handleAdminAuthChanged = () => {
      checkAdminSession();
    };

    checkAdminSession();
    window.addEventListener('focus', handleAdminAuthChanged);
    window.addEventListener('admin-auth-changed', handleAdminAuthChanged);

    return () => {
      mounted = false;
      window.removeEventListener('focus', handleAdminAuthChanged);
      window.removeEventListener('admin-auth-changed', handleAdminAuthChanged);
    };
  }, []);

  return { adminSessionActive, adminSessionChecked };
};

export default useAdminSession;
