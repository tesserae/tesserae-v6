// Fixed letter tables for Greek and Hebrew. The same rules as
// backend/transliterate.py, and both are tested against
// tests/fixtures/transliteration_cases.json so they cannot drift apart.
// The transliteration is made by this table, never by the language model.
// Beta code is provided for export controls and is not shown on any page.

const ROUGH = '̔';
const SMOOTH = '̓';
const SUBSCRIPT = 'ͅ';
const DIAERESIS = '̈';
const ACUTE = '́';
const GRAVE = '̀';
const CIRCUMFLEX = '͂';

const GREEK_LATIN = {
  α: 'a', β: 'b', γ: 'g', δ: 'd', ε: 'e', ζ: 'z', η: 'ē', θ: 'th',
  ι: 'i', κ: 'k', λ: 'l', μ: 'm', ν: 'n', ξ: 'x', ο: 'o', π: 'p',
  ρ: 'r', σ: 's', ς: 's', ϲ: 's', τ: 't', υ: 'y', φ: 'ph', χ: 'ch',
  ψ: 'ps', ω: 'ō',
};
const GREEK_BETA = {
  α: 'a', β: 'b', γ: 'g', δ: 'd', ε: 'e', ζ: 'z', η: 'h', θ: 'q',
  ι: 'i', κ: 'k', λ: 'l', μ: 'm', ν: 'n', ξ: 'c', ο: 'o', π: 'p',
  ρ: 'r', σ: 's', ς: 's', ϲ: 's', τ: 't', υ: 'u', φ: 'f', χ: 'x',
  ψ: 'y', ω: 'w',
};
const VOWELS = 'αεηιουω';
const DIPHTHONGS = new Set(['αι', 'ει', 'οι', 'υι', 'αυ', 'ευ', 'ηυ', 'ου']);
const NASALISING = 'γκξχ';
const LONG_WITH_IOTA = { α: 'āi', η: 'ēi', ω: 'ōi' };

const isCombining = (ch) => /\p{M}/u.test(ch);

function letters(text) {
  const out = [];
  for (const ch of String(text || '').normalize('NFD')) {
    const last = out[out.length - 1];
    const lower = ch.toLowerCase();
    if (isCombining(ch) && last && last.b !== null) {
      last.marks.add(ch);
    } else if (Object.prototype.hasOwnProperty.call(GREEK_LATIN, lower)) {
      out.push({ b: lower, up: ch !== lower, marks: new Set() });
    } else {
      out.push({ b: null, up: ch, marks: null });
    }
  }
  return out;
}

const cap = (s) => s[0].toUpperCase() + s.slice(1);

export function greekToLatin(text) {
  const toks = letters(text);
  const out = [];
  let skipH = false;
  toks.forEach((t, i) => {
    if (t.b === null) {
      out.push(t.up);
      skipH = false;
      return;
    }
    const b = t.b;
    const nxt = i + 1 < toks.length && toks[i + 1].b !== null ? toks[i + 1] : null;
    const prev = i > 0 && toks[i - 1].b !== null ? toks[i - 1] : null;
    let piece;
    if (VOWELS.includes(b)) {
      const dipth = !!(nxt && !nxt.marks.has(DIAERESIS) && DIPHTHONGS.has(b + nxt.b));
      const rough = t.marks.has(ROUGH) || (dipth && nxt.marks.has(ROUGH));
      const h = rough && !skipH ? 'h' : '';
      skipH = dipth;
      let core;
      if (b === 'υ') {
        const u = (nxt !== null && nxt.b === 'ι' && !nxt.marks.has(DIAERESIS) && !t.marks.has(DIAERESIS))
          || (prev !== null && 'αεηο'.includes(prev.b) && !t.marks.has(DIAERESIS)
              && DIPHTHONGS.has(prev.b + 'υ') && !prev.marks.has(DIAERESIS));
        core = u ? 'u' : 'y';
      } else if (t.marks.has(SUBSCRIPT) && LONG_WITH_IOTA[b]) {
        core = LONG_WITH_IOTA[b];
      } else {
        core = GREEK_LATIN[b];
      }
      piece = h + core;
    } else {
      skipH = false;
      if (b === 'γ' && nxt && NASALISING.includes(nxt.b)) piece = 'n';
      else if (b === 'ρ' && t.marks.has(ROUGH)) piece = 'rh';
      else piece = GREEK_LATIN[b];
    }
    out.push(t.up ? cap(piece) : piece);
  });
  return out.join('').normalize('NFC');
}

export function greekToBetaCode(text) {
  const out = [];
  letters(text).forEach((t) => {
    if (t.b === null) { out.push(t.up); return; }
    let d = '';
    if (t.marks.has(DIAERESIS)) d += '+';
    if (t.marks.has(SMOOTH)) d += ')';
    if (t.marks.has(ROUGH)) d += '(';
    if (t.marks.has(ACUTE)) d += '/';
    if (t.marks.has(GRAVE)) d += '\\';
    if (t.marks.has(CIRCUMFLEX)) d += '=';
    if (t.marks.has(SUBSCRIPT)) d += '|';
    out.push(t.up ? `*${d}${GREEK_BETA[t.b]}` : GREEK_BETA[t.b] + d);
  });
  return out.join('');
}

// ---- Hebrew ----------------------------------------------------------------

const HEB_CONS = {
  א: 'ʾ', ב: 'v', ג: 'g', ד: 'd', ה: 'h', ו: 'w', ז: 'z', ח: 'ḥ',
  ט: 'ṭ', י: 'y', כ: 'kh', ך: 'kh', ל: 'l', מ: 'm', ם: 'm', נ: 'n',
  ן: 'n', ס: 's', ע: 'ʿ', פ: 'f', ף: 'f', צ: 'ṣ', ץ: 'ṣ', ק: 'q',
  ר: 'r', ש: 'sh', ת: 't',
};
const HEB_PLAIN = { ב: 'b', כ: 'k', ך: 'k', פ: 'p', ף: 'p' };
const HEB_VOWELS = {
  'ֱ': 'e', 'ֲ': 'a', 'ֳ': 'o', 'ִ': 'i', 'ֵ': 'e',
  'ֶ': 'e', 'ַ': 'a', 'ָ': 'a', 'ֹ': 'o', 'ֺ': 'o',
  'ֻ': 'u', 'ׇ': 'a',
};
const SHEWA = 'ְ';
const DAGESH = 'ּ';
const SIN_DOT = 'ׂ';
const HEB_PUNCT = { '־': '-', '׃': '.' };

const isHebLetter = (ch) => ch >= 'א' && ch <= 'ת';
const isHebMark = (ch) => ch >= '֑' && ch <= 'ׇ';

export function hebrewToLatin(text) {
  const s = Array.from(String(text || '').normalize('NFD'));
  const out = [];
  let i = 0;
  const n = s.length;
  while (i < n) {
    if (!isHebLetter(s[i])) {
      if (HEB_PUNCT[s[i]]) out.push(HEB_PUNCT[s[i]]);
      else if (!isHebMark(s[i])) out.push(s[i]);
      i += 1;
      continue;
    }
    const word = [];
    while (i < n && (isHebLetter(s[i]) || isHebMark(s[i])) && !HEB_PUNCT[s[i]]) {
      if (isHebLetter(s[i])) word.push([s[i], new Set()]);
      else if (word.length) word[word.length - 1][1].add(s[i]);
      i += 1;
    }
    const pointed = word.some(([, ms]) => [...ms].some((m) => HEB_VOWELS[m] || m === SHEWA));
    const last = word.length - 1;
    word.forEach(([c, ms], k) => {
      const vowel = [...ms].filter((m) => HEB_VOWELS[m]).sort().map((m) => HEB_VOWELS[m]).join('');
      const dagesh = ms.has(DAGESH);
      if (c === 'ו' && pointed) {
        if (ms.has('ֹ') || ms.has('ֺ')) { out.push('o'); return; }
        if (dagesh && !vowel) { out.push('u'); return; }
      }
      if (c === 'י' && pointed && k > 0 && !vowel && !ms.has(SHEWA)) {
        const pm = word[k - 1][1];
        if (pm.has('ִ') || pm.has('ֵ')) return;
      }
      let cons;
      if (c === 'ש') cons = ms.has(SIN_DOT) ? 'ś' : 'sh';
      else if (!pointed && HEB_PLAIN[c]) cons = HEB_PLAIN[c];
      else if (pointed && HEB_PLAIN[c] && dagesh) cons = HEB_PLAIN[c];
      else cons = HEB_CONS[c];
      const sh = ms.has(SHEWA) && !vowel && k !== last ? 'e' : '';
      out.push(cons + vowel + sh);
    });
  }
  return out.join('').normalize('NFC');
}

// ---- Finding Greek and Hebrew inside running text -------------------------

// Greek (with its combining marks) and Hebrew runs. Spaces and an apostrophe
// may join two runs, so a phrase is one span. One capture group, for split().
const G = '[\\u0300-\\u03FF\\u1F00-\\u1FFF]';
const H = '[\\u0590-\\u05FF]';
export const SCRIPT_SPAN = new RegExp(
  `(${G}+(?:[ \\u00A0\\u0387\\u00B7'\\u2019]+${G}+)*|${H}+(?:[ \\u00A0]+${H}+)*)`, 'u');
export const GREEK_START = new RegExp(`^${G}`, 'u');
export const HEBREW_START = new RegExp(`^${H}`, 'u');

export function hasOriginalScript(text) {
  return SCRIPT_SPAN.test(String(text || ''));
}
