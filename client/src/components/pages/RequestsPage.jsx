import { useEffect, useState } from 'react';
import { RequestDialog } from '../common';

/**
 * The public mirror of the requests workflow (2026-10-08): every feature,
 * language, text, bug, correction and suggestion scholars have filed,
 * pulled live from the GitHub issues the site itself creates. A scholar
 * never needs a GitHub account to see what has been asked for, or to ask
 * for something themselves.
 */

const STATUS_STYLES = {
  open: 'bg-blue-100 text-blue-700',
  'in progress': 'bg-amber-100 text-amber-700',
  done: 'bg-green-100 text-green-700',
  declined: 'bg-gray-100 text-gray-600',
};

const STATUS_LABELS = {
  open: 'Open',
  'in progress': 'In progress',
  done: 'Done',
  declined: 'Declined',
};

function formatDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

function StatusChip({ status }) {
  return (
    <span
      className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
        STATUS_STYLES[status] || 'bg-gray-100 text-gray-600'}`}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function RequestRow({ item }) {
  return (
    <li className="flex items-start justify-between gap-3 py-3 border-b border-gray-100 last:border-0">
      <div className="min-w-0">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-gray-900 hover:text-red-700 hover:underline"
        >
          {item.title}
        </a>
        {item.summary && <p className="text-xs text-gray-600 mt-0.5">{item.summary}</p>}
        <p className="text-xs text-gray-500 mt-0.5">
          {item.type} &middot; {formatDate(item.created_at)}
          {item.pr_url && (
            <>
              {' '}&middot;{' '}
              <a href={item.pr_url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                See the fix
              </a>
            </>
          )}
        </p>
      </div>
      <StatusChip status={item.status} />
    </li>
  );
}

function RequestGroup({ heading, items, emptyText }) {
  return (
    <section className="mb-8">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-2">
        {heading} ({items.length})
      </h2>
      {items.length === 0 ? (
        <p className="text-sm text-gray-500">{emptyText}</p>
      ) : (
        <ul>
          {items.map((item) => <RequestRow key={item.number} item={item} />)}
        </ul>
      )}
    </section>
  );
}

export default function RequestsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    let dead = false;
    fetch('/api/requests')
      .then((r) => r.json())
      .then((d) => { if (!dead) setData(d); })
      .catch(() => { if (!dead) setError('Could not load the requests list right now.'); });
    return () => { dead = true; };
  }, []);

  return (
    <div className="bg-white rounded-lg shadow p-6 sm:p-8 max-w-3xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-2">
        <h1 className="text-2xl font-bold text-gray-900">Requests</h1>
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="shrink-0 px-3 py-1.5 text-sm rounded bg-red-700 text-white hover:bg-red-800"
        >
          Suggest a change
        </button>
      </div>
      <p className="text-gray-600 text-sm mb-6">
        Features, languages, texts, corrections and other requests from scholars using
        Tesserae, filed as public GitHub issues. Open items are things we have not
        finished yet. A done item links to the pull request that fixed it, when there
        is one.
      </p>

      {error && <p className="text-sm text-red-700">{error}</p>}
      {!data && !error && <p className="text-sm text-gray-500">Loading...</p>}

      {data && (
        <>
          <RequestGroup heading="Open" items={data.open} emptyText="Nothing open right now." />
          <RequestGroup heading="Done" items={data.done} emptyText="Nothing closed recently." />
        </>
      )}

      <RequestDialog
        isOpen={dialogOpen}
        onClose={() => setDialogOpen(false)}
        type="suggestion"
        context={{ page_url: typeof window !== 'undefined' ? window.location.href : '' }}
      />
    </div>
  );
}
