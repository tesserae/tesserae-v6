import { useEffect, useRef, useState } from 'react';
import useAssistantStream from './useAssistantStream';

// Openers that show what it can actually DO, not only what it can explain. It
// runs searches now, so "where does this phrase appear" gets real loci back.
/** The answer with the matched words marked.
 *
 *  A listing of six lines of Latin with nothing marked makes the reader hunt for
 *  what actually matched. The server sends the phrase it searched for and the
 *  inflected forms the variant pass found, so both can be shown.
 */
function mark(text, terms) {
  const list = (terms || []).filter((t) => t && t.length > 3);
  if (!text || !list.length) return text;
  const escaped = list.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  // Longest first, so "arma virumque" wins over "arma".
  escaped.sort((a, b) => b.length - a.length);
  const re = new RegExp(`(${escaped.join('|')})`, 'gi');
  const wanted = new Set(list.map((t) => t.toLowerCase()));
  // NOT re.test(): a /g regex carries lastIndex between calls, so testing the
  // pieces of a split alternates true and false and roughly half the matches
  // went unmarked. Membership is the whole question here anyway.
  return text.split(re).map((part, i) =>
    wanted.has(String(part).toLowerCase())
      ? <mark key={i} className="bg-yellow-200 rounded-sm px-0.5">{part}</mark>
      : part);
}

const OPENERS = [
  'Where does the phrase arma virumque appear?',
  'What Hebrew texts are in the corpus?',
  // Replaces the banner that used to sit across the top of every page. The
  // same thing is worth telling people, but as something they can ask rather
  // than something that occupies the site whether they care or not.
  'How can I use my AI agent with Tesserae?',
  'What is the difference between lemma and exact search?',
];

/**
 * The assistant's guide half: a docked panel available on every page.
 *
 * It recommends searches and explains what the tools do. It does not answer
 * questions about literature, and the closing note says so, because a scholar
 * needs to know which of its sentences carry authority. Result analysis lives
 * with the results instead, where the evidence is.
 *
 * The panel hides itself when the model is not running rather than showing a
 * dead control. The searches are the product; this is help on top of them.
 */
export default function AssistantDock() {
  const [available, setAvailable] = useState(false);
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState([]);
  const [draft, setDraft] = useState('');
  const { text, step, running, error, highlight, run } = useAssistantStream();
  const scrollRef = useRef(null);

  useEffect(() => {
    fetch('/api/assistant/status')
      .then((r) => r.json())
      .then((d) => setAvailable(Boolean(d.available)))
      .catch(() => setAvailable(false));
  }, []);

  // Fold a finished answer into the transcript so the next question starts clean.
  const prevRunning = useRef(false);
  useEffect(() => {
    if (prevRunning.current && !running && text) {
      setTurns((t) => [...t, { role: 'assistant', text }]);
    }
    prevRunning.current = running;
  }, [running, text]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [turns, text]);

  if (!available) return null;

  const ask = (q) => {
    const question = (q || '').trim();
    if (!question || running) return;
    // Send the conversation so far. A follow-up like "is it in Eobanus?" is
    // unanswerable without the turn that named the phrase, and the assistant
    // used to respond by telling the user to run the search themselves.
    const history = turns.slice(-8).map((t) => ({ role: t.role, text: t.text }));
    setTurns((t) => [...t, { role: 'user', text: question }]);
    setDraft('');
    run('/api/assistant/ask-stream', { question, history });
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="Open Tessa, the AI assistant"
        className="fixed bottom-6 right-6 z-40 flex items-center gap-3 pl-3 pr-5 py-3 rounded-2xl bg-red-700 text-white shadow-xl ring-1 ring-red-900/20 transition hover:bg-red-800 hover:shadow-2xl focus:outline-none focus:ring-2 focus:ring-red-400"
      >
        <span className="flex items-center justify-center w-9 h-9 rounded-xl bg-white/15 text-lg font-semibold leading-none">
          T
        </span>
        <span className="text-left leading-tight">
          <span className="block text-base font-semibold">Tessa</span>
          <span className="block text-[11px] font-medium text-red-100">
            AI Assistant &middot; ask the corpus
          </span>
        </span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-5 right-5 z-40 w-[24rem] max-w-[calc(100vw-2.5rem)] rounded-lg border border-gray-300 bg-white shadow-xl flex flex-col max-h-[min(32rem,calc(100vh-3rem))]">
      <header className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-800">
          <span className="flex items-center justify-center w-6 h-6 rounded-md bg-red-700 text-white text-xs font-semibold leading-none">
            T
          </span>
          Tessa AI Assistant
        </h2>
        <button
          onClick={() => setOpen(false)}
          className="text-gray-400 hover:text-gray-700 text-lg leading-none px-1"
          aria-label="Close Tessa"
        >
          ×
        </button>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {turns.length === 0 && !running && (
          <>
            <p className="text-sm text-gray-600 leading-relaxed">
              Ask a question and I will run searches to answer it. I can tell you
              where a phrase occurs, what the corpus holds in a language, and
              which searches are worth trying.
            </p>
            <div className="flex flex-col gap-1.5">
              {OPENERS.map((q) => (
                <button
                  key={q}
                  onClick={() => ask(q)}
                  className="text-left text-xs text-red-700 hover:text-red-900 hover:bg-red-50 rounded px-2 py-1.5 border border-gray-200"
                >
                  {q}
                </button>
              ))}
            </div>
          </>
        )}

        {turns.map((t, i) => (
          <div
            key={i}
            className={
              t.role === 'user'
                ? 'text-sm text-gray-800 font-medium'
                : 'text-sm text-gray-700 leading-relaxed whitespace-pre-wrap bg-gray-50 rounded p-2'
            }
          >
            {t.role === 'user' ? `You: ${t.text}` : t.text}
          </div>
        ))}

        {running && step && !text && (
          <div className="text-xs text-gray-500 italic px-2">{step}…</div>
        )}
        {running && (text || !step) && (
          <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap bg-gray-50 rounded p-2">
            {mark(text, highlight)}
            <span className="inline-block w-1.5 h-4 ml-0.5 bg-gray-400 animate-pulse align-text-bottom" />
          </div>
        )}

        {error && <p className="text-xs text-amber-700">{error}</p>}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); ask(draft); }}
        className="flex gap-2 p-2 border-t border-gray-200"
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="What are you trying to find?"
          className="flex-1 text-sm px-2 py-1.5 rounded border border-gray-300 focus:outline-none focus:ring-1 focus:ring-red-600"
        />
        <button
          type="submit"
          disabled={running || !draft.trim()}
          className="px-3 py-1.5 text-sm rounded bg-red-700 text-white hover:bg-red-800 disabled:opacity-40"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
