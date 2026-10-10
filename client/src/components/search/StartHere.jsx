import { useState, useEffect, useRef } from 'react';
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
      className="bg-white border border-gray-200 rounded-lg shadow-sm p-4 sm:p-6 mb-6"
    >
      <h2 id="start-here-heading" className="text-lg font-semibold text-gray-900 mb-3">
        What are you trying to do?
      </h2>
      <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {FRONT_DOOR_CHOICES.map((choice) => (
          <li key={choice.id}>
            <a
              href={choice.href}
              onClick={(e) => choose(e, choice)}
              className="block h-full rounded border border-gray-200 px-3 py-2 hover:bg-red-50 hover:border-red-200"
            >
              <span className="block font-bold text-gray-800">{choice.label}</span>
              <span className="block text-sm text-gray-500">{choice.detail}</span>
            </a>
          </li>
        ))}
      </ul>
      <div className="mt-3">
        <button
          type="button"
          onClick={close}
          className="text-sm text-gray-500 hover:text-red-700 hover:underline"
        >
          Skip this
        </button>
      </div>
    </section>
  );
}
