import { useCallback, useEffect, useState } from 'react';
import useCollections from '../../hooks/useCollections';
import { PAGE_NEEDS } from '../../collections/collectionsConfig';
import ObjectList from './ObjectList';
import ObjectView from './ObjectView';

function objectIdFromPath(path) {
  const m = /^\/objects\/(.+?)\/?$/.exec(path);
  return m ? decodeURIComponent(m[1]) : null;
}

/**
 * The Objects page: /objects lists museum objects, /objects/<id> is one object.
 * Shown only when the Collections control has objects on (PAGE_NEEDS.objects);
 * a direct link otherwise lands on Search.
 */
export default function ObjectsPage({ setPageType }) {
  const { anyOn } = useCollections();
  const allowed = anyOn(PAGE_NEEDS.objects);
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    if (!allowed && setPageType) setPageType('search');
  }, [allowed, setPageType]);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const go = useCallback((to) => {
    window.history.pushState({}, '', to);
    setPath(to);
    window.scrollTo?.(0, 0);
  }, []);

  if (!allowed) return null;
  const id = objectIdFromPath(path);
  return id
    ? <ObjectView id={id} goList={() => go('/objects')} />
    : <ObjectList openObject={(oid) => go(`/objects/${encodeURIComponent(oid)}`)} />;
}
