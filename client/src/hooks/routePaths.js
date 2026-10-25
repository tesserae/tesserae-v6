// The path-to-page map of the site, shared by the route hook and the
// remembered last place (utils/lastPlace.js).

const pathToPageType = {
  '/': 'search',
  '/read': 'read',
  '/document': 'document',
  '/theme-search': 'theme-search',
  '/mentions': 'mentions',
  // Old address of the one-text search: it opens
  // Theme Search on the one-text scope (see legacyRedirect below).
  '/ask-a-work': 'theme-search',
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
  '/terms': 'terms',
  '/research': 'research',
  '/blog-archive': 'blog-archive',
  '/text-credits': 'text-credits',
  '/requests': 'requests',
  '/upload-help': 'upload-help',
  '/scholarship-sources': 'scholarship-sources',
  '/admin': 'admin'
};

// /events/<id> is the focus view of one event: a page of its own whose address
// carries the event, so it is matched by prefix and its path is not rewritten.
// /coins/<id> is one coin type, and /objects/<id> one object, handled the same way.
// /comparisons/<id> is the status page of a queued whole-comparison download.
export const pageForPath = (path) => {
  if (path === '/events' || path.startsWith('/events/')) return 'events';
  if (path === '/coins' || path.startsWith('/coins/')) return 'coins';
  if (path === '/objects' || path.startsWith('/objects/')) return 'objects';
  if (path.startsWith('/comparisons/')) return 'comparison-job';
  return pathToPageType[path] || 'search';
};

/** True when the path is a page of the site (the prefixes included). */
export const isKnownPath = (path) => (
  Object.prototype.hasOwnProperty.call(pathToPageType, path)
  || ['/events/', '/coins/', '/objects/', '/comparisons/'].some((p) => path.startsWith(p))
);

// Theme Search has three scopes, in the address as ?scope=one|two|corpus.
export const SCOPES = ['one', 'two', 'corpus'];
export const SCOPE_LABELS = { one: 'One text', two: 'Two texts', corpus: 'Whole corpus' };

// The scope an address asks for. With no scope= (a link made before the
// scopes existed) the parameters decide: compare=/with= or tab=compare is
// the two-text form, query=, tab=map, languages= or in=scholarship the
// whole-corpus form, and anything else the one-text form.
export const scopeFromSearch = (search) => {
  const p = new URLSearchParams(search || '');
  const s = (p.get('scope') || '').trim().toLowerCase();
  if (SCOPES.includes(s)) return s;
  if (p.get('compare') || p.get('with') || p.get('tab') === 'compare') return 'two';
  if (p.get('query') || p.get('tab') === 'map' || p.get('languages') || p.get('in') || p.get('works') || p.get('author')) return 'corpus';
  return 'one';
};

// /ask-a-work (Tessa's links, Help, the blog, bookmarks) opens the one-text
// scope of Theme Search with the same parameters (work, lang, q, books).
// Takes an address "path?query" and returns it, rewritten when it is the old one.
export const legacyRedirect = (url) => {
  const [pathAndQuery, hash] = String(url).split('#');
  const [path, query = ''] = pathAndQuery.split('?');
  if (path !== '/ask-a-work') return url;
  const p = new URLSearchParams(query);
  p.set('scope', 'one');
  return '/theme-search?' + p.toString() + (hash ? '#' + hash : '');
};
