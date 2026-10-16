// Wording for a large pairwise comparison, which the server runs in parts.
// The server sends the numbers (fusion_parts: {part, total_parts}, a
// large_queue flag, and the estimate from /api/fusion-estimate); the page
// words them here.

export const LARGE_QUEUE_TEXT =
  'Waiting for another large comparison to finish. Another large comparison is running first.';

// "about 1 minute" / "about 27 minutes"
const minutes = (n) => `${n} ${n === 1 ? 'minute' : 'minutes'}`;

export const estimateMinutes = (estimate) =>
  Math.max(1, Math.round((estimate?.estimated_seconds || 0) / 60));

export const estimateMillions = (estimate) =>
  Math.max(1, Math.round((estimate?.pairs || 0) / 1e6));

// The warning shown before a large comparison is sent.
export const largeComparisonWarning = (sourceName, targetName, estimate) =>
  `Large comparison. ${sourceName} against ${targetName} is about ` +
  `${estimateMillions(estimate)} million line pairs and will take about ` +
  `${minutes(estimateMinutes(estimate))}. The results fill in part by part, ` +
  'and you can leave the page open. Comparing selected books finishes in a minute or two.';

// Minutes left, from the time the finished parts took (partStarts maps a part
// number to the seconds into the search at which it began); before the first
// part has finished, from the estimate. null when neither is known.
export const minutesLeft = (parts, elapsed, partStarts, estimateSeconds) => {
  if (!parts || !parts.total_parts) return null;
  const { part, total_parts: total } = parts;
  let seconds = null;
  const first = partStarts?.[1];
  const current = partStarts?.[part];
  if (part > 1 && first != null && current != null && current > first) {
    const perPart = (current - first) / (part - 1);
    seconds = perPart * (total - part + 1) - Math.max(0, elapsed - current);
  } else if (estimateSeconds) {
    seconds = estimateSeconds - elapsed;
  }
  if (seconds == null) return null;
  return Math.max(1, Math.round(Math.max(0, seconds) / 60));
};

// The progress line while a search runs in parts.
export const partsProgressText = (parts, elapsed, partStarts, estimateSeconds) => {
  if (!parts || !parts.total_parts) return '';
  const left = minutesLeft(parts, elapsed, partStarts, estimateSeconds);
  const base = `Large comparison: part ${parts.part} of ${parts.total_parts}`;
  return left == null ? base : `${base}, about ${minutes(left)} left`;
};

// The progress line for any search: the parts line when running in parts,
// otherwise the step the server reports.
export const progressWithParts = (step, detail, parts, elapsed, partStarts, estimateSeconds) => {
  const large = partsProgressText(parts, elapsed, partStarts, estimateSeconds);
  if (large) return large;
  return detail ? `${step}: ${detail}` : step;
};
