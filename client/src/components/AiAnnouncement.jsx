import { useState } from 'react';

// Dismissible banner announcing the "use your own AI with Tesserae" option.
// Links to the setup hub; dismissal persists via localStorage.
const KEY = 'tesserae_ai_banner_dismissed_v1';

const AiAnnouncement = () => {
  const [hidden, setHidden] = useState(() => {
    try { return localStorage.getItem(KEY) === '1'; } catch { return false; }
  });
  if (hidden) return null;

  const dismiss = () => {
    try { localStorage.setItem(KEY, '1'); } catch { /* ignore */ }
    setHidden(true);
  };

  return (
    <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 flex items-start gap-3">
      <span className="text-lg leading-none mt-0.5" aria-hidden="true">✨</span>
      <div className="flex-1 text-sm text-amber-900">
        <strong>New — use your own AI with Tesserae.</strong>{' '}
        Have ChatGPT or Claude run searches and help interpret the results.{' '}
        <a
          href="/tesserae-data/tesserae-ai-setup.html"
          target="_blank"
          rel="noopener noreferrer"
          className="font-semibold underline hover:text-amber-700"
        >
          Set it up →
        </a>{' '}
        <span className="text-amber-800">(Claude gives the fullest capabilities.)</span>
      </div>
      <button
        onClick={dismiss}
        className="text-amber-700 hover:text-amber-900 text-xl leading-none px-1 -mt-1"
        aria-label="Dismiss announcement"
      >
        ×
      </button>
    </div>
  );
};

export default AiAnnouncement;
