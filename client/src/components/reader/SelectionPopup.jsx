/**
 * What to do with the passage you just selected.
 *
 * Selecting lines in the Reader used to change the side panel and nothing else,
 * so the connection between the act of selecting and the searches available was
 * invisible. This is the popup from the design: it appears at the selection,
 * leads with the search that suits the size of what was chosen, and offers the
 * rest.
 *
 * WHY SIZE DECIDES THE DEFAULT
 *
 * One line is a line: the useful question is which other lines in the corpus
 * share its wording, which is a lexical search. A block of lines is a passage:
 * the useful question is which other passages are about the same thing, which is
 * content. Guessing right most of the time is worth more than making the reader
 * choose every time, and the alternatives are one click away when the guess is
 * wrong.
 */

const CONTENT_FROM = 3;   // lines. Below this, a selection reads as a line, not a passage.

export default function SelectionPopup({ selection, work, language, onClose, onTab }) {
  if (!selection) return null;

  const n = selection.lineCount || 1;
  const refStart = selection.refStart;
  const refEnd = selection.refEnd || refStart;
  const passage = n >= CONTENT_FROM;

  const lineSearchUrl = () => {
    const p = new URLSearchParams({ work: String(work || '').replace(/\.tess$/, ''),
                                    language: language || 'la', ref: refStart || '' });
    return `/line-search?${p.toString()}`;
  };
  const stringSearchUrl = () => {
    const p = new URLSearchParams({ language: language || 'la', ref: refStart || '' });
    return `/string-search?${p.toString()}`;
  };

  // The default first, then the others, in one list so nothing is hidden behind
  // a menu. Four options is short enough to read.
  const actions = [
    {
      key: 'similar',
      label: passage ? 'Find similar passages' : 'Find passages like this',
      hint: 'matched by content, across every language',
      primary: passage,
      onClick: () => onTab?.('similar'),
    },
    {
      key: 'verbal',
      label: 'Find shared wording',
      hint: 'other lines using the same words',
      primary: !passage,
      href: lineSearchUrl(),
    },
    {
      key: 'exact',
      label: 'Search this as an exact phrase',
      hint: 'the words as written',
      href: stringSearchUrl(),
    },
    {
      key: 'translation',
      label: 'Show the translation',
      hint: 'where an aligned English text exists',
      onClick: () => onTab?.('translation'),
    },
  ];
  actions.sort((a, b) => (b.primary ? 1 : 0) - (a.primary ? 1 : 0));

  return (
    <div className="absolute z-30 mt-1 w-72 rounded-lg border border-gray-300 bg-white shadow-xl"
         role="dialog"
         aria-label="What to do with the selected passage">
      <div className="flex items-baseline justify-between px-3 py-2 border-b border-gray-200">
        <span className="text-xs text-gray-600">
          {n} line{n === 1 ? '' : 's'} selected
          <span className="text-gray-400"> · {refStart}{refEnd !== refStart ? `–${refEnd}` : ''}</span>
        </span>
        <button onClick={onClose}
                className="text-gray-400 hover:text-gray-700 text-lg leading-none px-1"
                aria-label="Close">×</button>
      </div>

      <ul className="py-1">
        {actions.map((a) => {
          const cls = `w-full text-left px-3 py-2 hover:bg-red-50 ${
            a.primary ? 'text-red-800 font-medium' : 'text-gray-700'}`;
          const body = (
            <>
              <span className="block text-sm">{a.label}</span>
              <span className="block text-[11px] text-gray-500">{a.hint}</span>
            </>
          );
          return (
            <li key={a.key}>
              {a.href
                ? <a href={a.href} className={`block ${cls}`}>{body}</a>
                : <button onClick={() => { a.onClick?.(); onClose?.(); }} className={cls}>{body}</button>}
            </li>
          );
        })}
      </ul>

      <p className="px-3 pb-2 text-[11px] text-gray-500 leading-snug">
        {passage
          ? 'A passage this size is best matched by content.'
          : 'A single line is best matched by its wording.'}
      </p>
    </div>
  );
}
