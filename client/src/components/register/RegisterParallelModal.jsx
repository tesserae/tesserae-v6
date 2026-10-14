// The Save Parallel dialog and what it does (moved out of App.jsx, cleaning
// job H4, 2026-10-13, code unchanged): the state of the dialog, the sign-in
// prompt for a visitor who is signed out, the request that saves the
// parallel, and the dialog's markup.
import { useState, useCallback } from 'react';
import { Modal } from '../common';

export const useRegisterParallel = ({ user, activeTab, setPageType }) => {
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [registerPending, setRegisterPending] = useState(null);
  const [registerScore, setRegisterScore] = useState(0);
  const [registerNotes, setRegisterNotes] = useState('');
  const [registerVisibility, setRegisterVisibility] = useState('private');

  const handleRegister = useCallback((result) => {
    if (!user) {
      window.dispatchEvent(new CustomEvent('open-public-auth-modal', {
        detail: {
          mode: 'login',
          message: 'Sign in',
        }
      }));
      return;
    }
    setRegisterPending(result);
    setRegisterScore(0);
    setRegisterVisibility('private');
    setShowRegisterModal(true);
  }, [user]);

  const handleSubmitRegister = useCallback(async () => {
    if (!registerPending) return;
    if (!Number.isInteger(registerScore) || registerScore < 1 || registerScore > 5) {
      alert('Please select a star rating before saving.');
      return;
    }
    try {
      const sourceLocus = registerPending.source_locus || registerPending.source?.ref || '';
      const sourceText = registerPending.source_text || registerPending.source_snippet || registerPending.source?.text || '';
      const targetLocus = registerPending.target_locus || registerPending.target?.ref || '';
      const targetText = registerPending.target_text || registerPending.target_snippet || registerPending.target?.text || '';
      const sourceTextId = registerPending.source_text_id || registerPending.source?.text_id || sourceText?.split(' ')[0] || 'unknown';
      const targetTextId = registerPending.target_text_id || registerPending.target?.text_id || targetText?.split(' ')[0] || 'unknown';
      // A cross-language card carries its own two languages (they differ by
      // definition); every other card shares the one language on screen.
      // source_language/target_language are independent columns already
      // (backend/models.py Intertext and SavedIntertext), so this needs no
      // schema change.
      const sourceLanguage = registerPending.source_language || registerPending.source?.language || activeTab;
      const targetLanguage = registerPending.target_language || registerPending.target?.language || activeTab;

      const matchedLemmas = (registerPending.matched_words || []).map(w => {
        if (typeof w !== 'object') return w;
        return w.lemma || w.word || w.source_lemma || w.target_lemma || w.display || '';
      }).filter(Boolean);
      // The channels a cross-language card found the parallel through (e.g.
      // "semantic (85%), dictionary (3 words)"), carried into the existing
      // free-text tags field so a registered cross-language parallel keeps
      // that evidence on record (spec: owner's review, 2026-10-08).
      // A fusion-search row carries its channels as a list of names
      // (['lemma', 'semantic']); a cross-language card as one string. Saving a
      // fusion row failed with ".split is not a function" until 2026-10-13,
      // found by the render recording made for the App.jsx split (#901).
      const rawChannels = registerPending.channels || '';
      const channelTags = (Array.isArray(rawChannels) ? rawChannels.map(String) : String(rawChannels).split(','))
        .map(s => s.trim()).filter(Boolean);

      const res = await fetch('/api/intertexts/my', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: {
            text_id: sourceTextId,
            author: registerPending.source_author || registerPending.source?.author || '',
            work: registerPending.source_work || registerPending.source?.work || '',
            reference: sourceLocus,
            snippet: sourceText,
            language: sourceLanguage
          },
          target: {
            text_id: targetTextId,
            author: registerPending.target_author || registerPending.target?.author || '',
            work: registerPending.target_work || registerPending.target?.work || '',
            reference: targetLocus,
            snippet: targetText,
            language: targetLanguage
          },
          matched_lemmas: matchedLemmas,
          tags: channelTags,
          tesserae_score: registerPending.score || registerPending.overall_score || 0,
          intertext_score: registerScore,
          notes: registerNotes.trim().slice(0, 500),
          share_to_public: registerVisibility === 'public',
        })
      });
      
      if (!res.ok) {
        const err = await res.json();
        alert('Failed to register: ' + (err.error || 'Unknown error'));
        return;
      }
      
      setShowRegisterModal(false);
      setRegisterPending(null);
      setRegisterScore(0);
      setRegisterNotes('');
      setRegisterVisibility('private');
      setPageType('repository');
      window.history.pushState({}, '', '/repository');
    } catch (err) {
      console.error('Failed to register intertext:', err);
      alert('Failed to register intertext: ' + err.message);
    }
  }, [registerPending, activeTab, registerScore, registerNotes, registerVisibility, setPageType]);

  return {
    showRegisterModal, setShowRegisterModal, registerPending, setRegisterPending,
    registerScore, setRegisterScore, registerNotes, setRegisterNotes,
    registerVisibility, setRegisterVisibility, handleRegister, handleSubmitRegister,
  };
};

const RegisterParallelModal = ({ register }) => {
  const {
    showRegisterModal, setShowRegisterModal, setRegisterPending,
    registerPending, registerScore, setRegisterScore, registerNotes, setRegisterNotes,
    registerVisibility, setRegisterVisibility, handleSubmitRegister,
  } = register;
  return (
    <Modal
      isOpen={showRegisterModal}
      onClose={() => {
        setShowRegisterModal(false);
        setRegisterPending(null);
        setRegisterScore(0);
        setRegisterNotes('');
        setRegisterVisibility('private');
      }}
      title="Save Parallel"
    >
      {registerPending && (() => {
        const sourceLocus = registerPending.source_locus || registerPending.source?.ref || '';
        const sourceText = registerPending.source_text || registerPending.source_snippet || registerPending.source?.text || '';
        const targetLocus = registerPending.target_locus || registerPending.target?.ref || '';
        const targetText = registerPending.target_text || registerPending.target_snippet || registerPending.target?.text || '';
        return (
        <div className="space-y-4">
          <p className="text-gray-600">
            Save this parallel to your repository, with the option to keep it private or make it public.
          </p>
          <div className="bg-gray-50 p-4 rounded">
            <div className="text-sm text-gray-500 mb-1">Source</div>
            <div className="font-medium text-red-700">{sourceLocus}</div>
            <div className="text-sm text-gray-700 mt-1">{sourceText?.substring(0, 100)}{sourceText?.length > 100 ? '...' : ''}</div>
            <div className="text-sm text-gray-500 mt-3 mb-1">Target</div>
            <div className="font-medium text-amber-600">{targetLocus}</div>
            <div className="text-sm text-gray-700 mt-1">{targetText?.substring(0, 100)}{targetText?.length > 100 ? '...' : ''}</div>
          </div>
          <div className="mt-4">
            <div className="text-sm text-gray-600 mb-2">Visibility:</div>
            <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
              <button
                type="button"
                onClick={() => setRegisterVisibility('private')}
                className={`px-3 py-1.5 text-sm rounded ${
                  registerVisibility === 'private'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                Private
              </button>
              <button
                type="button"
                onClick={() => setRegisterVisibility('public')}
                className={`px-3 py-1.5 text-sm rounded ${
                  registerVisibility === 'public'
                    ? 'bg-white text-red-700 shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                Make Public
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              {registerVisibility === 'public'
                ? 'This parallel will appear in the public repository and stay in your personal repository.'
                : 'This parallel will only appear in your personal repository.'}
            </p>
          </div>
          <div className="mt-4">
            <div className="text-sm text-gray-600 mb-2">Rate this parallel:</div>
            <div className="flex gap-1">
              {[1,2,3,4,5].map(star => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRegisterScore(star)}
                  className={`text-2xl ${star <= registerScore ? 'text-yellow-500' : 'text-gray-300'} hover:text-yellow-400 transition-colors`}
                >
                  ★
                </button>
              ))}
              <span className="ml-2 text-sm text-gray-500 self-center">
                {registerScore > 0 ? `${registerScore}/5` : 'Required'}
              </span>
            </div>
          </div>
          <div className="mt-4">
            <label className="text-sm text-gray-600 mb-2 block">
              Notes (optional, max 500 characters):
            </label>
            <textarea
              value={registerNotes}
              onChange={(e) => setRegisterNotes(e.target.value.slice(0, 500))}
              placeholder="Add scholarly commentary, interpretation, or notes about this parallel..."
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent resize-none"
              rows={3}
              maxLength={500}
            />
            <div className="text-xs text-gray-500 text-right mt-1">
              {registerNotes.length}/500
            </div>
          </div>
          <div className="flex gap-3 justify-end">
            <button
              onClick={() => {
                setShowRegisterModal(false);
                setRegisterPending(null);
                setRegisterScore(0);
                setRegisterNotes('');
                setRegisterVisibility('private');
              }}
              className="px-4 py-2 bg-gray-100 text-gray-700 border border-gray-300 rounded hover:bg-gray-200"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmitRegister}
              disabled={registerScore < 1}
              className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Save Parallel
            </button>
          </div>
        </div>
        );
      })()}
    </Modal>
  );
};

export default RegisterParallelModal;
