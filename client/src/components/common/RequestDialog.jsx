import { useCallback, useState } from 'react';
import Modal from './Modal';

/**
 * The one dialog behind every "suggest a change" entry point: the Cite
 * popup's "Report a problem with this result", the Reader's "Suggest a
 * correction", and the plain "Suggest a change" link in the footer and on
 * the Help page (requests workflow, 2026-10-08).
 *
 * It always posts to the same backend route (POST /api/feature-request),
 * which is also what files the public GitHub issue a scholar never has to
 * touch themselves. Contact details are optional and are never published --
 * only kept to reply to the person, if they give one.
 *
 * @param {boolean} isOpen
 * @param {() => void} onClose
 * @param {'result-problem'|'text-correction'|'suggestion'} [type]
 * @param {object} [context] read-only context shown in the dialog and sent
 *   with the submission (e.g. page_url, language, source, target, score,
 *   channels, search_type, settings, work, selected_text).
 * @param {boolean} [showCorrection] show the optional "Corrected text" box
 *   (the Reader's transcription-fix case).
 */
export default function RequestDialog({
  isOpen, onClose, type = 'suggestion', context, showCorrection = false,
}) {
  const [message, setMessage] = useState('');
  const [correctedText, setCorrectedText] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState(null); // null | 'sending' | 'sent' | 'error'

  // Stable identities, not redefined on every keystroke: Modal's own
  // focus-trap effect depends on [isOpen, onClose] and re-runs (stealing
  // focus back to the dialog's close button) whenever onClose's identity
  // changes, which an inline function recreated on each render would do on
  // every keystroke in this form.
  const handleClose = useCallback(() => {
    setMessage('');
    setCorrectedText('');
    setName('');
    setEmail('');
    setStatus(null);
    onClose?.();
  }, [onClose]);

  const submit = async (e) => {
    e.preventDefault();
    if (!message.trim() || status === 'sending') return;
    setStatus('sending');
    try {
      const resp = await fetch('/api/feature-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type,
          source: 'site',
          message,
          name: name.trim() || undefined,
          contact: email.trim() || undefined,
          context: context || undefined,
          current_text: showCorrection ? (context?.selected_text || undefined) : undefined,
          corrected_text: showCorrection ? (correctedText.trim() || undefined) : undefined,
        }),
      });
      if (!resp.ok) throw new Error(`status ${resp.status}`);
      setStatus('sent');
    } catch {
      setStatus('error');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={TITLES[type] || TITLES.suggestion}>
      {status === 'sent' ? (
        <div>
          <p className="text-gray-700 text-sm">
            Thank you. Your note was received.
          </p>
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              onClick={handleClose}
              className="px-3 py-1.5 text-sm rounded bg-red-700 text-white hover:bg-red-800"
            >
              Close
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <ContextBlock context={context} />
          <div>
            <label htmlFor="request-dialog-message" className="block text-sm font-medium text-gray-700 mb-1">
              {PROMPTS[type] || PROMPTS.suggestion}
            </label>
            <textarea
              id="request-dialog-message"
              required
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          {showCorrection && (
            <div>
              <label htmlFor="request-dialog-corrected" className="block text-sm font-medium text-gray-700 mb-1">
                Corrected text (optional)
              </label>
              <textarea
                id="request-dialog-corrected"
                value={correctedText}
                onChange={(e) => setCorrectedText(e.target.value)}
                rows={3}
                className="w-full border rounded px-3 py-2 text-sm font-serif"
                placeholder="What the text should say"
              />
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="request-dialog-name" className="block text-sm font-medium text-gray-700 mb-1">
                Your name (optional)
              </label>
              <input
                id="request-dialog-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label htmlFor="request-dialog-email" className="block text-sm font-medium text-gray-700 mb-1">
                Email (optional)
              </label>
              <input
                id="request-dialog-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              />
              <p className="text-[11px] text-gray-500 mt-1">Only to reply to you. Never published.</p>
            </div>
          </div>
          {status === 'error' && (
            <p className="text-sm text-red-700">Something went wrong sending this. Please try again.</p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={handleClose}
              className="px-3 py-1.5 text-sm rounded border border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={status === 'sending'}
              className="px-3 py-1.5 text-sm rounded bg-red-700 text-white hover:bg-red-800 disabled:opacity-50"
            >
              {status === 'sending' ? 'Sending…' : 'Send'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

const TITLES = {
  'result-problem': 'Report a problem with this result',
  'text-correction': 'Suggest a correction',
  suggestion: 'Suggest a change',
};

const PROMPTS = {
  'result-problem': 'What is wrong, or what could be better?',
  'text-correction': 'What is wrong, or what should the text say?',
  suggestion: 'What would you like to see?',
};

// Order mirrors how the backend reads this same object into the issue body
// (backend/blueprints/feature_request.py _format_context), so what the
// scholar sees here matches what ends up filed.
const CONTEXT_FIELDS = [
  ['page_url', 'Page'],
  ['language', 'Language'],
  ['search_type', 'Search type'],
  ['settings', 'Settings'],
  ['source', 'Source'],
  ['target', 'Target'],
  ['refs', 'Line refs'],
  ['score', 'Score'],
  ['channels', 'Channels'],
  ['work', 'Work'],
  ['selected_text', 'Selected text'],
];

function ContextBlock({ context }) {
  const entries = CONTEXT_FIELDS
    .map(([key, label]) => [label, context?.[key]])
    .filter(([, v]) => v !== undefined && v !== null && v !== '');
  if (entries.length === 0) return null;
  return (
    <div className="bg-gray-50 border border-gray-200 rounded p-3 text-xs text-gray-600 space-y-1">
      {entries.map(([label, value]) => (
        <div key={label}>
          <span className="font-medium text-gray-700">{label}:</span> {String(value)}
        </div>
      ))}
    </div>
  );
}
