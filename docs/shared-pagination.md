# Shared pagination audit and architecture

This refactor is stacked on **PR #614**, which was OPEN and unmerged when work
started. Base: `perf/server-paged-search-results` at `1b4c3aae`.
Fetched `origin/main` was `732684d6`. The protected untracked file
`texts/la/finaltestauthor.finaltestwork.tess` was preserved.

## Complete frontend pagination inventory

The audit searched repository JS/JSX/TS/TSX, including hooks and every admin tab,
for display limits, Show/Load More, page state, slices, page-size constants,
offset/limit/per_page parameters, shared hooks/components and Previous/Next.
Backend parameter names were inspected as contracts, not standardized.
Rows below describe the implementation **before this refactor**.

| Page / Component | Current strategy | Data already local? | Backend paging? | Existing shared component? | Recommended migration / final decision |
|---|---|---|---|---|---|
| SearchResults | Local array or one server-held result page | Local fallback only | Search snapshot offset/limit from #614 | Yes | Retain both existing hooks and UI |
| RareResultsDisplay | Sorted local array | Yes | No | Yes | Retain existing hook and UI |
| LineSearch results | 50-result growing prefix | Yes | No | No | Migrated to usePagination + Pagination |
| LineSearch browse lines | 100-line growing prefix | Yes | No; full text lines fetched once | No | Migrated; retains 100 default |
| WildcardSearch | 50-result growing prefix | Yes | No | No | Migrated to usePagination + Pagination |
| CrossLingualSearch | 50-result growing prefix after sort/chart filter | Yes | No | No | Migrated to usePagination + Pagination |
| CorpusSearchResults | 50-result growing prefix after genre/era/author filters | Yes | No | No | Migrated to usePagination + Pagination |
| RareWordsExplorer | Append offset/limit batches | Loaded prefix only | Yes | No | Migrated to useIncrementalPagination + Pagination more variant |
| TextCredits | Append offset/limit batches; debounced query | Loaded prefix only | Yes | No | Migrated to useIncrementalPagination + Pagination more variant |
| Repository public/private/admin | Append page/per_page batches, summaries, normalization and expanded-form enrichment; mutations refresh collections | Loaded prefix only | Yes | No | Can migrate later; keep custom. Integrating writable public/private lifecycles, enrichment, totals and loaded-prefix filters needs separate collection work |
| ThemeSearchPage | Refetch growing prefixes 25/50/75/100, then offset batches with deduplication and language interleaving | Loaded prefix only | Yes | No | Should remain custom in this PR; a simple batch hook would need special modes and alter query behavior |
| DictionaryReviewTab | Fixed 25-entry server pages, Next inferred from returned length; reviewed entries removed in place | One page | Yes, offset/limit | No | Can migrate later; needs explicit end-of-list navigation and mutable review-count semantics. Existing controls disappear on short final pages; not addressed here |
| GenreClassificationTab | Fixed 50-item local slice, Previous/Next, pending edits | Yes | No | No | Migrated now to shared local hook/UI; edits preserved |
| ReaderPage / TextPane | Local growing prefix plus IntersectionObserver; line selection and go-to-line depend on visible indices | Yes | No; text fetched in full | No | Should remain custom: continuous reading, cross-line selection and automatic extension differ from result pages |
| Reader ResultsPanel | Similar-passage request grows limit 15 to 60; relevance cap | Loaded prefix only | Yes, increased query limit | No | Should remain custom: expands a capped ranked query, not fixed batches |
| RequestsTab | Full collection plus status filtering; 10-line preview in editor | Yes | No | No | No pagination to migrate; preview is intentionally truncated |
| UsersTab, MetadataTab, SourcesTab, FeedbackTab, CacheTab | Full collections / editor lists | Yes | No | No | No pagination implementation; future pagination is separate scope |
| AuditTab | Fetch last 100 actions; show at most 20 per person | Capped snapshot | API limit=100, no navigation | No | Should remain custom snapshot; adding paging changes dashboard scope |
| AnalyticsTab, StatsTab, PerformanceTab, SettingsTab, GeographicMap | Metrics, top-N summaries or settings | Summaries | No collection paging UI | No | No pagination to migrate |
| CorpusBrowser, ConnectionsMap | Corpus browsing / autocomplete choices capped at 25 | Yes | No collection pagination | No | Fixed suggestions are not result paging |
| NetworkGraph, FindingsBlock, ResultsInsight | Legend/top-N facts and assistant context sampling | Yes or sample adapter | ResultsInsight can fetch a sample | No | Not pagination UI; intentional samples remain |
| ReaderNav | Previous/Next books, jump and reading navigation | Book metadata | No collection pagination | No | Should remain custom book navigation |
| BlogArchivePage, ResearchPage, Navigation | App page routing | N/A | No | No | setPageType is routing, not pagination |

Other slices in highlighting, reference parsing, export filenames, selections,
translation text and formatting are unrelated to collection pagination. HelpPage's
Show More descriptions concern ThemeSearch and the Reader and remain accurate.

## Architecture before and after

Before: two shared result views and twelve distinct components/views with their
own pagination controls. LineSearch had two such blocks (results and browse).

After:

```text
complete local array -> usePagination -----------> Pagination (numbered)
server search snapshot -> useServerPagination ---> Pagination (numbered)
server batches -> useIncrementalPagination ------> Pagination (more)
```

### Every shared-hook caller

- `usePagination`: SearchResults local fallback, RareResultsDisplay,
  LineSearch results and browse lines, WildcardSearch, CrossLingualSearch,
  CorpusSearchResults, GenreClassificationTab.
- `useServerPagination`: SearchResults server snapshot mode, supplied by #614.
- `useIncrementalPagination`: RareWordsExplorer, TextCredits.

### Shared modules and contract

The established names remain: `visibleItems`, `currentPage`, `totalPages`,
`totalResults`, `pageSize`, `setPageSize`, `loading`, `hasNextPage`,
`hasPreviousPage`. Local/server page hooks also provide `setPage`, `resetPage`,
`startIndex`, `endIndex`. Server search keeps `pageLoading` and `pageError` for
compatibility. The batch hook exposes `pageError` and `loadMore`.

Accumulation deliberately has no arbitrary `setPage` or backwards transition;
earlier items remain on screen. Its currentPage counts loaded batches. The
common UI takes the hook object directly; existing onPageChange /
onPageSizeChange callers continue to work. No backend-specific flags belong in
the UI or batch hook.

`usePagination` already validated sizes against **10/20/50/100**, default 50,
clamped pages and integer page inputs, reset on page-size changes, supported
controlled sizes and streaming pin-to-first-page, and applied pagination after
caller filtering/sorting. It did **not** automatically reset for equal-sized new
arrays: callers must signal the new result set. Its resetKey comparison now uses
Object.is instead of interpolating keys into a string, so stable object/array
identities work without losing existing primitive-key behavior.

Converted result views memoize a reset token from completed result identity and
active sort/filter settings. Thus a new result array resets even when query and
count are unchanged, while unrelated renders stay on the selected page. Browse
lines use the returned line array as resetKey. GenreClassification includes
loaded texts and filter/sort values but excludes pendingEdits, so editing does
not reset the page unexpectedly; count shrinkage still clamps it.

`useServerPagination` remains #614's one-page search snapshot adapter with its
existing first-page seed, sort/filter requests, result-id/reset-key/page-size
resets, AbortController cleanup and page-loading/error state. This refactor adds
only shared loading and direction aliases to its return object.

`useIncrementalPagination` accepts a stable `fetchPage({page, pageSize, signal})`
adapter returning `{items, total}`. It accumulates fixed batches, resets when the
adapter identity, resetKey or size changes, rejects superseded responses even
if an adapter ignores abort, aborts on reset/unmount, prevents duplicate clicks,
and retains loaded items after errors so the same next page can be retried.
Both adapters preserve their API URLs, offset/limit parameters, query/sort
settings and cache settings. Their established **25/50/100/500** batch sizes now
have one exported constant. They keep full-prefix rendering and accumulated-row
export semantics; no numbered-page behavior is imposed on them.

`Pagination` already used a seven-slot numbered window with ellipses, native
keyboard-operable buttons/select, a linked Show label, aria-current=page,
Go-to-page labels, a labeled navigation landmark, a polite count announcement,
and disabled boundary buttons. These remain. Generic additions are supplied
pageSizeOptions, loading (disables controls and sets aria-busy), direct hook
setter names, and an accumulating `more` variant. The existing navigation
landmark label is preserved for existing accessibility tests. Empty numbered
lists still hide controls; empty batch lists retain their picker.

## Confirmed bugs and preserved behavior

LineSearch, CrossLingualSearch and CorpusSearchResults kept their expanded
local display limits across completed searches. WildcardSearch reset separately.
All four now start on page 1 for a new completed result set. Global row numbers
continue across page boundaries. Local filtering and sorting still happen before
slicing. Search execution, ranking, requests, exports, result card/table content,
empty/loading states and cancellation code remain unchanged. Group A still
downloads the full list and makes no requests when navigating/changing sizes.
This is reuse, consistency, state correctness and bounded DOM rendering, not a
backend search-computation optimization. Batch views still accumulate DOM rows.

## Reduction and remaining custom code

Counting components with actual handwritten paging controls (excluding fixed
previews, samples, routing and book navigation): **12 before -> 5 after**.
Counting blocks: **13 before -> 5 after**, with eight blocks migrated across
seven components. The remaining five are Repository, ThemeSearchPage,
DictionaryReviewTab, TextPane/ReaderPage, and Reader ResultsPanel, for the
reasons listed above. displayLimit / browseDisplayLimit and the migrated local
Show More blocks are gone. Test/document additions are reported separately from
production code so line counts do not imply an overall smaller diff.
Production changes: **215 added / 343 deleted (128 net lines removed)**,
including the new 78-line batch hook. Tests add 403 lines.

## Verification

Added **48 tests**:

- 24 integration cases across the four local search pages: first 50, page 2 and
  rank, Previous/Next/final remainder, 50-to-20 sizes, same-query/same-count new
  result reset, and sort/filter-before-slice reset. Navigation tests assert no
  added transport calls.
- One LineSearch browse integration: default 100, local page 2, new-load reset.
- Eight collection integration cases: two pages each cover append with existing
  offset/limit requests, size reset, query/language reset, failed-next-page rows
  and retry controls.
- One GenreClassification integration: local navigation, size and filter reset,
  one backend request throughout.
- Nine batch-hook unit cases: logical first/next, key and size reset, invalid
  size, stale responses ignoring abort, loading/concurrent clicks, error/retry,
  first error, unmount abort, and two independent parameter adapters.
- Four Pagination unit cases: hook setters, custom sizes/accumulated summary,
  loading disables, final/empty batch controls.
- One local-hook identity case: new identity resets, unchanged identity does
  not, common loading/direction fields.

Node **22.23.2**, without package/version changes:

- PASS: all pagination hooks/UI, all converted views, batch integrations,
  existing search frontend tests and restricted-credit/language regressions.
- Complete frontend suite: **48 files pass, 1 fails; 511 tests pass, 1 fails
  (512 total)**. The sole failure is the unchanged useCorpus.race test
  `shows the language asked for even when its answer is the slower one`, which
  expects authors[0].name even though the current authors entry is a string.
- Baseline demonstration: isolated export of origin/main at 732684d6 with the
  same installed dependencies and Node 22 reproduces that exact failure:
  **1 pass / 1 fail** in useCorpus.race.test.jsx. No baseline source edits.
- PASS: npm run build (existing large-chunk/Browserslist warnings).
- PASS: git diff --check and frontend-only API/ordering/export/cancellation
  diff review.
- SKIP: backend tests; no backend changes.
- NOT RUN: manual browser interaction; integration coverage runs in jsdom.
