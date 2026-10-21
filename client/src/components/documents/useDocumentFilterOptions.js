import { useEffect, useState } from 'react';

// The choices behind the Region, Text type, Material and Source drop-downs,
// read once from /api/documents/browse and kept for the rest of the visit.

const MIN_DOCUMENTS = 20;
const LEFT_OUT = new Set(['unknown', 'other', '']);

export const SOURCE_OPTIONS = [
  { value: 'edr', label: 'Epigraphic Database Roma' },
  { value: 'edh', label: 'Epigraphic Database Heidelberg' },
  { value: 'papyri', label: 'Papyri (papyri.info)' },
  { value: 'isicily', label: 'I.Sicily' },
  { value: 'aio', label: 'Attic Inscriptions Online' },
  { value: 'edh+edr', label: 'EDH and EDR (both databases)' },
];

function capitalise(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

/**
 * Turns a list of {value, count} into drop-down options. Values that differ
 * only in case or trailing punctuation become one option (counts added), shown
 * in lower case with a capital first letter. The server matches a text type or
 * material as a case-insensitive substring, so the merged label finds every
 * variant. Values with fewer than MIN_DOCUMENTS documents, and "unknown" and
 * "other", are left out. Sorted by count, highest first.
 */
export function buildOptions(items, { keepCase = false } = {}) {
  const merged = new Map();
  (items || []).forEach(({ value, count }) => {
    const raw = String(value ?? '').trim();
    const key = raw.toLowerCase().replace(/[\s.,;:]+$/, '');
    if (LEFT_OUT.has(key) || key.startsWith('unknown')) return;
    const entry = merged.get(key) || { key, count: 0, first: raw };
    entry.count += count || 0;
    merged.set(key, entry);
  });
  return [...merged.values()]
    .filter(e => e.count >= MIN_DOCUMENTS)
    .sort((a, b) => b.count - a.count || a.key.localeCompare(b.key))
    .map(e => {
      const label = keepCase ? e.first.replace(/[\s.,;:]+$/, '') : capitalise(e.key);
      return { value: label, label, count: e.count };
    });
}

let optionsPromise = null;

export function resetDocumentFilterOptions() {
  optionsPromise = null;
}

function loadOptions() {
  if (!optionsPromise) {
    optionsPromise = fetch('/api/documents/browse?page_size=1')
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (!data) return null;
        const f = data.filters || {};
        return {
          regions: buildOptions(data.region_counts, { keepCase: true }),
          textTypes: buildOptions(f.text_types),
          materials: buildOptions(f.materials),
        };
      })
      .catch(() => null);
    // A failed fetch is not remembered, so the next visit tries again.
    optionsPromise.then(v => { if (!v) optionsPromise = null; });
  }
  return optionsPromise;
}

/** Options for the four filter drop-downs; fetched when `active` first turns true. */
export default function useDocumentFilterOptions(active = true) {
  const [options, setOptions] = useState({ regions: [], textTypes: [], materials: [] });
  useEffect(() => {
    if (!active) return undefined;
    let dead = false;
    loadOptions().then(o => { if (!dead && o) setOptions(o); });
    return () => { dead = true; };
  }, [active]);
  return { ...options, sources: SOURCE_OPTIONS };
}
