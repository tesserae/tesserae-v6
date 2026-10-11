import { useState, useEffect, useRef } from 'react';
import useCollections from '../../hooks/useCollections';
import { viewById, orderBy } from '../../collections/collectionsConfig';
import {
  FRONT_DOOR_CHOICES, FRONT_DOOR_OPEN_EVENT,
  frontDoorUnseen, markFrontDoorSeen, addressHasQuery,
} from './frontDoor';

/**
 * "What are you trying to do?": six answers that lead to the right search.
 * Shown to a first-time visitor on the Search page, never when the address
 * already carries a search, and brought back by the header's "Start here"
 * link. Once hidden it takes no space.
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
        if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
      className="bg-white border border-gray-200 rounded-lg shadow-sm px-4 py-3 mb-4"
    >
      <div className="flex items-baseline justify-between gap-3 mb-1.5">
        <h2 id="start-here-heading" className="text-sm font-semibold text-gray-700">
          What are you trying to do?
        </h2>
        <button
          type="button"
          onClick={close}
          className="text-xs text-gray-500 hover:text-red-700 hover:underline"
        >
          Skip
        </button>
      </div>
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-0.5">
        {choices.map((choice) => (
          <li key={choice.id}>
            <a
              href={choice.href}
              onClick={(e) => choose(e, choice)}
              className="block text-sm py-0.5 text-gray-600 hover:text-red-700"
            >
              <span className="font-semibold text-gray-800">{viewData.startHereLabels?.[choice.id] || choice.label}:</span>{' '}
              <span>{choice.detail}</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
