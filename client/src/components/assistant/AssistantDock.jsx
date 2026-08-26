import { useEffect, useRef, useState } from 'react';
import useAssistantStream from './useAssistantStream';
import { getSessionValue, setSessionValue } from '../../utils/storage';

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

/** The answer as the reader should see it: emphasis rendered, matches marked.
 *
 *  The model writes titles as markdown, so answers arrived reading literally
 *  "Vergil's *Aeneid*, Ovid's *Tristia*" with the asterisks on show. Nothing
 *  rendered them, because the finished answer was printed as plain text.
 *
 *  Only bold and italic are handled. This is a chat panel, not a document
 *  viewer, and anything that builds HTML from model output is a hazard, so the
 *  text is split with a regex and rebuilt as React elements. No HTML is ever
 *  constructed from the answer.
 */
const EMPHASIS = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|_[^_\n]+_)/g;

function render(text, terms) {
  if (!text) return text;
  return String(text).split(EMPHASIS).map((part, i) => {
    if (/^\*\*[^*\n]+\*\*$/.test(part)) {
      return <strong key={i} className="font-semibold">{mark(part.slice(2, -2), terms)}</strong>;
    }
    if (/^\*[^*\n]+\*$/.test(part) || /^_[^_\n]+_$/.test(part)) {
      return <em key={i}>{mark(part.slice(1, -1), terms)}</em>;
    }
    return <span key={i}>{mark(part, terms)}</span>;
  });
}

/** The controls that take you to the real search.
 *
 *  Tessa's job is to help someone USE Tesserae, not to reprint the results in a
 *  chat panel. So the answer says what is there and how many, and these open the
 *  actual page with the actual query in it.
 *
 *  Real anchors, not click handlers: a scholar will want to middle-click one
 *  into a new tab and keep the conversation, or bookmark it, or send it to a
 *  colleague. Nothing navigates on its own -- the main window changes only when
 *  the reader chooses.
 */
function Actions({ items }) {
  if (!items || !items.length) return null;
  return (
    <div className="mt-2 flex flex-col gap-1">
      {items.map((a) => (
        <a
          key={a.url}
          href={a.url}
          className="group flex items-baseline gap-2 rounded border border-red-200 bg-red-50 px-2 py-1.5 hover:bg-red-100 hover:border-red-300"
        >
          <span className="text-red-700 text-xs leading-none pt-0.5">&#9654;</span>
          <span className="min-w-0">
            <span className="block text-xs font-medium text-red-800 group-hover:text-red-900">
              {a.label}
            </span>
            {a.detail && (
              <span className="block text-[11px] text-gray-500">{a.detail}</span>
            )}
          </span>
        </a>
      ))}
    </div>
  );
}

/** The conversation, kept across a page load.
 *
 *  Tessa's whole point now is to send you to a search, and every one of those
 *  actions is a real link, so taking one RELOADS the page: the app unmounts and
 *  the transcript goes with it. The reader arrived at the results having lost
 *  the reasoning that got them there, and the panel had shut itself.
 *
 *  sessionStorage rather than localStorage: a conversation belongs to the visit,
 *  not to the browser for ever. Kept small, because a transcript of quoted Latin
 *  grows fast and this is a 5MB store shared with the rest of the site.
 */
const KEEP_TURNS = 12;
const KEEP_CHARS = 4000;

function loadTurns() {
  try {
    const raw = JSON.parse(getSessionValue('tessa_turns', '[]'));
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function saveTurns(turns) {
  try {
    const trimmed = turns.slice(-KEEP_TURNS).map((t) => ({
      role: t.role,
      text: String(t.text || '').slice(0, KEEP_CHARS),
      terms: (t.terms || []).slice(0, 12),
      actions: (t.actions || []).slice(0, 4),
    }));
    setSessionValue('tessa_turns', JSON.stringify(trimmed));
  } catch {
    /* a full store must not break the panel */
  }
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
  // Reopens where it was left, because taking one of Tessa's own actions
  // reloads the page and would otherwise shut her and wipe the conversation.
  const [open, setOpen] = useState(() => getSessionValue('tessa_open', '0') === '1');
  const [turns, setTurns] = useState(loadTurns);
  const [draft, setDraft] = useState('');
  const { text, step, running, error, highlight, offer, actions, run } = useAssistantStream();
  const scrollRef = useRef(null);

  useEffect(() => {
    fetch('/api/assistant/status')
      .then((r) => r.json())
      .then((d) => setAvailable(Boolean(d.available)))
      .catch(() => setAvailable(false));
  }, []);

  // Fold a finished answer into the transcript so the next question starts clean.
  // The terms are stored WITH the turn. They arrive in the `done` event, which
  // fires at the very end, and the marked-up answer was only rendered while
  // `running` was true -- so the highlighting existed for the instant between
  // the terms arriving and the block being replaced by this plain transcript
  // entry, and no reader ever saw it.
  const prevRunning = useRef(false);
  // Restored as well: without it "yes" after a navigation would once again have
  // nothing to accept, which is the bug that took three attempts to kill.
  const pendingOffer = useRef(getSessionValue('tessa_pending_offer', '') || null);
  useEffect(() => {
    if (prevRunning.current && !running && text) {
      setTurns((t) => [...t, { role: 'assistant', text, terms: highlight, actions }]);
      pendingOffer.current = offer || null;
      setSessionValue('tessa_pending_offer', offer || '');
    }
    prevRunning.current = running;
  }, [running, text, highlight, offer, actions]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [turns, text]);

  useEffect(() => { saveTurns(turns); }, [turns]);
  useEffect(() => { setSessionValue('tessa_open', open ? '1' : '0'); }, [open]);

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
    // Hand back the offer this answer made, so "yes" is an acceptance rather
    // than a question with no content of its own.
    run('/api/assistant/ask-stream',
        { question, history, offered_phrase: pendingOffer.current || undefined });
  };

  // The launcher is deliberately two different things.
  //
  // On a desktop the two-line pill is worth its space: Tessa is new, and a bare
  // initial would not tell anyone what it is. On a phone that same pill sits on
  // top of the results a reader is trying to read, and the screenshots showed it
  // covering a result card. So below `sm` it becomes a plain round button and
  // the explanatory line is carried by the accessible name instead, where it
  // costs no screen.
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="Open Tessa, the AI assistant, and ask about the corpus"
        title="Tessa, the AI assistant"
        className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-40 flex items-center justify-center sm:justify-start w-14 h-14 sm:w-auto sm:h-auto sm:gap-3 sm:pl-3 sm:pr-5 sm:py-3 rounded-full sm:rounded-2xl bg-red-700 text-white shadow-xl ring-1 ring-red-900/20 transition hover:bg-red-800 hover:shadow-2xl focus:outline-none focus:ring-2 focus:ring-red-400"
      >
        <span className="flex items-center justify-center w-9 h-9 rounded-xl sm:bg-white/15 text-lg font-semibold leading-none">
          T
        </span>
        <span className="hidden sm:block text-left leading-tight">
          <span className="block text-base font-semibold">Tessa</span>
          <span className="block text-[11px] font-medium text-red-100">
            AI Assistant &middot; ask the corpus
          </span>
        </span>
      </button>
    );
  }

  return (
    // Opened, the panel is a floating card on a desktop and a bottom sheet on a
    // phone, where a 24rem card with margins on all four sides wastes the little
    // width there is.
    <div className="fixed z-40 inset-x-0 bottom-0 sm:inset-x-auto sm:bottom-5 sm:right-5 w-full sm:w-[24rem] sm:max-w-[calc(100vw-2.5rem)] rounded-t-xl sm:rounded-lg border-t sm:border border-gray-300 bg-white shadow-xl flex flex-col max-h-[85vh] sm:max-h-[min(32rem,calc(100vh-3rem))]">
      <header className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-800">
          <span className="flex items-center justify-center w-6 h-6 rounded-md bg-red-700 text-white text-xs font-semibold leading-none">
            T
          </span>
          Tessa AI Assistant
        </h2>
        <div className="flex items-center gap-1">
          {/* The conversation now survives a page load, so there has to be a way
              to end one. Closing the panel deliberately does NOT clear it: a
              reader who shuts Tessa to see the results underneath expects to
              find the thread still there when they reopen her. */}
          {turns.length > 0 && (
            <button
              onClick={() => {
                setTurns([]);
                pendingOffer.current = null;
                setSessionValue('tessa_pending_offer', '');
              }}
              className="text-[11px] text-gray-500 hover:text-gray-800 px-1"
            >
              Clear
            </button>
          )}
          <button
            onClick={() => setOpen(false)}
            className="text-gray-400 hover:text-gray-700 text-lg leading-none px-1"
            aria-label="Close Tessa"
          >
            ×
          </button>
        </div>
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
            {t.role === 'user' ? `You: ${t.text}` : render(t.text, t.terms)}
            {t.role !== 'user' && <Actions items={t.actions} />}
          </div>
        ))}

        {running && step && !text && (
          <div className="text-xs text-gray-500 italic px-2">{step}…</div>
        )}
        {running && (text || !step) && (
          <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap bg-gray-50 rounded p-2">
            {render(text, highlight)}
            <span className="inline-block w-1.5 h-4 ml-0.5 bg-gray-400 animate-pulse align-text-bottom" />
            <Actions items={actions} />
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
