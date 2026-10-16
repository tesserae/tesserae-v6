// Wording for a large pairwise comparison, which the server runs in parts.
// The server sends the numbers (fusion_parts: {part, total_parts}) and a
// large_queue flag; the page words them here.

export const LARGE_QUEUE_TEXT = 'Waiting for another large comparison to finish';

export const largeComparisonText = (parts) => {
  if (!parts || !parts.total_parts) return '';
  return `Large comparison: running in ${parts.total_parts} parts, part ${parts.part}`;
};

// The progress line while a search runs in parts: the parts wording, then the
// step the server reports.
export const progressWithParts = (step, detail, parts) => {
  const base = detail ? `${step}: ${detail}` : step;
  const prefix = largeComparisonText(parts);
  return prefix ? `${prefix}. ${base}` : base;
};
