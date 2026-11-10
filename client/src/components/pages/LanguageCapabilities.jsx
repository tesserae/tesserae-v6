import { useEffect, useState } from 'react';

// "What each language has" (2026-11-10): one row per language, one column per
// capability, a dot per cell. The server reads the installed stores
// (/api/scope/capabilities); this component only draws the answer. The site
// uses no blue: filled dot = red, half = red ring, none = gray ring.
const DOT = {
  full: 'bg-red-600 border-2 border-red-600',
  partial: 'bg-white border-2 border-red-600',
  none: 'bg-white border-2 border-gray-300'
};
const STATE_WORD = { full: 'In place', partial: 'Partly in place', none: 'Not yet' };

function cellTitle(name, cell) {
  const parts = [`${name}: ${STATE_WORD[cell.state] || cell.state}`];
  if (cell.count !== null && cell.count !== undefined) parts.push(cell.count.toLocaleString('en-US'));
  if (cell.note) parts.push(cell.note);
  return parts.join(', ');
}

export default function LanguageCapabilities() {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let dead = false;
    fetch('/api/scope/capabilities')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('bad status'))))
      .then((d) => { if (!dead) setData(d); })
      .catch(() => { if (!dead) setFailed(true); });
    return () => { dead = true; };
  }, []);

  if (failed) return null;
  if (!data) return <p className="text-sm text-gray-500">Loading the table of what each language has.</p>;

  return (
    <div data-testid="language-capabilities">
      <div className="overflow-x-auto border border-gray-200 rounded-lg">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th scope="col" className="text-left font-semibold text-gray-700 px-3 py-2 sticky left-0 bg-gray-50">Language</th>
              {data.capabilities.map((c) => (
                <th key={c.key} scope="col" title={c.name} className="font-semibold text-gray-700 px-2 py-2 text-xs align-bottom">{c.heading}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.languages.map((row) => (
              <tr key={row.code} className="border-t border-gray-100">
                <th scope="row" className="text-left font-medium text-gray-900 px-3 py-2 sticky left-0 bg-white">{row.label}</th>
                {data.capabilities.map((c) => {
                  const cell = row.capabilities[c.key] || { state: 'none', count: null, note: 'not read' };
                  return (
                    <td key={c.key} className="px-2 py-2 text-center">
                      <span
                        role="img"
                        aria-label={cellTitle(c.name, cell)}
                        title={cellTitle(c.name, cell)}
                        data-state={cell.state}
                        className={`inline-block w-4 h-4 rounded-full ${DOT[cell.state] || DOT.none}`}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.computed_at && (
        <p className="text-xs text-gray-500 mt-2">Read from the installed data on {data.computed_at}.</p>
      )}
    </div>
  );
}
