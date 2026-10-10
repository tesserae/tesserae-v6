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
