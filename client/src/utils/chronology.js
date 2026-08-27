/**
 * Dating a result, and putting results in the order a scholar reads them.
 *
 * Shared by Theme Search and the Reader's Similar Passages panel. It lived in
 * ThemeSearchPage, and the Reader grew its own list of cross-language results
 * with no dates and no order but score -- so the same kind of list behaved
 * differently on two pages of the same site. One copy, used twice, rather than
 * two that drift.
 */

/** Oldest first. A content search crosses centuries, so the order in which the
 *  results are read is itself information: seeing a Homeric scene, then its
 *  Hellenistic reworking, then a Latin one, is the point.
 *
 *  Undated works (Persian and Urdu authors are not in the dates table) go last
 *  rather than being guessed at or dropped.
 */
export function chronological(results) {
  return [...(results || [])].sort((a, b) => {
    const ay = typeof a.year === 'number' ? a.year : null;
    const by = typeof b.year === 'number' ? b.year : null;
    if (ay === null && by === null) return (b.score || 0) - (a.score || 0);
    if (ay === null) return 1;
    if (by === null) return -1;
    if (ay !== by) return ay - by;
    return (b.score || 0) - (a.score || 0);
  });
}

/** Split a date note into the date itself, what kind of date it is, and the
 *  scholarly caveat that often trails behind it.
 *
 *  The whole note used to be set as one small grey string, so the eye hit "d."
 *  before the year in a column whose entire job is to be scanned by year. The
 *  date now leads and the qualifier follows, spelled out: "c. 1020 CE (died)".
 *
 *  WHY THE REMAINDER IS SEPARATED TOO
 *
 *  103 of the 474 notes run past a bare date -- "fl. c. 55 CE (date contested;
 *  some scholars place in 3rd c.)", "d. c. 215 CE (c. 150-215), Clement of
 *  Alexandria" -- and the chip is one nowrap line in an 8rem column, so those
 *  ran straight across the work title. Truncating them would throw away real
 *  scholarly hedging. So the chip takes the date proper and the rest is set
 *  below it, where it wraps.
 *
 *  Notes whose date is not at the front ("Greek philosopher (d. 322 BCE);
 *  Latin translations primarily 12th-13th c.") fall back to the structured
 *  `year`, with the whole note beneath. Seven entries have neither, and they
 *  are genuinely undated.
 */
const QUALIFIER = [
  [/^d\.\s*/i, 'died'],
  [/^fl\.\s*/i, 'flourished'],
  [/^b\.\s*/i, 'born'],
  [/^r\.\s*/i, 'reigned'],
  [/^comp\.\s*/i, 'composed'],
  [/^composed\s+/i, 'composed'],
  [/^revealed\s+/i, 'revealed'],
  [/^active\s+/i, 'active'],
];

// A date at the front of what is left: "322 BCE", "c. 1020 CE", "c. 150-215".
const DATE_CORE = /^(?:c\.\s*)?\d{1,4}(?:\s*[-–]\s*(?:c\.\s*)?\d{1,4})?(?:\s*(?:BCE|CE|BC|AD))?/i;

function yearLabel(year) {
  return year < 0 ? `${Math.abs(year)} BCE` : `${year} CE`;
}

/** Trim the punctuation a remainder is left holding when the date is cut off.
 *
 *  Cutting "d. c. 215 CE (c. 150-215), Clement of Alexandria" after the date
 *  leaves the opening bracket behind and the closing one orphaned, so unmatched
 *  brackets are dropped from either end rather than just the leading one.
 */
function tidy(s) {
  let out = s.replace(/^[\s,;:.–-]+/, '').replace(/[\s,;:]+$/, '').trim();
  while (out.startsWith('(') && !out.includes(')')) out = out.slice(1).trim();
  while (out.endsWith(')') && !out.slice(0, -1).includes('(')) out = out.slice(0, -1).trim();
  if (out.startsWith('(') && out.endsWith(')') && out.indexOf('(', 1) === -1) {
    out = out.slice(1, -1).trim();
  }
  return out.replace(/^[\s,;:.–-]+/, '').trim();
}

export function dateParts(r) {
  const note = (r.date_note || '').trim();
  const hasYear = typeof r.year === 'number';
  if (note) {
    let kind = null;
    let rest = note;
    for (const [re, word] of QUALIFIER) {
      if (re.test(rest)) { kind = word; rest = rest.replace(re, '').trim(); break; }
    }
    const m = rest.match(DATE_CORE);
    if (m && m[0].trim()) {
      return { date: m[0].trim(), kind, about: tidy(rest.slice(m[0].length)) || null };
    }
    // The note is prose. Keep the structured year in the chip and the prose below.
    if (hasYear) return { date: yearLabel(r.year), kind: null, about: note };
    return null;
  }
  if (!hasYear) return null;
  return { date: yearLabel(r.year), kind: null, about: null };
}

export function dateLabel(r) {
  const p = dateParts(r);
  return p ? p.date : null;
}
