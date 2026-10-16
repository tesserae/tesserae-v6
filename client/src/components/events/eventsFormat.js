import { bareLocus } from '../reader/refId';
import { citationFromCorpusMap } from '../../utils/textNames';

/** Years are signed: -490 is 490 BCE, 9 is 9 CE. */
export function yearLabel(y) {
  if (y === null || y === undefined) return '';
  return y < 0 ? `${-y} BCE` : `${y} CE`;
}

export function dateLabel(start, end) {
  if (start === null || start === undefined) return '';
  if (end === null || end === undefined || end === start) return yearLabel(start);
  // 'from 52 to 49 BCE' reads better than '52 BCE to 49 BCE' when both share an era
  if ((start < 0) === (end < 0)) {
    const a = Math.abs(start);
    return `${a} to ${yearLabel(end)}`;
  }
  return `${yearLabel(start)} to ${yearLabel(end)}`;
}

const ORD = (n) => {
  const t = n % 100;
  if (t >= 11 && t <= 13) return `${n}th`;
  return `${n}${({ 1: 'st', 2: 'nd', 3: 'rd' })[n % 10] || 'th'}`;
};

/** A signed century: -5 is "5th century BCE", 1 is "1st century CE". */
export function centuryLabel(c) {
  return `${ORD(Math.abs(c))} century ${c < 0 ? 'BCE' : 'CE'}`;
}

export function kmLabel(km) {
  if (km === null || km === undefined) return '';
  return `${km < 10 ? km.toFixed(1) : Math.round(km)} km`;
}

/** The Reader link for a passage, with the way back to the event. */
export function readerLinkWithBack(url, eventId, eventLabel) {
  return `${url}&event=${encodeURIComponent(eventId)}&eventLabel=${encodeURIComponent(eventLabel || '')}`;
}

/** The heading over one work's passages: "Thucydides, Peloponnesian War" from the
 *  corpus text map; without an entry, the id read as words ("Herodotus, Histories"). */
export function workHeading(work, corpusMap) {
  const id = String(work || '').replace(/\.tess$/, '').replace(/\.part\.\d+.*$/, '');
  const hit = citationFromCorpusMap(`${id}.0`, corpusMap);
  if (hit && (hit.author || hit.work)) return [hit.author, hit.work].filter(Boolean).join(', ');
  return id.split('.')
    .map((part) => part.split('_').filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1)).join(' '))
    .filter(Boolean).join(', ');
}

/** A scholarship row's passage_ref ("thuc. pele. 7.49.3-7.53.2") as the short locus
 *  ("7.49.3 to 7.53.2"). A ref with no range is shortened alone. */
export function shortPassageRef(ref) {
  const s = String(ref || '').trim();
  const m = /^(.*?\d[^\s]*?)\s*[-\u2013]\s*(\S*\d\S*)$/.exec(s);
  if (!m) return bareLocus(s);
  const a = bareLocus(m[1]);
  const b = bareLocus(m[2]);
  return a === b ? a : `${a} to ${b}`;
}
