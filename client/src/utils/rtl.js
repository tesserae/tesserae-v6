// Right-to-left languages in the corpus. Persian, Arabic, Urdu, and Hebrew all
// use RTL scripts; everything else is left-to-right. Use isRTL(language) to set
// `dir` on elements that render corpus text, so the text lays out correctly.
export const RTL_LANGS = new Set(['fa', 'ar', 'ur', 'he']);

export const isRTL = (language) => RTL_LANGS.has(language);

// Convenience for JSX `dir` attributes: 'rtl' for RTL languages, else undefined
// (so LTR languages are unaffected).
export const dirFor = (language) => (isRTL(language) ? 'rtl' : undefined);
