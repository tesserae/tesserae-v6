/**
 * The page and address a visitor left the site on, remembered so that a bare
 * visit to the site opens there again (2026-10-19). Kept in the browser's own
 * storage (localStorage) only, never sent to the server. Storage can be missing
 * or blocked, so every read and write is guarded.
 */
import { isKnownPath } from '../hooks/routePaths';

const KEY = 'tesserae_last_place';
const NEVER = ['/admin', '/downloads', '/privacy', '/text-credits'];

/** True for an address worth coming back to: a page the site knows, not an admin or legal page. */
export function isRememberedPath(path) {
  if (!path || NEVER.includes(path)) return false;
  return isKnownPath(path);
}

/** Record the current address when it is a page worth coming back to. */
export function rememberLastPlace() {
  try {
    const { pathname, search } = window.location;
    if (isRememberedPath(pathname)) window.localStorage.setItem(KEY, pathname + search);
  } catch { /* storage blocked: nothing to remember */ }
}

/** The remembered address, or null. */
export function readLastPlace() {
  try {
    const v = window.localStorage.getItem(KEY);
    if (v && v.startsWith('/') && !v.startsWith('//') && isRememberedPath(v.split(/[?#]/)[0])) return v;
    return null;
  } catch { return null; }
}
