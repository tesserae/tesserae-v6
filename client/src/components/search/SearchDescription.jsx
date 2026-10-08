import React from 'react';

// One-line, plain-language explanation of what each search mode does, shown
// under the mode toggle (and on the standalone Line/String pages). The same
// description applies to every language. Cross-Language has no entry here:
// the owner asked for no description line above that page (owner's review,
// 2026-10-08).
export const SEARCH_DESCRIPTIONS = {
  parallel:
    'You set only the texts to compare; the search finds the most similar phrases between them, based on a variety of similarity types.',
  line:
    'Enter a line to find other lines like it. Choose an existing line to search or write your own.',
  string:
    'Enter specific terms, optionally with wildcards (am*), phrases, or AND/OR operators.',
  bigram:
    'Finds rare two-word combinations that two chosen texts share. It can catch unusual pairings of otherwise ordinary words.',
  hapax:
    'Finds rare individual words that two chosen texts share.',
};

export default function SearchDescription({ mode, className = '' }) {
  const text = SEARCH_DESCRIPTIONS[mode];
  if (!text) return null;
  return <p className={`text-sm text-gray-600 ${className}`}>{text}</p>;
}
