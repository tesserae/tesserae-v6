// Frontend mirror of backend `normalize_coptic`. The .tess display text uses
// the U+03E2-U+03EF (legacy / Greek-Coptic) block for the seven Coptic-only
// letters; the backend's lemma cache and matched-word strings use the
// duplicate U+2CB2-U+2CBF block (set apart for Coptic). Without
// normalisation, char-for-char highlight matching fails on any verse
// containing ϣ ϥ ϩ ϫ ϭ ϯ.

const LEGACY_TO_PRIMARY = {
  'Ϣ': 'Ⲳ', 'ϣ': 'ⲳ',
  'Ϥ': 'Ⲵ', 'ϥ': 'ⲵ',
  'Ϧ': 'Ⲷ', 'ϧ': 'ⲷ',
  'Ϩ': 'Ⲹ', 'ϩ': 'ⲹ',
  'Ϫ': 'Ⲻ', 'ϫ': 'ⲻ',
  'Ϭ': 'Ⲽ', 'ϭ': 'ⲽ',
  'Ϯ': 'Ⲿ', 'ϯ': 'ⲿ',
};

export const normalizeCoptic = (text) => {
  if (!text) return '';
  let out = text.normalize('NFC');
  out = out.replace(/[Ϣ-ϯ]/g, ch => LEGACY_TO_PRIMARY[ch] || ch);
  out = out.replace(/[̀-ͯ]/g, '');
  return out.toLowerCase();
};


// --- Leipzig-Jerusalem transliteration input -------------------------------
// Lets users type Coptic with a normal keyboard: Latin letters -> Coptic
// Unicode, following the Leipzig-Jerusalem standard (Grossman & Haspelmath),
// with plain-ASCII aliases for the four diacritic letters so no special
// keyboard is needed:
//   sh -> ϣ (LJ š)   E -> ⲏ (LJ ê)   O -> ⲱ (LJ ô)   j -> ϫ (LJ č)
//   h -> ϩ   f -> ϥ   c -> ϭ   x -> ϧ (Bohairic)   + -> ϯ
// eta/omega use capital E/O (not "ee"/"oo") to avoid clashing with genuine
// ⲉⲉ / ⲟⲟ sequences. The backend normalises both the query and the
// text, so the exact output block does not matter for matching; these are the
// standard, well-displaying glyphs the user sees in the preview.

const LJ_DIGRAPHS = { 'sh': 'ϣ', 'th': 'ⲑ', 'ph': 'ⲫ', 'kh': 'ⲭ', 'ps': 'ⲯ', 'ks': 'ⲝ' };
const LJ_SINGLES = { 'a': 'ⲁ', 'b': 'ⲃ', 'g': 'ⲅ', 'd': 'ⲇ', 'e': 'ⲉ', 'z': 'ⲍ', 'i': 'ⲓ', 'k': 'ⲕ', 'l': 'ⲗ', 'm': 'ⲙ', 'n': 'ⲛ', 'o': 'ⲟ', 'p': 'ⲡ', 'r': 'ⲣ', 's': 'ⲥ', 't': 'ⲧ', 'u': 'ⲩ', 'f': 'ϥ', 'h': 'ϩ', 'j': 'ϫ', 'c': 'ϭ', 'x': 'ϧ', '+': 'ϯ' };
const LJ_NATIVE = { 'ê': 'ⲏ', 'ô': 'ⲱ', 'š': 'ϣ', 'č': 'ϫ' };  // accept LJ's own diacritics too
const LJ_ETA = 'ⲏ';
const LJ_OMEGA = 'ⲱ';
const BOOLEAN_OPS = new Set(['AND', 'OR', 'NOT']);

const transliterateToken = (tok) => {
  let out = '';
  let i = 0;
  while (i < tok.length) {
    const two = tok.slice(i, i + 2).toLowerCase();
    if (LJ_DIGRAPHS[two]) { out += LJ_DIGRAPHS[two]; i += 2; continue; }
    const ch = tok[i];
    if (ch === 'E') { out += LJ_ETA; i += 1; continue; }      // capital E = eta
    if (ch === 'O') { out += LJ_OMEGA; i += 1; continue; }    // capital O = omega
    const mapped = LJ_SINGLES[ch.toLowerCase()] ?? LJ_NATIVE[ch];
    out += (mapped !== undefined ? mapped : ch);  // pass through wildcards, quotes, existing Coptic
    i += 1;
  }
  return out;
};

// Convert a Latin/transliterated query to Coptic. Preserves whitespace,
// wildcard/phrase syntax (* ? " ~ #), and the uppercase boolean operators
// AND / OR / NOT. Idempotent on text that is already Coptic (paste-safe).
export const transliterateToCoptic = (input) => {
  if (!input) return input;
  return input
    .split(/(\s+)/)
    .map(tok => (/^\s+$/.test(tok) || BOOLEAN_OPS.has(tok)) ? tok : transliterateToken(tok))
    .join('');
};
