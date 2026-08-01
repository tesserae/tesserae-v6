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
