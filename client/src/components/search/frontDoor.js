// The six answers to "What are you trying to do?" on the Search page's
// "Start here" panel. Tessa answers "where do I start" with the same six
// (backend/assistant/front_door.py holds the same labels and paths; a test
// checks the two agree). Change both together.
//
// The Reader lives at /read and the Inscriptions & Papyri page at
// /inscriptions-papyri (client/src/App.jsx, pathToPageType).

export const FRONT_DOOR_CHOICES = [
  {
    id: 'phrase',
    label: 'Find where a phrase or a pair of words occurs',
    detail: 'Every line in the corpus that carries the words, with the lines that quote the phrase first.',
    href: '/?tab=line',
  },
  {
    id: 'compare',
    label: 'Compare two works for shared language',
    detail: 'Every pair of lines the two works share, scored.',
    href: '/?tab=parallel',
  },
  {
    id: 'rare',
    label: 'Find the rare words two works share',
    detail: 'Words and word pairs that occur in few other works.',
    href: '/?tab=hapax',
  },
  {
    id: 'subject',
    label: 'Find passages about a subject, in any words',
    detail: 'Describe a scene or an idea in English and get the passages, across languages.',
    href: '/theme-search',
  },
  {
    id: 'read',
    label: 'Read a text and see what each passage echoes',
    detail: 'The Reader shows the connections of every passage beside the text.',
    href: '/read',
  },
  {
    id: 'documents',
    label: 'Search inscriptions, papyri, events and coins',
    detail: 'The historical collections, searched with the literature or on their own.',
    href: '/inscriptions-papyri?profile=everything',
  },
];

export const FRONT_DOOR_KEY = 'tesserae_front_door';
export const FRONT_DOOR_OPEN_EVENT = 'tesserae:open-start-here';

/** True when the panel should open by itself: nothing remembered, and the
 *  address carries no search of its own. A storage error (private window)
 *  counts as "seen". */
export function frontDoorUnseen() {
  try {
    return !window.localStorage.getItem(FRONT_DOOR_KEY);
  } catch {
    return false;
  }
}

export function markFrontDoorSeen() {
  try {
    window.localStorage.setItem(FRONT_DOOR_KEY, 'seen');
  } catch {
    // nothing to remember it in
  }
}

export function addressHasQuery() {
  try {
    return window.location.search.length > 1;
  } catch {
    return false;
  }
}
