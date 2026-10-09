// Pure display helpers for a documents-collection hit (a /api/line-search
// result with collection==='documents'). Extracted from LineSearch.jsx so
// the Inscriptions & Papyri page renders a document hit identically
// without re-deriving the token/restoration/fragment logic.

/**
 * Document hit text, rendered by TOKEN POSITION (not a whitespace re-split
 * of `text`) so restored-word marking lines up with restored_indices
 * exactly as the index stored it. Falls back to `highlightFallback` (the
 * plain literary highlighter) if a hit carries no token list.
 */
export function renderDocumentText(result, highlightFallback) {
  const tokens = result.tokens || [];
  if (!tokens.length) {
    return highlightFallback ? highlightFallback(result.text, result.matched_words || []) : result.text;
  }
  const restoredSet = new Set(result.restored_indices || []);
  const fragmentSet = new Set(result.fragment_indices || []);
  const matchedSet = new Set((result.matched_words || []).map(w => (w || '').toLowerCase()));
  return tokens.map((tok, i) => {
    let el = <span>{tok}</span>;
    if (restoredSet.has(i)) {
      // Light dotted underline for an editorially restored word -- chosen
      // over scholarly square brackets because the matched-word highlight
      // below already uses <mark>, and the corpus's own angle-bracket
      // convention is reserved for editorial brackets carried IN the
      // source text itself; an underline reads as "mark on top of the
      // word" without colliding with either.
      el = <span className="underline decoration-dotted decoration-2 decoration-sky-500" title="editorially restored">{tok}</span>;
    } else if (fragmentSet.has(i)) {
      el = <span className="italic text-gray-500" title="surviving fragment of a damaged word">{tok}</span>;
    }
    if (matchedSet.has((tok || '').toLowerCase())) {
      el = <mark className="bg-amber-200 px-0.5 rounded">{el}</mark>;
    }
    return <span key={i}>{el}{' '}</span>;
  });
}

/** "101 AD–300 AD", "300 AD", or null when the document carries no date. */
export function documentDateLabel(result) {
  const nb = result.date_not_before, na = result.date_not_after;
  if (nb == null && na == null) return null;
  const fmt = (y) => (y < 0 ? `${-y} BC` : `${y} AD`);
  if (nb != null && na != null && nb !== na) return `${fmt(nb)}–${fmt(na)}`;
  return fmt(nb != null ? nb : na);
}
