import { useState, useEffect } from 'react';
import useAssistantStream from './useAssistantStream';
import FindingsBlock from './FindingsBlock';

/**
 * "What does this show?" attached to a set of results.
 *
 * Deliberately not automatic. Reading a scholar's results without being asked
 * spends a slow generation on someone who may only want the list, and it puts a
 * machine opinion above their own before they have formed one. So it sits as one
 * quiet control, and it opens with the computed figures rather than the prose.
 *
 * Scope is a choice, and it is said out loud. Tessa read the top 25 by default
 * and the panel only admitted it in a hover tooltip, so a reader took a summary
 * of 25 parallels for a summary of the whole list. The header now names the
 * count, and the reader can widen it to the top 100 or to everything loaded.
 * The figures are computed over every parallel sent; only a handful of
 * passages go to the model, so widening the scope costs little.
 */
const SCOPES = [25, 100];

export default function ResultsInsight({ results, source, target, className = '' }) {
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState(25);
  const [question, setQuestion] = useState('');
  const { text, facts, guardrails, running, error, run } = useAssistantStream();

  if (!results?.length) return null;

  const total = results.length;
  const count = Math.min(scope, total);
  const scopeLabel = count === total ? `all ${total}` : `the top ${count} of ${total}`;

  const ask = (q, n = scope) => {
    setOpen(true);
    run('/api/assistant/analyze-stream', {
      results: results.slice(0, n),
      source,
      target,
      question: q || undefined,
    });
  };

  const changeScope = (n) => {
    setScope(n);
    ask(question, n);
  };

  if (!open) {
    return (
      <button
        onClick={() => ask('')}
        title={`Tessa reads ${scopeLabel} parallels in this list and summarizes what they show, starting from the computed figures. You can widen the scope once the panel is open. Nothing runs until you click.`}
        className={`text-sm text-red-700 hover:text-red-900 font-medium underline decoration-dotted underline-offset-4 ${className}`}
      >
        What does this evidence show?
      </button>
    );
  }

  const scopeOptions = SCOPES.filter((n) => n < total);

  return (
    <section className={`rounded border border-gray-200 bg-gray-50 p-3 space-y-3 ${className}`}>
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <h3 className="text-sm font-semibold text-gray-800">
          Tessa is reading {scopeLabel} parallels
        </h3>
        <button
          onClick={() => setOpen(false)}
          className="text-xs text-gray-500 hover:text-gray-700"
        >
          Close
        </button>
      </div>

      {(scopeOptions.length > 0) && (
        <div className="flex items-center gap-2 text-xs text-gray-600 flex-wrap">
          <span>Read:</span>
          {scopeOptions.map((n) => (
            <ScopeButton key={n} active={scope === n} disabled={running} onClick={() => changeScope(n)}>
              top {n}
            </ScopeButton>
          ))}
          <ScopeButton active={scope >= total} disabled={running} onClick={() => changeScope(total)}>
            all {total}
          </ScopeButton>
          <span className="text-gray-500">
            (the parallels loaded on this page, in ranked order)
          </span>
        </div>
      )}

      <FindingsBlock facts={facts} />

      {error && <p className="text-xs text-amber-700">{error}</p>}

      {running && !text && (
        <WorkingLine label="Tessa is reading the figures and the passages, then writing" />
      )}
      {text && (
        <div className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
          {text}
          {running && <span className="inline-block w-1.5 h-4 ml-0.5 bg-gray-400 animate-pulse align-text-bottom" />}
        </div>
      )}

      {guardrails && !guardrails.clean && (
        <p className="text-[11px] text-amber-700 leading-snug">
          {guardrails.references_removed?.length > 0 &&
            `The assistant cited a passage that is not in these results, so that citation was taken out of the text above. `}
          {guardrails.unsupported_numbers?.length > 0 &&
            `The text above uses a figure (${guardrails.unsupported_numbers.join(', ')}) that is not among the values measured in the box above. `}
          {guardrails.access_sentences_removed?.length > 0 &&
            `A sentence speculating about whether the later author knew the earlier text was taken out. `}
          Where the text and the measured values disagree, the values are right.
        </p>
      )}

      {!running && (
        <form
          onSubmit={(e) => { e.preventDefault(); ask(question); }}
          className="flex gap-2"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={`Ask about ${scopeLabel} parallels`}
            className="flex-1 text-sm px-2 py-1.5 rounded border border-gray-300 focus:outline-none focus:ring-1 focus:ring-red-600"
          />
          <button
            type="submit"
            className="px-3 py-1.5 text-sm rounded bg-red-700 text-white hover:bg-red-800 disabled:opacity-50"
            disabled={!question.trim()}
          >
            Ask
          </button>
        </form>
      )}

      <p className="text-[11px] text-gray-500 leading-snug">
        The figures are computed by the search engine over {scopeLabel} parallels. The prose is
        written by a local open model from those figures and a few of the passages, and it knows
        nothing else.
      </p>
    </section>
  );
}

/**
 * What the reader sees while the model has not yet produced a word: a
 * spinner, what is being done, and the seconds so far. A local model takes
 * ten to thirty seconds to read a long prompt before its first word, and a
 * bare blinking cursor for that long reads as a dead page (NC, 2026-09-07).
 */
export function WorkingLine({ label }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="flex items-center gap-2 text-xs text-gray-600 px-1 py-1" role="status" aria-live="polite">
      <span className="inline-block w-3.5 h-3.5 rounded-full border-2 border-gray-300 border-t-red-700 animate-spin" />
      <span>{label}…</span>
      <span className="text-gray-400 tabular-nums">{seconds}s</span>
    </div>
  );
}

function ScopeButton({ active, disabled, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || active}
      className={`px-2 py-0.5 rounded border text-xs ${
        active
          ? 'bg-red-700 border-red-700 text-white'
          : 'bg-white border-gray-300 text-gray-700 hover:border-red-600 hover:text-red-700 disabled:opacity-50'
      }`}
    >
      {children}
    </button>
  );
}
