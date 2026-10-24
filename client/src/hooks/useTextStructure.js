import { useEffect, useState } from 'react';
import { getJson } from '../utils/api';

// One request per work for the life of the page. A work with no structure
// (a 404) is remembered as null so it is not asked for again.
const cache = new Map();

export function clearTextStructureCache() { cache.clear(); }

/** The id the structure route takes: the work file without ".tess". */
export function structureId(work) {
  return String(work || '').replace(/\.tess$/, '');
}

/** A work's own division into stories (the Shahnameh's 857), or null while
 *  loading, when `enabled` is false, or when the work has none. Returns
 *  { work, unit, sections: [{ number, title_en, title_fa, reign_fa, first_ref,
 *  last_ref, n_couplets }] }. */
export default function useTextStructure(work, enabled = true) {
  const id = structureId(work);
  const [state, setState] = useState({ id: '', data: null });
  useEffect(() => {
    if (!id || !enabled) return undefined;
    if (cache.has(id)) {
      setState({ id, data: cache.get(id) });
      return undefined;
    }
    let dead = false;
    getJson(`/api/texts/structure/${encodeURIComponent(id)}`)
      .then((d) => (d && Array.isArray(d.sections) && d.sections.length ? d : null))
      .catch(() => null)
      .then((d) => {
        cache.set(id, d);
        if (!dead) setState({ id, data: d });
      });
    return () => { dead = true; };
  }, [id, enabled]);
  return enabled && state.id === id ? state.data : null;
}
