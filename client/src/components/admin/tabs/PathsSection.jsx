import React from 'react';
import { Activity } from 'lucide-react';

const th = 'py-2 text-xs font-bold text-gray-500 uppercase tracking-wider';

function Table({ title, head, rows, empty = 'Nothing yet.' }) {
  return (
    <div>
      <h4 className="text-sm font-bold text-gray-900 mb-2">{title}</h4>
      {rows.length === 0 ? (
        <p className="text-sm text-gray-500">{empty}</p>
      ) : (
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-gray-100">
              {head.map((h, i) => (
                <th key={h} className={`${th} ${i > 0 ? 'text-right' : ''}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-gray-50 last:border-0">
                {r.map((c, j) => (
                  <td key={j} className={`py-1.5 text-sm ${j > 0 ? 'text-right font-bold text-gray-900' : 'text-gray-700'}`}>{c}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const PathsSection = ({ paths }) => {
  const days = paths?.days || 30;
  const heading = `Paths through the site (last ${days} days)`;
  return (
    <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm mt-8">
      <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
        <Activity className="w-5 h-5 text-[#b91c1c]" />
        {heading}
      </h3>
      {!paths || paths.available === false ? (
        <p className="text-sm text-gray-600">Page views are not being recorded yet, because the page_views table does not exist.</p>
      ) : (
        <div className="space-y-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              ['Visits', paths.visits],
              ['Page views', paths.page_views],
              ['Median pages per visit', paths.pages_per_visit_median],
              ['One-page visits', paths.one_page_visits],
            ].map(([label, value]) => (
              <div key={label} className="border border-gray-100 rounded-lg p-4">
                <div className="text-2xl font-bold text-[#b91c1c]">{value}</div>
                <div className="text-xs text-gray-500 uppercase tracking-wider">{label}</div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <Table title="Visits by day" head={['Date', 'Visits', 'Page views']}
              rows={(paths.visits_by_day || []).map(d => [d.date, d.visits, d.page_views])} />
            <Table title="Entry pages" head={['Page', 'Visits']}
              rows={(paths.entry_pages || []).map(d => [d.page, d.visits])} />
            <Table title="Top paths (first three pages)" head={['Path', 'Visits']}
              rows={(paths.top_paths || []).map(d => [d.path, d.visits])} />
            <Table title="Pages reached" head={['Page', 'Visits']}
              rows={(paths.pages_reached || []).map(d => [d.page, d.visits])} />
            <Table title="Countries" head={['Country', 'Visits']}
              rows={(paths.countries || []).map(d => [d.country, d.visits])} />
            <Table title="Referrers" head={['Host', 'Visits']}
              rows={(paths.referrer_hosts || []).map(d => [d.host, d.visits])} />
          </div>
        </div>
      )}
    </div>
  );
};

export default PathsSection;
