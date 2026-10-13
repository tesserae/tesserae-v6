// The bars of the "In this comparison" chart: where along the source (or the
// target) the parallels fall. Moved out of SearchResults.jsx (cleaning job
// H4, 2026-10-13), body unchanged. Returns null when there is nothing to draw.
export const buildDistributionData = ({ results, distributionChartView, serverMode, resultSet }) => {
  if (!results || results.length === 0) return null;
  const isSourceView = distributionChartView === 'source';
  const color = isSourceView ? 'rgba(185, 28, 28, 0.7)' : 'rgba(217, 119, 6, 0.7)';
  const border = isSourceView ? 'rgb(185, 28, 28)' : 'rgb(217, 119, 6)';
  if (serverMode) {
    // Computed by the server over every row (backend/result_pages.distribution).
    const d = resultSet.aggregates?.distribution?.[distributionChartView];
    if (!d) return null;
    return {
      _mode: d.mode, _band: d.band, labels: d.labels,
      datasets: [{ label: 'Parallels', data: d.counts, backgroundColor: color, borderColor: border, borderWidth: 1 }]
    };
  }
  // A locus like "1.469" -> book 1, line 469; a flat "469" -> line only.
  const parseLoc = (locus) => {
    const nums = (String(locus).match(/\d+/g) || []).map(Number);
    return { book: nums.length >= 2 ? nums[0] : null, line: nums.length ? nums[nums.length - 1] : null };
  };
  const pts = results.map(r => parseLoc(isSourceView
    ? (r.source_locus || r.source?.ref || '')
    : (r.target_locus || r.target?.ref || '')));
  const books = new Set(pts.map(p => p.book).filter(b => b != null));

  // Single book (e.g. Aeneid 1 vs Lucan 1): a by-book chart is one useless
  // column, so show WHERE ALONG THE BOOK the parallels fall — bin by line.
  if (books.size <= 1) {
    const lines = pts.map(p => p.line).filter(n => n != null);
    if (lines.length === 0) return null;
    const maxLine = Math.max(...lines);
    const band = [10, 25, 50, 100, 200, 500, 1000].find(b => Math.ceil(maxLine / b) <= 18) || 1000;
    const nBands = Math.max(1, Math.ceil(maxLine / band));
    const counts = new Array(nBands).fill(0);
    pts.forEach(p => { if (p.line != null) counts[Math.min(nBands - 1, Math.floor((p.line - 1) / band))]++; });
    return {
      _mode: 'line', _band: band,
      labels: counts.map((_, i) => `${i * band + 1}–${(i + 1) * band}`),
      datasets: [{ label: 'Parallels', data: counts, backgroundColor: color, borderColor: border, borderWidth: 1 }]
    };
  }

  // Multiple books: keep the by-book view.
  const bookData = {};
  pts.forEach(p => { const k = `Book ${p.book}`; (bookData[k] = bookData[k] || { count: 0 }).count++; });
  const sorted = Object.keys(bookData).sort((a, b) =>
    (parseInt(a.replace(/\D/g, '')) || 0) - (parseInt(b.replace(/\D/g, '')) || 0));
  return {
    _mode: 'book',
    labels: sorted,
    datasets: [{ label: 'Parallels', data: sorted.map(k => bookData[k].count), backgroundColor: color, borderColor: border, borderWidth: 1 }]
  };
};
