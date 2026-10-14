import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

// The authors in whose works a parallel's shared words recur, placed on a
// vertical date axis: the axis runs top (latest) to bottom (earliest); each
// author sits at its actual year, so time clusters and gaps are visible, with
// one dot per occurrence of the shared words in that author. Click an author
// to list its actual instances below the chart.
//
// This is the hand-drawn D3 timeline that SearchResults.jsx carried until the
// split of 2026-10-13 (#899), moved here as it was. #899 had redrawn it as a
// Chart.js bar chart, which lost the date axis and the dots; the owner's rule
// for the cleaning is that nothing a visitor sees goes backwards, so the
// original drawing is restored (2026-10-13 evening).
//
// rows: [{ author, year, n }], one per work or author, as the panel counts them.

const datedYear = (l) => (l.year != null && l.year < 9999 ? l.year : null);
const fmtYear = (y) => (y < 0 ? `${-y} BCE` : `${y} CE`);
const trunc = (s) => (s.length > 15 ? s.slice(0, 14) + '…' : s);
const MAX_AUTHORS = 40;

// The data behind the drawing: one entry per dated author, the forty with the
// most occurrences, latest first.
export const timelineEntries = (rows) => {
  const agg = {};
  rows.forEach((l) => {
    const a = l.author || 'Unknown';
    (agg[a] = agg[a] || { count: 0, year: datedYear(l) }).count += l.n;
    if (agg[a].year == null) { const y = datedYear(l); if (y != null) agg[a].year = y; }
  });
  return Object.entries(agg)
    .map(([author, v]) => ({ author, count: v.count, year: v.year }))
    .filter((d) => d.year != null)
    .sort((a, b) => b.count - a.count)
    .slice(0, MAX_AUTHORS)
    .sort((a, b) => b.year - a.year);
};

const ResultsTimeline = ({ rows, selectedAuthor, onSelectAuthor, comparedAuthors = [] }) => {
  const host = useRef(null);
  const comparedKey = comparedAuthors.filter(Boolean).join('\u0001');

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    el.innerHTML = '';
    if (!rows || !rows.length) return;
    const data = timelineEntries(rows);
    if (!data.length) {
      d3.select(el).append('div').attr('class', 'text-xs text-gray-500 p-2')
        .text('No dated authors to place on a timeline.');
      return;
    }

    const rowH = 16, marginTop = 16, marginBottom = 8, axisW = 50, labelW = 175;
    const width = el.clientWidth || 340;
    const baseHeight = marginTop + marginBottom + data.length * rowH;

    const years = data.map((d) => d.year);
    const yScale = d3.scaleLinear().domain([d3.min(years), d3.max(years)])
      .range([baseHeight - marginBottom, marginTop]).nice();
    let lastY = -Infinity;
    data.forEach((d) => { d.trueY = yScale(d.year); d.y = Math.max(d.trueY, lastY + rowH); lastY = d.y; });
    // Greedy de-overlap can push the earliest author below baseHeight when dates
    // cluster or an outlier stretches the scale; grow the canvas so nothing clips.
    const height = Math.max(baseHeight, lastY + marginBottom + 6);
    const svg = d3.select(el).append('svg').attr('width', width).attr('height', height)
      .attr('font-family', 'inherit');
    const dotR = 3, dotGap = 8;
    const dotCap = Math.max(1, Math.floor((width - axisW - labelW) / dotGap));

    svg.append('line').attr('x1', axisW - 6).attr('x2', axisW - 6)
      .attr('y1', marginTop - 6).attr('y2', baseHeight - marginBottom).attr('stroke', '#e5e7eb');
    // As many year labels as the axis has room for at 9px, and never more
    // than six. A fixed six put "1840 CE" through "1660 CE" on top of one
    // another when the timeline held two authors and was 40px tall
    // (2026-09-10).
    const tickCount = Math.max(2, Math.min(6, Math.floor((baseHeight - marginTop - marginBottom) / 14)));
    svg.append('g').selectAll('text.tick').data(yScale.ticks(tickCount)).join('text')
      .attr('x', 2).attr('y', (d) => yScale(d)).attr('dy', '0.32em')
      .attr('font-size', 9).attr('fill', '#9ca3af').text((d) => fmtYear(d));

    const groups = svg.append('g').selectAll('g.row').data(data).join('g')
      .style('cursor', 'pointer')
      .on('click', (event, d) => onSelectAuthor(d.author))
      .on('mouseover', function () { d3.select(this).select('text.author-label').style('text-decoration', 'underline'); })
      .on('mouseout', function () { d3.select(this).select('text.author-label').style('text-decoration', null); });
    groups.append('line').attr('x1', axisW - 6).attr('x2', axisW)
      .attr('y1', (d) => d.trueY).attr('y2', (d) => d.y).attr('stroke', '#e5e7eb');
    // One dot per occurrence, so a single instance is a single dot rather than a
    // long bar. Beyond dotCap dots a "+" marks the overflow; the exact total is in
    // the label. dotCap is width-driven, so longer names simply leave room for fewer.
    const compared = new Set(comparedKey ? comparedKey.split('\u0001') : []);
    groups.each(function (d) {
      const g = d3.select(this);
      const n = Math.min(d.count, dotCap);
      // The two texts under comparison are drawn in red so the reader can see
      // them among the rest of the corpus (they used to be left out).
      const base = compared.has(d.author) ? '185,28,28' : '37,99,235';
      const fill = d.author === selectedAuthor ? `rgba(${base},1)` : `rgba(${base},0.75)`;
      for (let i = 0; i < n; i++) {
        g.append('circle').attr('cx', axisW + dotR + i * dotGap).attr('cy', d.y)
          .attr('r', dotR).attr('fill', fill);
      }
      if (d.count > dotCap) {
        g.append('text').attr('x', axisW + n * dotGap + 1).attr('y', d.y).attr('dy', '0.32em')
          .attr('font-size', 10).attr('font-weight', 700).attr('fill', fill).text('+');
      }
    });
    groups.append('text').attr('class', 'author-label')
      .attr('x', (d) => axisW + Math.min(d.count, dotCap) * dotGap + (d.count > dotCap ? 9 : 0) + 6)
      .attr('y', (d) => d.y).attr('dy', '0.32em')
      .attr('font-size', 9)
      .attr('font-weight', (d) => (d.author === selectedAuthor ? 700 : 400))
      .attr('fill', '#2563eb')
      .text((d) => `${trunc(d.author.replace(/_/g, ' '))}, ${fmtYear(d.year)} (${d.count})`);
    groups.append('title').text((d) => `${d.author.replace(/_/g, ' ')} — ${fmtYear(d.year)} — ${d.count} occurrence${d.count !== 1 ? 's' : ''}`);
  }, [rows, selectedAuthor, comparedKey, onSelectAuthor]);

  return <div ref={host} className="w-full" />;
};

export default ResultsTimeline;
