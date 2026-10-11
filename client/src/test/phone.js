/** Test helper: make window.matchMedia answer as a phone (max-width: 767px
 *  matches) and, separately, as a narrow screen (max-width: 639px, Tailwind's
 *  `sm` break, where the main menu goes to one row). Returns `restore`,
 *  `setPhone(bool)` and `setNarrow(bool)`, which fire the change listeners.
 *  `narrow` defaults to false so existing phone tests keep the wide menu. */
export function installPhone(initial = true, narrowInitial = false) {
  const original = window.matchMedia;
  let phone = initial;
  let narrow = narrowInitial;
  const listeners = new Set();
  window.matchMedia = (query) => ({
    get matches() {
      if (/639px/.test(query)) return narrow;
      return /max-width/.test(query) ? phone : false;
    },
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
    setNarrow: (v) => { narrow = v; listeners.forEach((fn) => fn({ matches: v })); },
  };
}
