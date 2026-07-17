const CURATED_STOPLISTS = {
  latin: {
    words: [
      'et', 'in', 'est', 'non', 'ut', 'cum', 'ad', 'sed',
      'si', 'quod', 'qui', 'quae', 'que', 'de', 'ex', 'per',
      'ab', 'ac', 'atque', 'aut', 'nec', 'neque', 'enim', 'nam',
      'iam', 'tamen', 'autem', 'quidem', 'hic', 'haec', 'hoc', 'ille',
      'illa', 'illud', 'is', 'ea', 'id', 'ipse', 'ipsa', 'ipsum',
      'se', 'suus', 'sua', 'suum', 'esse', 'sum', 'fui', 'sunt',
      'erat', 'erant', 'fuit', 'ait', 'a', 'o', 'te', 'tu',
      'me', 'ego', 'nos', 'vos', 'noster', 'vester', 'omnis', 'omnia',
      'omnes', 'nullus', 'nulla', 'nullum', 'unus', 'duo', 'tres', 'primus',
      'secundus', 'tertius', 'ubi', 'nunc', 'sic', 'tam', 'tum', 'ita',
      'ibi', 'hinc', 'inde', 'quo', 'qua', 'quam', 'quando', 'unde',
      'cur', 'ergo', 'igitur'
    ]
  },
  greek: {
    words: [
      'και', 'δε', 'τε', 'γαρ', 'μεν', 'δη', 'ου', 'ουκ',
      'ουχ', 'μη', 'αλλα', 'αλλ', 'ουδε', 'μηδε', 'ουτε', 'μητε',
      'ειτε', 'ητοι', 'νυ', 'τοι', 'περ', 'γε', 'κε', 'κεν',
      'ρα', 'εν', 'εις', 'εκ', 'εξ', 'προς', 'απο', 'περι',
      'κατα', 'μετα', 'δια', 'υπο', 'υπερ', 'παρα', 'επι', 'αντι',
      'συν', 'προ', 'αρ', 'επ', 'απ', 'κατ', 'μετ', 'παρ',
      'υπ', 'αμφ', 'αντ', 'ο', 'η', 'το', 'οι', 'αι',
      'τα', 'τον', 'την', 'του', 'της', 'τω', 'τη', 'τοις',
      'ταις', 'τους', 'τας', 'των', 'ος', 'ης', 'ον', 'οστις',
      'ητις', 'οτι', 'ως', 'αν', 'ει', 'ω', 'ην', 'οις',
      'αις', 'ους', 'ας', 'ων', 'α', 'αυτος', 'αυτη', 'αυτο',
      'αυτον', 'αυτην', 'αυτου', 'αυτης', 'αυτω', 'αυτοι', 'αυται', 'αυτα',
      'αυτους', 'αυτας', 'αυτων', 'αυτοις', 'αυταις', 'ουτος', 'τουτο', 'τουτον',
      'ταυτην', 'τουτου', 'ταυτης', 'τουτω', 'ταυτη', 'ουτοι', 'ταυτα', 'τουτους',
      'ταυτας', 'τουτων', 'τουτοις', 'ταυταις', 'εκεινος', 'εκεινη', 'εκεινο', 'εκεινον',
      'εκεινην', 'εκεινου', 'εκεινης', 'εκεινω', 'εκεινοι', 'εκειναι', 'εκεινα', 'εκεινους',
      'εκεινας', 'εκεινων', 'εκεινοις', 'εκειναις', 'εγω', 'εμε', 'με', 'εμου',
      'μου', 'εμοι', 'μοι', 'συ', 'σε', 'σου', 'σοι', 'ημεις',
      'ημας', 'ημων', 'ημιν', 'υμεις', 'υμας', 'υμων', 'υμιν', 'τις',
      'τι', 'τινα', 'τινος', 'τινι', 'τινες', 'τινων', 'τισι', 'τισιν',
      'εστι', 'εστιν', 'ειμι', 'ησαν', 'εσμεν', 'εστε', 'εισι', 'εισιν',
      'βη', 'βαν', 'βας', 'βησαν', 'εβη', 'φη', 'εφη', 'φησι',
      'ηλθε', 'ηλθον', 'νυν', 'ετι', 'ουν', 'αρα', 'τοτε', 'ποτε',
      'πω', 'πως', 'που', 'οπου', 'οθεν', 'ενθα', 'ενθεν', 'οπως',
      'ωστε', 'ουτω', 'ουτως'
    ]
  },
  english: {
    words: [
      'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that',
      'have', 'i', 'it', 'for', 'not', 'on', 'with', 'he',
      'as', 'you', 'do', 'at', 'this', 'but', 'his', 'by',
      'from', 'they', 'we', 'say', 'her', 'she', 'or', 'an',
      'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
      'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which',
      'go', 'me', 'when', 'make', 'can', 'like', 'no', 'just',
      'him', 'know', 'take', 'into', 'your', 'some', 'could', 'them',
      'see', 'other', 'than', 'then', 'now', 'its', 'is', 'am',
      'are', 'was', 'were', 'been', 'being', 'has', 'had', 'having',
      'thou', 'thee', 'thy', 'thine', 'thyself', 'ye', 'art', 'doth',
      'dost', 'hath', 'hast', 'shalt', 'wilt', 'canst', 'wouldst', 'shouldst',
      'couldst', 'didst', 'hadst', 'mayst', 'mightst', 'wast', 'wert', 'wherefore',
      'wherein', 'whereon', 'thereof', 'therein', 'herein', 'hereby', 'hither', 'thither',
      'whither', 'hence', 'thence', 'ere', 'oft', 'nay', 'yea', 'aye',
      'prithee', 'methinks', 'forsooth', 'verily', 'tis', 'twas', 'twere', 'twill',
      'twould', 'o', 'oh', 'ah', 'alas', 'lo', 'behold', 'nought',
      'naught', 'upon', 'unto', 'thus', 'such', 'each', 'every', 'both',
      'own', 'same', 'much', 'more', 'most', 'yet', 'still', 'even',
      'also', 'too', 'very', 'here', 'how', 'why', 'where', 'whence',
      'whether', 'while', 'whilst', 'though', 'although', 'because', 'since', 'before',
      'after', 'until', 'till', 'shall', 'should', 'may', 'might', 'must',
      'need', 'dare', 'let', 'lest', 'nor', 'neither', 'either', 'none',
      'any', 'many', 'few', 'less', 'least'
    ]
  }
};

export const STOPLIST_INFO = {
  description: "The Default stoplist combines curated function words with automatic high-frequency detection using Zipf's law. In Fusion mode, the curated stoplist also plays a key role in scoring: it identifies function-word matches so they can be ranked below content-word matches.",

  howItWorks: [
    "Curated words: Pronouns, articles, conjunctions, prepositions, common verbs",
    "Zipf detection: Automatically identifies 10-50 additional high-frequency words from your selected texts",
    "The two lists are combined to filter out noise while preserving meaningful vocabulary",
    "In Fusion mode: the curated list is used in the scoring layer to penalize function-word-only matches (e.g., sharing tum + nec) while preserving content-word matches (e.g., pectore + curas)"
  ],

  latin: CURATED_STOPLISTS.latin,
  greek: CURATED_STOPLISTS.greek,
  english: CURATED_STOPLISTS.english,

  options: {
    default: "Uses curated stop words + Zipf elbow detection (recommended)",
    manual: "Enter a number (e.g., 50) to use only the top N most frequent words",
    disabled: "Enter -1 to disable stoplisting entirely (not recommended)"
  },

  customStopwordsNote: "Use dictionary forms (lemmata): pietas not pietate, λόγος not λόγον, king not kings."
};
