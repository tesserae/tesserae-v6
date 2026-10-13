import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  workTitle,
  recordFrom, toRIS, toBibTeX, toText, risList, bibList, bibKeys, parseEdition, safeName,
  loadEditions, resetEditions, withEdition,
} from '../citations';

const SERVIUS_ED = 'Georgius Thilo and Hermannus Hagen, eds., Servii Grammatici qui feruntur in Vergilii carmina commentarii (Leipzig: B. G. Teubner, 1878-1902)';

const article = () => recordFrom({
  type: 'journal-article', authors: ['A. J. Woodman'], year: 2006, title: 'Mutiny and Madness: Tacitus Annals 1.16-49',
  venue: 'Arethusa', volume: '39', issue: '2', doi: '10.1353/are.2006.0014',
}, 'main');
const thesis = () => recordFrom({
  authors: ['Alyson Wright'], year: 1996, title: 'The Hunt in Latin Epic', venue: 'Durham e-Theses', url: 'http://etheses.dur.ac.uk/1234/',
}, 'main');
const book = () => recordFrom({
  authors: ['Philip Hardie'], year: 1986, title: "Virgil's Aeneid: Cosmos and Imperium", publisher: 'Clarendon Press',
  preview: 'https://books.google.com/books?id=abc',
}, 'book');
const servius = () => recordFrom({
  note: { ref: '1.1', text: 'x' },
  section: { commentator: 'Servius', title: 'In Vergilii Aeneidos libros commentarii', edition: SERVIUS_ED },
  work: 'vergil.aeneid',
}, 'note');

describe('recordFrom', () => {
  it('types a journal article, a thesis, a chapter and a book', () => {
    expect(article().type).toBe('article');
    expect(thesis().type).toBe('thesis');
    expect(recordFrom({ type: 'book-chapter', title: 'x' }, 'main').type).toBe('chapter');
    expect(book().type).toBe('book');
  });
  it('maps a Theme Search commentary card and an article card', () => {
    const c = recordFrom({ kind: 'commentary', commentator: 'Servius', work: 'vergil.aeneid', ref_start: '1.1', ref_end: '1.3', snippet: 's' }, 'card');
    expect(c).toMatchObject({ type: 'commentary', commentator: 'Servius', ref_start: '1.1', ref_end: '1.3' });
    const a = recordFrom({ kind: 'article', journal: 'Classical Philology', title: 'Notes', authors: 'A. B. Smith; C. Jones', year: 1912, link: { url: 'https://www.jstor.org/stable/1' } }, 'card');
    expect(a).toMatchObject({ type: 'article', venue: 'Classical Philology', url: 'https://www.jstor.org/stable/1' });
    expect(a.authors).toEqual(['A. B. Smith', 'C. Jones']);
  });
  it('does not take the citing pages of an index record for its page range', () => {
    expect(recordFrom({ title: 't', pages: [3, 5] }, 'index').pages).toBe('');
  });
});

describe('toRIS', () => {
  it('writes an article as it always did, with a DOI link', () => {
    expect(toRIS(article())).toBe([
      'TY  - JOUR', 'AU  - A. J. Woodman', 'TI  - Mutiny and Madness: Tacitus Annals 1.16-49', 'JO  - Arethusa',
      'PY  - 2006', 'VL  - 39', 'IS  - 2', 'DO  - 10.1353/are.2006.0014', 'UR  - https://doi.org/10.1353/are.2006.0014', 'ER  - ', '']
      .join('\n'));
  });
  it('prefers the free copy for UR', () => {
    const r = { ...article(), oa_url: 'https://free.example/p.pdf' };
    expect(toRIS(r)).toContain('UR  - https://free.example/p.pdf');
    expect(toRIS(r)).not.toContain('UR  - https://doi.org');
  });
  it('writes a thesis as THES', () => {
    const t = toRIS(thesis());
    expect(t.startsWith('TY  - THES')).toBe(true);
    expect(t).toContain('PB  - Durham e-Theses');
  });
  it('writes a commentary note as a BOOK with the edition and the locus', () => {
    expect(toRIS(servius())).toBe([
      'TY  - BOOK', 'AU  - Servius', 'TI  - Servii Grammatici qui feruntur in Vergilii carmina commentarii',
      'A2  - Georgius Thilo', 'A2  - Hermannus Hagen', 'PB  - B. G. Teubner', 'CY  - Leipzig', 'PY  - 1878',
      'N1  - on Vergil, Aeneid 1.1', 'ER  - ', ''].join('\n'));
  });
  it('puts an unparsed edition whole in TI and nothing else of it', () => {
    const r = { ...servius(), edition: 'Some old edition' };
    const t = toRIS(r);
    expect(t).toContain('TI  - Some old edition');
    expect(t).not.toContain('A2  -');
    expect(t).not.toContain('PB  -');
  });
  it('joins a list, one record each', () => {
    expect(risList([article(), thesis()]).match(/ER {2}- /g)).toHaveLength(2);
  });
});

describe('toBibTeX', () => {
  it('writes an article with a key, braces round the title and no url that repeats the DOI', () => {
    const b = toBibTeX(article());
    expect(b).toContain('@article{woodman2006mutiny,');
    expect(b).toContain('title = {Mutiny and Madness: Tacitus Annals 1.16-49}');
    expect(b).toContain('journal = {Arethusa}');
    expect(b).toContain('number = {2}');
    expect(b).not.toContain('url =');
  });
  it('picks the entry type', () => {
    expect(toBibTeX(thesis())).toContain('@phdthesis{wright1996hunt,');
    expect(toBibTeX(thesis())).toContain('school = {Durham e-Theses}');
    expect(toBibTeX(book())).toContain('@book{hardie1986virgils,');
    expect(toBibTeX(recordFrom({ type: 'book-chapter', title: 'A chapter here', authors: ['X Y'], venue: 'A Companion', year: 2001 }, 'main')))
      .toContain('@incollection{y2001chapter,');
  });
  it('escapes special characters and joins authors with and', () => {
    const r = { ...article(), title: 'Fish & Chips_100%', authors: ['A One', 'B Two'] };
    const b = toBibTeX(r);
    expect(b).toContain('Fish \\& Chips\\_100\\%');
    expect(b).toContain('author = {A One and B Two}');
  });
  it('strips accents from keys and makes list keys unique', () => {
    const a = { ...article(), authors: ['Émile Zölle'] };
    expect(toBibTeX(a)).toContain('zolle2006mutiny');
    expect(bibKeys([article(), article(), thesis()])).toEqual(['woodman2006mutinya', 'woodman2006mutinyb', 'wright1996hunt']);
    expect(bibList([article(), article()])).toContain('woodman2006mutinyb');
  });
  it('writes a commentary note with editors and the locus', () => {
    const b = toBibTeX(servius());
    expect(b).toContain('@book{servius1878servii,');
    expect(b).toContain('editor = {Georgius Thilo and Hermannus Hagen}');
    expect(b).toContain('note = {on Vergil, Aeneid 1.1}');
  });
});

describe('toText', () => {
  it('writes an article', () => {
    expect(toText(article())).toBe('Woodman, A. J. 2006. "Mutiny and Madness: Tacitus Annals 1.16-49." Arethusa 39 (2). https://doi.org/10.1353/are.2006.0014');
  });
  it('inverts only the first of several authors', () => {
    expect(toText({ type: 'article', authors: ['Alyson Wright', 'Pat Smith', 'Lee Ng'], year: 2000, title: 'T?' }))
      .toBe('Wright, Alyson, Pat Smith, and Lee Ng. 2000. "T?"');
  });
  it('leaves missing parts out cleanly', () => {
    expect(toText({ type: 'article', title: 'Only a title' })).toBe('"Only a title."');
    expect(toText(book())).toBe("Hardie, Philip. 1986. Virgil's Aeneid: Cosmos and Imperium. Clarendon Press. https://books.google.com/books?id=abc");
  });
  it('writes a commentary note with its locus, or the commentator alone', () => {
    expect(toText(servius())).toBe(`Servius. ${SERVIUS_ED}. On Vergil, Aeneid 1.1.`);
    expect(toText({ type: 'commentary', commentator: 'Servius', work: 'vergil.aeneid', ref_start: '1.1' })).toBe('Servius. On Vergil, Aeneid 1.1.');
  });
  it('lets a ref that starts with letters stand alone', () => {
    expect(toText({ type: 'commentary', commentator: 'C', work: 'vergil.aeneid', ref_start: 'verg. aen. 7.641' })).toBe('C. On verg. aen. 7.641.');
  });
});

describe('parseEdition and names', () => {
  it('parses the usual form and refuses others', () => {
    expect(parseEdition(SERVIUS_ED)).toMatchObject({ editors: ['Georgius Thilo', 'Hermannus Hagen'], place: 'Leipzig', publisher: 'B. G. Teubner', year: '1878-1902' });
    expect(parseEdition('Anonymous printing')).toBeNull();
  });
  it('makes an ASCII file name under 60 characters', () => {
    expect(safeName('Ciceró: what is "virtue"?')).toBe('Cicero_what_is_virtue');
    expect(safeName('x'.repeat(100)).length).toBeLessThan(60);
    expect(safeName('')).toBe('citations');
  });
});

describe('editions lookup', () => {
  beforeEach(() => { resetEditions(); });
  it('fetches the sources once and fills a commentary record by commentator', async () => {
    global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ commentaries: [{ commentator: 'Servius', edition: SERVIUS_ED }] }) }));
    await loadEditions();
    const r = await withEdition({ type: 'commentary', commentator: 'servius', work: 'vergil.aeneid', ref_start: '1.1' });
    expect(r.edition).toBe(SERVIUS_ED);
    await withEdition({ type: 'commentary', commentator: 'Servius' });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
  it('cites the commentator and locus alone when the lookup fails', async () => {
    global.fetch = vi.fn(async () => { throw new Error('down'); });
    const r = await withEdition({ type: 'commentary', commentator: 'Servius', work: 'vergil.aeneid', ref_start: '1.1' });
    expect(r.edition).toBeUndefined();
    expect(toText(r)).toBe('Servius. On Vergil, Aeneid 1.1.');
  });
});

describe('workTitle', () => {
  it('reads a work id as author and title', () => {
    expect(workTitle('vergil.aeneid')).toBe('Vergil, Aeneid');
    expect(workTitle('vergil.aeneid.part.4')).toBe('Vergil, Aeneid');
    expect(workTitle('how_wells.herodotus.histories')).toBe('How Wells, Herodotus, Histories');
    expect(workTitle('')).toBe('');
  });
});
