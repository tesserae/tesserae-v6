import { useState, useMemo } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import Pagination from '../common/Pagination';
import { dirFor } from '../../utils/rtl';
import { renderDocumentText, documentDateLabel } from './documentDisplay';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

// A compact distribution chart for the documents collection, by century and
// by region, over EVERY match (docDistribution, computed server-side), not
// just the current page. Same Bar component/visual style as the literary
// timeline in LineSearch.jsx, in the site's amber/red palette rather than
// the era colors (this is a different kind of chart: date ranges from
// metadata.db, not the literary era classification). Extracted from
// LineSearch.jsx verbatim.
function useDocDistributionCharts(docDistribution) {
  const docCenturyChartData = useMemo(() => {
    const items = docDistribution.by_century || [];
    return {
      labels: items.map(i => i.century),
      datasets: [{
        label: 'Documents',
        data: items.map(i => i.count),
        backgroundColor: 'rgba(180, 83, 9, 0.7)',
        borderColor: 'rgba(180, 83, 9, 1)',
        borderWidth: 1,
      }],
    };
  }, [docDistribution]);

  // documents_by_source_region is {source, region, count} (the credit
  // archive and the Roman province/region together); the chart wants
  // region alone, so sources sharing one region are summed here. Capped
  // to the 10 largest regions so a query spanning the whole empire still
  // renders a compact chart rather than a hundred thin bars.
  const docRegionChartData = useMemo(() => {
    const bySourceRegion = docDistribution.by_source_region || [];
    const byRegion = {};
    bySourceRegion.forEach(({ region, count }) => {
      const key = region || 'unknown';
      byRegion[key] = (byRegion[key] || 0) + count;
    });
    const sorted = Object.entries(byRegion).sort((a, b) => b[1] - a[1]).slice(0, 10);
    return {
      labels: sorted.map(([r]) => r),
      datasets: [{
        label: 'Documents',
        data: sorted.map(([, c]) => c),
        backgroundColor: 'rgba(185, 28, 28, 0.7)',
        borderColor: 'rgba(185, 28, 28, 1)',
        borderWidth: 1,
      }],
    };
  }, [docDistribution]);

  return { docCenturyChartData, docRegionChartData };
}

const docDistributionChartOptions = (title) => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    title: { display: true, text: title },
    tooltip: {
      callbacks: {
        label: (context) => `${context.parsed.y} match${context.parsed.y !== 1 ? 'es' : ''}`,
      },
    },
  },
  scales: {
    y: { beginAtZero: true, ticks: { precision: 0 } },
    x: { ticks: { maxRotation: 45, minRotation: 45 } },
  },
});

/**
 * The documents-collection results section: count + sort + distribution
 * toggle, the century/region charts, the result cards, and server-side
 * pagination. Extracted from LineSearch.jsx (stage 4) so the Inscriptions
 * & Papyri page renders a documents result set identically.
 *
 * @param {Function} documentViewUrl  (docId) => url for a hit's citation
 *   link, built by the caller (it depends on the caller's own query/type/
 *   trial state and which page's "back" link it should carry).
 * @param {string} language  Used only for `dir` on the hit text.
 */
export default function DocumentsResultsPanel({
  documentResults, docTotal, docSort, onSortChange, docDistribution,
  docPagination, docPageLoading, documentViewUrl, language,
}) {
  const [showDocDistribution, setShowDocDistribution] = useState(true);
  const { docCenturyChartData, docRegionChartData } = useDocDistributionCharts(docDistribution);

  if (!documentResults || documentResults.length === 0) return null;

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-gray-600">
          Found {docTotal.toLocaleString()} documents
        </span>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1 text-sm text-gray-600">
            Sort
            <select
              value={docSort}
              onChange={e => onSortChange(e.target.value)}
              disabled={docPageLoading}
              className="text-sm border rounded px-2 py-1 disabled:opacity-50"
            >
              <option value="relevance">Relevance</option>
              <option value="oldest">Oldest first</option>
              <option value="newest">Newest first</option>
              <option value="region">Region</option>
            </select>
          </label>
          {(docDistribution.by_century?.length > 0 || docDistribution.by_source_region?.length > 0) && (
            <button
              onClick={() => setShowDocDistribution(!showDocDistribution)}
              className={`text-sm px-3 py-1 rounded ${showDocDistribution ? 'bg-amber-700 text-white' : 'bg-amber-100 text-amber-700 hover:bg-amber-200'}`}
            >
              {showDocDistribution ? 'Hide Distribution' : 'Show Distribution'}
            </button>
          )}
        </div>
      </div>

      {showDocDistribution && (docCenturyChartData.labels.length > 0 || docRegionChartData.labels.length > 0) && (
        <div className="p-4 border-b bg-gray-50 grid grid-cols-1 sm:grid-cols-2 gap-6">
          {docCenturyChartData.labels.length > 0 && (
            <div>
              <div style={{ height: '160px' }}>
                <Bar data={docCenturyChartData} options={docDistributionChartOptions('By Century')} />
              </div>
            </div>
          )}
          {docRegionChartData.labels.length > 0 && (
            <div>
              <div style={{ height: '160px' }}>
                <Bar data={docRegionChartData} options={docDistributionChartOptions('By Region')} />
              </div>
            </div>
          )}
        </div>
      )}

      <div className="divide-y divide-gray-200">
        {docPageLoading && (
          <div className="p-4 text-sm text-gray-500 text-center">Loading…</div>
        )}
        {documentResults.map((result, i) => {
          const credit = result.credit || {};
          const labels = [result.text_type_label, result.object_type_label, result.material_label]
            .filter(Boolean);
          const place = result.ancient_place || result.modern_place;
          const dateLabel = documentDateLabel(result);
          return (
            <div key={i} className="p-4 hover:bg-gray-50">
              <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                <span className="text-xs text-gray-500 min-w-[2.5rem] text-right shrink-0 leading-none" style={{ paddingTop: '1px' }}>
                  {docPagination.startIndex + i + 1}.
                </span>
                <div className="sm:w-48 flex-shrink-0 min-w-0 break-words">
                  <div className="text-sm font-medium text-gray-900">
                    <a href={documentViewUrl(result.doc_id)} className="hover:underline">
                      {credit.principal_edition || result.doc_id}
                    </a>
                  </div>
                  <div className="text-xs text-gray-500">
                    {[dateLabel, place, result.region].filter(Boolean).join(' · ')}
                  </div>
                  {labels.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {labels.map((lab, li) => (
                        <span key={li} className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded inline-block">
                          {lab}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0 break-words text-gray-700" dir={dirFor(language)}>
                  {renderDocumentText(result)}
                  {result.matched_restored && (
                    <div className="mt-1 text-xs text-sky-700">match on restored text</div>
                  )}
                  {(credit.source_name || credit.source_url) && (
                    <div className="mt-1 text-xs text-gray-500">
                      Text:{' '}
                      {credit.source_url ? (
                        <a href={credit.source_url} target="_blank" rel="noopener noreferrer"
                           className="text-amber-700 hover:text-amber-900 underline">
                          {credit.source_name || 'source'}
                        </a>
                      ) : (credit.source_name)}
                      {credit.licence_name && <span>, {credit.licence_name}</span>}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <Pagination {...docPagination} idPrefix="docsearch" itemLabel="documents" pageSizeOptions={[docPagination.pageSize]} />
    </div>
  );
}
