import { useEffect, useId, useRef, useState } from 'react';

/**
 * A small badge that carries its own explanation, instead of a native
 * `title` tooltip.
 *
 * Owner's review of the result card (2026-10-08): a `title` attribute shows
 * nothing for a second or two, gives no sign anything is there, and does
 * nothing at all on a phone. InfoBadge opens its popover at once (no
 * meaningful delay) on hover, on keyboard focus, and on tap, which toggles
 * it; Escape or a tap outside closes it. Every badge carries the same small
 * info mark and a "help" cursor, so the explanation is visible before
 * anyone hovers.
 *
 * @param {ReactNode} children the badge's visible label.
 * @param {string} [heading] a bold one-line heading for the popover.
 * @param {ReactNode} [explanation] the popover body. A string is split on
 *   blank lines into separate paragraphs; any other node is used as given
 *   (for a list, or other structured content).
 * @param {ReactNode} [footer] one final, muted line, e.g. "Site ID: ...".
 * @param {string} [className] classes for the badge's own look (background,
 *   text colour, size) -- InfoBadge adds only the affordance and layout.
 * @param {string} [label] an accessible name for the trigger when the
 *   visible children are not already a readable label (defaults to none,
 *   which lets the children speak for themselves).
 */
export default function InfoBadge({ children, heading, explanation, footer, className = '', label }) {
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [clicked, setClicked] = useState(false);
  const [position, setPosition] = useState('bottom');
  const [align, setAlign] = useState('left');
  const wrapRef = useRef(null);
  const triggerRef = useRef(null);
  // Escape returns focus to the trigger for accessibility, but a plain
  // `.focus()` call fires a real focus event that would otherwise re-open
  // the popover it just closed; this flag tells the next onFocus to skip.
  const suppressFocusRef = useRef(false);
  const popoverId = useId();

  const open = hovered || focused || clicked;

  // Keeps the popover inside the viewport: flips above the badge when there
  // is not enough room below, and right-aligns when the 22rem box would run
  // off the right edge (the layout a phone-width card forces).
  useEffect(() => {
    if (!open) return undefined;
    const trigger = triggerRef.current;
    if (trigger && typeof window !== 'undefined') {
      const rect = trigger.getBoundingClientRect();
      const POPOVER_H = 180;
      const POPOVER_W = 352; // 22rem at the default 16px root
      setPosition(
        rect.bottom + POPOVER_H > window.innerHeight && rect.top > POPOVER_H ? 'top' : 'bottom'
      );
      setAlign(rect.left + POPOVER_W > window.innerWidth ? 'right' : 'left');
    }
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setClicked(false);
        setHovered(false);
        setFocused(false);
        suppressFocusRef.current = true;
        triggerRef.current?.focus();
      }
    };
    const onDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setClicked(false);
      }
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [open]);

  const paragraphs = typeof explanation === 'string'
    ? explanation.split(/\n\s*\n/).filter(Boolean)
    : null;

  return (
    <span
      ref={wrapRef}
      className="relative inline-block"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        ref={triggerRef}
        type="button"
        aria-describedby={popoverId}
        aria-expanded={open}
        aria-label={label}
        onFocus={() => {
          if (suppressFocusRef.current) { suppressFocusRef.current = false; return; }
          setFocused(true);
        }}
        onBlur={() => setFocused(false)}
        onClick={() => setClicked((v) => !v)}
        className={`cursor-help inline-flex items-center gap-0.5 text-xs px-2 py-0.5 rounded ${className}`}
      >
        {children}
        <svg aria-hidden="true" viewBox="0 0 16 16" width="10" height="10" className="shrink-0 opacity-70" fill="none">
          <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
          <rect x="7.25" y="7" width="1.5" height="5" rx="0.5" fill="currentColor" />
          <circle cx="8" cy="4.6" r="1" fill="currentColor" />
        </svg>
      </button>
      {open && (
        <div
          id={popoverId}
          role="tooltip"
          className={`absolute z-50 w-[22rem] max-w-[90vw] rounded border border-gray-300
                     bg-white shadow-lg p-3 text-left text-sm normal-case font-normal
                     ${position === 'top' ? 'bottom-full mb-1' : 'top-full mt-1'}
                     ${align === 'right' ? 'right-0' : 'left-0'}`}
        >
          {heading && <p className="font-semibold text-gray-900 mb-1 leading-snug">{heading}</p>}
          {paragraphs
            ? paragraphs.map((p, idx) => (
                <p key={idx} className="text-gray-700 leading-snug mb-1 last:mb-0">{p}</p>
              ))
            : explanation != null && <div className="text-gray-700 leading-snug">{explanation}</div>}
          {footer && (
            <p className="text-[11px] text-gray-500 mt-2 pt-1.5 border-t border-gray-100">{footer}</p>
          )}
        </div>
      )}
    </span>
  );
}
