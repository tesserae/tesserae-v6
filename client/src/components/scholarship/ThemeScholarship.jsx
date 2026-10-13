import { useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import ScopeBox from '../common/ScopeBox';
import { RECENT_SERVICES, RECENT_LABELS, joinNames, mergeRecent, recentUrl, fetchRecent } from '../../utils/recentArticles';

/**
 * The Scholarship option of Theme Search: commentary notes and journal
 * sentences ranked by meaning and keyword together, on their own, never mixed
 * into the passage ranking. The label comes from GET /api/scholarship/theme.
 */

export function workName(work) {
  return String(work || '').replace(/\.part\.\d+.*$/, '').split(/[._]/).filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

export function heading(m) {
  if (m.kind === 'article') {
    return [m.journal, m.year].filter(Boolean).join(', ');
  }
  const where = [workName(m.work), m.ref_start].filter(Boolean).join(', ');
  return [m.commentator, where].filter(Boolean).join(' on ');
}

export function linkText(link) {
  if (!link) return null;
  if (link.kind === 'reader') return 'Open the passage in the Reader';
  return /jstor\.org/.test(link.url) ? 'Open the article on JSTOR' : 'Open the article';
}

/** The articles the live services give for the question (under the held list):
 *  each service's items paint as it answers. With a work (the question came from
 *  Search One Text) the server also requires the work to be named. */
function RecentArticles({ recent }) {
  if (!recent) return null;
  return (
    <>
      {recent.items.length > 0 && (
        <section aria-label="Articles found online" className="mt-4 rounded border border-gray-200 bg-white px-3 py-2" data-testid="theme-recent">
          <p className="text-xs font-semibold text-gray-600">Articles found online</p>
          <ul className="mt-1 space-y-2">
            {recent.items.map((it) => {
              const url = recentUrl(it);
              const meta = [(it.authors || []).join(', '), it.year, it.venue].filter(Boolean).join(', ');
              return (
                <li key={`${it.doi || ''}|${it.title}`} className="text-sm text-gray-800 leading-snug" data-testid="theme-recent-item">
                  {url ? (
                    <a href={url} target="_blank" rel="noopener noreferrer" className="text-red-800 hover:text-red-900 hover:underline">{it.title}</a>
                  ) : it.title}
                  {meta && <span className="text-gray-600">{`, ${meta}`}</span>}
                  {it.oa_url && <span className="ml-1 rounded bg-gray-100 px-1 text-[11px] text-gray-500">free copy</span>}
                  {it.excerpt && <span className="block text-xs text-gray-500">{it.excerpt}</span>}
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {recent.pending.length > 0 && (
        <p className="mt-1 text-xs text-gray-500" data-testid="theme-recent-pending">
          {`Asking ${joinNames(recent.pending.map((x) => RECENT_LABELS[x]))} for articles...`}
        </p>
      )}
    </>
  );
}

export default function ThemeScholarship({ search }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [recent, setRecent] = useState(null);   // { pending: [service], items: [...] }

  // The five services are asked at once, alongside the held list.
  useEffect(() => {
    if (!search?.q) return undefined;
    setRecent({ pending: [...RECENT_SERVICES], items: [] });
    const ask = fetchRecent(search.q, search.work, (svc, r) => {
      setRecent((cur) => (cur ? {
        pending: cur.pending.filter((x) => x !== svc),
        items: r && r.available && Array.isArray(r.results) ? mergeRecent(cur.items, r.results) : cur.items,
      } : cur));
    });
    return () => ask.stop();
  }, [search]);

  useEffect(() => {
    if (!search?.q) return undefined;
    let dead = false;
    setData(null);
    setError(null);
    fetch(`/api/scholarship/theme?q=${encodeURIComponent(search.q)}&k=10`)
      .then((r) => { if (!r.ok) throw new Error(`Server answered ${r.status}`); return r.json(); })
      .then((d) => { if (!dead) setData(d); })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [search]);

  if (!search?.q) {
    return <p className="mt-4 text-sm text-gray-600">Describe a theme, a passage or a point of interpretation, then press Search.</p>;
  }
  if (error) return <p className="mt-4 text-sm text-red-700">Scholarship could not be searched ({error}).</p>;
  if (!data) return <div className="mt-4"><LoadingSpinner text="Searching commentaries and articles..." /></div>;
  if (data.available === false) {
    return <p className="mt-4 text-sm text-gray-600">The scholarship search is not installed on this server yet.</p>;
  }
  if (data.unavailable) return <p className="mt-4 text-sm text-gray-600">{data.error}</p>;
  const results = data.results || [];
  return (
    <div className="mt-4" data-testid="theme-scholarship">
      <p className="text-xs text-gray-500" data-testid="theme-scholarship-label">{data.label}</p>
      <ScopeBox id="scholarship_theme" className="mt-2" />
      <ul className="mt-2 space-y-2">
        {results.map((m) => (
          <li key={m.id} className="bg-white border border-gray-200 rounded-lg p-3" data-testid="scholarship-match">
            <p className="text-sm font-semibold text-gray-900">{heading(m)}</p>
            {m.kind === 'article' && m.title && <p className="text-sm italic text-gray-700">{m.title}</p>}
            <p className="text-sm text-gray-900 mt-0.5">{m.snippet}</p>
            {m.link && (
              <p className="text-xs mt-1">
                <a href={m.link.url} className="text-red-700 hover:underline"
                   {...(m.link.kind === 'jstor' ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>
                  {linkText(m.link)}
                </a>
              </p>
            )}
          </li>
        ))}
      </ul>
      {results.length === 0 && <p className="text-sm text-gray-600">Nothing close was found.</p>}
      <RecentArticles recent={recent} />
    </div>
  );
}
