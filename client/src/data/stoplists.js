export const STOPLIST_INFO = {
  description: "The Default stoplist combines curated function words with automatic high-frequency detection using Zipf's law.",
  
  howItWorks: [
    "Curated words: Pronouns, articles, conjunctions, prepositions, common verbs",
    "Zipf detection: Automatically identifies 10-50 additional high-frequency words from your selected texts",
    "The two lists are combined to filter out noise while preserving meaningful vocabulary"
  ],
  
  latin: {
    count: 66,
    examples: ["et", "in", "est", "non", "ut", "cum", "qui", "quae", "que", "hic", "ille", "sum", "esse"]
  },
  
  greek: {
    count: 88,
    examples: ["καί", "δέ", "τε", "γάρ", "μέν", "ὁ", "ἡ", "τό", "αὐτός", "οὗτος", "ἐγώ", "σύ", "εἰμί"]
  },
  
  english: {
    count: 60,
    examples: ["the", "be", "to", "of", "and", "a", "in", "that", "have", "it", "thou", "thee", "thy", "hath"]
  },
  
  options: {
    default: "Uses curated stop words + Zipf elbow detection (recommended)",
    manual: "Enter a number (e.g., 50) to use only the top N most frequent words",
    disabled: "Enter -1 to disable stoplisting entirely (not recommended)"
  },
  
  customStopwordsNote: "Use dictionary forms (lemmata): pietas not pietate, λόγος not λόγον, king not kings."
};
