import { useEffect, useState } from 'react';
import { getJson } from '../../utils/api';

// "Your prepared comparisons": the visitor's own queued and finished
// whole-comparison downloads of the last 14 days, found by the cookie token
// (GET /api/comparisons/jobs). Shown only when there is at least one, so a
// visitor finds the file again without keeping an address. `refreshKey` asks
// for a fresh read (the page bumps it when a job is queued).

const STATUS_TEXT = {
  queued: (j) => (j.position ? `waiting, number ${j.position} in line` : 'waiting'),
  running: () => 'being prepared now',
  done: () => 'ready',
  failed: () => 'did not finish',
};

const YourComparisons = ({ refreshKey = 0, labelFor = (id) => id }) => {
  const [jobs, setJobs] = useState([]);

  useEffect(() => {
    let stopped = false;
    getJson('/api/comparisons/jobs', { credentials: 'same-origin' })
      .then((body) => { if (!stopped) setJobs(Array.isArray(body?.jobs) ? body.jobs : []); })
      .catch(() => { if (!stopped) setJobs([]); });
    return () => { stopped = true; };
  }, [refreshKey]);

  if (!jobs.length) return null;
  return (
    <div role="region" aria-label="Your prepared comparisons"
         className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-800">
      <h3 className="font-semibold text-gray-900 mb-2">Your prepared comparisons</h3>
      <ul className="space-y-1">
        {jobs.map((j) => (
          <li key={j.id}>
            <a href={`/comparisons/${j.id}`} className="text-red-700 underline">
              {labelFor(j.source)} and {labelFor(j.target)}
            </a>
            {': '}{(STATUS_TEXT[j.status] || (() => j.status))(j)}
            {j.created ? `, asked ${new Date(j.created).toLocaleDateString()}` : ''}
            {j.status === 'done' && j.download_url && (
              <>{' '}<a href={j.download_url} className="text-red-700 underline">Download</a></>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default YourComparisons;
