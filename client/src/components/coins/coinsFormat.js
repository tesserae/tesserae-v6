import { dateLabel } from '../events/eventsFormat';

export { dateLabel, yearLabel } from '../events/eventsFormat';

/** The label for a coin type's date range, or "undated". */
export function coinDate(c) {
  return dateLabel(c.date_start, c.date_end) || 'undated';
}

/** A signed year from a number and an era ('BCE' or 'CE'); null for an empty box. */
export function signedYear(text, era) {
  const n = parseInt(String(text).trim(), 10);
  if (Number.isNaN(n) || n <= 0) return null;
  return era === 'BCE' ? -n : n;
}

/** The title shown on a card: the catalogue reference, else the identifier. */
export function coinTitle(c) {
  return c.title || c.id;
}

export function coinPath(c) {
  return `/coins/${encodeURIComponent(c.id)}`;
}
