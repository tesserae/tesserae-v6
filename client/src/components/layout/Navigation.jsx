import { useState, useEffect, useRef, useCallback } from 'react';
import { rememberLanguage } from '../../utils/languagePreference';
import StartLanguageControl from './StartLanguageControl';
import useCollections from '../../hooks/useCollections';
import { useIsNarrow } from '../../hooks/useIsPhone';
import { VIEWS, viewById, orderBy } from '../../collections/collectionsConfig';
import CollectionsControl from './CollectionsControl';
import { fetchLanguages } from '../../utils/api';

/** Tells a horizontally scrolling strip whether there is more to its right.
 *
 *  The tab strips hide their scrollbar, which looks clean on a laptop where
 *  every tab fits and hides half the site on a phone where three or four do.
 *  This sets data-more on the container; index.css paints a fade while it is
 *  true (2026-09-08). Watches scrolling, resizing and content changes, because
 *  the language row appears and disappears with the page.
 */
function useScrollHint(contentKey) {
  const ref = useRef(null);
  const [more, setMore] = useState(false);
  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    setMore(el.scrollWidth - el.clientWidth - el.scrollLeft > 4);
  }, []);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    // contentKey re-measures when the tabs themselves change: adding a tab
    // changes scrollWidth but not the container's own box, so a ResizeObserver
    // alone would not notice.
    measure();
    el.addEventListener('scroll', measure, { passive: true });
    window.addEventListener('resize', measure);
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    if (ro) ro.observe(el);
    return () => {
      el.removeEventListener('scroll', measure);
      window.removeEventListener('resize', measure);
      if (ro) ro.disconnect();
    };
  }, [measure, contentKey]);
  return [ref, more];
}

/**
 * How many leading tabs fit in `available` pixels beside a More button of
 * `moreWidth`, given each tab's width. Everything after that goes into More
 * (owner 2026-10-10: with every collection on, "the About tab is fading away
 * at the margin"). With no measurements (jsdom, first paint) every tab fits.
 */
export function fitTabs(widths, available, moreWidth) {
  if (!widths.length || !available) return widths.length;
  const total = widths.reduce((a, b) => a + b, 0);
  if (total <= available) return widths.length;
  let used = 0;
  let n = 0;
  for (const w of widths) {
    if (used + w > available - moreWidth) break;
    used += w;
    n += 1;
  }
  return n;
}

/**
 * A small menu hung from a button and positioned FIXED from the button's place
 * on screen (the More menu and the People, Places & Things menu use it). A menu
 * hanging absolutely under its button inside the tab row was clipped by the
 * row, which scrolls sideways, and opened unseen (the owner, 2026-10-12:
 * "Clicking on More does nothing."). The menu closes on a click elsewhere, on
 * scrolling and on resizing.
 */
function useFixedMenu(width) {
  const ref = useRef(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState(null);
  const toggle = () => {
    const r = ref.current ? ref.current.getBoundingClientRect() : null;
    const left = r ? Math.max(0, Math.min(r.left, (window.innerWidth || width) - width - 8)) : 0;
    setPos({ top: (r ? r.bottom : 0) + 4, left });
    setOpen((o) => !o);
  };
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const shut = () => setOpen(false);
    document.addEventListener('mousedown', close);
    window.addEventListener('scroll', shut, true);
    window.addEventListener('resize', shut);
    return () => {
      document.removeEventListener('mousedown', close);
      window.removeEventListener('scroll', shut, true);
      window.removeEventListener('resize', shut);
    };
  }, [open]);
  return { ref, open, setOpen, pos, toggle };
}

// The pages about what the texts refer to sit under one menu in the top row
// (the project lead, 2026-10-19). Each member keeps its own flags below.
const THINGS_GROUP = { code: 'things', label: 'People, Places & Things' };

const mainTabs = [
  { code: 'search', label: 'Intertextual Search' },
  { code: 'read', label: 'Read' },
  { code: 'theme-search', label: 'Theme Search' },
  // Where a place, person or god is named.
  { code: 'mentions', label: 'People & Places', group: 'things' },
  { code: 'ask-a-work', label: 'Search One Text', beta: true },
  // Trial: shown only when the documents trial is active, both the server
  // switch (TESSERAE_DOCUMENTS=1, read from /api/languages below) and the
  // client's own ?documents=1 session flag -- see useDocumentsTrial and
  // the documentsEnabled state below. Filtered out of `mainTabs` at
  // render time rather than left out of this list, so its position
  // (beside Theme Search) does not depend on where a conditional push
  // would land it.
  // No beta mark since 2026-10-19 (the project lead): the condition set that morning, a Latin documents index rebuilt
  // after the Latin lemma corrections, was met by the rebuild installed at 00:20 the same day.
  { code: 'inscriptions-papyri', label: 'Inscriptions & Papyri', trial: true, group: 'things' },
  // Events (battles, sieges, treaties).
  { code: 'events', label: 'Events', beta: true, needs: 'events', group: 'things' },
  // Coins (Greek and Roman coin types).
  // No beta mark since 2026-10-19 (the project lead): the page lists the coin types as OCRE and CRRO publish them, nothing on it is the site's own inference.
  { code: 'coins', label: 'Coins', needs: 'coins', group: 'things' },
  // Objects (museum catalogue descriptions). No beta mark since 2026-10-19, for the same reason as Coins.
  { code: 'objects', label: 'Objects', needs: 'objects', group: 'things' },
  { code: 'browse', label: 'Browse Corpus' },
  // Repository and Downloads sit under a small "More" menu at the end of the
  // row (owner 2026-10-10: with every collection on, thirteen entries no
  // longer fit and the last ones faded off the right edge).
  { code: 'repository', label: 'Repository', more: true },
  // DISABLED FOR PRODUCTION - Uncomment to restore Visualizations
  // { code: 'visualizations', label: 'Visualize' },
  { code: 'downloads', label: 'Downloads', more: true },
  // Research has no main-menu entry (owner 2026-10-10: most visitors will not
  // look at it regularly); it is reached from the About page and at /research.
  { code: 'about', label: 'About' },
  { code: 'help', label: 'Help & Support' },
  // Under the More menu, after Help: what the scholarship results are made from.
  { code: 'scholarship-sources', label: 'Scholarship sources', more: true },
  { code: 'admin', label: 'Admin' }
];

const defaultLanguageTabs = [
  { code: 'la', label: 'Latin' },
  { code: 'grc', label: 'Greek' },
  { code: 'en', label: 'English' },
  { code: 'cross', label: 'Cross-Language' }
];

const Navigation = ({
  pageType,
  setPageType,
  activeTab,
  setActiveTab,
  onLanguageReset,
  lockedToAdmin = false,
  onAdminLogout,
  showDownloads = false,
  setShowDownloads,
  onViewChange
}) => {
  const [languageTabs, setLanguageTabs] = useState(defaultLanguageTabs);
  // Below `sm` the view switch is one button with a small menu, so the whole
  // main menu fits on one row.
  const narrow = useIsNarrow();
  const [viewMenuOpen, setViewMenuOpen] = useState(false);
  const [collectionsOpen, setCollectionsOpen] = useState(false);
  const viewMenuRef = useRef(null);
  useEffect(() => {
    if (!viewMenuOpen) return undefined;
    const onDown = (e) => { if (viewMenuRef.current && !viewMenuRef.current.contains(e.target)) setViewMenuOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setViewMenuOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [viewMenuOpen]);
  useEffect(() => { if (!narrow) { setViewMenuOpen(false); setCollectionsOpen(false); } }, [narrow]);
  const moreMenu = useFixedMenu(160);
  const thingsMenu = useFixedMenu(260);
  const [mainRef, mainMore] = useScrollHint(showDownloads);
  // Overflow into More: the visible tabs are measured in a hidden copy of
  // the row, and the ones past the container's width move into the menu.
  const measureRef = useRef(null);
  const [fitCount, setFitCount] = useState(null);
  const refit = useCallback(() => {
    const row = mainRef.current;
    const probe = measureRef.current;
    if (!row || !probe) return;
    const items = Array.from(probe.querySelectorAll('[data-tab]'));
    const widths = items.map((el) => el.offsetWidth || 0);
    const moreEl = probe.querySelector('[data-more-probe]');
    const moreWidth = moreEl ? moreEl.offsetWidth || 0 : 0;
    const available = row.clientWidth || 0;
    if (!available || widths.every((w) => !w)) { setFitCount(null); return; }
    setFitCount(fitTabs(widths, available, moreWidth));
  }, [mainRef]);
  const [langRef, langMore] = useScrollHint(languageTabs.length + ':' + pageType);
  // The documents trial's client-side flag (?documents=1, remembered for
  // the visit) and the server switch together gate the "Inscriptions &
  // Papyri" tab -- the same two-part gate LineSearch.jsx's own documents
  // control and CorpusBrowser's Documents tab use.
  const { view, setView } = useCollections();
  // The Collections control is shown to every visitor (owner 2026-10-10: the
  // Start here panel named the historical collections while nothing at the
  // top of the page showed them). The default profile is still Literary, so
  // the tabs change only when a visitor switches a collection on.
  const showCollections = true;
  const [documentsEnabled, setDocumentsEnabled] = useState(false);

  useEffect(() => {
    fetchLanguages()
      .then(data => {
        if (data.languages) {
          const tabs = data.languages.map(l => ({ code: l.code, label: l.label }));
          tabs.push({ code: 'cross', label: 'Cross-Language' });
          setLanguageTabs(tabs);
        }
        setDocumentsEnabled(!!data.documents_enabled);
      })
      .catch(() => {}); // fall back to defaults
  }, []);
  // The documents pages are listed whenever the server switch is on; the
  // client's ?documents=1 flag and the collection switches no longer gate
  // the menu (2026-10-19).
  const showInscriptionsPapyri = documentsEnabled;
  const handleLanguageClick = (tabCode) => {
    if (onLanguageReset) {
      onLanguageReset();
    }
    rememberLanguage(tabCode);
    setActiveTab(tabCode);
  };


  const orderedTabs = orderBy(mainTabs, viewById(view).menuOrder, (t) => t.code)
    .filter(tab => tab.code !== 'admin')
    .filter(tab => !tab.trial || showInscriptionsPapyri);
  // Every page of the group is listed in every view (the project lead,
  // 2026-10-19: "Why not put everything in the Literature one as well?").
  // The collection switches still decide what a search covers and which
  // Reader tabs show; they no longer hide pages from this menu. The server
  // switch for the documents collection (trial above) is the one gate kept.
  // The members are replaced by one tab, placed where the first member stands
  // in the view's order.
  const thingsMembers = orderedTabs.filter(tab => tab.group === THINGS_GROUP.code);
  const shownTabs = [];
  orderedTabs.forEach((tab) => {
    if (tab.group !== THINGS_GROUP.code) shownTabs.push(tab);
    else if (tab === thingsMembers[0]) shownTabs.push({ ...THINGS_GROUP, isGroup: true, members: thingsMembers });
  });
  const thingsOpenPage = thingsMembers.some(t => t.code === pageType);
  const candidateTabs = shownTabs.filter(tab => !tab.more);
  const nFit = fitCount === null ? candidateTabs.length : Math.min(fitCount, candidateTabs.length);
  const rowTabs = candidateTabs.slice(0, nFit);
  // A group that falls into More is listed there by its members.
  const menuTabs = candidateTabs.slice(nFit)
    .flatMap(tab => (tab.isGroup ? tab.members : [tab]))
    .concat(shownTabs.filter(tab => tab.more));
  const tabsKey = candidateTabs.map(t => (t.isGroup ? t.members.map(m => m.code).join('+') : t.code)).join(',');
  useEffect(() => {
    refit();
    const row = mainRef.current;
    const ro = typeof ResizeObserver !== 'undefined' && row ? new ResizeObserver(refit) : null;
    if (ro && row) ro.observe(row);
    window.addEventListener('resize', refit);
    return () => { if (ro) ro.disconnect(); window.removeEventListener('resize', refit); };
  }, [refit, tabsKey, showCollections, mainRef, narrow]);

  // The admin-only menu returns early, AFTER every hook above, so the hooks
  // run in the same order on every render (the linter's rules-of-hooks).
  if (lockedToAdmin) {
    return (
      <nav className="bg-gray-50 border-b sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 py-2">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setPageType('admin')}
              aria-current="page"
              className="px-3 py-2 font-semibold text-sm border-b-2 border-red-700 text-red-700"
            >
              Admin Panel
            </button>
            <div className="text-xs text-gray-600 flex items-center gap-1">
              <span>Admin session active. Public tabs are restricted until</span>
              <button
                onClick={onAdminLogout}
                className="text-red-700 hover:text-red-800 underline"
              >
                logout
              </button>
              <span>.</span>
            </div>
          </div>
        </div>
      </nav>
    );
  }
  return (
    <nav className="bg-gray-50 border-b sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-3 sm:px-6">
        <div className="flex flex-row items-center">
          {/* The view switch first, then the Collections control as a smaller
              secondary button: the view sets the profile, the switches refine
              it. The divider stays before the page tabs. */}
          {showCollections && narrow && (
            <div ref={viewMenuRef} className="relative shrink-0 mr-1">
              <button
                type="button"
                aria-haspopup="menu"
                aria-expanded={viewMenuOpen}
                onClick={() => { setCollectionsOpen(false); setViewMenuOpen((o) => !o); }}
                className="px-2 py-2 text-xs border-b-2 border-transparent text-gray-700 hover:text-red-600 font-semibold whitespace-nowrap"
              >
                {viewById(view).label} <span aria-hidden="true">&#9662;</span>
              </button>
              {viewMenuOpen && (
                <div role="menu" aria-label="View" className="absolute left-0 mt-1 w-40 bg-white border border-gray-200 rounded shadow-lg py-1 z-50">
                  {VIEWS.map((v) => (
                    <button
                      key={v.id}
                      type="button"
                      role="menuitemradio"
                      aria-checked={view === v.id}
                      onClick={() => { setViewMenuOpen(false); setView(v.id); if (onViewChange) onViewChange(v.id); }}
                      className={`block w-full text-left px-3 py-1.5 text-sm hover:bg-red-50 ${
                        view === v.id ? 'text-red-700 font-semibold' : 'text-gray-700'
                      }`}
                    >
                      {v.label}
                    </button>
                  ))}
                  <div role="separator" className="my-1 border-t border-gray-200" />
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => { setViewMenuOpen(false); setCollectionsOpen(true); }}
                    className="block w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-red-50"
                  >
                    Collections&hellip;
                  </button>
                </div>
              )}
              <CollectionsControl hideButton open={collectionsOpen} onOpenChange={setCollectionsOpen} />
            </div>
          )}
          {showCollections && !narrow && (
            <div className="flex items-center gap-2 py-1 sm:py-0 sm:mr-3 sm:pr-3 sm:border-r sm:border-gray-200">
              <div role="group" aria-label="View" className="flex">
                {VIEWS.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    aria-pressed={view === v.id}
                    onClick={() => { setView(v.id); if (onViewChange) onViewChange(v.id); }}
                    className={`px-2 sm:px-3 py-2 sm:py-3 text-xs sm:text-sm border-b-2 whitespace-nowrap ${
                      view === v.id
                        ? 'border-red-700 text-red-700 font-semibold'
                        : 'border-transparent text-gray-500 hover:text-red-600 font-medium'
                    }`}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
              <CollectionsControl />
            </div>
          )}
          <div
            ref={mainRef}
            data-more={mainMore}
            className="scroll-hint relative flex overflow-x-auto scrollbar-hide flex-1 min-w-0"
          >
            {/* Hidden copy of every candidate tab, measured for the overflow. */}
            <div ref={measureRef} aria-hidden="true"
                 className="absolute left-0 top-0 flex invisible pointer-events-none whitespace-nowrap">
              {candidateTabs.map(tab => (
                <span key={tab.code} data-tab className="px-2 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm font-medium inline-block">
                  {tab.label}
                  {tab.isGroup && <span> &#9662;</span>}
                  {tab.beta && !narrow && <span className="ml-1 text-[9px] font-semibold uppercase tracking-wide">beta</span>}
                </span>
              ))}
              <span data-more-probe className="px-2 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm font-medium inline-block">More &#9662;</span>
            </div>
            {rowTabs.map(tab => (tab.isGroup ? (
              <div key={tab.code} ref={thingsMenu.ref} className="relative">
                <button
                  type="button"
                  onClick={thingsMenu.toggle}
                  aria-haspopup="menu"
                  aria-expanded={thingsMenu.open}
                  className={`px-2 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm border-b-2 whitespace-nowrap ${
                    thingsOpenPage
                      ? 'border-red-700 text-red-700 font-semibold'
                      : 'border-transparent text-gray-500 hover:text-red-600 font-medium'
                  }`}
                >
                  {tab.label} <span aria-hidden="true">&#9662;</span>
                </button>
                {thingsMenu.open && (
                  <div role="menu" data-testid="things-menu"
                       style={{ position: 'fixed', top: thingsMenu.pos ? thingsMenu.pos.top : 0, left: thingsMenu.pos ? thingsMenu.pos.left : 0 }}
                       className="w-64 bg-white border border-gray-200 rounded shadow-lg py-1 z-50">
                    {tab.members.map(member => (
                      <button
                        key={member.code}
                        role="menuitem"
                        type="button"
                        onClick={() => { thingsMenu.setOpen(false); setPageType(member.code); }}
                        className={`block w-full text-left px-3 py-1.5 text-sm hover:bg-red-50 ${
                          pageType === member.code ? 'text-red-700 font-semibold' : 'text-gray-700'
                        }`}
                      >
                        {member.label}
                        {member.beta && !narrow && (
                          <span className="ml-1 relative -top-1 inline-block leading-none text-[9px] font-semibold uppercase tracking-wide text-amber-700">
                            beta
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <button
                key={tab.code}
                onClick={() => setPageType(tab.code)}
                aria-current={pageType === tab.code ? 'page' : undefined}
                className={`px-2 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm border-b-2 whitespace-nowrap ${
                  pageType === tab.code
                    ? 'border-red-700 text-red-700 font-semibold'
                    : 'border-transparent text-gray-500 hover:text-red-600 font-medium'
                }`}
              >
                {tab.label}
                {/* Said plainly rather than in a tooltip. The Reader, Theme
                    Search and Tessa are all new and all still changing, and a
                    scholar deciding whether to cite something needs to know
                    that before they rely on it, not afterwards. */}
                {tab.beta && !narrow && (
                  <span className="ml-1 relative -top-1 inline-block leading-none text-[9px] font-semibold uppercase tracking-wide text-amber-700">
                    beta
                  </span>
                )}
              </button>
            )))}
            {showDownloads && setShowDownloads && (
              <button
                onClick={() => setShowDownloads(true)}
                className={`px-2 sm:px-4 py-2 sm:py-3 font-medium text-xs sm:text-sm border-b-2 whitespace-nowrap hidden sm:block ${
                  pageType === 'downloads' 
                    ? 'border-red-700 text-red-700' 
                    : 'border-transparent text-gray-500 hover:text-red-600'
                }`}
              >
                Downloads
              </button>
            )}
            <div ref={moreMenu.ref} className="relative">
              <button
                type="button"
                onClick={moreMenu.toggle}
                aria-haspopup="menu"
                aria-expanded={moreMenu.open}
                className={`px-2 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm border-b-2 whitespace-nowrap ${
                  menuTabs.some(t => t.code === pageType)
                    ? 'border-red-700 text-red-700 font-semibold'
                    : 'border-transparent text-gray-500 hover:text-red-600 font-medium'
                }`}
              >
                More <span aria-hidden="true">&#9662;</span>
              </button>
              {moreMenu.open && (
                <div role="menu" data-testid="more-menu"
                     style={{ position: 'fixed', top: moreMenu.pos ? moreMenu.pos.top : 0, left: moreMenu.pos ? moreMenu.pos.left : 0 }}
                     className="w-40 bg-white border border-gray-200 rounded shadow-lg py-1 z-50">
                  {menuTabs.map(tab => (
                    <button
                      key={tab.code}
                      role="menuitem"
                      type="button"
                      onClick={() => { moreMenu.setOpen(false); setPageType(tab.code); }}
                      className={`block w-full text-left px-3 py-1.5 text-sm hover:bg-red-50 ${
                        pageType === tab.code ? 'text-red-700 font-semibold' : 'text-gray-700'
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        
        {pageType === 'search' && (
          <div className="py-2 border-t">
            <div
              ref={langRef}
              data-more={langMore}
              className="scroll-hint flex overflow-x-auto scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0"
            >
              {languageTabs.map(tab => (
                <button
                  key={tab.code}
                  onClick={() => handleLanguageClick(tab.code)}
                  aria-current={activeTab === tab.code ? 'true' : undefined}
                  className={`px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-t whitespace-nowrap ${
                    activeTab === tab.code
                      ? 'bg-white text-red-700 border-t border-l border-r border-gray-200'
                      : 'text-gray-600 hover:text-red-600'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
              <StartLanguageControl
                languages={languageTabs.filter((t) => t.code !== 'cross')}
                className="ml-auto pl-3 shrink-0 self-center"
              />
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navigation;
