import { useCallback, useEffect, useState } from 'react';
import EventList from './EventList';
import EventView from './EventView';

function eventIdFromPath(path) {
  const m = /^\/events\/([^/]+)\/?$/.exec(path);
  return m ? decodeURIComponent(m[1]) : null;
}

/**
 * The Events page: /events lists events, /events/<id> is one event's focus
 * view. Opens in every view and with any collection switch (the project lead, 2026-10-20: Events
 * chosen from the menu in the Literature view returned to Intertextual Search). The
 * collection switches decide what a search covers, not which pages open.
 */
export default function EventsPage() {
  const [path, setPath] = useState(() => window.location.pathname);


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

  const id = eventIdFromPath(path);
  return id
    ? <EventView id={id} goList={() => go('/events')} />
    : <EventList openEvent={(eid) => go(`/events/${encodeURIComponent(eid)}`)} />;
}
