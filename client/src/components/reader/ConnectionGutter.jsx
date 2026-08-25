import { useEffect, useState } from 'react';

/**
 * The Reader's margin: two marks per line showing where the corpus has something
 * to say about it.
 *
 *   red    verbal parallels  (shared words, from the lexical index)
 *   violet similar passages  (shared content, from the scene index)
 *
 * Read together they tell a reader at a glance whether a line is echoed in
 * wording, in substance, or both. A line dark in both columns is the strongest
 * intertextual signal the interface can give without running a search.
 */
export default function ConnectionGutter({ work, units, onSelectLine }) {
  const [content, setContent] = useState({});   // ref -> 0..1
  const [verbal, setVerbal] = useState({});     // ref -> 0..1
  // Loading has to look different from "loaded, nothing here". Both used to
  // render at the faint end of the same opacity scale, so a reader opening a
  // text saw an empty margin and concluded the corpus held no connections to
  // it, when in fact the answer had not arrived. Content density is computed
  // against the whole corpus and takes about five seconds the first time a work
  // is opened, so this is the common case, not an edge one.
  const [loadingContent, setLoadingContent] = useState(true);
  const [loadingVerbal, setLoadingVerbal] = useState(true);

  useEffect(() => {
    if (!work) return;
    let cancelled = false;
    fetch(`/api/passages/density?work=${encodeURIComponent(work)}`)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled || !d.windows) return;
        // A window covers a span of lines; give each line in the span its density.
        const map = {};
        d.windows.forEach((w) => {
          const lo = lineNumber(w.ref_start);
          const hi = lineNumber(w.ref_end);
          if (lo == null) return;
          for (let n = lo; n <= (hi ?? lo); n += 1) {
            map[n] = Math.max(map[n] || 0, w.density || 0);
          }
        });
        setContent(map);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoadingContent(false); });
    return () => { cancelled = true; };
  }, [work]);

  useEffect(() => {
    if (!work) return;
    let cancelled = false;
    fetch(`/api/lexical-density?work=${encodeURIComponent(work)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (cancelled || !d?.lines) return;
        const map = {};
        d.lines.forEach((l) => {
          const n = lineNumber(l.ref);
          if (n != null) map[n] = l.density || 0;
        });
        setVerbal(map);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoadingVerbal(false); });
    return () => { cancelled = true; };
  }, [work]);

  const loading = loadingContent || loadingVerbal;

  return (
    <div
      className="w-9 shrink-0 border-r border-gray-200 bg-gray-50 pt-6"
      aria-hidden="true"
      title={loading
        ? 'Working out what the corpus connects to this text...'
        : 'Left: verbal parallels. Right: similar passages.'}
    >
      {units.map((u) => {
        const n = lineNumber(u.ref);
        const v = n != null ? verbal[n] || 0 : 0;
        const c = n != null ? content[n] || 0 : 0;
        return (
          <div
            key={u.ref}
            className="flex gap-[3px] justify-center items-center cursor-pointer"
            style={{ height: '1.75rem' }}
            onClick={() => onSelectLine?.(u)}
          >
            {/* While a stream is still loading its marks are hollow and
                pulsing, which reads as "not known yet" rather than as "nothing
                here". They fill in as each answer arrives, independently. */}
            <span
              className={`block w-[9px] h-[7px] rounded-sm ${
                loadingVerbal ? 'border border-red-300 animate-pulse' : 'bg-red-700'}`}
              style={loadingVerbal ? undefined : { opacity: 0.12 + v * 0.88 }}
            />
            <span
              className={`block w-[9px] h-[7px] rounded-sm ${
                loadingContent ? 'border animate-pulse' : ''}`}
              style={loadingContent
                ? { borderColor: '#c7bfe0' }
                : { backgroundColor: '#7c6bb0', opacity: 0.12 + c * 0.88 }}
            />
          </div>
        );
      })}
    </div>
  );
}

/** Last numeric component of a reference, which is the line or verse. */
function lineNumber(ref) {
  const nums = String(ref || '').match(/\d+/g);
  return nums ? parseInt(nums[nums.length - 1], 10) : null;
}
