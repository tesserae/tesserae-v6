/**
 * Collections: the one place that lists the source collections a visitor can
 * switch on and off, the named profiles that set them together, and which
 * Reader tabs and pages need which collection.
 *
 * Adding a collection (coins, say) means adding ONE entry to COLLECTIONS here
 * (set `available: true` once its data is live), adding its id to the
 * profiles that should include it, and, if it brings a Reader tab or a page,
 * one line in READER_TABS or PAGE_NEEDS. Nothing else in the app lists
 * collections.
 */

export const COLLECTIONS = [
  { id: 'literature', label: 'Literature', blurb: 'The literary texts and translations', available: true },
  { id: 'inscriptions', label: 'Inscriptions', blurb: 'Latin and Greek inscriptions', available: true },
  { id: 'papyri', label: 'Papyri', blurb: 'Documentary and literary papyri', available: true },
  { id: 'coins', label: 'Coins', blurb: 'Coin types and legends', available: false },
  { id: 'objects', label: 'Objects', blurb: 'Inscribed and decorated objects', available: false },
  { id: 'scholarship', label: 'Scholarship', blurb: 'Commentaries, articles and books', available: true },
];

export const COLLECTION_IDS = COLLECTIONS.map((c) => c.id);

/**
 * Profiles. `on` lists the collections the profile switches on (all others
 * go off). `layout` carries presentation hints a profile sets with them.
 * Literary reproduces the site as it was before Collections existed.
 */
export const PROFILES = [
  { id: 'literary', label: 'Literary', on: ['literature'], layout: { browseView: 'language' } },
  {
    id: 'historical', label: 'Historical',
    on: ['literature', 'inscriptions', 'papyri', 'scholarship'],
    layout: { browseView: 'language' },
  },
  {
    id: 'archaeological', label: 'Archaeological',
    on: ['literature', 'inscriptions', 'papyri', 'coins', 'objects'],
    layout: { browseView: 'documents' },
  },
  { id: 'everything', label: 'Everything', on: COLLECTION_IDS, layout: { browseView: 'language' } },
];

export const DEFAULT_PROFILE = 'literary';

export function profileById(id) {
  return PROFILES.find((p) => p.id === id) || null;
}

/** The on/off map a profile sets, for every collection id. */
export function profileSwitches(id) {
  const p = profileById(id) || profileById(DEFAULT_PROFILE);
  const on = {};
  COLLECTION_IDS.forEach((cid) => { on[cid] = p.on.includes(cid); });
  return on;
}

/** The profile whose switches equal `on`, or 'custom'. */
export function matchProfile(on) {
  const hit = PROFILES.find((p) => {
    const s = profileSwitches(p.id);
    return COLLECTION_IDS.every((cid) => !!on[cid] === s[cid]);
  });
  return hit ? hit.id : 'custom';
}

/**
 * Reader tabs and what each needs. `needs` is a list of collection ids of
 * which ANY must be on (empty means always shown). The Reader builds its tab
 * row from this, so a literary scholar never sees a tab for a collection
 * that is off.
 */
export const READER_TABS = [
  { id: 'similar', needs: [] },
  { id: 'verbal', needs: [] },
  { id: 'translation', needs: [] },
  { id: 'reuse', needs: [] },
  { id: 'scholarship', needs: ['scholarship'] },
];

/** Groups inside a tab that depend on a collection. */
export const REUSE_GROUPS = {
  documents: ['inscriptions', 'papyri'],
};

/** Pages (main-menu codes) and the collections that open them (any of). */
export const PAGE_NEEDS = {
  'inscriptions-papyri': ['inscriptions', 'papyri'],
  // Events (battles, sieges, treaties) gather passages, documents and scholarship.
  events: ['inscriptions', 'papyri', 'scholarship'],
};

/** The documents collection is served as one unit: either switch opens it. */
export const DOCUMENT_COLLECTIONS = ['inscriptions', 'papyri'];
