import { useState, useEffect } from 'react';

// "Sources and credits" for every collection the site serves. The records
// come from data/sources_credits.json through /api/sources-credits: each
// import of texts, documents or a scholarship source adds one record there,
// and this view needs no change.
export const COLLECTION_ORDER = [
  'Literary texts',
  'Translations',
  'Inscriptions and papyri',
  'Scholarship',
  'Events',
  'Places and identifiers',
];

export function groupRecords(records) {
  const groups = new Map(COLLECTION_ORDER.map((c) => [c, []]));
  for (const rec of records || []) {
    if (!groups.has(rec.collection)) groups.set(rec.collection, []);
    groups.get(rec.collection).push(rec);
  }
  return [...groups.entries()].filter(([, recs]) => recs.length > 0);
}

function Link({ href, children }) {
  if (!href) return <span>{children}</span>;
  const internal = href.startsWith('/');
  return (
    <a href={href} className="text-red-700 hover:underline"
       {...(internal ? {} : { target: '_blank', rel: 'noopener noreferrer' })}>
      {children}
    </a>
  );
}

export default function SourcesCredits() {
  const [records, setRecords] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let dead = false;
    fetch('/api/sources-credits')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('failed'))))
      .then((d) => { if (!dead) setRecords(d.records || []); })
      .catch(() => { if (!dead) setFailed(true); });
    return () => { dead = true; };
  }, []);

  if (failed) {
    return <p className="text-sm text-red-600 mb-6">The list of sources and licences could not be loaded.</p>;
  }
  if (!records) return null;

  return (
    <section id="sources-and-credits" className="mb-8" aria-label="Sources and credits">
      <h2 className="text-2xl font-semibold text-gray-900 mb-2">Sources and credits</h2>
      <p className="text-gray-700 leading-relaxed mb-4">
        Every collection Tesserae serves, with where it came from, the licence it was given to us
        under, and the version we hold. The table of literary texts follows below.
      </p>
      {groupRecords(records).map(([collection, recs]) => (
        <div key={collection} className="mb-5" data-testid={`credits-group-${collection}`}>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">{collection}</h3>
          <div className="space-y-3">
            {recs.map((rec) => (
              <div key={rec.name} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="font-medium text-gray-900">
                  <Link href={rec.url}>{rec.name}</Link>
                </div>
                <p className="text-sm text-gray-700 mt-1">
                  <span className="font-semibold">Licence: </span>
                  <Link href={rec.licence_url}>{rec.licence_name}</Link>
                </p>
                {(rec.version || rec.retrieved) && (
                  <p className="text-sm text-gray-700">
                    <span className="font-semibold">Version: </span>{rec.version}
                    {rec.retrieved ? <span>{' '}(retrieved {rec.retrieved})</span> : null}
                  </p>
                )}
                {rec.what_we_use && (
                  <p className="text-sm text-gray-700">
                    <span className="font-semibold">What we use: </span>{rec.what_we_use}
                  </p>
                )}
                {rec.notes && <p className="text-xs text-gray-500 mt-1">{rec.notes}</p>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
