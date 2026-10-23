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

/** The unit a "Go to line" entry names, among `refs` (the units' refs in order).
 *
 * A reader types what the margin shows: a line number ("851"), book and line
 * ("6.851"), or for a work divided into stories the story, couplet and
 * hemistich ("151.1.1"). Refs come in two shapes: "verg. aen. 6.851", where the
 * locus follows a space, and "rumi.masnavi.1.18" or "ferdowsi.shahnameh.151.1.1",
 * where it follows a dot (2026-10-23: the dotted shape only ever matched a
 * single number, so "1.18" found nothing in the Masnavi).
 *
 * Returns { index, problem }: index -1 with a plain reason when nothing matches
 * or the entry names several places. */
export function findRefIndex(refs, query) {
  const q = String(query || '').trim().toLowerCase();
  const list = (refs || []).map((r) => String(r || '').toLowerCase());
  if (!q || !list.length) return { index: -1, problem: `no line ${query} here` };
  let index = list.findIndex((r) => r === q || r.endsWith(' ' + q));
  if (index < 0 && /^\d+(\.\d+)*[a-z]?$/.test(q)) {
    const hits = [];
    list.forEach((r, k) => { if (r.endsWith('.' + q)) hits.push(k); });
    if (hits.length > 1) {
      const m = /(\d+(?:\.\d+)*[a-z]?)$/.exec(list[hits[0]]);
      const example = m ? m[1] : `6.${q}`;
      return { index: -1, problem: `line ${query} is in ${hits.length} places here; add what comes before it, e.g. ${example}` };
    }
    if (hits.length === 1) index = hits[0];
  }
  if (index < 0) return { index: -1, problem: `no line ${query} here` };
  return { index, problem: '' };
}

/** The number the Reader prints in the margin beside a line (every fifth one).
 *
 * Ordinarily the ref's last number, the line. In a Persian or Urdu work whose
 * references run story.couplet.hemistich (the Shahnameh since 2026-10-23), the
 * last number is the hemistich, 1 or 2, so the margin would never reach a
 * fifth: there the couplet number is returned on the first hemistich and null
 * on the second. */
export function marginNumber(ref, language) {
  const nums = (String(ref || '').match(/\d+/g) || []).map((x) => parseInt(x, 10));
  if (!nums.length) return null;
  const hemistichs = (language === 'fa' || language === 'ur') && nums.length >= 3;
  if (!hemistichs) return nums[nums.length - 1];
  return nums[nums.length - 1] === 1 ? nums[nums.length - 2] : null;
}
