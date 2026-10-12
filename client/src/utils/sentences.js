/**
 * Sentences inside a long unit of prose.
 *
 * In a prose work the Reader's unit is a whole chapter or section (Annals 1.1
 * is 876 characters, others pass 1,700), so a reader could only ever select the
 * unit. This cuts a unit into sentences so one can be selected.
 *
 * THE RULE. A sentence ends at a full stop, question mark or exclamation mark
 * (or the Greek question mark, U+037E) followed by whitespace, WHATEVER THE CASE
 * of the next word, because this corpus writes lowercase after a full stop
 * ("... L. Brutus instituit. dictaturae ad tempus ..."). A semicolon ends one
 * only before a capital letter, as in the index's cutter. Nothing is ever cut
 * inside a word. A full stop that closes an abbreviation does not end a
 * sentence: a single letter ("L.", "q.", "p. c."), the first names Ap, App, Cn,
 * Mam, Opet, Pub, Ser, Sex, Sp, Ti, Tib, the titles cos, coss, pr, tr, pl, and
 * the calendar words Kal, Non, Id and the month names after them (only when
 * capitalised, since "non" and "id" are ordinary Latin words).
 *
 * THE READER'S SENTENCES ARE FINER THAN THE INDEX'S CUT POINTS. The passage
 * index's prose windows were cut by `sentence_spans` in
 * scripts/corpus/prose_windows.py, which cuts only before a capital letter and
 * cuts after "L." in "L. Brutus". Every cut made there is made here too (apart
 * from the abbreviation guard), and this rule adds more. That is harmless: the
 * Similar route maps a sentence to its window by CHARACTER OFFSET (the prose
 * window whose char_start..char_end holds the sentence's start), not by cut
 * point, so a sentence never needs to coincide with a window boundary.
 *
 * Each piece is {start, end, textEnd}: offsets in the unit text, `end` taking
 * in the whitespace after the sentence (so the pieces tile the text exactly and
 * rendering them changes nothing), `textEnd` the end of the sentence itself.
 */

// . ; ? ! and the Greek question mark (U+037E).
const SENT_END = /[.;?!\u037e](?=\s+\S)/gu;

// Abbreviations that keep their full stop inside the sentence. Either case:
// a single letter, and words that are never ordinary words.
const ABBREV_ANY_CASE = new Set(['cos', 'coss', 'pr', 'tr', 'pl']);
// Only when written with a capital: Roman first names and calendar words, some
// of which ("non", "id") are also ordinary Latin.
const ABBREV_CAPITAL = new Set([
  'ap', 'app', 'cn', 'kal', 'mam', 'non', 'id', 'opet', 'pub', 'ser', 'sex', 'sp', 'ti', 'tib',
  // month names after Kal., Non., Id.
  'ian', 'feb', 'mart', 'apr', 'mai', 'iun', 'iul', 'aug', 'sept', 'oct', 'nov', 'dec',
]);

/** True when the full stop at `i` closes an abbreviation, not a sentence. */
function closesAbbreviation(text, i) {
  if (text[i] !== '.') return false;
  let j = i;
  while (j > 0 && /[\p{L}'\u2019]/u.test(text[j - 1])) j -= 1;
  const word = text.slice(j, i);
  if (!word) return false;
  if (j > 0 && !/[\s([\u201c"']/u.test(text[j - 1])) return false;
  const bare = word.replace(/['\u2019]$/, '');
  if ([...bare].length === 1) return true;
  const low = bare.toLowerCase();
  if (ABBREV_ANY_CASE.has(low)) return true;
  return /^\p{Lu}/u.test(bare) && ABBREV_CAPITAL.has(low);
}

/** [{start, end, textEnd}] covering `text` completely. */
export function splitSentences(text) {
  const s = String(text || '');
  const cuts = [0];
  SENT_END.lastIndex = 0;
  let m;
  while ((m = SENT_END.exec(s)) !== null) {
    let j = m.index + m[0].length;
    while (j < s.length && /\s/u.test(s[j])) j += 1;
    if (j >= s.length) continue;
    if (s[m.index] === ';' && !/^\p{Lu}$/u.test(s[j])) continue;
    if (closesAbbreviation(s, m.index)) continue;
    cuts.push(j);
  }
  cuts.push(s.length);
  const out = [];
  for (let k = 0; k + 1 < cuts.length; k += 1) {
    const start = cuts[k];
    const end = cuts[k + 1];
    if (end <= start) continue;
    let textEnd = end;
    while (textEnd > start && /\s/u.test(s[textEnd - 1])) textEnd -= 1;
    out.push({ start, end, textEnd });
  }
  return out;
}

/** A unit longer than this is shown as sentences. Verse lines never are. */
export const LONG_UNIT_CHARS = 400;

/** The sentences of a unit, or null when the unit is too short to need them
 *  or has only one. */
export function sentencesOf(text) {
  const s = String(text || '');
  if (s.length <= LONG_UNIT_CHARS) return null;
  const parts = splitSentences(s);
  return parts.length > 1 ? parts : null;
}

/**
 * The selection fields for sentences `lo`..`hi` (indices into `parts`) of a
 * unit. When they take in every sentence the selection is the whole unit and
 * charStart and charEnd are null. `text` is the selected sentences' text (the
 * whole unit's, for a whole-unit selection); `sentenceText` is always the text
 * of the sentences from `startSentence` on, which is what the Sentence scope
 * searches. `startSentence` is kept for a whole-unit selection too, so that
 * choosing Sentence afterwards can narrow back to the sentence first touched.
 */
export function sentenceFields(unitText, parts, lo, hi) {
  const first = Math.max(0, Math.min(lo, parts.length - 1));
  const last = Math.max(first, Math.min(hi, parts.length - 1));
  const sentenceText = unitText.slice(parts[first].start, parts[last].textEnd);
  const whole = first === 0 && last === parts.length - 1;
  return {
    charStart: whole ? null : parts[first].start,
    charEnd: whole ? null : parts[last].textEnd,
    text: whole ? unitText : sentenceText,
    sentenceText,
    sentenceCount: last - first + 1,
    sentenceTotal: parts.length,
    startSentence: first,
  };
}

/** The sentence range [lo, hi] a selection with charStart/charEnd covers. */
export function sentenceRangeOf(selection, parts) {
  if (selection?.charStart == null) return [0, parts.length - 1];
  let lo = parts.findIndex((p) => p.start === selection.charStart);
  let hi = parts.findIndex((p) => p.textEnd === selection.charEnd);
  if (lo < 0) lo = Math.max(0, parts.findIndex((p) => p.end > selection.charStart));
  if (hi < 0) hi = parts.length - 1;
  return [lo, Math.max(lo, hi)];
}

/**
 * The selection after the reader picks a scope on the toolbar: Section
 * widens a sentence selection to its whole unit, Sentence narrows a
 * whole-unit selection to the first sentence it touched. Anything else, or a
 * selection that is not inside one long unit, comes back unchanged.
 */
export function rescope(selection, unitText, scopeKey) {
  if (!selection || !selection.sentenceTotal || selection.lineCount !== 1) return selection;
  const parts = sentencesOf(unitText);
  if (!parts) return selection;
  if (scopeKey === 'section' && selection.charStart != null) {
    return {
      ...selection,
      ...sentenceFields(unitText, parts, 0, parts.length - 1),
      startSentence: selection.startSentence || 0,   // so Sentence can narrow back
    };
  }
  if (scopeKey === 'sentence' && selection.charStart == null) {
    const k = selection.startSentence || 0;
    return { ...selection, ...sentenceFields(unitText, parts, k, k) };
  }
  return selection;
}
