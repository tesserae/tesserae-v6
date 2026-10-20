import { useCallback, useEffect, useState } from 'react';
import CoinList from './CoinList';
import CoinView from './CoinView';

function coinIdFromPath(path) {
  const m = /^\/coins\/(.+?)\/?$/.exec(path);
  return m ? decodeURIComponent(m[1]) : null;
}

/**
 * The Coins page: /coins lists coin types, /coins/<id> is one type.
 * Opens in every view and with any collection switch (the project lead, 2026-10-20: Events
 * chosen from the menu in the Literature view returned to Intertextual Search). The
 * collection switches decide what a search covers, not which pages open.
 */
export default function CoinsPage() {
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

  const id = coinIdFromPath(path);
  return id
    ? <CoinView id={id} goList={() => go('/coins')} />
    : <CoinList openCoin={(cid) => go(`/coins/${encodeURIComponent(cid)}`)} />;
}
