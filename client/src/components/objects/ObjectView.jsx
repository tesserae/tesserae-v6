import { useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import ObjectCard from './ObjectCard';
import { objectTitle } from './objectsFormat';

function Row({ label, text }) {
  if (!text) return null;
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-gray-500">{label}</dt>
      <dd className="text-gray-800 whitespace-pre-line break-words">{text}</dd>
    </div>
  );
}

/** One object on a page of its own (/objects/<id>), with the full description and label. */
export default function ObjectView({ id, goList }) {
  const [object, setObject] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let dead = false;
    setObject(null);
    setError(null);
    fetch(`/api/objects/${encodeURIComponent(id)}`)
      .then((r) => {
        if (r.status === 404) throw new Error('No such object.');
        if (!r.ok) throw new Error(`Server answered ${r.status}`);
        return r.json();
      })
      .then((d) => { if (!dead) setObject(d.object); })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [id]);

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <button type="button" onClick={goList} className="text-sm text-red-700 hover:underline mb-3">
        All objects
      </button>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {!object && !error && <div className="py-8"><LoadingSpinner text="Loading object..." /></div>}
      {object && (
        <>
          <h2 className="sr-only">{objectTitle(object)}</h2>
          <ObjectCard object={object} full />
          <dl className="mt-4 bg-white border border-gray-200 rounded-lg p-4 text-sm space-y-2">
            <Row label="Museum label" text={object.short_text} />
            <Row label="Inscription" text={object.inscription_text} />
            <Row label="Place" text={object.place_text} />
            <Row label="Licence" text={object.licence} />
            <Row label="Identifier" text={object.id} />
          </dl>
        </>
      )}
    </div>
  );
}
