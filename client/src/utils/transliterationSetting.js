import { useEffect, useState } from 'react';

// Whether the written paragraphs show a transliteration after each Greek or
// Hebrew word. On by default, kept in the browser, and every read and write
// is guarded because storage can be blocked.
const KEY = 'tesserae:transliterate';
const EVENT = 'tesserae:transliterate';

export function isOn() {
  try {
    return window.localStorage.getItem(KEY) !== 'off';
  } catch {
    return true;
  }
}

export function setOn(value) {
  try {
    window.localStorage.setItem(KEY, value ? 'on' : 'off');
  } catch {
    // storage blocked: the setting lasts until the page is closed
  }
  try {
    window.dispatchEvent(new CustomEvent(EVENT, { detail: !!value }));
  } catch {
    // no window events: nothing else to tell
  }
}

export function useTransliteration() {
  const [on, setState] = useState(isOn);
  useEffect(() => {
    const update = (e) => setState(typeof e?.detail === 'boolean' ? e.detail : isOn());
    window.addEventListener(EVENT, update);
    return () => window.removeEventListener(EVENT, update);
  }, []);
  return on;
}
