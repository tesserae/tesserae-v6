// The path-to-page map of the site, shared by the route hook and the
// remembered last place (utils/lastPlace.js).

const pathToPageType = {
  '/': 'search',
  '/read': 'read',
  '/document': 'document',
  '/theme-search': 'theme-search',
  '/mentions': 'mentions',
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
