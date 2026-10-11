/**
 * Collections state: the visitor's saved choice (localStorage), session
 * overrides from the URL, and the old trial switches mapped onto them.
 *
 * Effective state = saved choice, then URL overrides for this visit
 * (?profile=, ?collections=), then the legacy switches (?documents=1 turns
 * Inscriptions and Papyri on, ?scholarship=1 turns Scholarship on). Overrides
 * last for the visit (sessionStorage) and never overwrite the saved choice.
 */
import {
  COLLECTION_IDS, DEFAULT_PROFILE, profileById, profileSwitches, matchProfile,
} from './collectionsConfig';

export const STORAGE_KEY = 'tesserae_collections';
const OVERRIDE_KEY = 'tesserae_collections_override';
// The old trial switches' own session keys (kept: other code and tests read them).
const LEGACY = { documents_trial: ['inscriptions', 'papyri'], scholarship_tab: ['scholarship'] };

const listeners = new Set();
let last = null;
let lastKey = null;

function readJson(store, key) {
  try { return JSON.parse(store.getItem(key)); } catch { return null; }
}
function writeJson(store, key, value) {
  try { store.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ }
}
function safe(getStore) {
  try { return getStore(); } catch { return null; }
}

/** Record this page load's URL switches for the rest of the visit. */
export function captureUrlOverrides() {
  const ss = safe(() => window.sessionStorage);
  if (!ss) return;
  const params = new URLSearchParams(window.location.search);
  if (params.get('documents') === '1') ss.setItem('tesserae_documents_trial', '1');
  if (params.get('scholarship') === '1') ss.setItem('tesserae_scholarship_tab', '1');
  const profile = params.get('profile');
  if (profile && profileById(profile)) {
    writeJson(ss, OVERRIDE_KEY, { on: profileSwitches(profile) });
  }
  const list = params.get('collections');
  if (list !== null) {
    const ids = list.split(',').map((s) => s.trim());
    const on = {};
    COLLECTION_IDS.forEach((id) => { on[id] = ids.includes(id); });
    writeJson(ss, OVERRIDE_KEY, { on });
  }
}

// The URL is parsed once per distinct query string, not on every snapshot
// read (useSyncExternalStore calls getSnapshot often, and the capture writes
// to sessionStorage).
let lastSearch = null;
function captureOnce() {
  const search = safe(() => window.location.search);
  const ss = safe(() => window.sessionStorage);
  if (search === lastSearch && ss) {
    // Re-capture only if the session keys the URL calls for have gone
    // (cleared storage), so a cleared session still honours the link.
    const params = new URLSearchParams(search || '');
    const missing = (params.get('documents') === '1' && !ss.getItem('tesserae_documents_trial'))
      || (params.get('scholarship') === '1' && !ss.getItem('tesserae_scholarship_tab'))
      || ((params.get('profile') || params.get('collections') !== null) && !ss.getItem(OVERRIDE_KEY));
    if (!missing) return;
  }
  lastSearch = search;
  captureUrlOverrides();
}

function compute() {
  captureOnce();
  const ls = safe(() => window.localStorage);
  const ss = safe(() => window.sessionStorage);
  const saved = ls ? readJson(ls, STORAGE_KEY) : null;
  const base = profileSwitches(saved?.profile && profileById(saved.profile) ? saved.profile : DEFAULT_PROFILE);
  const on = { ...base };
  if (saved?.on && typeof saved.on === 'object') {
    COLLECTION_IDS.forEach((id) => { if (typeof saved.on[id] === 'boolean') on[id] = saved.on[id]; });
  }
  const override = ss ? readJson(ss, OVERRIDE_KEY) : null;
  if (override?.on) {
    COLLECTION_IDS.forEach((id) => { if (typeof override.on[id] === 'boolean') on[id] = override.on[id]; });
  }
  if (ss) {
    Object.entries(LEGACY).forEach(([key, ids]) => {
      if (ss.getItem('tesserae_' + key) === '1') ids.forEach((id) => { on[id] = true; });
    });
  }
  const profile = matchProfile(on);
  const layout = (profileById(profile) || profileById(DEFAULT_PROFILE)).layout;
  return { on, profile, layout };
}

/** Snapshot with a stable identity while nothing changed (for useSyncExternalStore). */
// True once a visitor has chosen collections (saved or for this visit) or
// arrived through a trial link. Until then the public site shows no
// Collections control, so nothing changes for today's visitors (2026-10-09).
export function hasExplicitChoice() {
  const ls = safe(() => window.localStorage);
  const ss = safe(() => window.sessionStorage);
  if (ls && ls.getItem(STORAGE_KEY)) return true;
  if (ss && (ss.getItem(OVERRIDE_KEY) || ss.getItem('tesserae_documents_trial') || ss.getItem('tesserae_scholarship_tab'))) return true;
  return false;
}

export function getSnapshot() {
  const next = compute();
  const key = JSON.stringify(next);
  if (key !== lastKey) { lastKey = key; last = next; }
  return last;
}

export function subscribe(fn) {
  listeners.add(fn);
  const onStorage = (e) => { if (!e.key || e.key === STORAGE_KEY) fn(); };
  window.addEventListener('storage', onStorage);
  return () => { listeners.delete(fn); window.removeEventListener('storage', onStorage); };
}

function save(on) {
  const ls = safe(() => window.localStorage);
  if (ls) writeJson(ls, STORAGE_KEY, { profile: matchProfile(on), on });
  // A deliberate choice replaces this visit's URL overrides and legacy switches.
  const ss = safe(() => window.sessionStorage);
  if (ss) {
    ss.removeItem(OVERRIDE_KEY);
    Object.keys(LEGACY).forEach((k) => ss.removeItem('tesserae_' + k));
  }
  listeners.forEach((fn) => fn());
}

export function setCollection(id, value) {
  if (!COLLECTION_IDS.includes(id)) return;
  if (id === 'literature') return;  // always on (collectionsConfig: fixed)
  save({ ...getSnapshot().on, [id]: !!value });
}

export function setProfile(id) {
  if (!profileById(id)) return;
  save(profileSwitches(id));
}
