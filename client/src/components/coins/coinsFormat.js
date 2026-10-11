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

/** The full names of the catalogues the coin types come from, by source code. */
export const CATALOGUE_NAMES = {
  ocre: 'Online Coins of the Roman Empire',
  crro: 'Coinage of the Roman Republic Online',
  cn: 'Corpus Nummorum',
  sco: 'Seleucid Coins Online',
  pella: 'PELLA',
  pco: 'Ptolemaic Coins Online',
  bigr: 'Bactrian and Indo-Greek Rulers',
  iris: 'IRIS',
  lco: 'Levantine Coinages Online',
};

export function catalogueName(c) {
  return CATALOGUE_NAMES[String(c.source || '').toLowerCase()] || (c.source ? String(c.source).toUpperCase() : 'the catalogue');
}

/** The catalogue's own name for the type: "Corpus Nummorum type 18624". */
export function catalogueLine(c) {
  const name = catalogueName(c);
  const suffix = String(c.id || '').split(':').slice(1).join(':');
  if (/^\d+$/.test(suffix)) return `${name} type ${suffix}`;
  const ref = c.title || suffix;
  return ref ? `${name}, ${ref}` : name;
}

function known(authority) {
  return authority && !/^(anonymous|unknown|uncertain)$/i.test(authority.trim()) ? authority : null;
}

/**
 * A plain description built from the fields, not the catalogue number:
 * "Bronze coin of Scepsis, 44 BCE to 69 CE", or with an authority and a
 * denomination "Silver denarius of Augustus, minted at Rome, 27 to 25 BCE".
 */
export function coinHeading(c) {
  const denom = c.denomination && c.denomination.trim();
  const material = c.material && c.material.trim();
  let noun = 'coin';
  if (denom) noun = material && /^[A-Z][a-z]+$/.test(denom) ? denom.toLowerCase() : denom;
  let what = material ? `${material} ${noun}` : noun;
  what = what.charAt(0).toUpperCase() + what.slice(1);
  const authority = known(c.authority);
  let head = what;
  if (authority) {
    head += ` of ${authority}`;
    if (c.mint) head += `, minted at ${c.mint}`;
  } else if (c.mint) {
    head += ` of ${c.mint}`;
  }
  if (c.date_start !== null && c.date_start !== undefined) head += `, ${coinDate(c)}`;
  return head;
}

/** The type's credit with its identifier at the end, for the small grey line. */
export function creditLine(c) {
  return [c.credit, c.id ? `id ${c.id}` : null].filter(Boolean).join(' · ');
}
