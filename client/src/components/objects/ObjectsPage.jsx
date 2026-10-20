import { useCallback, useEffect, useState } from 'react';
import ObjectList from './ObjectList';
import ObjectView from './ObjectView';

function objectIdFromPath(path) {
  const m = /^\/objects\/(.+?)\/?$/.exec(path);
  return m ? decodeURIComponent(m[1]) : null;
}

/**
 * The Objects page: /objects lists museum objects, /objects/<id> is one object.
 * Opens in every view and with any collection switch (the project lead, 2026-10-20: Events
 * chosen from the menu in the Literature view returned to Intertextual Search). The
 * collection switches decide what a search covers, not which pages open.
 */
export default function ObjectsPage() {
  const [path, setPath] = useState(() => window.location.pathname);


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

  const id = objectIdFromPath(path);
  return id
    ? <ObjectView id={id} goList={() => go('/objects')} />
    : <ObjectList openObject={(oid) => go(`/objects/${encodeURIComponent(oid)}`)} />;
}
