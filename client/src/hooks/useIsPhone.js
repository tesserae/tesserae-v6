import { useEffect, useState } from 'react';

const PHONE_QUERY = '(max-width: 767px)';
const NARROW_QUERY = '(max-width: 639px)';

function read(query) {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return !!window.matchMedia(query)?.matches;
}

function useMedia(query) {
  const [matches, setMatches] = useState(() => read(query));
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const mq = window.matchMedia(query);
    if (!mq) return undefined;
    const update = () => setMatches(!!mq.matches);
    update();
    if (mq.addEventListener) {
      mq.addEventListener('change', update);
      return () => mq.removeEventListener('change', update);
    }
    if (mq.addListener) {
      mq.addListener(update);
      return () => mq.removeListener(update);
    }
    return undefined;
  }, [query]);
  return matches;
}

/** True on a phone: a viewport narrower than 768 pixels (Tailwind's `md`).
 *  False during server rendering or where matchMedia does not exist. */
export function useIsPhone() {
  return useMedia(PHONE_QUERY);
}

/** True below Tailwind's `sm` (640 pixels), where the main menu fits on one row. */
export function useIsNarrow() {
  return useMedia(NARROW_QUERY);
}

export default useIsPhone;
