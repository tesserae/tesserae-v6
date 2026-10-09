import { useEffect, useId, useRef, useState } from 'react';

const HOVER_OPEN_DELAY = 150;

/**
 * A small badge that carries its own explanation, instead of a native
 * `title` tooltip.
 *
 * Second pass (result card tidy, 2026-10-08): the first pass carried a
 * visible "i" mark and a help cursor on every badge, which read as
 * clickable when it only opens on hover. Following the Nielsen Norman
 * Group's tooltip guidance and Carbon/Inclusive Components' hover-vs-toggle
 * distinction, a hover popover gets no icon at all; the badge itself is the
 * trigger. It opens after a short delay on hover (long enough that moving
 * the pointer across the card does not flicker every badge it crosses), at
 * once on keyboard focus, and at once on tap, which toggles it. It stays
 * open while the pointer is over the badge or the popover, and closes on
 * leaving both, on Escape, or on a tap outside (WCAG 2.1 SC 1.4.13).
 *
 * @param {ReactNode} children the badge's visible label.
 * @param {ReactNode} [explanation] the popover body: one short sentence. A
 *   string is split on blank lines into separate paragraphs; any other node
 *   is used as given.
 * @param {ReactNode} [extra] optional compact content shown after the
 *   explanation and before the "More" link (e.g. the refrain's own line
 *   lists, which are the information the badge stands for).
 * @param {{anchor: string, onClick: () => void}} [more] a "More" link to
 *   the matching Help section anchor.
 * @param {ReactNode} [footer] one final, muted line, e.g. "Site ID: ...".
 * @param {string} [className] classes for the badge's own look (background,
 *   text color, size) -- InfoBadge adds only the affordance and layout.
 * @param {string} [label] an accessible name for the trigger when the
 *   visible children are not already a readable label (defaults to none,
 *   which lets the children speak for themselves).
 */
export default function InfoBadge({ children, explanation, extra, more, footer, className = '', label }) {
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [clicked, setClicked] = useState(false);
  const [position, setPosition] = useState('bottom');
  const [align, setAlign] = useState('left');
  const wrapRef = useRef(null);
  const triggerRef = useRef(null);
  const hoverTimerRef = useRef(null);
  // Escape returns focus to the trigger for accessibility, but a plain
  // `.focus()` call fires a real focus event that would otherwise re-open
  // the popover it just closed; this flag tells the next onFocus to skip.
  const suppressFocusRef = useRef(false);
  const popoverId = useId();

  const open = hovered || focused || clicked;

  const clearHoverTimer = () => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  };

  const onMouseEnter = () => {
    clearHoverTimer();
    hoverTimerRef.current = setTimeout(() => setHovered(true), HOVER_OPEN_DELAY);
  };

  const onMouseLeave = () => {
    clearHoverTimer();
    setHovered(false);
  };

  useEffect(() => clearHoverTimer, []);

  // Keeps the popover inside the viewport: flips above the badge when there
  // is not enough room below, and right-aligns when the 22rem box would run
  // off the right edge (the layout a phone-width card forces).
  useEffect(() => {
    if (!open) return undefined;
    const trigger = triggerRef.current;
    if (trigger && typeof window !== 'undefined') {
      const rect = trigger.getBoundingClientRect();
      const POPOVER_H = 160;
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
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
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
        className={`inline-flex items-center text-xs px-2 py-0.5 rounded ${className}`}
      >
        {children}
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
          {paragraphs
            ? paragraphs.map((p, idx) => (
                <p key={idx} className="text-gray-700 leading-snug mb-1 last:mb-0">{p}</p>
              ))
            : explanation != null && <div className="text-gray-700 leading-snug">{explanation}</div>}
          {extra && <div className="text-gray-600 text-xs leading-snug mt-1">{extra}</div>}
          {more && (
            <p className="mt-1">
              <button
                type="button"
                onClick={more.onClick}
                className="text-xs text-amber-700 hover:text-amber-900 underline"
              >
                More
              </button>
            </p>
          )}
          {footer && (
            <p className="text-[11px] text-gray-500 mt-2 pt-1.5 border-t border-gray-100">{footer}</p>
          )}
        </div>
      )}
    </span>
  );
}
