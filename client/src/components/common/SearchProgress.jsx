import { useEffect, useState } from 'react';
import { formatRunningTime } from '../../utils/formatting';

/**
 * What a page shows while a search runs: a spinner, the one-line account of
 * what is happening, and a clock in whole seconds. Theme Search and Search
 * One Text showed the line alone, and a reader could not tell whether
 * anything was still happening (the owner, 2026-10-12: "No indication here
 * of ongoing work, no ongoing search or progress indicator.").
 */
export default function SearchProgress({ text, className = 'mt-6' }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className={`${className} flex items-center gap-3 text-sm text-gray-600`} role="status" data-testid="search-progress">
      <span className="w-5 h-5 shrink-0 border-2 border-gray-200 border-t-red-700 rounded-full animate-spin" aria-hidden="true" />
      <span>{text}</span>
      {seconds > 0 && <span className="tabular-nums text-gray-500" data-testid="search-progress-clock">{formatRunningTime(seconds)}</span>}
    </div>
  );
}
