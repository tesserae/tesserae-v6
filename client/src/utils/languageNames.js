// One place for the display name of a language code (2026-09-06). Three
// components had spelled the same chain out by hand and every one fell back
// to 'English' for a code it did not know, so the Persian tab read
// "Search English Texts".
export const LANGUAGE_NAMES = {
  la: 'Latin', grc: 'Greek', en: 'English', cop: 'Coptic', he: 'Hebrew',
  fa: 'Persian', ur: 'Urdu', ar: 'Arabic',
  it: 'Italian', fro: 'Old French', gmh: 'Middle High German',
};

export function languageName(code) {
  return LANGUAGE_NAMES[code] || (code ? String(code).toUpperCase() : '');
}
