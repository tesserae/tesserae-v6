import { useState, useEffect, useRef } from 'react';
import useCollections from '../../hooks/useCollections';
import { viewById, orderBy } from '../../collections/collectionsConfig';
import {
  FRONT_DOOR_CHOICES, FRONT_DOOR_OPEN_EVENT,
  frontDoorUnseen, markFrontDoorSeen, addressHasQuery,
} from './frontDoor';

/**
 * "What are you trying to do?": seven answers that lead to the right search.
 * Shown to a first-time visitor on the Intertextual Search page, never when the address
 * already carries a search, and brought back by the header's "Start here"
 * link. Once hidden it takes no space.
 *
 * Layout (2026-11-11, the owner found the plain list "boring and unappealing"):
 * each answer is a tile with the search's name on its own line and the
 * description under it, in a grid on a warm band, so the seven choices read as
 * a set of doors rather than a paragraph. Nothing about the behavior changed:
 * the same links, the same onChoose and Skip handling, the same order and
 * labels per collection view.
 *
 * Props
 *   onChoose(choice)  optional. Called with the chosen answer; when it is
 *                     given the click is handled inside the app (no page
 *                     reload). Without it the link is followed normally.
 *   onDismiss()       optional. Called when the panel closes.
 *   forceOpen         true when the app opened it from another page.
 *   suppressed        true when the page was opened with a search in the
 *                     address (decided once, at load, by the app). When left
 *                     out, the address is read when the panel mounts.
 */
export default function StartHere({ onChoose, onDismiss, forceOpen = false, suppressed }) {
  const [open, setOpen] = useState(() => {
    if (forceOpen) return true;
    const hidden = suppressed === undefined ? addressHasQuery() : suppressed;
    return !hidden && frontDoorUnseen();
  });
  const ref = useRef(null);
  const { view } = useCollections();
  const viewData = viewById(view);
  const choices = orderBy(FRONT_DOOR_CHOICES, viewData.startHereOrder, (c) => c.id);

  useEffect(() => {
    const show = () => {
      setOpen(true);
      setTimeout(() => {
        const el = ref.current;
        if (!el) return;
        // The top bars are sticky (the page tabs and the language row, about
        // 150 px together), so scrolling the panel to the top of the window
        // put its heading and first answers under them (the project lead,
        // 2026-10-19: "a weird half position ... cut off"). Scroll to just
        // below the bars instead, measured, with the plain scroll as the
        // fallback where window.scrollTo is missing (jsdom).
        const nav = document.querySelector('nav.sticky');
        const bars = nav ? nav.getBoundingClientRect().height : 0;
        const top = el.getBoundingClientRect().top + window.scrollY - bars - 12;
        if (typeof window.scrollTo === 'function') window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
        else if (el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 0);
    };
    window.addEventListener(FRONT_DOOR_OPEN_EVENT, show);
    return () => window.removeEventListener(FRONT_DOOR_OPEN_EVENT, show);
  }, []);

  useEffect(() => {
    if (forceOpen) setOpen(true);
  }, [forceOpen]);

  if (!open) return null;

  const close = () => {
    markFrontDoorSeen();
    setOpen(false);
    if (onDismiss) onDismiss();
  };

  const choose = (event, choice) => {
    const plain = !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button > 0);
    close();
    if (onChoose && plain) {
      event.preventDefault();
      onChoose(choice);
    }
  };

  return (
    <section
      ref={ref}
      aria-labelledby="start-here-heading"
      className="rounded-lg border border-red-100 bg-gradient-to-b from-red-50/70 to-white shadow-sm px-4 sm:px-5 pt-3 pb-4 mb-4"
    >
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <div>
          <h2 id="start-here-heading" className="text-base font-semibold text-gray-900">
            What are you trying to do?
          </h2>
          <p className="text-xs text-gray-600 mt-0.5">Pick one and the right search opens, set up for you.</p>
        </div>
        <button
          type="button"
          onClick={close}
          className="shrink-0 text-xs text-gray-500 border border-gray-300 rounded px-2 py-0.5 bg-white hover:text-red-700 hover:border-red-300"
        >
          Skip
        </button>
      </div>
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {choices.map((choice) => (
          <li key={choice.id} className="h-full">
            <a
              href={choice.href}
              onClick={(e) => choose(e, choice)}
              className="group flex h-full flex-col rounded-md border border-gray-200 bg-white px-3 py-2.5 hover:border-red-300 hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
            >
              <span className="text-sm font-semibold text-red-700 group-hover:underline">
                {viewData.startHereLabels?.[choice.id] || choice.label}
              </span>
              <span className="mt-0.5 text-[13px] leading-snug text-gray-600">{choice.detail}</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
