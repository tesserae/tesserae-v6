import { useCallback, useEffect, useState } from 'react';
import useCollections from '../../hooks/useCollections';
import { PAGE_NEEDS } from '../../collections/collectionsConfig';
import CoinList from './CoinList';
import CoinView from './CoinView';

function coinIdFromPath(path) {
  const m = /^\/coins\/(.+?)\/?$/.exec(path);
  return m ? decodeURIComponent(m[1]) : null;
}

/**
 * The Coins page: /coins lists coin types, /coins/<id> is one type. Shown
 * only when the Collections control has coins on (PAGE_NEEDS.coins); a
 * direct link otherwise lands on Search.
 */
export default function CoinsPage({ setPageType }) {
  const { anyOn } = useCollections();
  const allowed = anyOn(PAGE_NEEDS.coins);
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
  const id = coinIdFromPath(path);
  return id
    ? <CoinView id={id} goList={() => go('/coins')} />
    : <CoinList openCoin={(cid) => go(`/coins/${encodeURIComponent(cid)}`)} />;
}
