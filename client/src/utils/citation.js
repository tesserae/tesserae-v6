/**
 * Citations for a Tesserae finding.
 *
 * A scholar who finds a parallel wants to put it in a footnote, and until now
 * the site offered no way to do that: it could export a table and copy a link,
 * and neither is a citation (interface audit, 2026-09-08).
 *
 * Three formats. The reproducible one is the default and the reason this
 * exists. A bibliography reference tells a reader where you were; it does not
 * let them get the same answer. Naming the corpus version and the search does,
 * because the corpus changes as texts are added and lemmatization improves, and
 * a result cited without that stamp cannot be checked a year later. The site
 * already stamps every search, so the fact is there to be used.
 *
 * MLA and Chicago are offered because most journals still want one of them.
 * They are deliberately plain: the styles have no rule for a database query, so
 * anything fancier would be invention dressed as authority.
 */

const SITE = 'Tesserae V6';
const HOST = 'tesserae.caset.buffalo.edu';

const MONTHS_MLA = ['Jan.', 'Feb.', 'Mar.', 'Apr.', 'May', 'June',
  'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
const MONTHS_FULL = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];

/** Drop empty pieces and join. Keeps a missing corpus version from leaving
 *  a dangling comma in the middle of a reference. */
const join = (parts, sep = ', ') => parts.filter(Boolean).join(sep);

function accessed(date, style) {
  const d = date instanceof Date ? date : new Date();
  if (style === 'mla') return `${d.getDate()} ${MONTHS_MLA[d.getMonth()]} ${d.getFullYear()}`;
  if (style === 'chicago') return `${MONTHS_FULL[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
  return d.toISOString().slice(0, 10);
}

/**
 * @param {object} f the finding.
 * @param {string} f.kind        what was run, e.g. 'fusion search', 'theme search'.
 * @param {string} [f.source]    "Hafez, Diwan 1626".
 * @param {string} [f.target]    "Ghalib, Diwan Wikisource 264.30".
 * @param {string} [f.query]     the query, for searches that take one.
 * @param {string} [f.language]  a display name, e.g. 'Persian'.
 * @param {number} [f.score]
 * @param {string} [f.channels]  e.g. 'semantic, shared vocabulary'.
 * @param {string} [f.corpusVersion]
 * @param {string} [f.url]       a link that reruns the search.
 * @param {Date}   [f.date]      defaults to today.
 */
export function reproducibleCitation(f) {
  const pair = f.source && f.target ? `${f.source} ~ ${f.target}` : (f.source || f.target || '');
  const head = join([
    SITE,
    f.corpusVersion ? `corpus ${f.corpusVersion}` : null,
    f.kind,
    f.language,
  ]);
  const body = join([
    f.query ? `query: "${f.query}"` : null,
    pair,
    typeof f.score === 'number' ? `score ${f.score.toFixed(3)}` : null,
    f.channels ? `channels: ${f.channels}` : null,
  ]);
  const tail = join([`accessed ${accessed(f.date)}`]);
  return join([head, body, tail], '. ') + (f.url ? `.\n${f.url}` : '.');
}

export function mlaCitation(f) {
  const pair = f.source && f.target ? `${f.source} and ${f.target}` : (f.source || f.target || '');
  const what = join([
    f.query ? `Search for “${f.query}”` : null,
    pair ? `Parallel between ${pair}` : null,
  ], '; ');
  // MLA 9 separates containers with periods and elements within a container
  // with commas. The loci themselves contain commas ("Hafez, Diwan 1626"), so
  // period-separated containers are what keeps this readable.
  return join([
    `Coffee, Neil, et al. ${SITE}`,
    `University at Buffalo, ${HOST}`,
    join([what || null, f.corpusVersion ? `corpus version ${f.corpusVersion}` : null]),
    `Accessed ${accessed(f.date, 'mla')}`,
  ], '. ') + '.';
}

export function chicagoCitation(f) {
  const pair = f.source && f.target ? `${f.source} and ${f.target}` : (f.source || f.target || '');
  const what = join([
    f.query ? `search for “${f.query}”` : null,
    pair ? `parallel between ${pair}` : null,
  ], '; ');
  return join([
    `Neil Coffee et al., ${SITE} (University at Buffalo)`,
    what || null,
    f.corpusVersion ? `corpus version ${f.corpusVersion}` : null,
    `accessed ${accessed(f.date, 'chicago')}`,
    `https://${HOST}`,
  ]) + '.';
}

export const CITATION_STYLES = [
  {
    key: 'reproducible',
    label: 'Reproducible',
    build: reproducibleCitation,
    note: 'Names the corpus version and the search, so a reader can run it again and get the same result.',
  },
  { key: 'mla', label: 'MLA', build: mlaCitation, note: 'For a works-cited list.' },
  { key: 'chicago', label: 'Chicago', build: chicagoCitation, note: 'For a footnote.' },
];

export function buildCitation(style, finding) {
  const s = CITATION_STYLES.find((x) => x.key === style) || CITATION_STYLES[0];
  return s.build(finding);
}
