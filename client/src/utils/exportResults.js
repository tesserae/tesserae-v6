// Shared export helpers for search results.
//
// CSV path is the existing Blob-download pattern. PDF path opens a
// print-friendly window populated with the same data and triggers the
// browser's print dialog so the user picks "Save as PDF". This avoids
// font-embedding problems for Coptic, Greek, Arabic, Hebrew, etc. — the
// browser renders with its native fonts, exactly as the on-screen view.

export function exportRowsToCSV(headers, rows, filename) {
  const escape = (cell) => {
    const s = cell == null ? '' : String(cell);
    return `"${s.replace(/"/g, '""')}"`;
  };
  const csv = [
    headers.map(escape).join(','),
    ...rows.map(r => r.map(escape).join(',')),
  ].join('\n');
  const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Open a new window with results formatted for printing, then trigger
// the browser's print dialog. Users save as PDF from there.
//
// title: page heading
// subtitle: optional one-line context (e.g. "Vergil, Aeneid 1 vs Lucan, BC 1")
// headers: array of column names
// rows: array of arrays; each cell can be a string or HTML-safe pre-rendered
//       string (we will not double-escape). If you pass HTML, set
//       options.htmlCells = true.
// options.dir: 'ltr' (default) or 'rtl' — for Arabic/Hebrew/Persian/Urdu
// options.lang: ISO code for the lang attribute (helps font fallback)
// options.htmlCells: if true, cells are inserted as innerHTML (use for pre-highlighted strings)
// options.orientation: 'landscape' (default) or 'portrait'
// options.colWidths: optional array of CSS widths, one per header column, e.g.
//                    ['4%','10%','30%','10%','30%','5%','6%','5%']. With
//                    table-layout: fixed (default), unset widths split evenly;
//                    pass this when some columns hold long text and others
//                    hold short metadata.
export function exportRowsToPDF(title, subtitle, headers, rows, options = {}) {
  const { dir = 'ltr', lang = '', htmlCells = false, orientation = 'landscape', colWidths = null } = options;

  const win = window.open('', '_blank', 'width=900,height=700');
  if (!win) {
    alert('Pop-up blocked. Allow pop-ups for this site to export PDF.');
    return;
  }

  const escape = (s) => {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  };

  const renderCell = (c) => htmlCells ? (c == null ? '' : String(c)) : escape(c);

  const colGroup = (colWidths && colWidths.length === headers.length)
    ? `<colgroup>${colWidths.map(w => `<col style="width:${escape(w)}">`).join('')}</colgroup>`
    : '';
  const headRow = `<tr>${headers.map(h => `<th>${escape(h)}</th>`).join('')}</tr>`;
  const bodyRows = rows.map(r =>
    `<tr>${r.map(c => `<td>${renderCell(c)}</td>`).join('')}</tr>`
  ).join('');

  const langAttr = lang ? ` lang="${escape(lang)}"` : '';
  const dateStr = new Date().toLocaleString();

  const html = `<!doctype html>
<html${langAttr} dir="${dir}">
<head>
<meta charset="utf-8">
<title>${escape(title)}</title>
<style>
  @page { size: letter ${orientation}; margin: 0.5in; }
  /* Force browsers to honour our highlight background colour when printing.
     Without this, Chrome/Safari strip background-color from printed/PDF output
     unless the user manually ticks "Background graphics". */
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body {
    font-family: 'Crimson Pro', 'Noto Sans', 'Antinoou', 'Noto Sans Coptic', 'Noto Naskh Arabic', 'Noto Sans Hebrew', serif;
    color: #111; margin: 0; padding: 0;
  }
  h1 { font-size: 14pt; margin: 0 0 3pt 0; }
  .subtitle { color: #555; font-size: 10pt; margin-bottom: 3pt; }
  .meta { color: #888; font-size: 9pt; margin-bottom: 10pt; }
  table { border-collapse: collapse; width: 100%; font-size: 9pt; table-layout: fixed; }
  th, td {
    border: 1px solid #bbb; padding: 3pt 5pt; vertical-align: top;
    text-align: ${dir === 'rtl' ? 'right' : 'left'};
    word-break: break-word; overflow-wrap: anywhere;
  }
  th { background: #f3f3f3; font-weight: 600; }
  tr { page-break-inside: avoid; }
  /* Highlighted matched words: yellow background + bold + underline so they
     remain visible even if a printer strips background colours. */
  td .hl, td b.hl, td strong.hl, td b, td strong {
    background: #ffe066;
    font-weight: 700;
    text-decoration: underline;
    padding: 0 1pt;
  }
  .controls { padding: 8pt; background: #fffbe6; border-bottom: 1px solid #e6d990; font-size: 11pt; }
  .controls button { font-size: 11pt; padding: 4pt 12pt; margin-right: 6pt; }
  @media print { .controls { display: none; } }
</style>
</head>
<body>
<div class="controls">
  <button onclick="window.print()">Print / Save as PDF</button>
  <button onclick="window.close()">Close</button>
  <span style="color:#666; font-size:10pt;">In the print dialog, choose "Save as PDF" as the destination.</span>
</div>
<h1>${escape(title)}</h1>
${subtitle ? `<div class="subtitle">${escape(subtitle)}</div>` : ''}
<div class="meta">Exported ${escape(dateStr)} · ${rows.length} ${rows.length === 1 ? 'result' : 'results'}</div>
<table>
  ${colGroup}
  <thead>${headRow}</thead>
  <tbody>${bodyRows}</tbody>
</table>
<script>
  // Auto-open the print dialog after the document fully renders.
  window.addEventListener('load', function () { setTimeout(function() { window.print(); }, 250); });
</script>
</body>
</html>`;

  win.document.open();
  win.document.write(html);
  win.document.close();
}
