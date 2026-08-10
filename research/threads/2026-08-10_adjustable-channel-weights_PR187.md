# Thread dossier — User-adjustable channel weights & channel on/off (PR #187)

**Status:** DRAFT PR, not deployed. Verified default-equivalent. Awaiting NC's decision to preview.
**Last updated:** 2026-08-10
**Owner:** Neil Coffee / Claude
**One-line:** Let users tune each fusion channel's weight and switch channels fully on/off from the search UI (and via the API), without changing default behavior for anyone who doesn't touch the controls.

---

## 1. Genealogy — how this arose and the reasoning

**Origin (user desiderata, surfaced during the Help-page revision, early Aug 2026).**
While rewriting the Help page, NC recalled that users had asked to *adjust the search* — and, specifically, that **one user wanted results from just (some form of) sound + syntax**, i.e. the ability to turn channels *off*, not merely reweight them. NC asked how complicated user-adjustable weights would be, and whether we'd also need on/off switches.

**Feasibility finding.** The core scorer was already parameterized: `fuse_results(channel_results, weights=None, …)` in `backend/fusion.py` falls back to `get_weight_profile(language=…)` only when `weights is None`. So *passing* a weights dict already overrides the profile — the hard part (threading a per-request weight set through scoring) was effectively free. This made the feature "moderate effort," mostly plumbing + UI, which is why we prototyped it.

**Two distinct controls — and why they are not the same thing.**
- **Weight** tunes how much a channel *contributes* to the fused score.
- **On/off** *excludes a channel from running at all.*
- Key insight that shaped the design: **weight = 0 is not the same as "off."** A channel at weight 0 still *runs*, and can still pull a pair into the results via the convergence bonus (multi-channel agreement). A user who says "I only want sound + syntax" needs the other channels to *not run*, not to run at zero. Hence a true on/off is a separate mechanism from a 0 weight.

**Why send the OFF list, not the ON list.** The request carries `disabled_channels` (what the user turned off), which the backend converts into an `enabled_channels` keep-set (`available_for_lang − disabled`). Sending the *off* list means any channel the user never touched — and, importantly, **any channel we add later** (e.g. Coptic's `quotation`) — stays ON by default. An ON-list would silently freeze the channel set at whatever existed when the UI was written.

**Cache-correctness insight.** User weights/enabled-set must be part of the results cache key, or a tuned search could return a cached *default* result (or vice-versa). But we only fold them into the cache key **when they are non-default** — so the large existing default-search cache stays valid and default searches are byte-for-byte unchanged.

**Open design question NC raised (unresolved).** If users can turn channels off, *do we still need the separate single-channel search modes* (lemma, exact, sound, …) as their own UI entries? Tentative answer: keep them as convenient "main alternatives," but this is a product decision to revisit once adjustable weights ship.

**Provenance note for future write-ups.** This is a good example of the V6 design philosophy that the AI-API guide also leans on: the pipeline is *transparent and adjustable*. Adjustable weights make that adjustability user-facing, which strengthens the "Tesserae results are auditable" claim.

---

## 2. Current state — everything needed to rebuild

**PR:** #187 "Prototype: user-adjustable channel weights (Advanced)" — https://github.com/tesserae/tesserae-v6/pull/187
**Branch:** `feature/adjustable-channel-weights` @ `de26387a` · base `main` · **DRAFT/OPEN** · created 2026-08-09 · **+391 / −6 across 6 files.**
(Branch is behind current `main` `76cd7ef`; a preview/merge should rebase or merge main first.)

**Files changed and what each does:**
| File | +/− | Role |
|---|---|---|
| `backend/blueprints/fusion.py` | +70 | `/search-fusion` reads optional `channel_weights` + `disabled_channels`; converts disabled→`enabled_channels` keep-set; folds non-default settings into the cache key; passes both into the search. Adds `GET /api/fusion-default-weights`. |
| `backend/fusion.py` | +116/−4 | New helpers: `sanitize_channel_weights(raw)`, `sanitize_channel_keys(raw)`, `merge_channel_weights(channel_weights, language, corpus_type, …)` (overlays user weights on the default profile). Threads `channel_weights` + `enabled_channels` through the search into `fuse_results`. |
| `backend/cache.py` | +9 | Includes `channel_weights` / `enabled_channels` in the cache settings **only when present**, so default searches keep their existing cache keys. |
| `client/src/utils/api.js` | +5 | `getFusionDefaultWeights(language)` → `GET /api/fusion-default-weights?language=…`. |
| `client/src/components/search/SearchSettings.jsx` | +175/−1 | New collapsible **"Advanced — Channels & weights"**: per-channel weight inputs/sliders + per-channel ON/OFF checkboxes, pre-filled from the default-weights endpoint. |
| `client/src/App.jsx` | +16/−1 | Passes `channel_weights` + `disabled_channels` into the search request. |

**New / changed API surface:**
- `POST /api/search-fusion` — now also accepts optional:
  - `channel_weights`: `{ "<channel>": <number>, … }` (overlaid on the language default profile)
  - `disabled_channels`: `[ "<channel>", … ]` (true off — those channels don't run)
- `GET /api/fusion-default-weights?language=la` → `{ "language":"la", "weights": {"lemma":2.0, …}, … }` (to pre-fill the UI).
- Channel keys are the 10 fusion channels (+ `quotation` for cop): `lemma, lemma_min1, exact, sound, edit_distance, semantic, dictionary, syntax, syntax_structural, rare_word` (see `CHANNEL_WEIGHTS` in `backend/fusion.py`).

**Verification already done:** default path is unchanged — with no `channel_weights`/`disabled_channels` in the request, weights fall back to `get_weight_profile()` and the cache key is unchanged, so results are byte-identical to production. Built via two background agents; one esbuild parse-check failed only because the worktree had no `node_modules` (CI validated the build).

---

## 3. How to resume / preview / ship

**To preview on production (NC's pending decision):** temporary deploy of the branch, exactly like the Marvin concurrency-gate branch deploy pattern —
1. On prod: `git checkout -- dist/`, `git fetch`, `git checkout -B feature/adjustable-channel-weights origin/feature/adjustable-channel-weights` (rebase/merge `main` first so it includes `76cd7ef`), `npm run build`, `touch tesseraev6_flask.wsgi`.
2. Verify arma-virum regression + a weighted/disabled search actually differs from default.
3. **Rollback (one block):** `git checkout -- dist/; git checkout main; npm run build; touch tesseraev6_flask.wsgi` → back to `76cd7ef`.

**To ship for real:** rebase branch onto `main`, take it out of draft, let CI run, merge, then standard prod deploy (**`npm run build` is mandatory** — this PR touches `client/`).

**Before shipping, decide:** (a) keep or retire the standalone single-channel search modes; (b) whether the API's `channel_weights`/`disabled_channels` should be documented in the AI-API guide (they should — see the sibling AI-API thread).

---

## 4. Related
- Sibling thread: `2026-08-10_ai-api-access.md` (the API guide should document these two new params once #187 ships).
- Scoring context: `CHANNEL_WEIGHTS` / `get_weight_profile()` in `backend/fusion.py`; current default profile in project memory / CLAUDE.md.
