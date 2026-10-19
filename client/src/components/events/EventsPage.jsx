import { useCallback, useEffect, useState } from 'react';
import useCollections from '../../hooks/useCollections';
import { PAGE_NEEDS } from '../../collections/collectionsConfig';
import EventList from './EventList';
import EventView from './EventView';

function eventIdFromPath(path) {
  const m = /^\/events\/([^/]+)\/?$/.exec(path);
  return m ? decodeURIComponent(m[1]) : null;
}

/**
 * The Events page: /events lists events, /events/<id> is one event's focus
 * view. Shown only when the Collections control has inscriptions, papyri or
 * scholarship on (PAGE_NEEDS.events); a direct link otherwise lands on Search.
 */
export default function EventsPage({ setPageType }) {
  const { anyOn } = useCollections();
  const allowed = anyOn(PAGE_NEEDS.events);
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    if (!allowed && setPageType) setPageType('search');
  }, [allowed, setPageType]);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // The Events tab clicked while an event is open (the app has already
  // pushed /events onto the history).
  useEffect(() => {
    const onHome = () => {
      setPath('/events');
      window.scrollTo?.(0, 0);
    };
    window.addEventListener('tesserae:events-home', onHome);
    return () => window.removeEventListener('tesserae:events-home', onHome);
  }, []);

  const go = useCallback((to) => {
    window.history.pushState({}, '', to);
    setPath(to);
    window.scrollTo?.(0, 0);
  }, []);

  if (!allowed) return null;
  const id = eventIdFromPath(path);
  return id
    ? <EventView id={id} goList={() => go('/events')} />
    : <EventList openEvent={(eid) => go(`/events/${encodeURIComponent(eid)}`)} />;
}
