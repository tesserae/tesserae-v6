import { useState } from 'react';
import { postJsonTo } from '../../utils/api';

// Shown when the server will not run a pair of works live because it is above
// the size limit (backend/compare_limit.py). `answer` is the server's
// too_large body: line_pairs, limit, books (each {side, id, label, lines}),
// download_job_url and email_notice. The reader can choose one book on a side
// and compare now, or ask for the whole comparison as a file.

const millions = (n) => Math.max(1, Math.round((n || 0) / 1e6));

const SIDES = [['source', 'Source'], ['target', 'Target']];

const TooLargePanel = ({ sourceName, targetName, answer, params, onChooseBook }) => {
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState(null);
  const [problem, setProblem] = useState('');

  if (!answer?.too_large) return null;
  const books = answer.books || [];

  const submit = async () => {
    setBusy(true);
    setProblem('');
    try {
      const body = {
        source: params.source,
        target: params.target,
        language: params.language,
        settings: params,
      };
      if (answer.email_notice && email.trim()) body.email = email.trim();
      const res = await postJsonTo(answer.download_job_url || '/api/comparisons/jobs', body);
      if (res?.id) setJob(res);
      else setProblem(res?.error || 'The request could not be sent. Please try again.');
    } catch (e) {
      setProblem(e.message || 'The request could not be sent. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="region"
      aria-label="Comparison too large"
      className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-gray-800"
    >
      <p>
        {sourceName} against {targetName} is about {millions(answer.line_pairs)} million line pairs.
        {' '}Two whole works this size take the server about an hour. Choose a book on one side to
        compare now, with every chart, or ask for the whole comparison as a file.
      </p>

      <div className="mt-3 flex flex-wrap gap-4">
        {SIDES.map(([side, label]) => {
          const list = books.filter((b) => b.side === side);
          if (!list.length) return null;
          return (
            <label key={side} className="flex flex-col text-xs text-gray-600">
              {label} book
              <select
                aria-label={`${label} book`}
                defaultValue=""
                onChange={(e) => e.target.value && onChooseBook(side, e.target.value)}
                className="mt-1 border border-gray-300 rounded px-2 py-1 text-sm text-gray-800 bg-white"
              >
                <option value="">Choose a book</option>
                {list.map((b) => (
                  <option key={b.id} value={b.id}>{b.label}</option>
                ))}
              </select>
            </label>
          );
        })}
      </div>

      {!job && (
        <div className="mt-4 border-t border-amber-200 pt-3">
          {answer.email_notice && (
            <label className="block text-xs text-gray-600 mb-2">
              Email me when it is ready (optional)
              <input
                type="email"
                aria-label="Email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 block w-full max-w-xs border border-gray-300 rounded px-2 py-1 text-sm text-gray-800 bg-white"
              />
            </label>
          )}
          <button
            type="button"
            onClick={submit}
            disabled={busy}
            className="px-4 py-2 bg-red-700 text-white rounded-lg hover:bg-red-800 disabled:opacity-50"
          >
            Prepare the whole comparison as a download
          </button>
          {problem && <p role="alert" className="mt-2 text-red-700">{problem}</p>}
        </div>
      )}

      {job && (
        <div className="mt-4 border-t border-amber-200 pt-3" role="status">
          <p>
            Your comparison is queued
            {job.position ? `, number ${job.position} in line` : ''}. The server prepares one at a
            time, and a file is kept {job.retention_days || 14} days.
          </p>
          <p className="mt-1">
            <a href={`/comparisons/${job.id}`} className="text-red-700 underline">
              Check on it here
            </a>
            {answer.email_notice && email.trim() ? ', or wait for the email.' : '. Keep this link: it is the only notice.'}
          </p>
        </div>
      )}
    </div>
  );
};

export default TooLargePanel;
