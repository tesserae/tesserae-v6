import { useState } from 'react';

/**
 * Taking a Theme Search away with you.
 *
 * Theme Search names a work and a line range and shows a machine-written
 * summary, so what a reader could keep was a list of pointers to passages they
 * would then have to go and find one at a time. The export carries the passages
 * themselves, labelled, oldest first.
 *
 * WHY THE PDF IS THE BROWSER'S, NOT THE SERVER'S
 *
 * The obvious build is a server-side PDF. It is the wrong one here. This corpus
 * is seven languages in six scripts, including right-to-left Hebrew, Arabic-
 * script Persian with contextual joining, and Urdu, whose Nastaliq needs a font
 * almost nothing has. Server-side PDF on this box would need pango and a full
 * Noto family installed as root on the production machine, and WeasyPrint is
 * present but cannot load its native libraries.
 *
 * A browser already solves all of it. It has the fonts, it shapes Arabic, it
 * lays out RTL, and its "Save as PDF" produces real selectable text rather than
 * an image. So the PDF route opens a document formatted for print and lets the
 * reader save it. That is not a workaround standing in for the real thing: it
 * is the route that renders Urdu correctly.
 *
 * CSV is the manipulable form, with a BOM so Excel does not turn every Greek
 * and Persian passage into mojibake.
 */
export default function ThemeExport({ query, language, count }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (!query || !count) return null;

  const params = (fmt) =>
    `/api/passages/export?q=${encodeURIComponent(query)}&format=${fmt}&limit=25`
    + (language ? `&languages=${encodeURIComponent(language)}` : '');

  const openPrintable = async () => {
    setBusy(true);
    setError(null);
    // Opened BEFORE the await. A window.open() that happens after an await is
    // no longer inside the click's user gesture, and every popup blocker stops
    // it, so the button would appear to do nothing.
    const win = window.open('', '_blank');
    try {
      const res = await fetch(params('json'));
      const d = await res.json();
      if (d.error) throw new Error(d.error);
      if (!win) {
        setError('Your browser blocked the new window. Allow pop-ups for this '
                 + 'site, or use Download CSV.');
        return;
      }
      win.document.write(printableHtml(d));
      win.document.close();
    } catch (e) {
      if (win) win.close();
      setError(e.message || 'Could not build the document.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        Export
      </span>
      {/* PDF FIRST, because it is what people mean by "download". The printable
          page renders the scripts better -- a browser shapes Arabic and lays
          out right-to-left text more faithfully than any PDF library -- but it
          is not a file you can send to a colleague, which is what NC asked for. */}
      <a
        href={params('pdf')}
        className="text-xs font-semibold text-red-700 border border-red-200 bg-red-50
                   rounded px-3 py-1.5 hover:bg-red-100 hover:border-red-300"
      >
        Download PDF
      </a>
      <button
        onClick={openPrintable}
        disabled={busy}
        className="text-xs font-semibold text-gray-700 border border-gray-300 bg-white
                   rounded px-3 py-1.5 hover:bg-gray-50 disabled:opacity-50"
      >
        {busy ? 'Preparing...' : 'Printable page'}
      </button>
      <a
        href={params('csv')}
        className="text-xs font-semibold text-gray-700 border border-gray-300 bg-white
                   rounded px-3 py-1.5 hover:bg-gray-50"
      >
        Download CSV
      </a>
      <span className="text-xs text-gray-500">
        with the passages themselves, oldest first
      </span>
      {error && <p className="w-full text-xs text-red-700">{error}</p>}
    </div>
  );
}

const RTL = new Set(['Hebrew', 'Persian', 'Urdu', 'Arabic']);

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** A self-contained document, because the new window shares no stylesheet. */
function printableHtml(d) {
  const rows = (d.results || []).map((r) => {
    const rtl = RTL.has(r.language);
    return `
    <article>
      <h2><span class="n">${r.n}</span> ${esc(r.author)}${
        r.work ? `, <em>${esc(r.work)}</em>` : ''}</h2>
      <p class="meta">${[esc(r.locus), esc(r.date), esc(r.era),
                         esc(r.language)].filter(Boolean).join(' &middot; ')}${
      r.strong === 'no' ? ' &middot; <span class="weak">weak match</span>' : ''}</p>
      ${r.gist ? `<p class="gist">${esc(r.gist)}</p>` : ''}
      <blockquote${rtl ? ' dir="rtl" lang="' + esc(r.language) + '"' : ''}>${
        esc(r.text)}</blockquote>
      ${r.themes ? `<p class="themes">${esc(r.themes)}</p>` : ''}
    </article>`;
  }).join('\n');

  const when = new Date().toLocaleDateString(undefined,
    { year: 'numeric', month: 'long', day: 'numeric' });

  return `<!doctype html>
<html><head><meta charset="utf-8">
<title>Tesserae theme search: ${esc(d.query)}</title>
<style>
  /* Serif for the passages, because most of this is verse and it is what a
     reader expects on a page they will print. */
  body { font: 11pt/1.5 Georgia, "Times New Roman", serif; color: #111;
         max-width: 42em; margin: 2em auto; padding: 0 1em; }
  h1 { font-size: 15pt; margin: 0 0 .2em; }
  .query { font-size: 13pt; font-style: italic; margin: 0 0 .3em; }
  .sub { font-size: 9pt; color: #555; margin: 0 0 1.5em;
         border-bottom: 1px solid #ccc; padding-bottom: 1em; }
  article { margin: 0 0 1.6em; break-inside: avoid; page-break-inside: avoid; }
  h2 { font-size: 11.5pt; margin: 0 0 .15em; font-weight: 700; }
  .n { color: #888; font-weight: 400; margin-right: .3em; }
  .meta { font-size: 8.5pt; color: #555; margin: 0 0 .4em; }
  .weak { color: #a33; }
  .gist { font-size: 9.5pt; color: #444; margin: 0 0 .4em; }
  blockquote { margin: 0; padding: .5em .9em; border-left: 3px solid #b91c1c;
               background: #fafafa; white-space: pre-wrap; font-size: 10.5pt; }
  /* RTL passages get their own direction; the surrounding page stays LTR. */
  blockquote[dir="rtl"] { border-left: none; border-right: 3px solid #b91c1c;
                          text-align: right; font-size: 12.5pt; line-height: 1.9; }
  .themes { font-size: 8.5pt; color: #777; margin: .3em 0 0; font-style: italic; }
  footer { margin-top: 2em; border-top: 1px solid #ccc; padding-top: .8em;
           font-size: 8.5pt; color: #666; }
  .hint { background: #fff8e1; border: 1px solid #ffe0a3; padding: .6em .9em;
          font-size: 9pt; margin-bottom: 1.5em; border-radius: 4px; }
  @media print { .hint { display: none; } body { margin: 0; max-width: none; } }
</style></head><body>
<div class="hint">Use your browser's Print command and choose
  <strong>Save as PDF</strong>. This note will not be printed.</div>
<h1>Tesserae Theme Search</h1>
<p class="query">&ldquo;${esc(d.query)}&rdquo;</p>
<p class="sub">${d.count} passage${d.count === 1 ? '' : 's'}, oldest first${
  d.confidence?.level ? ` &middot; confidence: ${esc(d.confidence.level)}` : ''
} &middot; retrieved ${esc(when)}${
  d.missing_text ? ` &middot; ${d.missing_text} passage(s) had no source text` : ''}</p>
${rows}
<footer>
  Tesserae V6, tesserae.caset.buffalo.edu. Passages are matched by content
  rather than wording, so results in different languages need share no words
  with the query. Summaries in italic are machine-written and are not part of
  the source text.
</footer>
</body></html>`;
}
