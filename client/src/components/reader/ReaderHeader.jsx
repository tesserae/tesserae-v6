import { Fragment, useEffect, useMemo, useState } from 'react';
import { LANGUAGE_NAMES as LANG_LABEL } from '../../utils/languageNames';
import SearchableSelect from '../common/SearchableSelect';
import { formatSelectionRange, useCorpusTextMap } from '../../utils/textNames';
import { dateLabel } from '../../utils/chronology';
import { decodeEntities } from '../../utils/htmlEntities';

/**
 * The Reader's header: where you are, and how to go somewhere else.
 *
 * Four plain dropdowns in the order a reader thinks in -- language, author,
 * work, book -- then the position in the text on the right.
 *
 * This replaces a two-step author-then-work selector borrowed from the search
 * page. That selector passed the Reader's own language through, so a reader of
 * a Greek text was offered only Greek authors and could not reach Coptic,
 * Hebrew or English at all; and choosing an author left the header showing the
 * previous work until a text was picked, so the page sat in a half-changed
 * state. Making the language a control of its own fixes both: every corpus is
 * reachable, and each step narrows the next.
 *
 * The Book dropdown hides itself for a work that has no books, rather than
 * showing one disabled control on every prose text.
 */

// Latin, Greek, English first, as everywhere else on the site. This is a
// display order, not a name lookup, so it stays local; the names themselves
// come from the one shared table (utils/languageNames.js).
const LANG_ORDER = ['la', 'grc', 'en', 'he', 'cop', 'fa', 'ur', 'ar', 'it', 'fro', 'gmh'];

function Select({ label, value, options, onChange, disabled }) {
  return (
    <label className="flex items-center">
      <span className="sr-only">{label}</span>
      <select
        aria-label={label}
        value={value || ''}
        disabled={disabled || !options.length}
        onChange={(e) => onChange(e.target.value)}
        className="max-w-[11rem] truncate rounded border border-gray-300 bg-white px-2 py-1 text-sm
                   text-gray-800 hover:border-gray-400 focus:outline-none focus:ring-1
                   focus:ring-red-600 disabled:bg-gray-50 disabled:text-gray-500"
      >
        {!value && <option value="">{label}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

export default function ReaderHeader({
  language, onLanguage, hierarchy, work, onWork, units, selection,
}) {
  const [languages, setLanguages] = useState([]);
  const corpusMap = useCorpusTextMap(language);

  // A curated two-or-three-sentence orientation blurb for the open work,
  // where one exists (data/text_descriptions.json). The About button only
  // appears when there is something to show.
  const [about, setAbout] = useState(null);
  const [aboutOpen, setAboutOpen] = useState(false);
  // Licensed for indexing and search only (data/restricted_texts.json): the
  // same lookup that fetches the orientation blurb carries this work's credit
  // line, so one request answers both.
  const [credit, setCredit] = useState(null);
  // The About panel's right-hand facts (author, date, era, kind, edition):
  // additive on the same response, rather than a second route (see
  // backend/blueprints/corpus.py's _work_facts).
  const [facts, setFacts] = useState(null);
  useEffect(() => {
    setAbout(null);
    setAboutOpen(false);
    setCredit(null);
    setFacts(null);
    if (!work) return undefined;
    let dead = false;
    const p = new URLSearchParams({ language: language || 'la', work });
    fetch(`/api/text-descriptions?${p}`)
      .then((r) => r.json())
      .then((d) => {
        if (dead) return;
        setAbout(d.description || null);
        setCredit(d.restricted ? d.credit : null);
        setFacts(d.facts || null);
      })
      .catch(() => {});
    return () => { dead = true; };
  }, [work, language]);

  // The attached translation's attribution, where one exists, for the About
  // panel's Translation row. Fetched only once the panel is actually opened
  // (the same route the Translation tab calls for the whole work, /api/
  // passages/translation-full, but the blocks are not needed here -- only
  // the attribution it carries).
  const [translationAttribution, setTranslationAttribution] = useState(null);
  useEffect(() => {
    setTranslationAttribution(null);
    if (!aboutOpen || !work) return undefined;
    let dead = false;
    const p = new URLSearchParams({ work, language: language || 'la' });
    fetch(`/api/passages/translation-full?${p}`)
      .then((r) => r.json())
      .then((d) => { if (!dead) setTranslationAttribution(d?.available ? (d.attribution || null) : null); })
      .catch(() => {});
    return () => { dead = true; };
  }, [aboutOpen, work, language]);

  useEffect(() => {
    let dead = false;
    fetch('/api/languages')
      .then((r) => r.json())
      .then((d) => {
        if (dead) return;
        const codes = (d.languages || []).map((l) => l.code || l).filter(Boolean);
        setLanguages(codes.length ? codes : LANG_ORDER);
      })
      .catch(() => { if (!dead) setLanguages(LANG_ORDER); });
    return () => { dead = true; };
  }, []);

  // Where the current work sits in the hierarchy, so the dropdowns show the
  // text actually open rather than whatever was last picked.
  const here = useMemo(() => {
    const id = String(work || '');
    for (const a of hierarchy || []) {
      for (const w of a.works || []) {
        if ((w.sections || []).some((s) => s.file === id)) {
          return { author: a.author_key || a.author, workKey: w.work_key, work: w };
        }
      }
    }
    return { author: '', workKey: '', work: null };
  }, [hierarchy, work]);

  const authorOptions = (hierarchy || [])
    .map((a) => ({ value: a.author_key || a.author, label: a.author }))
    .sort((x, y) => x.label.localeCompare(y.label));

  const authorEntry = (hierarchy || []).find(
    (a) => (a.author_key || a.author) === here.author);

  const workOptions = (authorEntry?.works || [])
    .map((w) => ({ value: w.work_key, label: w.work }));

  const bookOptions = (here.work?.sections || [])
    .map((s) => ({ value: s.file, label: s.label }));

  const langOptions = [...new Set([...LANG_ORDER, ...languages])]
    .filter((c) => languages.length === 0 || languages.includes(c))
    .map((c) => ({ value: c, label: LANG_LABEL[c] || c }));

  /** First text of an author, or of a work: what "choose this" should open. */
  const firstOf = (entry) => {
    const w = (entry?.works || [])[0];
    return (w?.sections || [])[0]?.file || '';
  };

  const range = (() => {
    if (selection?.refStart) {
      return formatSelectionRange(selection.refStart, selection.refEnd, corpusMap, work);
    }
    if (!units?.length) return '';
    return `${units.length} lines`;
  })();

  // The About panel, set out the way a library work page is: the work's name
  // first, one quiet line of landmark facts (date, era, kind, length), the
  // description, then the sources as a footnote. A fact with nothing to show
  // is left out. Date reuses the formatter Theme Search and Similar Passages
  // use ("19 BCE", "c. 390 CE").
  const aboutTitle = useMemo(() => {
    if (!facts) return null;
    const parts = [facts.author, facts.work, facts.part].filter(Boolean);
    return parts.length ? parts.join(', ') : null;
  }, [facts]);
  const factItems = useMemo(() => {
    const date = facts ? dateLabel({ year: facts.year, date_note: facts.date_note }) : null;
    const kind = facts?.kind === 'poetry' ? 'Poetry' : facts?.kind === 'prose' ? 'Prose' : null;
    const lineCount = units?.length ? `${units.length} line${units.length === 1 ? '' : 's'}` : null;
    return [
      [date, 'Approximate date of the work'],
      [facts?.era || null, "The period of Greek or Roman history the author's work belongs to"],
      [kind, kind === 'Poetry' ? 'Written in verse' : 'Written in prose'],
      [lineCount, 'The number of lines in the text open in the Reader'],
    ].filter(([value]) => value);
  }, [facts, units]);
  const sourcesNote = useMemo(() => {
    const edition = facts?.edition || null;
    const print = edition?.print_source
      ? decodeEntities(edition.print_source).trim().replace(/[.,;\s]+$/, '') : null;
    const digital = edition?.e_source
      ? (edition.e_source_url
        ? <a href={edition.e_source_url} target="_blank" rel="noopener noreferrer"
             className="text-red-700 hover:underline">{edition.e_source}</a>
        : edition.e_source)
      : null;
    const translation = translationAttribution
      ? decodeEntities(translationAttribution).trim().replace(/[.,;\s]+$/, '') : null;
    if (!print && !digital && !translation) return null;
    return (
      <>
        {(print || digital) && (
          <>
            {'Text from '}{print || digital}{print && digital ? ', through ' : ''}{print && digital ? digital : ''}{'. '}
          </>
        )}
        {translation && `Translation by ${translation}. `}
      </>
    );
  }, [facts, translationAttribution]);
  const creditsHref = facts?.author
    ? `/text-credits?author=${encodeURIComponent(facts.author)}`
    : '/text-credits';

  return (
    <>
    <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-200 flex-wrap">
      <span className="font-semibold tracking-wide text-gray-900 mr-1"
            style={{ fontFamily: '"Gentium Book", Georgia, serif' }}>
        TESSERAE <span className="text-red-700">READER</span>
      </span>
      <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px]
                       font-semibold uppercase tracking-wide text-amber-800">
        Beta
      </span>

      <Select label="Language" value={language} options={langOptions}
              onChange={(v) => onLanguage(v)} />
      <div className="flex items-center">
        <SearchableSelect
          ariaLabel="Author"
          value={here.author}
          options={authorOptions}
          placeholder="Author"
          disabled={!authorOptions.length}
          onChange={(v) => {
            const entry = (hierarchy || []).find(
              (a) => (a.author_key || a.author) === v);
            const next = firstOf(entry);
            if (next) onWork(next);
          }}
          className="max-w-[11rem] truncate rounded border border-gray-300 bg-white px-2 py-1 text-sm
                     text-gray-800 hover:border-gray-400 disabled:bg-gray-50 disabled:text-gray-500"
        />
      </div>
      <div className="flex items-center">
        <SearchableSelect
          ariaLabel="Work"
          value={here.workKey}
          options={workOptions}
          placeholder="Work"
          disabled={!workOptions.length}
          onChange={(v) => {
            const w = (authorEntry?.works || []).find((x) => x.work_key === v);
            const next = (w?.sections || [])[0]?.file;
            if (next) onWork(next);
          }}
          className="max-w-[11rem] truncate rounded border border-gray-300 bg-white px-2 py-1 text-sm
                     text-gray-800 hover:border-gray-400 disabled:bg-gray-50 disabled:text-gray-500"
        />
      </div>
      {bookOptions.length > 1 && (
        <div className="flex items-center">
          <SearchableSelect
            ariaLabel="Book"
            value={work}
            options={bookOptions}
            placeholder="Book"
            onChange={(v) => onWork(v)}
            className="max-w-[11rem] truncate rounded border border-gray-300 bg-white px-2 py-1 text-sm
                       text-gray-800 hover:border-gray-400 disabled:bg-gray-50 disabled:text-gray-500"
          />
        </div>
      )}
      {about && (
        <button
          onClick={() => setAboutOpen((o) => !o)}
          aria-expanded={aboutOpen}
          aria-label="About this text"
          title="About this text"
          className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
            aboutOpen
              ? 'border-red-300 bg-red-50 text-red-800'
              : 'border-gray-300 text-gray-600 hover:border-gray-400 hover:text-gray-800'}`}
        >
          About this text
        </button>
      )}

      {/* THE POSITION ONLY. This also printed metadata.display_name, so the
          header read "Vergil | Aeneid | Book 6 ... Vergil, Aeneid, Book 6" --
          the dropdowns already say which text is open, and saying it again in
          grey beside them is noise pretending to be information. What the
          dropdowns cannot say is WHERE in the text you are. */}
      <span className="ml-auto text-sm text-gray-600 tabular-nums">
        {range}
      </span>
    </div>
    {aboutOpen && about && (
      <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
        {/* One column at reading width (about 65 characters). */}
        {aboutTitle && (
          <h2 className="text-base font-semibold text-gray-900">{aboutTitle}</h2>
        )}
        {factItems.length > 0 && (
          <p className="mt-0.5 text-sm text-gray-500">
            {factItems.map(([value, tip], i) => (
              <Fragment key={tip}>
                {i > 0 && <span aria-hidden="true"> &middot; </span>}
                <span title={tip}>{value}</span>
              </Fragment>
            ))}
          </p>
        )}
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-gray-700">
          {about}
        </p>
        {facts && (
          <p className="mt-2 max-w-prose text-xs text-gray-500">
            {sourcesNote}
            <a href={creditsHref} className="text-red-700 hover:underline">Full credits</a>
          </p>
        )}
      </div>
    )}
    {credit && (
      <p className="px-4 py-1 text-[11px] text-gray-400 border-b border-gray-200">
        {credit}
      </p>
    )}
    </>
  );
}
