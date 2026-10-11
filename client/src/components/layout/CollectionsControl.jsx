import { useEffect, useRef, useState } from 'react';
import useCollections from '../../hooks/useCollections';
import { COLLECTIONS, PROFILES } from '../../collections/collectionsConfig';

/**
 * The Collections control: a header button that opens a small panel with the
 * profiles and one switch per collection. The choice is saved for the
 * visitor (see collections/collectionsStore.js).
 */
export default function CollectionsControl() {
  const { on, profile, setProfile, setCollection } = useCollections();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        title="Choose which bodies of material the site shows: literature, inscriptions, papyri, coins, objects, scholarship"
        className="px-2 py-0.5 text-xs text-gray-500 hover:text-red-700 border border-gray-300 rounded bg-white whitespace-nowrap"
      >
        Collections
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Collections"
          className="absolute left-0 mt-1 w-72 bg-white border border-gray-200 rounded shadow-lg p-3 z-50 text-sm"
        >
          <p className="text-xs text-gray-600 mb-2">
            The view sets the profile, and the switches below refine it. The literature is always
            on. Each other body of material you switch on adds its
            pages to the menu, its tabs to the Reader and its choices to the searches. A profile
            sets the switches together.
          </p>
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">Profile</div>
          <div className="flex flex-wrap gap-1 mb-3">
            {PROFILES.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setProfile(p.id)}
                aria-pressed={profile === p.id}
                className={`px-2 py-1 rounded border text-xs ${
                  profile === p.id
                    ? 'border-red-700 text-red-700 font-semibold'
                    : 'border-gray-300 text-gray-600 hover:text-red-700'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">Collections</div>
          <ul className="space-y-1">
            {COLLECTIONS.map((c) => (
              <li key={c.id}>
                {c.fixed ? (
                  <div className="flex items-start gap-2">
                    <span className="mt-1 inline-block w-[13px] h-[13px] rounded-sm bg-gray-300" aria-hidden="true" />
                    <span>
                      <span className="font-medium">{c.label}</span>
                      <span className="ml-1 text-xs text-gray-500">always on</span>
                      <span className="block text-xs text-gray-500">{c.blurb}</span>
                    </span>
                  </div>
                ) : (
                <label className={`flex items-start gap-2 ${c.available ? '' : 'text-gray-400'}`}>
                  <input
                    type="checkbox"
                    className="mt-1 accent-red-700"
                    checked={!!on[c.id]}
                    disabled={!c.available}
                    onChange={(e) => setCollection(c.id, e.target.checked)}
                  />
                  <span>
                    <span className="font-medium">{c.label}</span>
                    {!c.available && <span className="ml-1 text-xs">(coming)</span>}
                    <span className="block text-xs text-gray-500">{c.blurb}</span>
                  </span>
                </label>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
