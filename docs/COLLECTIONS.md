# Collections

One control where a visitor turns source collections on and off and picks a
profile. It replaces the separate trial switches (`?documents=1`,
`?scholarship=1`), which keep working.

## Collections

| id | Label | Status |
|---|---|---|
| `literature` | Literature | live |
| `inscriptions` | Inscriptions | live (served with papyri as the documents collection) |
| `papyri` | Papyri | live |
| `coins` | Coins | coming (shown disabled) |
| `objects` | Objects | coming (shown disabled) |
| `scholarship` | Scholarship | live |

The server still gates the documents data with `TESSERAE_DOCUMENTS=1`
(`documents_enabled` in `/api/languages`). The client switch only decides
whether the site shows what the server can send; both must agree for the
Inscriptions & Papyri page, its menu entry, the Browse Corpus documents view
and the Line Search documents control to appear. The Reader's Scholarship tab
also needs scholarship installed for the text's language, as before.

## Profiles

| Profile | On |
|---|---|
| Literary (default) | literature |
| Historical | literature, inscriptions, papyri, scholarship |
| Archaeological | literature, inscriptions, papyri, coins, objects; Browse Corpus opens on documents |
| Everything | all |

Literary reproduces the site as it was before Collections. When the switches
match no profile the control reads "Custom".

## Where the control lives

A "Collections: <profile>" button at the right of the main menu, on every
page, opening a panel with the four profiles and one checkbox per collection.
(The language tabs appear only on Search, so they are not a home for a
site-wide control.)

## Persistence and URL switches

- Saved choice: `localStorage["tesserae_collections"]`, `{profile, on}`.
- Visit overrides, in `sessionStorage`, never written to the saved choice:
  - `?documents=1` turns inscriptions and papyri on (old session key
    `tesserae_documents_trial` is still written and read);
  - `?scholarship=1` turns scholarship on (`tesserae_scholarship_tab`);
  - `?profile=<id>` applies a profile; `?collections=a,b` sets exactly those on.
- Precedence: saved choice, then `?profile=` / `?collections=`, then the two
  legacy switches. A deliberate change in the panel clears the visit
  overrides.
- The app captures the URL switches once at first load (`App.jsx`), and the
  store re-reads them on every call, so a link that sets one holds for the
  visit whatever page is opened next.

## How code uses it

- `client/src/collections/collectionsConfig.js`: the only list of
  collections, profiles, Reader tabs and pages.
- `client/src/collections/collectionsStore.js`: state, persistence, URL
  mapping.
- `client/src/hooks/useCollections.js`: `isOn(id)`, `anyOn([ids])`,
  `profile`, `layout`, `setProfile`, `setCollection`. `useDocumentsTrial()`
  remains as a wrapper meaning "inscriptions or papyri is on".
- A page declares what it needs in `PAGE_NEEDS` (menu code to collection ids,
  any of). The Reader's tabs come from `READER_TABS`, each with the
  collections it needs; a tab with none is always shown. Groups inside a tab
  (the Reuse tab's "In inscriptions and papyri") use `REUSE_GROUPS`.
- A page or focus view can carry overrides without saving them:
  `<CollectionsScope overrides={{ scholarship: false }}>`.

## Adding a collection (for example coins)

1. Add one entry to `COLLECTIONS` and set `available: true` when its data is live.
2. Add its id to the profiles that include it.
3. If it brings a Reader tab or a page, add one line to `READER_TABS` or
   `PAGE_NEEDS`, with the tab or page component itself.
