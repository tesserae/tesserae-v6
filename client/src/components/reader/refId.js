/** A passage ref like "valerius flaccus 1.1" as a usable DOM id.
 *
 * In its own module rather than in ReaderPage, because TextPane needs it too and
 * importing it from ReaderPage made the two files import each other. A circular
 * import can leave one of them half-initialised at runtime, which shows up as a
 * blank page rather than as a build error.
 */
export function cssRef(ref) {
  return String(ref || '').replace(/[^A-Za-z0-9]+/g, '-');
}

/** A ref as shown to a reader. Some corpus files carry malformed line tags
 * ("sal.  Cat..58.15": a double space, and a doubled period standing in for the
 * space before the locus). Same rule as normalize_ref() on the server. */
export function displayRef(ref) {
  const s = String(ref || '').trim().replace(/\s+/g, ' ');
  return readableLocus(s.replace(/\.{2,}(?=\S)/g, '. ').replace(/\.{2,}/g, '.').replace(/\s+/g, ' '));
}

/** The Ennius Annales file labels fragments of uncertain book "sedinc.N" (sedis
 * incertae) and of uncertain work "opinc.N" (operis incerti); N is Skutsch's
 * number. Shown to a reader as "N (book uncertain)" and "uncertain work N".
 * Same rule as format_short_locus() on the server. */
export function readableLocus(s) {
  return String(s || '')
    .replace(/\bsedinc\.(\d+[a-z]?)\b/g, '$1 (book uncertain)')
    .replace(/\bopinc\.(\d+[a-z]?)\b/g, 'uncertain work $1');
}

/** A ref as a reader should see it: the locus alone, without the file's
 * abbreviation ("thuc. pele. 2.57.1" -> "2.57.1", "verg. aen. 1.1" -> "1.1").
 * The last whitespace-separated token when it begins with a digit, else the
 * tidied ref unchanged. Same idea as format_short_locus() on the server, for
 * objects that do not carry the server's `locus`. */
export function bareLocus(ref) {
  const s = displayRef(ref);
  const last = s.split(' ').pop();
  return /^\d/.test(last) ? last : s;
}

/** The locus line for a passage window or translation block: the server's
 * `locus` when the object has one, else the short form of ref_start, with
 * ref_end after an en dash when it differs. Print this, with the full tag
 * (`fullRef`) as hover text. */
export function windowLocus(w) {
  if (!w) return '';
  if (w.locus) return w.locus;
  const start = bareLocus(w.ref_start);
  const end = w.ref_end ? bareLocus(w.ref_end) : '';
  return end && end !== start ? `${start}–${end}` : start;
}

/** Hover text for a printed locus: the file's own tag(s). */
export function fullRef(w) {
  if (!w) return '';
  const a = displayRef(w.ref_start);
  const b = w.ref_end ? displayRef(w.ref_end) : '';
  return b && b !== a ? `${a} – ${b}` : a;
}
