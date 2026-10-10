import React from 'react';
import { SEARCH_SCOPE } from '../../data/searchScope';

// One-line, plain-language explanation of what each search mode does. The
// sentences now live in data/searchScope.js, where the scope box reads them
// too, so the two always agree. The same
// description applies to every language. Cross-Language has no entry here:
// the owner asked for no description line above that page (owner's review,
// 2026-10-08).
export const SEARCH_DESCRIPTIONS = Object.fromEntries(
  ['parallel', 'line', 'string', 'bigram', 'hapax'].map((id) => [id, SEARCH_SCOPE[id].does]),
);

export default function SearchDescription({ mode, className = '' }) {
  const text = SEARCH_DESCRIPTIONS[mode];
  if (!text) return null;
  return <p className={`text-sm text-gray-600 ${className}`}>{text}</p>;
}
