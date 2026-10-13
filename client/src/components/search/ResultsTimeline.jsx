import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

// The authors in whose works a parallel's shared words recur, placed by date
// and drawn as horizontal bars (cleaning job H4, 2026-10-13; it was a
// hand-drawn D3 timeline of dots, and the public pages now use one chart
// library). The earliest author is at the bottom and the latest at the top,
// as the dot timeline ran. A bar is as long as the number of occurrences.
// The two works under comparison are drawn in red among the blue rest, the
// selected author in full color. Click an author to list its instances.
//
// rows: [{ author, year, n }], one per work or author, as the panel counts them.

const datedYear = (l) => (l.year != null && l.year < 9999 ? l.year : null);
const fmtYear = (y) => (y < 0 ? `${-y} BCE` : `${y} CE`);
const trunc = (s) => (s.length > 15 ? s.slice(0, 14) + '…' : s);
const MAX_AUTHORS = 40;
const ROW_HEIGHT = 16;

// The data behind the chart: one entry per dated author, the forty with the
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
  if (!rows || !rows.length) return <div className="w-full" />;
  const data = timelineEntries(rows);
  if (!data.length) {
    return (
      <div className="w-full">
        <div className="text-xs text-gray-500 p-2">No dated authors to place on a timeline.</div>
      </div>
    );
  }
  const compared = new Set(comparedAuthors.filter(Boolean));
  const color = (d) => {
    const base = compared.has(d.author) ? '185,28,28' : '37,99,235';
    return d.author === selectedAuthor ? `rgba(${base},1)` : `rgba(${base},0.75)`;
  };
  const chartData = {
    labels: data.map((d) => `${trunc(d.author.replace(/_/g, ' '))}, ${fmtYear(d.year)} (${d.count})`),
    datasets: [{
      label: 'Occurrences',
      data: data.map((d) => d.count),
      backgroundColor: data.map(color),
      borderWidth: 0,
    }],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: () => '',
          label: (c) => {
            const d = data[c.dataIndex];
            return `${d.author.replace(/_/g, ' ')} — ${fmtYear(d.year)} — ${d.count} occurrence${d.count !== 1 ? 's' : ''}`;
          },
        },
      },
    },
    onClick: (evt, elements) => {
      if (elements && elements.length) onSelectAuthor(data[elements[0].index].author);
    },
    onHover: (evt, elements) => {
      const el = evt?.native?.target;
      if (el && el.style) el.style.cursor = elements && elements.length ? 'pointer' : 'default';
    },
    scales: {
      x: { beginAtZero: true, ticks: { precision: 0 } },
      y: { ticks: { autoSkip: false, font: { size: 9 } } },
    },
  };
  return (
    <div className="w-full" style={{ height: data.length * ROW_HEIGHT + 30 }}>
      <Bar data={chartData} options={options} />
    </div>
  );
};

export default ResultsTimeline;
