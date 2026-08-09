import React from 'react';

// One-line, plain-language explanation of what each search mode does, shown
// under the mode toggle (and on the standalone Line/String and Cross-Language
// pages). Language-agnostic — the same description applies to every language.
export const SEARCH_DESCRIPTIONS = {
  parallel:
    'You set only the texts to compare; the search finds the most similar phrases between them, based on a variety of similarity types.',
  line:
    'You enter a line to find other lines like it.',
  string:
    'You enter specific terms, and can use wildcards (am*), phrases, and AND/OR operators.',
  bigram:
    'Finds uncommon two-word combinations that appear in both of two chosen texts but are rare across the corpus — it can catch rare combinations of otherwise ordinary words.',
  hapax:
    'Finds rare words that two chosen texts share.',
  cross:
    'Finds parallels across languages — e.g. the Greek source behind a Latin, Coptic, or English text.',
};

export default function SearchDescription({ mode, className = '' }) {
  const text = SEARCH_DESCRIPTIONS[mode];
  if (!text) return null;
  return <p className={`text-sm text-gray-600 ${className}`}>{text}</p>;
}
