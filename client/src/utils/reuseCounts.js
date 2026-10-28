/** "5 works with 9 passages": the gutter's dashed box counts other works, and one
 *  work can echo a line in several passages, so the section label gives both
 *  numbers and the box's figure is always visible here (2026-10-27: a box read
 *  5 and the label 9, and the two looked like a mismatch). */
export function passagesInWorks(quotations) {
  const n = quotations.length;
  const w = new Set(quotations.map((q) => q.work)).size;
  const passages = `${n} passage${n === 1 ? '' : 's'}`;
  const works = `${w} work${w === 1 ? '' : 's'}`;
  // Works first, the figure the box beside the line shows (2026-10-28).
  return n === w ? works : `${works} with ${passages}`;
}
