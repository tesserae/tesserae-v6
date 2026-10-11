/** Test helper: make window.matchMedia answer as a phone (max-width queries
 *  match) or not, and restore the original after. Returns a restore function
 *  and a `setPhone(bool)` that fires the change listeners. */
export function installPhone(initial = true) {
  const original = window.matchMedia;
  let phone = initial;
  const listeners = new Set();
  window.matchMedia = (query) => ({
    get matches() { return /max-width/.test(query) ? phone : false; },
    media: query,
    onchange: null,
    addListener: (fn) => listeners.add(fn),
    removeListener: (fn) => listeners.delete(fn),
    addEventListener: (_t, fn) => listeners.add(fn),
    removeEventListener: (_t, fn) => listeners.delete(fn),
    dispatchEvent: () => false,
  });
  return {
    restore: () => { window.matchMedia = original; },
    setPhone: (v) => { phone = v; listeners.forEach((fn) => fn({ matches: v })); },
  };
}
