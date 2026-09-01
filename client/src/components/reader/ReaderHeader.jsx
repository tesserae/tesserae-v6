import { useEffect, useMemo, useState } from 'react';

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

// Latin, Greek, English first, as everywhere else on the site.
const LANG_ORDER = ['la', 'grc', 'en', 'he', 'cop', 'fa', 'ur', 'it', 'fro', 'gmh'];
const LANG_LABEL = {
  la: 'Latin', grc: 'Greek', en: 'English', he: 'Hebrew',
  cop: 'Coptic', fa: 'Persian', ur: 'Urdu', ar: 'Arabic',
  it: 'Italian', fro: 'Old French', gmh: 'Middle High German',
};

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
                   focus:ring-red-600 disabled:bg-gray-50 disabled:text-gray-400"
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

  // A curated two-or-three-sentence orientation blurb for the open work,
  // where one exists (data/text_descriptions.json). The About button only
  // appears when there is something to show.
  const [about, setAbout] = useState(null);
  const [aboutOpen, setAboutOpen] = useState(false);
  useEffect(() => {
    setAbout(null);
    setAboutOpen(false);
    if (!work) return undefined;
    let dead = false;
    const p = new URLSearchParams({ language: language || 'la', work });
    fetch(`/api/text-descriptions?${p}`)
      .then((r) => r.json())
      .then((d) => { if (!dead) setAbout(d.description || null); })
      .catch(() => {});
    return () => { dead = true; };
  }, [work, language]);

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
      return selection.refStart === selection.refEnd
        ? selection.refStart
        : `${selection.refStart}–${shortRef(selection.refEnd, selection.refStart)}`;
    }
    if (!units?.length) return '';
    return `${units.length} lines`;
  })();

  return (
    <>
    <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-200 flex-wrap">
      <span className="font-semibold tracking-wide text-gray-900 mr-1"
            style={{ fontFamily: '"Gentium Book Plus", Georgia, serif' }}>
        TESSERAE <span className="text-red-700">READER</span>
      </span>
      <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px]
                       font-semibold uppercase tracking-wide text-amber-800">
        Beta
      </span>

      <Select label="Language" value={language} options={langOptions}
              onChange={(v) => onLanguage(v)} />
      <Select label="Author" value={here.author} options={authorOptions}
              onChange={(v) => {
                const entry = (hierarchy || []).find(
                  (a) => (a.author_key || a.author) === v);
                const next = firstOf(entry);
                if (next) onWork(next);
              }} />
      <Select label="Work" value={here.workKey} options={workOptions}
              onChange={(v) => {
                const w = (authorEntry?.works || []).find((x) => x.work_key === v);
                const next = (w?.sections || [])[0]?.file;
                if (next) onWork(next);
              }} />
      {bookOptions.length > 1 && (
        <Select label="Book" value={work} options={bookOptions}
                onChange={(v) => onWork(v)} />
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
          About
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
      <p className="px-4 py-2 text-sm text-gray-700 border-b border-gray-200 bg-gray-50">
        {about}
      </p>
    )}
    </>
  );
}

/** The range's end, shortened to what differs from its start:
 *  "verg. aen. 6.263"-"verg. aen. 6.301" -> "301". The old version kept the
 *  trailing digit run of the end ref alone, which read digits out of the WORK
 *  name: "shenoute.a22.1"-"shenoute.a22.3" displayed as "22.1-22.3" (NC hit
 *  it in Coptic, where several of Shenoute's canons are numbered works). */
function shortRef(refEnd, refStart) {
  const a = String(refStart || '');
  const b = String(refEnd || '');
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i += 1;
  const cut = Math.max(b.lastIndexOf('.', i - 1), b.lastIndexOf(' ', i - 1)) + 1;
  return b.slice(cut) || b;
}
