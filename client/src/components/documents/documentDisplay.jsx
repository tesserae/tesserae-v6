// Pure display helpers for a documents-collection hit (a /api/line-search
// result with collection==='documents'). Extracted from LineSearch.jsx so
// the Inscriptions & Papyri page renders a document hit identically
// without re-deriving the token/restoration/fragment logic.

// Does the documents index keep anything of this written word? The same rule
// as scripts/build_inverted_index.py's tokenize_latin_fast / tokenize_greek_fast:
// "/", numerals and punctuation leave nothing, so the card's token list is
// shorter than the written text.
function makesIndexToken(word, language) {
  const w = word.toLowerCase();
  if (language === 'grc') return /[\u0300-\u036f\u0370-\u03ff\u1f00-\u1fff]/.test(w);
  return /[a-z]/.test(w.replace(/j/g, 'i').replace(/v/g, 'u'));
}

/**
 * restored_indices and fragment_indices count the written words of the line
 * (the "/" between lines included); the card renders the index's tokens, which
 * leave those out. Turns the written positions into the card's positions.
 * Returns the positions unchanged when the written text does not line up with
 * the token list (so a hit never loses its marks to a failed guess).
 */
export function toTokenPositions(result, positions) {
  const written = (result.text || '').split(/\s+/).filter(Boolean);
  const tokens = result.tokens || [];
  if (!positions || !positions.length || !written.length) return positions || [];
  const map = [];
  let kept = 0;
  for (const w of written) {
    map.push(makesIndexToken(w, result.language) ? kept++ : -1);
  }
  if (kept !== tokens.length) return positions;
  return positions.map((p) => map[p]).filter((p) => p !== undefined && p >= 0);
}

/**
 * Document hit text, rendered by TOKEN POSITION (not a whitespace re-split
 * of `text`) so restored-word marking lines up with restored_indices
 * exactly as the index stored it. `gap_before` lists the positions before which
 * the stone has a gap (text lost); each gets a gray "[...]". Falls back to `highlightFallback` (the
 * plain literary highlighter) if a hit carries no token list.
 */
export function renderDocumentText(result, highlightFallback) {
  const tokens = result.tokens || [];
  if (!tokens.length) {
    return highlightFallback ? highlightFallback(result.text, result.matched_words || []) : result.text;
  }
  const restoredSet = new Set(toTokenPositions(result, result.restored_indices));
  const fragmentSet = new Set(toTokenPositions(result, result.fragment_indices));
  const matchedSet = new Set((result.matched_words || []).map(w => (w || '').toLowerCase()));
  const gapSet = new Set(result.gap_before || []);
  const gapMarker = (i) => (
    <span key={`gap-${i}`} className="text-gray-400" title="text lost">[...]{' '}</span>
  );
  const words = tokens.map((tok, i) => {
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
    return (
      <span key={i}>
        {gapSet.has(i) ? gapMarker(i) : null}{el}{' '}
      </span>
    );
  });
  // A gap at the end of the line (its position is the number of tokens).
  if (gapSet.has(tokens.length)) words.push(gapMarker(tokens.length));
  return words;
}

/** "101 AD–300 AD", "300 AD", or null when the document carries no date. */
export function documentDateLabel(result) {
  const nb = result.date_not_before, na = result.date_not_after;
  if (nb == null && na == null) return null;
  const fmt = (y) => (y < 0 ? `${-y} BC` : `${y} AD`);
  if (nb != null && na != null && nb !== na) return `${fmt(nb)}–${fmt(na)}`;
  return fmt(nb != null ? nb : na);
}

// Findspot abbreviations the Epigraphic Database Heidelberg uses as they
// stand. "Hr." (Henchir, the North African word for a ruin site) was read by
// the owner on 2026-10-12 as an unknown term, so the card writes it out.
const PLACE_ABBREVIATIONS = [
  [/\bHr\.\s*/g, 'Henchir '],
  [/\bKh\.\s*/g, 'Khirbet '],
];

/** The findspot line of a document: the ancient place when known, else the
 *  modern one, with the database's abbreviations written out. */
export function documentPlace(r) {
  let place = (r && (r.ancient_place || r.modern_place)) || '';
  for (const [pattern, word] of PLACE_ABBREVIATIONS) place = place.replace(pattern, word);
  return place || null;
}

const UNKNOWN_LABELS = new Set(['unknown', 'unbekannt', '?', 'n/a', 'none']);

/** The type, object and material chips, leaving out the ones that only say
 *  the database does not know (three "unknown" chips told the reader nothing,
 *  2026-10-12). */
export function documentLabels(r) {
  if (!r) return [];
  return [r.text_type_label, r.object_type_label, r.material_label]
    .filter((x) => x && !UNKNOWN_LABELS.has(String(x).trim().toLowerCase()));
}


/**
 * An edition text split into the stone's text and the editor's notes. The Epigraphic Database Roma writes
 * a note into the text between 〈: and 〉 ("〈:Rusellis adtributa, sed est Cosana〉"); shown plain, a note
 * reads as words of the stone (2026-10-22).
 */
export function editorNoteParts(text) {
  const parts = [];
  const re = /\u3008:([^\u3009]*)\u3009/g;
  let last = 0;
  let m;
  while ((m = re.exec(text || '')) !== null) {
    if (m.index > last) parts.push({ note: false, text: text.slice(last, m.index) });
    parts.push({ note: true, text: m[1].trim() });
    last = m.index + m[0].length;
  }
  if (last < (text || '').length) parts.push({ note: false, text: text.slice(last) });
  return parts;
}
