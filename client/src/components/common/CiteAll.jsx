import { bibList, risList, withEditions, download, safeName, RIS_MIME, BIB_MIME } from '../../utils/citations';

/**
 * "Export citations" over a whole list: one RIS file or one BibTeX file
 * holding every record. Shown only when the list has two or more records.
 * `name` becomes the file name (ASCII, under 60 characters).
 */
export default function CiteAll({ records, name, label = 'Export citations' }) {
  const list = (records || []).filter(Boolean);
  if (list.length < 2) return null;
  const stem = safeName(name, 'citations');
  const go = async (kind) => {
    const full = await withEditions(list);
    if (kind === 'ris') download(`${stem}.ris`, risList(full), RIS_MIME);
    else download(`${stem}.bib`, bibList(full), BIB_MIME);
  };
  return (
    <span className="text-[11px] text-gray-600 whitespace-nowrap" data-testid="cite-all">
      {label}:{' '}
      <button type="button" onClick={() => go('ris')} className="text-red-700 hover:underline"
              title="One .ris file for Zotero and EndNote">RIS</button>
      {' '}
      <button type="button" onClick={() => go('bib')} className="text-red-700 hover:underline"
              title="One .bib file for LaTeX">BibTeX</button>
    </span>
  );
}
