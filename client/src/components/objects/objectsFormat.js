import { dateLabel } from '../events/eventsFormat';

export { signedYear } from '../coins/coinsFormat';

/** The label for an object's date: the museum's own words, else the span of years, else "undated". */
export function objectDate(o) {
  return o.date_text || dateLabel(o.date_start, o.date_end) || 'undated';
}

/** The title shown on a card: the museum's title, else the identifier. */
export function objectTitle(o) {
  return o.title || o.id;
}

export function objectPath(o) {
  return `/objects/${encodeURIComponent(o.id)}`;
}

/** The accession number: the identifier without the museum prefix. */
export function accession(o) {
  return String(o.id).replace(/^[a-z]+:/, '');
}

export const MUSEUM_NAMES = {
  cleveland: 'Cleveland Museum of Art',
  chicago: 'Art Institute of Chicago',
  smithsonian: 'Smithsonian',
};
