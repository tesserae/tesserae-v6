// The settings a new search starts with (moved out of App.jsx, cleaning job
// H4, 2026-10-13, values unchanged). A fresh object each call, because the
// page keeps and replaces its own copy.
export const defaultSearchSettings = () => ({
  match_type: 'fusion',
  min_matches: 2,
  stoplist_basis: 'source_target',
  stoplist_size: 0,
  custom_stopwords: '',
  source_unit_type: 'line',
  target_unit_type: 'line',
  max_distance: 999,
  max_results: 0,
  bigram_boost: false,
  stoplist: false,
  use_meter: true,
  exclude_proper_nouns: false,
  freq_basis: 'corpus',
  // Advanced: user-overridden fusion channel weights. Contains only the
  // channels the user has explicitly changed; empty => use tuned defaults.
  channel_weights: {},
  // Advanced: fusion channels the user has turned OFF via the on/off
  // switches. Empty => every channel runs (default). Only sent to the
  // backend when non-empty (see request-building below).
  disabled_channels: [],
  // Formula filter: null/false => no filtering (default). Set together by
  // SearchSettings' "Formulas" control (hide rows recurring in more than
  // formula_max works, or show only those at/above it).
  formula_max: null,
  formula_only: false
});
