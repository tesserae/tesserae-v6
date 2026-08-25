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
