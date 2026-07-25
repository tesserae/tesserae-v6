export const STOPLIST_INFO = {
  description: "The Default stoplist combines curated function words with automatic high-frequency detection using Zipf's law. In Fusion mode, the curated stoplist also plays a key role in scoring: it identifies function-word matches so they can be ranked below content-word matches.",

  howItWorks: [
    "Curated words: Pronouns, articles, conjunctions, prepositions, common verbs",
    "Zipf detection: Automatically identifies 10-50 additional high-frequency words from your selected texts",
    "The two lists are combined to filter out noise while preserving meaningful vocabulary",
    "In Fusion mode: the curated list is used in the scoring layer to penalize function-word-only matches (e.g., sharing tum + nec) while preserving content-word matches (e.g., pectore + curas)"
  ],

  options: {
    default: "Uses curated stop words + Zipf elbow detection (recommended)",
    manual: "Enter a number (e.g., 50) to use only the top N most frequent words",
    disabled: "Enter -1 to disable stoplisting entirely (not recommended)"
  },

  customStopwordsNote: "Use dictionary forms (lemmata): pietas not pietate, λόγος not λόγον, king not kings."
};
