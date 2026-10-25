// The seven answers to "What are you trying to do?" on the Intertextual Search page's
// "Start here" panel: the feature's fixed name, then what it does (owner's
// review 2026-10-10: name the feature, then a brief description, smaller). Tessa answers "where do I start" with the same eight
// (backend/assistant/front_door.py holds the same labels and paths; a test
// checks the two agree). Change both together.
//
// The Reader lives at /read and the Inscriptions & Papyri page at
// /inscriptions-papyri (client/src/App.jsx, pathToPageType).

export const FRONT_DOOR_CHOICES = [
  {
    id: 'compare',
    label: 'Phrase Search',
    detail: 'the phrases two works share, ranked by how distinctive they are',
    href: '/?tab=parallel',
  },
  {
    id: 'phrase',
    label: 'Line Search',
    detail: 'every line in the corpus where a phrase or a pair of words occurs',
    href: '/?tab=line',
  },
  {
    id: 'rare',
    label: 'Rare Words',
    detail: 'the rare words and word pairs two works share',
    href: '/?tab=hapax',
  },
  {
    id: 'subject',
    label: 'Theme Search',
    detail: 'passages on a subject you describe in your own words: in one text, in two texts compared, or across the whole corpus',
    href: '/theme-search?scope=one',
  },
  {
    id: 'read',
    label: 'Reader',
    detail: 'read a text with its echoes, translations and scholarship beside each passage',
    href: '/read',
  },
  {
    id: 'mentions',
    label: 'People & Places',
    detail: 'every line where a person, place or god is named, in Latin, Greek and English',
    href: '/mentions',
  },
  {
    id: 'documents',
    label: 'Collections',
    detail: 'inscriptions, papyri, events, coins and museum objects, switched on from the top row',
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
