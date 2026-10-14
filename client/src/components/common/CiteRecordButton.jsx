import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  toRIS, toBibTeX, toText, withEdition, withEditionSync, copyText, download, safeName, bibKey, RIS_MIME, BIB_MIME,
} from '../../utils/citations';

/**
 * "Cite" for one piece of scholarship (an article, chapter, book, thesis or
 * commentary note): a small link that opens a box under itself holding one
 * plain reference, with four actions: copy the line, copy the RIS for
 * Zotero's clipboard import, save a .ris file, save a .bib file.
 *
 * Not the same control as CiteButton, which cites a search finding.
 * The box is fixed to the button's rectangle (as the navigation's More menu
 * is), closes on scroll, resize, Escape or a click elsewhere, and only one is
 * open at a time.
 */
const OPEN_EVENT = 'tesserae:cite-record-open';
let nextId = 1;

export default function CiteRecordButton({ record, label = 'Cite', className = '' }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const [rec, setRec] = useState(() => withEditionSync(record));
  const [copied, setCopied] = useState('');
  const btnRef = useRef(null);
  const boxRef = useRef(null);
  const firstRef = useRef(null);
  const idRef = useRef(nextId++);

  // The record may change under the button (a list re-sorts); the edition,
  // for a commentary note, is looked up when the box opens.
  useEffect(() => { setRec(withEditionSync(record)); }, [record]);
  useEffect(() => {
    if (!open) return undefined;
    let dead = false;
    withEdition(record).then((r) => { if (!dead) setRec(r); });
    return () => { dead = true; };
  }, [open, record]);

  useEffect(() => {
    if (!open) return undefined;
    const close = () => setOpen(false);
    const onDown = (e) => {
      if (boxRef.current && boxRef.current.contains(e.target)) return;
      if (btnRef.current && btnRef.current.contains(e.target)) return;
      setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { setOpen(false); btnRef.current?.focus(); }
    };
    const onOther = (e) => { if (e.detail !== idRef.current) setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    window.addEventListener(OPEN_EVENT, onOther);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', close, true);
      window.removeEventListener('resize', close);
      window.removeEventListener(OPEN_EVENT, onOther);
    };
  }, [open]);

  useEffect(() => { if (open) firstRef.current?.focus(); }, [open]);

  const toggle = () => {
    if (open) { setOpen(false); return; }
    const b = btnRef.current?.getBoundingClientRect();
    const width = 320;
    const left = b ? Math.max(8, Math.min(b.left, window.innerWidth - width - 8)) : 8;
    setPos({ top: b ? b.bottom + 4 : 0, left });
    window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: idRef.current }));
    setOpen(true);
  };

  const flash = (what) => { setCopied(what); setTimeout(() => setCopied(''), 2000); };
  const line = toText(rec);
  const stem = safeName(bibKey(rec), 'citation');
  const act = 'text-red-700 hover:underline';

  return (
    <>
      <button type="button" ref={btnRef} onClick={toggle} aria-haspopup="dialog" aria-expanded={open}
              className={`text-red-700 hover:underline ${className}`}>
        {label}
      </button>
      {open && createPortal(
        <div ref={boxRef} role="dialog" aria-label="Cite this item"
             style={{ position: 'fixed', top: pos.top, left: pos.left, width: 320, zIndex: 60 }}
             className="rounded border border-gray-300 bg-white p-2 shadow-lg text-xs text-gray-800">
          <textarea readOnly value={line} rows={4} aria-label="Reference"
                    className="w-full rounded border border-gray-200 bg-gray-50 p-1 text-xs"
                    onFocus={(e) => e.target.select()} />
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
            <button type="button" ref={firstRef} className={act}
                    onClick={async () => { if (await copyText(line)) flash('line'); }}>
              {copied === 'line' ? 'copied' : 'Copy'}
            </button>
            <button type="button" className={act}
                    title="Copies the reference as RIS; in Zotero choose File, Import from Clipboard."
                    onClick={async () => { if (await copyText(toRIS(rec))) flash('ris'); }}>
              {copied === 'ris' ? 'copied' : 'Copy RIS'}
            </button>
            <button type="button" className={act} onClick={() => download(`${stem}.ris`, toRIS(rec), RIS_MIME)}>
              RIS file
            </button>
            <button type="button" className={act} onClick={() => download(`${stem}.bib`, toBibTeX(rec), BIB_MIME)}>
              BibTeX
            </button>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
