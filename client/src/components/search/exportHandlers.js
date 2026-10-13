// The CSV and PDF exports of a result list, moved out of SearchResults.jsx
// (cleaning job H4, 2026-10-13). The bodies are unchanged; the recorded
// outputs are in client/src/test/__snapshots__/renderRecording.test.jsx.snap.
// loadAllRows() returns every row, fetching them from the server when the
// list is held there.
import { normalizeCoptic } from '../../utils/copticUtils';
import { exportRowsToPDF } from '../../utils/exportResults';
import { isRTL } from '../../utils/rtl';
import { markMatchedWords } from '../../utils/highlight';

export const exportSearchCSV = async ({ results, loadAllRows }) => {
  if (!results || results.length === 0) return;
  let allRows;
  try { allRows = await loadAllRows(); } catch { return; }

  // Sort by fused_score descending — the same score the on-screen list and
  // ranking show. Falls back to score / overall_score for legacy formats.
  // Without this explicit sort the CSV could appear unordered if the API
  // serializes results in some other internal order.
  const scoreOf = (r) => r.fused_score ?? r.score ?? r.overall_score ?? 0;
  const sorted = [...allRows].sort((a, b) => scoreOf(b) - scoreOf(a));
  const headers = ['Rank', 'Source Locus', 'Source Text', 'Target Locus', 'Target Text', 'Score', 'Matched Words', 'Channels'];
  const rows = sorted.map((r, idx) => {
    const mw = r.matched_words || [];
    const sourceText = (r.source_text || r.source_snippet || r.source?.text || '').replace(/<[^>]*>/g, '').replace(/"/g, '""');
    const targetText = (r.target_text || r.target_snippet || r.target?.text || '').replace(/<[^>]*>/g, '').replace(/"/g, '""');
    return [
      String(idx + 1),
      r.source_locus || r.source?.ref || '',
      markMatchedWords(sourceText, mw, 'source'),
      r.target_locus || r.target?.ref || '',
      markMatchedWords(targetText, mw, 'target'),
      scoreOf(r).toFixed(3),
      mw.map(w => typeof w === 'object' ? (w.lemma || w.word || '') : w).join('; '),
      (r.channels || []).join('; '),
    ];
  });

  const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n');
  // Prepend UTF-8 BOM so Excel reads non-Latin scripts (Coptic, Greek) as Unicode, not Windows-1252.
  const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `tesserae_results_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
};

export const exportSearchPDF = async ({ results, loadAllRows, sourceTextInfo, targetTextInfo, language }) => {
  if (!results || results.length === 0) return;
  let allRows;
  try { allRows = await loadAllRows(); } catch { return; }
  const headers = ['#', 'Source Locus', 'Source Text', 'Target Locus', 'Target Text', 'Score', 'Matched Words', 'Channels'];
  // Token-based renderer: split source/target text on whitespace, compare each
  // token against the matched-word set. Robust against any script and avoids
  // regex word-boundary issues with non-ASCII alphabets. For Coptic the
  // legacy/primary Unicode-block mismatch is normalised before comparing.
  const escHtml = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const stripPunct = (s) => s.replace(/^[\s.,;:!?'"()—–·‧·-]+/, '')
                            .replace(/[\s.,;:!?'"()—–·‧·-]+$/, '');
  const isCop = language === 'cop';
  const norm = (s) => isCop ? normalizeCoptic(s) : s.toLowerCase();
  const renderHL = (text, mw, side) => {
    if (!text) return '';
    const targets = new Set();
    (mw || []).forEach(w => {
      const word = typeof w === 'object'
        ? (side === 'source' ? w.source_word : w.target_word) || w.word || w.lemma
        : w;
      if (!word) return;
      const s = String(word);
      if (s.includes('~') || s.includes('[')) return; // skip composite labels
      targets.add(norm(stripPunct(s)));
    });
    if (targets.size === 0) return escHtml(text);
    return String(text).split(/(\s+)/).map(part => {
      if (/^\s+$/.test(part) || part === '') return escHtml(part);
      const stripped = stripPunct(part);
      const cmp = norm(stripped);
      let hit = targets.has(cmp);
      if (!hit) {
        // Substring fallback: bound-group token containing a sub-word match.
        for (const t of targets) {
          if (t.length >= 3 && cmp.includes(t)) { hit = true; break; }
        }
      }
      return hit ? `<strong class="hl">${escHtml(part)}</strong>` : escHtml(part);
    }).join('');
  };
  // Sort by fused_score descending so the PDF order matches what's shown
  // on screen (which uses fused_score as the primary score). The API may
  // serialize results in a different internal order; without an explicit
  // sort the PDF could appear out of order.
  const scoreOf = (r) => r.fused_score ?? r.score ?? r.overall_score ?? 0;
  const sorted = [...allRows].sort((a, b) => scoreOf(b) - scoreOf(a));
  const rows = sorted.map((r, idx) => {
    const mw = r.matched_words || [];
    const sourceText = (r.source_text || r.source_snippet || r.source?.text || '').replace(/<[^>]*>/g, '');
    const targetText = (r.target_text || r.target_snippet || r.target?.text || '').replace(/<[^>]*>/g, '');
    return [
      String(idx + 1),
      r.source_locus || r.source?.ref || '',
      renderHL(sourceText, mw, 'source'),
      r.target_locus || r.target?.ref || '',
      renderHL(targetText, mw, 'target'),
      scoreOf(r).toFixed(3),
      mw.map(w => typeof w === 'object' ? (w.lemma || w.word || '') : w).join('; '),
      (r.channels || []).join('; '),
    ];
  });
  const sourceLabel = sourceTextInfo ? `${sourceTextInfo.author || ''} ${sourceTextInfo.title || sourceTextInfo.work || ''}`.trim() : '';
  const targetLabel = targetTextInfo ? `${targetTextInfo.author || ''} ${targetTextInfo.title || targetTextInfo.work || ''}`.trim() : '';
  const subtitle = sourceLabel && targetLabel ? `${sourceLabel} vs ${targetLabel}` : '';
  const rtl = isRTL(language);  // he/fa/ur/ar are right-to-left (Coptic/Greek/Latin/English are LTR)
  // Headers are ['#', 'Source Locus', 'Source Text', 'Target Locus',
  // 'Target Text', 'Score', 'Matched Words', 'Channels']. Widths chosen
  // to minimise row height: each column gets width roughly proportional to
  // its typical content length, so every column wraps to a similar number
  // of lines instead of one column blowing up the row.
  const colWidths = ['3%', '8%', '25%', '8%', '25%', '4%', '17%', '10%'];
  exportRowsToPDF('Tesserae V6 — Search Results', subtitle, headers, rows, {
    htmlCells: true,
    dir: rtl ? 'rtl' : 'ltr',
    lang: language || '',
    colWidths,
  });
};
