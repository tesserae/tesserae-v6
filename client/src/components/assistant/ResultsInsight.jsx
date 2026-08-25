import { useState } from 'react';
import useAssistantStream from './useAssistantStream';
import FindingsBlock from './FindingsBlock';

/**
 * "What does this show?" attached to a set of results.
 *
 * Deliberately not automatic. Reading a scholar's results without being asked
 * spends a slow generation on someone who may only want the list, and it puts a
 * machine opinion above their own before they have formed one. So it sits as one
 * quiet control, and it opens with the computed figures rather than the prose.
 */
export default function ResultsInsight({ results, source, target, className = '' }) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const { text, facts, guardrails, running, error, run } = useAssistantStream();

  if (!results?.length) return null;

  const ask = (q) => {
    setOpen(true);
    run('/api/assistant/analyze-stream', {
      results: results.slice(0, 25),
      source,
      target,
      question: q || undefined,
    });
  };

  if (!open) {
    return (
      <button
        onClick={() => ask('')}
        className={`text-sm text-red-700 hover:text-red-900 font-medium underline decoration-dotted underline-offset-4 ${className}`}
      >
        What does this evidence show?
      </button>
    );
  }

  return (
    <section className={`rounded border border-gray-200 bg-gray-50 p-3 space-y-3 ${className}`}>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold text-gray-800">Reading these results</h3>
        <button
          onClick={() => setOpen(false)}
          className="text-xs text-gray-500 hover:text-gray-700"
        >
          Close
        </button>
      </div>

      <FindingsBlock facts={facts} />

      {error && <p className="text-xs text-amber-700">{error}</p>}

      {(text || running) && (
        <div className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
          {text}
          {running && <span className="inline-block w-1.5 h-4 ml-0.5 bg-gray-400 animate-pulse align-text-bottom" />}
        </div>
      )}

      {guardrails && !guardrails.clean && (
        <p className="text-[11px] text-amber-700 leading-snug">
          {guardrails.references_removed?.length > 0 &&
            `A citation not present in these results was removed from the text above. `}
          {guardrails.unsupported_numbers?.length > 0 &&
            `A figure above (${guardrails.unsupported_numbers.join(', ')}) was not among the measured values. `}
          Trust the measured figures over the prose.
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
            placeholder="Ask about these results"
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
        The figures are computed by the search engine. The prose is written by a local
        open model from those figures and the passages shown, and it knows nothing else.
      </p>
    </section>
  );
}
