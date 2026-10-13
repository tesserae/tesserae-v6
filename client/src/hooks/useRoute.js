// Which page is open and how the address and the browser history follow it
// (moved out of App.jsx, cleaning job H4, 2026-10-13, code unchanged). The
// path-to-page maps, the opening page of a visit, the address sync on a tab
// change, the tab title, the lock to the admin page during an admin session,
// the back button, the page switch with its guards, and the move to a view's
// home page.
import { useState, useEffect, useCallback, useRef } from 'react';
import { getView } from '../collections/collectionsStore';
import { viewById } from '../collections/collectionsConfig';

// What each page is called in the browser tab, the bookmark and the history.
const PAGE_TITLES = {
  search: 'Intertextual Search',
  read: 'Reader',
  document: 'Document',
  'theme-search': 'Theme Search',
  'ask-a-work': 'Search One Text',
  'inscriptions-papyri': 'Inscriptions & Papyri',
  events: 'Events',
  coins: 'Coins',
  objects: 'Objects',
  browse: 'Browse Corpus',
  repository: 'Repository',
  'line-search': 'Line Search',
  'string-search': 'String Search',
  visualizations: 'Visualize',
  downloads: 'Downloads',
  about: 'About',
  help: 'Help & Support',
  privacy: 'Privacy',
  research: 'Research',
  'blog-archive': 'Blog Archive',
  requests: 'Requests',
  admin: 'Admin',
};

const pathToPageType = {
  '/': 'search',
  '/read': 'read',
  '/document': 'document',
  '/theme-search': 'theme-search',
  '/ask-a-work': 'ask-a-work',
  '/inscriptions-papyri': 'inscriptions-papyri',
  '/events': 'events',
  '/coins': 'coins',
  '/objects': 'objects',
  '/browse': 'browse',
  // Alias: Help and Theme Search link to "/corpus" for the covered-works
  // list (the owner's word for the page), and it lands on Browse Corpus.
  // The address then canonicalizes to /browse (see the pageType->path
  // effect below); the query string carries the filter regardless of path.
  '/corpus': 'browse',
  '/repository': 'repository',
  '/line-search': 'line-search',
  '/string-search': 'string-search',
  '/visualize': 'visualizations',
  '/downloads': 'downloads',
  '/about': 'about',
  '/help': 'help',
  '/privacy': 'privacy',
  '/research': 'research',
  '/blog-archive': 'blog-archive',
  '/text-credits': 'text-credits',
  '/requests': 'requests',
  '/admin': 'admin'
};

// /events/<id> is the focus view of one event: a page of its own whose address
// carries the event, so it is matched by prefix and its path is not rewritten.
// /coins/<id> is one coin type, and /objects/<id> one object, handled the same way.
export const pageForPath = (path) => {
  if (path === '/events' || path.startsWith('/events/')) return 'events';
  if (path === '/coins' || path.startsWith('/coins/')) return 'coins';
  if (path === '/objects' || path.startsWith('/objects/')) return 'objects';
  return pathToPageType[path] || 'search';
};

const pageTypeToPath = {
  'search': '/',
  'read': '/read',
  'document': '/document',
  'theme-search': '/theme-search',
  'ask-a-work': '/ask-a-work',
  'inscriptions-papyri': '/inscriptions-papyri',
  'events': '/events',
  'coins': '/coins',
  'objects': '/objects',
  'browse': '/browse',
  'repository': '/repository',
  'line-search': '/line-search',
  'string-search': '/string-search',
  'visualizations': '/visualize',
  'downloads': '/downloads',
  'about': '/about',
  'help': '/help',
  'privacy': '/privacy',
  'research': '/research',
  'text-credits': '/text-credits',
  'requests': '/requests',
  'admin': '/admin'
};

// The address of a view's home page when that page is not the Intertextual
// Search page at '/': the Reader on a text, or Search One Text.
const viewHomeUrl = (view) => {
  const home = viewById(view).home;
  if (home.page === 'ask-a-work') return '/ask-a-work';
  if (home.page !== 'read') return null;
  const p = new URLSearchParams({ work: home.work, lang: home.lang });
  return '/read?' + p.toString();
};

// A visit to the bare site address, apart from the switches that choose a
// view or collections, which name no page of their own.
const NON_PAGE_PARAMS = ['view', 'profile', 'collections', 'documents', 'scholarship'];
const isPlainVisit = () => {
  if (window.location.pathname !== '/') return false;
  const params = new URLSearchParams(window.location.search);
  return Array.from(params.keys()).every((k) => NON_PAGE_PARAMS.includes(k));
};

export const useRoute = ({ adminSessionChecked, adminSessionActive }) => {
  const [pageType, setPageType] = useState(() => {
    const path = window.location.pathname;
    // A plain visit in a view whose home is the Reader opens the Reader on
    // that view's text. The address is rewritten before the Reader mounts so
    // it reads the work and language from it.
    if (isPlainVisit()) {
      const url = viewHomeUrl(getView());
      if (url) {
        window.history.replaceState({}, '', url);
        return viewById(getView()).home.page;
      }
    }
    return pageForPath(path);
  });

  // The first run of this effect is the page load: an alias address such as
  // /corpus?theme=1 is rewritten to its page's own path and MUST keep its
  // parameters (the deep link into Browse Corpus depends on it). Every later
  // run is a tab change, and a tab change starts the new page clean: the
  // query string used to be carried along, so after one Theme Search its
  // "?query=..." followed the visitor to Search, Read and back, and Theme
  // Search re-ran the old query every time its tab was opened
  // (2026-09-20). Returning to Theme Search kept autofilling the previous
  // query.
  const pathSyncedOnce = useRef(false);
  useEffect(() => {
    const newPath = pageTypeToPath[pageType] || '/';
    const firstRun = !pathSyncedOnce.current;
    pathSyncedOnce.current = true;
    const onEventPage = (pageType === 'events' && window.location.pathname.startsWith('/events/'))
      || (pageType === 'coins' && window.location.pathname.startsWith('/coins/'))
      || (pageType === 'objects' && window.location.pathname.startsWith('/objects/'));
    if (!onEventPage && window.location.pathname !== newPath) {
      window.history.pushState({}, '', firstRun ? newPath + window.location.search : newPath);
    }
  }, [pageType]);

  // Every page used to be called "Tesserae V6", so six open tabs, a list of
  // bookmarks and the browser history were all indistinguishable, and a saved
  // Reader page gave no clue what was in it (2026-09-08). The Reader sets its
  // own title from the work it is showing; this covers the rest.
  useEffect(() => {
    document.title = pageType === 'read'
      ? document.title
      : `${PAGE_TITLES[pageType] || 'Search'} — Tesserae`;
  }, [pageType]);

  useEffect(() => {
    if (adminSessionChecked && adminSessionActive && pageType !== 'admin') {
      setPageType('admin');
    }
  }, [adminSessionChecked, adminSessionActive, pageType]);

  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      if (adminSessionChecked && adminSessionActive) {
        setPageType('admin');
      } else {
        setPageType(pageForPath(path));
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [adminSessionChecked, adminSessionActive]);

  const setPageTypeWithGuard = useCallback((nextPageType) => {
    if (adminSessionChecked && adminSessionActive && nextPageType !== 'admin') {
      setPageType('admin');
      return;
    }
    // The Read tab clicked while the Reader is open used to do nothing (the
    // page type did not change, so no effect ran). It now takes the Reader
    // back to its starting page: a clean address and the language's opening
    // text (2026-09-20).
    if (nextPageType === 'read' && pageType === 'read') {
      window.history.pushState({}, '', '/read');
      window.dispatchEvent(new Event('tesserae:reader-home'));
      return;
    }
    setPageType(nextPageType);
  }, [adminSessionChecked, adminSessionActive, pageType]);

  // Switching view goes to the new view's home: the Reader on its text, or the
  // Intertextual Search page. Done inside the app, with no reload.
  const goViewHome = useCallback((nextView) => {
    if (adminSessionChecked && adminSessionActive) return;
    const url = viewHomeUrl(nextView);
    if (url) {
      window.history.pushState({}, '', url);
      // The Reader reads its work from the address on a back step, so a
      // popstate also moves an open Reader to the new text.
      window.dispatchEvent(new PopStateEvent('popstate'));
      setPageType(viewById(nextView).home.page);
    } else {
      window.history.pushState({}, '', '/');
      setPageType('search');
    }
  }, [adminSessionChecked, adminSessionActive]);

  return { pageType, setPageType, setPageTypeWithGuard, goViewHome };
};

export default useRoute;
