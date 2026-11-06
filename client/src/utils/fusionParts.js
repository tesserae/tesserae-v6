// Wording for a large pairwise comparison, which the server runs in parts.
// The server sends the numbers (fusion_parts: {part, total_parts}, a
// large_queue flag, and the estimate from /api/fusion-estimate); the page
// words them here.

export const LARGE_QUEUE_TEXT =
  'Waiting to start: another large comparison is running first. Yours starts as soon as that one finishes.';

const CLOCK = (seconds) => {
  const s = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

// The line shown while a comparison waits to start. The server words it and
// sends it as `message` (in a streamed "queued" event and in the poll answer
// with status "queued"); this builds the same line if only the numbers came.
export const queuedText = (q) => {
  if (!q) return '';
  if (q.message) return q.message;
  const waited = q.wait_seconds ?? q.wait_time ?? 0;
  const head = q.kind === 'memory' || q.kind === 'emergency'
    ? "Waiting to start: the server's memory is in use by other searches"
    : `Waiting to start: ${(q.running || 0) + Math.max(0, (q.position || 1) - 1)} comparisons are ahead of yours`;
  return `${head}. Waiting for ${CLOCK(waited)} so far.`;
};

// "about 1 minute" / "about 27 minutes"
const minutes = (n) => `${n} ${n === 1 ? 'minute' : 'minutes'}`;

export const estimateMinutes = (estimate) =>
  Math.max(1, Math.round((estimate?.estimated_seconds || 0) / 60));

export const estimateMillions = (estimate) =>
  Math.max(1, Math.round((estimate?.pairs || 0) / 1e6));

// The line shown at the start of a large comparison, while it runs.
export const largeComparisonLine = (sourceName, targetName, estimate) =>
  `${sourceName} against ${targetName}: about ` +
  `${estimateMillions(estimate)} million line pairs, about ` +
  `${minutes(estimateMinutes(estimate))}. The results fill in part by part.`;

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
