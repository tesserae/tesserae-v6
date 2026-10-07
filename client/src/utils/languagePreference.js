/**
 * Which language the site opens in, remembered across visits (2026-10-07).
 *
 * With seven languages, choosing yours on every visit is a chore, and asking
 * people to make an account just for that would be worse. So the choice is
 * kept in the browser's own storage (localStorage), never sent to the server,
 * and needs no cookie notice.
 *
 * Two settings:
 *   - "last" (the default): open in the language used last.
 *   - a language code: always open in that language, whatever was used last
 *     (for a reader who visits other languages but always starts in Latin).
 *
 * An address that names a language (?lang=fa) always wins over either.
 * Storage can be missing or blocked (private windows, some embeds), so every
 * read and write is guarded and the site falls back to Latin.
 */
const LAST_KEY = 'tesserae_last_language';
const MODE_KEY = 'tesserae_start_language';

export const START_LAST = 'last';

function read(key) {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function write(key, value) {
  try {
    if (value == null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch { /* storage blocked: nothing to remember */ }
}

/** The start setting: START_LAST or a language code. */
export function getStartSetting() {
  return read(MODE_KEY) || START_LAST;
}

export function setStartSetting(value) {
  write(MODE_KEY, value && value !== START_LAST ? value : null);
}

/** Record the language just chosen. 'cross' is a search tab, not a language,
 *  but the search page may reopen on it, so it is kept too. */
export function rememberLanguage(code) {
  if (code) write(LAST_KEY, code);
}

/**
 * The language to open in, or null when there is no preference yet.
 * `allowed` (optional) limits the answer to codes the page can show: the
 * Reader cannot open 'cross'.
 */
export function startLanguage(allowed) {
  const setting = getStartSetting();
  const pick = setting !== START_LAST ? setting : read(LAST_KEY);
  if (!pick) return null;
  if (allowed && !allowed.includes(pick)) return null;
  return pick;
}
