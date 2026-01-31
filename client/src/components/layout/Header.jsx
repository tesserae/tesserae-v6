import { useState, useEffect, useRef } from 'react';
import { fetchAuthStatus } from '../../utils/api';

const Header = ({ user, setUser }) => {
  const [showDropdown, setShowDropdown] = useState(false);
  const [showOrcidModal, setShowOrcidModal] = useState(false);
  const [orcidInput, setOrcidInput] = useState('');
  const [orcidNameInput, setOrcidNameInput] = useState('');
  const [orcidLinking, setOrcidLinking] = useState(false);
  const [orcidError, setOrcidError] = useState(null);
  const [authEnabled, setAuthEnabled] = useState(true);
  const dropdownRef = useRef(null);

  useEffect(() => {
    fetchAuthStatus()
      .then(data => {
        if (data.auth_enabled !== undefined) {
          setAuthEnabled(data.auth_enabled);
        }
        if (data.authenticated) {
          setUser(data.user);
        }
      })
      .catch(() => {
        setAuthEnabled(false);
      });
  }, [setUser]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const linkOrcid = async () => {
    if (!orcidInput.trim()) {
      setOrcidError('Please enter your ORCID');
      return;
    }
    setOrcidLinking(true);
    setOrcidError(null);
    try {
      const res = await fetch('/api/auth/orcid/link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          orcid: orcidInput.trim(),
          orcid_name: orcidNameInput.trim()
        })
      });
      const data = await res.json();
      if (data.success) {
        setUser({ ...user, orcid: orcidInput.trim(), orcid_name: orcidNameInput.trim() });
        setShowOrcidModal(false);
        setOrcidInput('');
        setOrcidNameInput('');
      } else {
        setOrcidError(data.error || 'Failed to link ORCID');
      }
    } catch (e) {
      setOrcidError('Failed to link ORCID');
    }
    setOrcidLinking(false);
  };

  const unlinkOrcid = async () => {
    if (!confirm('Remove your ORCID from this account?')) return;
    try {
      const res = await fetch('/api/auth/orcid/unlink', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setUser({ ...user, orcid: null, orcid_name: null });
      }
    } catch (e) {
      alert('Failed to unlink ORCID');
    }
  };

  return (
    <>
      <header className="bg-gradient-to-r from-red-800 via-red-700 to-orange-600 shadow-lg">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 sm:py-5 flex justify-between items-center">
          <div className="flex items-center gap-2 sm:gap-4">
            <img src="/tesserae-icon.jpg" alt="Tesserae" className="h-10 w-10 sm:h-14 sm:w-14 rounded-full" />
            <div>
              <h1 className="tesserae-title text-2xl sm:text-4xl font-semibold text-white tracking-wide">
                TESSERAE
              </h1>
              <p className="text-orange-100 text-xs sm:text-sm mt-0.5 hidden sm:block">
                Intertextual and Literary Discovery
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {user ? (
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setShowDropdown(!showDropdown)}
                  className="flex items-center gap-2 bg-white/10 hover:bg-white/20 px-3 py-2 rounded text-white text-sm"
                >
                  <div className="text-left">
                    <div className="font-medium">{user.name || user.orcid_name || `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'Account'}</div>
                    {user.orcid && (
                      <div className="text-xs text-orange-200 flex items-center gap-1">
                        <img src="https://orcid.org/assets/vectors/orcid.logo.icon.svg" alt="" className="w-3 h-3" />
                        {user.orcid}
                      </div>
                    )}
                  </div>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                
                {showDropdown && (
                  <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border z-50">
                    <div className="p-3 border-b">
                      <p className="font-medium text-gray-900">{user.name || user.orcid_name || `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'Account'}</p>
                      <p className="text-xs text-gray-500">{user.email || 'Signed in with Replit'}</p>
                    </div>
                    
                    <div className="p-2">
                      {user.orcid ? (
                        <div className="px-3 py-2 text-sm">
                          <div className="flex items-center justify-between">
                            <span className="text-gray-600">ORCID:</span>
                            <a 
                              href={`https://orcid.org/${user.orcid}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-green-600 hover:underline text-xs"
                            >
                              {user.orcid}
                            </a>
                          </div>
                          <button
                            onClick={unlinkOrcid}
                            className="text-xs text-red-500 hover:text-red-700 mt-1"
                          >
                            Unlink ORCID
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => { setShowOrcidModal(true); setShowDropdown(false); }}
                          className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
                        >
                          Link ORCID for Attribution
                        </button>
                      )}
                    </div>
                    
                    <div className="border-t p-2">
                      <a
                        href="/api/auth/logout"
                        className="block w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
                      >
                        Sign out
                      </a>
                    </div>
                  </div>
                )}
              </div>
            ) : authEnabled ? (
              <a 
                href="/api/auth/login" 
                className="flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white px-3 py-2 rounded text-sm"
              >
                <span>Sign in</span>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </a>
            ) : null}
          </div>
        </div>
      </header>

      {showOrcidModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-900">Link ORCID</h3>
              <button
                onClick={() => { setShowOrcidModal(false); setOrcidError(null); }}
                className="text-gray-400 hover:text-gray-600"
              >
                &times;
              </button>
            </div>
            
            <p className="text-sm text-gray-600 mb-4">
              Link your ORCID iD for proper attribution when you contribute parallels to the repository.
            </p>
            
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">ORCID iD</label>
                <input
                  type="text"
                  value={orcidInput}
                  onChange={(e) => setOrcidInput(e.target.value)}
                  placeholder="0000-0002-1234-5678"
                  className="w-full border rounded px-3 py-2 text-sm"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name (as it appears on ORCID)</label>
                <input
                  type="text"
                  value={orcidNameInput}
                  onChange={(e) => setOrcidNameInput(e.target.value)}
                  placeholder="Your name"
                  className="w-full border rounded px-3 py-2 text-sm"
                />
              </div>
              
              {orcidError && (
                <p className="text-sm text-red-600">{orcidError}</p>
              )}
              
              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => { setShowOrcidModal(false); setOrcidError(null); }}
                  className="flex-1 px-4 py-2 border rounded text-gray-700 hover:bg-gray-50 text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={linkOrcid}
                  disabled={orcidLinking}
                  className="flex-1 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 text-sm"
                >
                  {orcidLinking ? 'Linking...' : 'Link ORCID'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default Header;
