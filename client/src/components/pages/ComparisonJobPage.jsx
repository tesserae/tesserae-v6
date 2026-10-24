import { useEffect, useState } from 'react';
import { getJson } from '../../utils/api';

// The status page of a queued whole-comparison download, /comparisons/<id>.
// It reads GET /api/comparisons/jobs/<id> every ten seconds until the job is
// done or failed, and shows the download link when the file is ready.

const POLL_MS = 10000;

export const jobIdFromPath = (path) => {
  const m = /^\/comparisons\/([A-Za-z0-9]+)\/?$/.exec(path || '');
  return m ? m[1] : '';
};

const place = (n) => (n === 1 ? 'It is next in line.' : `It is number ${n} in line.`);

const ComparisonJobPage = ({ jobId }) => {
  const id = jobId || jobIdFromPath(window.location.pathname);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return undefined;
    let stopped = false;
    let timer = null;
    const load = async () => {
      try {
        const body = await getJson(`/api/comparisons/jobs/${encodeURIComponent(id)}`);
        if (stopped) return;
        if (body?.error) {
          setError(body.error);
          return;
        }
        setError('');
        setJob(body);
        if (body.status === 'queued' || body.status === 'running') {
          timer = setTimeout(load, POLL_MS);
        }
      } catch (e) {
        if (stopped) return;
        setError(e.message || 'Could not reach the server.');
        timer = setTimeout(load, POLL_MS);
      }
    };
    load();
    return () => { stopped = true; if (timer) clearTimeout(timer); };
  }, [id]);

  const openUrl = job
    ? `/?${new URLSearchParams({ source: job.source, target: job.target, lang: job.language })}`
    : '';

  return (
    <div className="max-w-2xl mx-auto bg-white rounded-lg shadow p-6">
      <h1 className="text-xl font-semibold text-gray-900 mb-3">Prepared comparison</h1>
      {!id && <p>This address names no comparison.</p>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {job && (
        <div className="text-sm text-gray-800 space-y-2">
          <p><span className="text-gray-500">Source</span> {job.source}</p>
          <p><span className="text-gray-500">Target</span> {job.target}</p>
          {job.status === 'queued' && (
            <p role="status">Waiting in the queue. {place(job.position || 1)}
              {' '}The server prepares one comparison at a time, and each takes about an hour.
              This page updates by itself.</p>
          )}
          {job.status === 'running' && (
            <p role="status">The server is preparing it now. This takes about an hour, and this page
              updates by itself.</p>
          )}
          {job.status === 'done' && (
            <div role="status">
              <p>Ready: {job.rows} parallels, in the columns of the page&apos;s CSV export.</p>
              <p className="mt-2">
                <a href={job.download_url} className="px-4 py-2 bg-red-700 text-white rounded-lg hover:bg-red-800 inline-block">
                  Download the file
                </a>
              </p>
              <p className="mt-2 text-gray-600">
                The comparison also opens on <a href={openUrl} className="text-red-700 underline">the comparison page</a>,
                with its charts. The file is kept {job.retention_days} days.
              </p>
            </div>
          )}
          {job.status === 'failed' && (
            <p role="alert" className="text-red-700">{job.error}</p>
          )}
        </div>
      )}
    </div>
  );
};

export default ComparisonJobPage;
