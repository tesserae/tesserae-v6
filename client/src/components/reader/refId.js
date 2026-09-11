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
  return s.replace(/\.{2,}(?=\S)/g, '. ').replace(/\.{2,}/g, '.').replace(/\s+/g, ' ');
}
