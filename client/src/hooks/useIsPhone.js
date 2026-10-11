import { useEffect, useState } from 'react';

const QUERY = '(max-width: 767px)';

function read() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return !!window.matchMedia(QUERY)?.matches;
}

/** True on a phone: a viewport narrower than 768 pixels (Tailwind's `md`).
 *  False during server rendering or where matchMedia does not exist. */
export function useIsPhone() {
  const [phone, setPhone] = useState(read);
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const mq = window.matchMedia(QUERY);
    if (!mq) return undefined;
    const update = () => setPhone(!!mq.matches);
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
  }, []);
  return phone;
}

export default useIsPhone;
