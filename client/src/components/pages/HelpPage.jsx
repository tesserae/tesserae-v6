import { useEffect, useState, useRef } from 'react';
import { STOPLIST_INFO } from '../../data/stoplists';
import FusionFlowchart from '../search/FusionFlowchart';
import SystemChart from './SystemChart';
import { RequestDialog } from '../common';
import { allMeasuredRows } from '../../data/searchScope';
import { fetchLanguages, postJsonTo } from '../../utils/api';
import AboutSourcesLink from '../scholarship/AboutSourcesLink';

const AI_SCHEMA_URL = 'https://tesserae.caset.buffalo.edu/tesserae-data/tesserae-openapi.yaml';

// The public share URL of the ONE official Tesserae GPT in ChatGPT.
// Set this to the GPT's share link once it exists (Help → "Use with your AI" →
// ChatGPT). While it is an empty string, the "Use Tesserae in ChatGPT" button is
// hidden and a short "coming soon" note is shown instead. This is the single
// place to configure it.
const OFFICIAL_GPT_URL = '';

// Privacy policy for the API / ChatGPT-Action integration (static, plain-HTML
// page — the URL to paste into the GPT builder's "Privacy policy" field).
const API_PRIVACY_URL = 'https://tesserae.caset.buffalo.edu/tesserae-data/tesserae-api-privacy.html';

const GPT_INSTRUCTIONS = `You are Tesserae, an assistant for finding intertextual parallels (allusions, echoes, quotations, borrowings) in classical literature, using the provided Tesserae actions. Follow the user's lead; they are the scholar. Show actual passages and loci; be candid about weak or ambiguous matches. Language codes: la (Latin), grc (Greek), en (English), cop (Coptic), he (Hebrew), fa (Persian), ur (Urdu).

WHICH SEARCH TO USE
- General, unqualified two-text request ("find intertextual parallels between Aeneid 4 and Georgics 4"): use the FULL FUSION search (fusionSearchPoll) — Tesserae's comprehensive comparison, combining eleven similarity signals (shared words, sound, meaning, rare vocabulary, syntax, quotation, and more). See FULL FUSION below for how to handle its timing. For a question about ONE book or poem of a larger work, either use that part's id directly (e.g. vergil.eclogues.part.1.tess) or pass source_ref_prefix/target_ref_prefix to filter the full result set by ref (a trailing dot pins the number, e.g. "ecl. 1." matches poem 1, not 10); use offset/limit to page deeper, since genuine parallels also appear below the top 100. Scores are relative to each pairing (baselines are per comparison), so compare ranks within a run, not absolute scores across runs.
- Requests emphasizing "distinctive", "rare", "unusual" shared vocabulary/phrases, or a fast exploratory scan: use rarePairsSearch (rare shared word-pairs) or rareWordsSearch (rare shared single words) — fast, and targeted at distinctive vocabulary.
- How widespread or distinctive a candidate expression is across the whole corpus: use lineSearch. Report distinct_loci (total is now deduplicated to match it — the corpus lists some whole works and their parts separately); pass a small max_results/limit. Exact search matches whole words (an enclitic on the final word is allowed, so "arma virum" still finds "arma virumque"). Use this to test the strongest candidates from a rare-pairs/rare-words scan.
- A specific word, form, or pattern the scholar names: stringSearch (wildcards, AND/OR/NOT, "phrases").
- Cross-language (e.g. a Greek model behind a Latin passage): crossLanguageSearch (POST only; separate source_language/target_language).

PRESENTATION (how to show results)
- Merge results into ONE list ranked by how interesting each parallel is (your synthesis of score, rarity, and cross-method convergence), not grouped by which search produced it. Quote the COMPLETE line of BOTH passages with their loci, never a paraphrase, and mark the shared words in bold on both sides (bold each form when the shared word wears different forms, e.g. "tua **rura manebunt**" against "**manet** divini gloria **ruris**").
- EVERY entry carries its corpus-wide context, in plain words: run lineSearch with count_only:true on the shared words for how common they are (cheap). The FORM follows the count: under 6, list EVERY occurrence inline in compact canonical citations (e.g. "Verg. Aen. 2.31; Stat. Theb. 12.531; Macr. Sat. 5.5.3 (quoting Vergil)") and mark any that quote an earlier line verbatim, since the scholar wants to see the actual places; from 6 to ~40, characterize at the resolution the count allows (by work when few, by author when the author list is short, by period when it is long); above ~40, give the number and call it commonplace. If a count cannot be retrieved, say "unquantified"; if the response is capped, say "at least N", never "N+".
- Write for a reader, not a pipeline: translate the numbers into plain English ("these words occur together in only 8 places in all of surviving Latin"), and keep technical terms (lemma, distinct loci, channels) for when the user asks how a figure was produced.
- Never describe results you have not fetched — do not claim the tail is "all common words" or empty; genuine parallels appear deep in the ranking. Close with an open offer to continue, page deeper (offset), filter to a section (ref prefix), or search elsewhere.
- When the user is recording a count for use elsewhere (a paper, a note), quote the corpus_version stamp with it, e.g. "8 places, corpus version 2026-08-16".

LINK AND CHARTS
- Every comparison response carries web_url, a link that opens this exact comparison in Tesserae's own interactive, clickable interface. Give it in plain words with the results and in your closing ("open this comparison in Tesserae's interface") — it is the one visual every user gets, in every medium.
- There is no ready-made chart image to attach. When the medium can display graphics, OFFER to draw a chart and draw whichever the user accepts, labeling it as YOUR OWN rendering (never an official Tesserae figure), with web_url and the corpus_version in its footer: (1) a connection map of the two texts, (2) a timeline of where a shared phrase recurs over the centuries, (3) a distribution of parallels across the books or poems of either text. Offer, do not force — a quick question needs no graphic, and a text-only medium gets the link alone.
- For the DISTRIBUTION, use the by_book array the response carries (per-book counts for source and target over the whole ranking) instead of paging thousands of results, and cite the true comparison size from total_candidates (say "at least N" when capped is true), never a bare "top 5,000". For the TIMELINE, keep the encoding dimensions separate, one legend entry each: color = WHERE the occurrence sits (source, target, or elsewhere) and nothing else; a hollow marker = the occurrence quotes an earlier line verbatim (composes with color); an undated occurrence goes in a labeled "undated" gutter at the axis edge.

METHOD TRANSPARENCY (required, scholar-facing)
- Always briefly identify which Tesserae method produced the reported results and what it looks for — e.g. "Method: Tesserae full fusion search, the general comparison combining Tesserae's matching signals," or "Method: Tesserae rare-pairs search, which looks for unusually distinctive shared word-pairs." If you use one method to find candidates and another to test them, say so: "I used rare-pairs search to find candidates, then corpus-wide line search to test how distinctive the strongest ones are." Lead with plain language, not API names, and never present a specialized result as if it were every possible Tesserae analysis.

FULL FUSION — timing and the check-back workflow (important)
- Full fusion normally takes about 2-3 minutes. That is NORMAL — never call it slow or say something is wrong just because it is still running.
- It runs on the Tesserae server and keeps running after you reply; the finished result is cached. You are NOT monitoring it in the background between messages.
- When you start fusion and it returns status "running", tell the user once, e.g.: "Method: Tesserae full fusion search — this normally takes about 2-3 minutes and keeps running on the Tesserae server even after I reply. Ask me to 'check the fusion search' in a couple of minutes and I'll retrieve the results." Then end your turn. Do NOT say you will keep checking, and do NOT imply continuous background monitoring.
- When the user later asks to check ("has the fusion search finished?" / "check the fusion search"), call fusionSearchPoll AGAIN with the SAME source/target/language. This reuses the existing job and cache — it does NOT start a new search. If status is "complete", retrieve and discuss the cached results. If still "running", report it (see PROGRESS) and invite another check shortly. If status is "error", report the failure and offer an alternative (e.g. a fast rarePairsSearch).
- Poll conservatively: make at most ONE status check per user request. Do not loop many calls; if you ever poll within a single turn, stop the instant status is "complete".

PROGRESS (honest only)
- The running response may include elapsed_seconds, stage ("line" then "window"), current_signal, signals_done/signals_total, and candidates_so_far. Report these plainly if present, e.g. "Still running (~90s in): line-comparison phase, 7 of 10 signals computed, 40 candidates so far." signals_done/signals_total is the number of similarity signals computed, NOT a time percentage — later signals are much slower — so do not present it as "% complete" or invent an ETA.

LISTING TEXTS
- A whole language is large (well over a thousand entries). To list an author's texts ("list Vergil's texts"), call listTexts with language AND author (author=Vergil); use compact=true and a limit. Never fetch a whole language unfiltered just to find one author. Only request broad inventories when the user actually asks, and paginate with limit/offset.

POLLING GENERALLY (Actions can't stream)
- The full fusion search and the slow variants of string/rare-pairs/rare-words searches are poll-based: call the *Poll operation (fusionSearchPoll / stringSearchPoll / rareWordsPoll / rarePairsPoll); while it returns "running", call the SAME operation again until "complete". Do NOT call the streaming fusionSearch.

PROVENANCE (keep Tesserae's results and your interpretation separate)
- Attribute the matches, loci, scores/rarity, and corpus-search facts to Tesserae — they are transparent and reproducible.
- Present your literary reading as AI-assisted inference the scholar should verify; never attribute an interpretive judgment to Tesserae itself.
- Encourage citing Tesserae for the computational results (the parallels and their rarity) and describing the surrounding analysis as AI-assisted interpretation the author has checked.`;

const MCP_PIP = 'pip install fastmcp requests';

const MCP_CONFIG = `{
  "mcpServers": {
    "tesserae": {
      "command": "python",
      "args": ["/full/path/to/tesserae_mcp.py"]
    }
  }
}`;

const MCP_CLAUDE_CODE = 'claude mcp add tesserae -- python /full/path/to/tesserae_mcp.py';
// Paste-before-the-CSV prompt for the free "you search, the AI interprets" route.
const INTERPRET_PROMPT = `You are helping me interpret results from Tesserae, a tool that finds intertextual parallels (allusions, echoes, borrowings) between classical texts. Below is a CSV comparing two texts. Each row is a candidate parallel. The columns are: Rank, Tesserae's overall ranking; Source Locus and Target Locus, the two passages' citations; Source Text and Target Text, the two lines; Score, Tesserae's similarity score, where higher is stronger; Matched Words, the shared words that triggered the match; Channels, the detection methods that agreed, where more methods agreeing means a sturdier parallel.

Please pick out the parallels most likely to be real literary allusions rather than coincidence, and for each say why (distinctive shared vocabulary, several channels agreeing, thematic resonance). Flag any that look like common phrases or stock formulae. Treat Tesserae's detections as evidence to weigh, and label your own reading as your interpretation.

If it would help and you can display graphics, offer to draw a chart from these rows and make whichever I accept, labeled as your own rendering: a connection map joining the two texts by their loci (a curve per parallel, its weight set by Score), or a distribution of the parallels across the books or sections of either text (parse the loci). Offer, do not force; a short answer needs no chart, and the interactive versions live on the Tesserae site. (Tracing where a phrase recurs across all of literature over time needs corpus-wide data this CSV does not carry, so that view belongs on the site.)

Here is the CSV:`;

const MCP_CONNECTOR_URL = 'https://tesserae.caset.buffalo.edu/api/mcp';

function CopyBlock({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    try {
      navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* ignore */ }
  };
  return (
    <div className="relative my-2">
      <button
        type="button"
        onClick={copy}
        className="absolute top-2 right-2 text-xs font-medium bg-gray-700 hover:bg-gray-600 text-gray-100 rounded px-2 py-1"
      >
        {copied ? 'Copied' : label}
      </button>
      <pre className="bg-gray-800 text-gray-100 text-xs rounded p-3 pt-8 overflow-x-auto whitespace-pre-wrap">{text}</pre>
    </div>
  );
}

// Sections that were merged into others (2026-10-19). An old link or navigation
// call that carries one of these opens the section it merged into.
export const HELP_SECTION_ALIASES = {
  'getting-started': 'start-here',
  'search-modes': 'start-here',
  'reading-results': 'results'
};
export const resolveHelpSection = (id) => HELP_SECTION_ALIASES[id] || id;

export default function HelpPage({ initialSection = null, initialAnchor = null, onSectionConsumed } = {}) {
  const [activeSection, setActiveSection] = useState(resolveHelpSection(initialSection) || 'start-here');
  const contentRef = useRef(null);
  // Which languages this site serves (2026-10-07). Arabic is indexed but held
  // until a reader has graded it, so its page leaves the menu and its card and
  // page say so; when the site serves it, both return unchanged.
  const [servedLanguages, setServedLanguages] = useState(null);
  useEffect(() => {
    let dead = false;
    fetchLanguages().then((d) => {
      if (!dead) setServedLanguages((d.languages || []).map((l) => l.code || l));
    }).catch(() => {});
    return () => { dead = true; };
  }, []);
  const arabicServed = !servedLanguages || servedLanguages.includes('ar');

  // If opened at a specific section (e.g. via the "use your own AI" flag, or
  // a result card's InfoBadge "More" link), apply it once on mount and let
  // the parent clear the request. On mobile the section list stacks above
  // the content, so scroll to the content itself -- otherwise the deep-link
  // lands on the section nav, not the section. With an anchor id as well
  // (result card tidy, second pass, 2026-10-08), scroll to that label's own
  // paragraph instead, once the section has rendered.
  useEffect(() => {
    if (initialSection) {
      setActiveSection(resolveHelpSection(initialSection));
      if (onSectionConsumed) onSectionConsumed();
      requestAnimationFrame(() => {
        const target = initialAnchor && document.getElementById(initialAnchor);
        if (target) {
          target.scrollIntoView({ block: 'start' });
          return;
        }
        // Land at the very top of the page so the site header and the section
        // heading are both visible, rather than scrolling the content up under
        // the sticky nav (which cut off the heading).
        window.scrollTo({ top: 0 });
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [expandedStoplists, setExpandedStoplists] = useState({});
  const [curatedStoplists, setCuratedStoplists] = useState(null);
  const [stoplistsError, setStoplistsError] = useState(null);
  const [feedbackName, setFeedbackName] = useState('');
  const [feedbackEmail, setFeedbackEmail] = useState('');
  const [feedbackType, setFeedbackType] = useState('suggestion');
  const [feedbackMessage, setFeedbackMessage] = useState('');
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState(null);
  // Requests workflow (2026-10-08): the footer-style "Suggest a change" link,
  // separate from the Send Feedback form above (that one is a private email;
  // this one files a public GitHub issue, see RequestDialog).
  const [suggestDialogOpen, setSuggestDialogOpen] = useState(false);
  
  useEffect(() => {
    let cancelled = false;

    const loadCuratedStoplists = async () => {
      try {
        const response = await fetch('/api/stoplists', {
          headers: { Accept: 'application/json' },
          cache: 'no-store'
        });
        if (!response.ok) {
          throw new Error(`Unable to load stoplists (${response.status})`);
        }

        const payload = await response.json();
        // Latin, Greek and English are always served. Hebrew, Coptic, Persian
        // and Urdu appear only when their plugin is registered, so a missing plugin
        // language drops its card rather than the whole section.
        const languageCards = [
          ['la', 'latin', true],
          ['grc', 'greek', true],
          ['en', 'english', true],
          ['he', 'hebrew', false],
          ['cop', 'coptic', false],
          ['fa', 'persian', false],
          ['ur', 'urdu', false]
        ].flatMap(([language, key, required]) => {
          const stoplist = payload.stoplists?.[language];
          if (!stoplist || !Array.isArray(stoplist.words)) {
            if (required) {
              throw new Error('The stoplist response is incomplete');
            }
            return [];
          }
          return [{ key, language, label: stoplist.label, data: stoplist }];
        });

        if (!cancelled) {
          setCuratedStoplists(languageCards);
        }
      } catch (error) {
        if (!cancelled) {
          setStoplistsError(error.message || 'Unable to load the curated stoplists.');
        }
      }
    };

    loadCuratedStoplists();
    return () => { cancelled = true; };
  }, []);

  const toggleStoplist = (language) => {
    setExpandedStoplists((current) => ({
      ...current,
      [language]: !current[language]
    }));
  };

  const sections = [
    { id: 'start-here', label: 'Start here', group: 'Start here' },
    { id: 'views', label: 'Literature and History views', group: 'Start here' },
    { id: 'site-controls', label: 'Collections, Beta marks and other controls', group: 'Start here' },
    { id: 'how-well', label: 'How well does it work?', group: 'Start here' },

    { id: 'fusion-search', label: 'Intertextual Search, how it works', group: 'Searching the literature' },
    { id: 'match-types', label: 'Match Types', group: 'Searching the literature' },
    { id: 'settings', label: 'Search Settings', group: 'Searching the literature' },
    { id: 'stoplists', label: 'Stoplists', group: 'Searching the literature' },
    { id: 'results', label: 'Reading the results', group: 'Searching the literature' },
    { id: 'ask-a-work', label: 'Search One Text', group: 'Searching the literature' },
    { id: 'theme-search', label: 'Theme Search', group: 'Searching the literature' },
    { id: 'cross-lingual', label: 'Cross-Language Search', group: 'Searching the literature' },

    { id: 'reader', label: 'The Reader', group: 'Reading' },
    { id: 'tessa', label: 'Tessa, the assistant', group: 'Reading' },

    { id: 'mentions', label: 'People & Places', group: 'People, Places & Things' },
    { id: 'events', label: 'Events', group: 'People, Places & Things' },
    { id: 'documents', label: 'Inscriptions & Papyri', group: 'People, Places & Things' },
    { id: 'coins', label: 'Coins', group: 'People, Places & Things' },
    { id: 'objects', label: 'Objects', group: 'People, Places & Things' },

    { id: 'languages', label: 'Languages overview', group: 'Languages' },
    { id: 'coptic', label: 'Coptic', group: 'Languages' },
    { id: 'hebrew', label: 'Hebrew', group: 'Languages' },
    { id: 'persian', label: 'Persian', group: 'Languages' },
    { id: 'urdu', label: 'Urdu', group: 'Languages' },
    { id: 'arabic', label: 'Arabic', group: 'Languages' },
    { id: 'poetics', label: 'Poetic form: Persian, Urdu, Arabic', group: 'Languages' },

    { id: 'ai-guide', label: 'Use with your AI', group: 'Reference & tools' },
    { id: 'syntax-texts', label: 'Syntax', group: 'Reference & tools' },
    { id: 'best-practices', label: 'Search Tips', group: 'Reference & tools' },
    { id: 'repository', label: 'Repository', group: 'Reference & tools' },
    { id: 'faq', label: 'FAQ', group: 'Reference & tools' },
    { id: 'how-built', label: 'How the system is built', group: 'Reference & tools' },
    { id: 'feedback', label: 'Send Feedback', group: 'Reference & tools' }
  ];

  const submitFeedback = async (e) => {
    e.preventDefault();
    if (!feedbackMessage.trim()) {
      setFeedbackStatus({ type: 'error', text: 'Please enter your feedback' });
      return;
    }
    setFeedbackSubmitting(true);
    setFeedbackStatus(null);
    try {
      const data = await postJsonTo('/api/feedback', {
        name: feedbackName,
        email: feedbackEmail,
        type: feedbackType,
        message: feedbackMessage
      });
      if (data.success) {
        setFeedbackStatus({ type: 'success', text: 'Thank you for your feedback!' });
        setFeedbackMessage('');
      } else {
        setFeedbackStatus({ type: 'error', text: data.error || 'Failed to submit feedback' });
      }
    } catch (err) {
      setFeedbackStatus({ type: 'error', text: 'Failed to submit feedback' });
    }
    setFeedbackSubmitting(false);
  };

  // The same invitation under every language: the measured figures are a
  // first indication, the articles with full details are in preparation, and
  // specialists' feedback and help are wanted (2026-09-13).
  const Invitation = ({ language }) => (
    <p className="text-gray-600 text-sm mt-2 border-l-2 border-gray-300 pl-3">
      These figures are a first indication of how {language} search performs; articles with full
      details are in preparation. We would value the judgment of specialists in {language} on the
      results, and if you would like to help make it better, from a gold set of known parallels to a
      correction of the text, please{' '}
      <button type="button" onClick={() => setActiveSection('feedback')} className="text-red-700 hover:underline">
        write to us
      </button>.
    </p>
  );

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="flex flex-col md:flex-row">
        <nav className="md:w-64 p-4 bg-gray-50 border-b md:border-b-0 md:border-r">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Help Topics</h2>
          <ul className="space-y-1">
            {sections.filter((section) => section.id !== 'arabic' || arabicServed).map((section, i, shown) => (
              <li key={section.id}>
                {(i === 0 || shown[i - 1].group !== section.group) && (
                  // Group labels read as headings: darker and bolder than the items, a
                  // rule above each group, items indented under it (2026-10-07; the
                  // same fix was approved 2026-09-06 on a branch that never merged).
                  <p className={`px-3 pb-1 text-xs font-bold uppercase tracking-wider text-gray-700 ${i === 0 ? 'pt-1' : 'mt-3 pt-4 border-t border-gray-200'}`}>
                    {section.group}
                  </p>
                )}
                <button
                  onClick={() => setActiveSection(section.id)}
                  className={`w-full text-left pl-6 pr-3 py-1.5 rounded text-sm ${
                    activeSection === section.id
                      ? 'bg-red-100 text-red-700 font-semibold'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {section.label}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-4 pt-3 border-t border-gray-200 px-3 text-xs">
            <button
              type="button"
              onClick={() => setSuggestDialogOpen(true)}
              className="text-gray-500 hover:text-red-700 hover:underline"
            >
              Suggest a change
            </button>
          </p>
        </nav>

        <div ref={contentRef} className="flex-1 p-6">
          {activeSection === 'start-here' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Start here</h3>
              <p className="text-gray-700 mb-4">
                Tesserae finds passages that echo one another in Latin, Greek, English, Coptic, Hebrew, Persian and Urdu,
                whether through shared words, shared sounds, or a shared subject. It offers eight kinds of search, listed
                below in the order of the "What are you trying to do?" panel. The Search One Text page, where a visit starts,
                and the Intertextual Search page show that panel the first time you visit. Choosing an answer takes you to the
                right search, and "Skip" closes the panel for good. The "Start here" link at the top of every page brings it
                back, and Tessa gives the same list when you ask her where to start.
              </p>

              <div className="space-y-5">
                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Phrase Search</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Compares a source text with a target text and ranks the passages they share. The default match type is
                    Fusion, which combines eleven detection methods. Use it to discover allusions, quotations and echoes between
                    two works. See{' '}
                    <button onClick={() => setActiveSection('fusion-search')} className="text-red-600 hover:underline">Intertextual Search, how it works</button>{' '}
                    and{' '}
                    <button onClick={() => setActiveSection('match-types')} className="text-red-600 hover:underline">Match types</button>.
                  </p>
                </div>

                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Line Search</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Finds every line in the corpus that shares vocabulary with one line, chosen from a text or typed in. Match
                    on dictionary forms, on identical forms, or with a regular expression, and Greek may be typed with or without
                    accents. For example, "arma virumque cano" finds every line sharing "arma" and "vir". See{' '}
                    <button onClick={() => setActiveSection('match-types')} className="text-red-600 hover:underline">Match types</button>.
                  </p>
                </div>

                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Rare Words, Rare Pairs and String Search</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Rare Words lists words found in fewer than 50 texts that your two texts share, and Rare Pairs lists unusual
                    word pairs that few texts contain together. Both suggest direct borrowing or a stylistic fingerprint. Export CSV
                    saves the list you see, and Download everything (CSV) fetches every place each word occurs in the corpus, which
                    can be a large file. String Search looks for words, patterns and combinations across the whole corpus, with
                    wildcards and the operators AND, OR, NOT and proximity. The patterns are explained under{' '}
                    <button onClick={() => setActiveSection('match-types')} className="text-red-600 hover:underline">Match types</button>,
                    and{' '}
                    <button onClick={() => setActiveSection('best-practices')} className="text-red-600 hover:underline">Search Tips</button>{' '}
                    suggests when to try the rare-word modes.
                  </p>
                </div>

                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Theme Search</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Finds passages on a subject you describe in your own words, in every indexed language at once, even when they
                    share no vocabulary with your description. Use it when you do not know what words a scene is phrased in. See{' '}
                    <button onClick={() => setActiveSection('theme-search')} className="text-red-600 hover:underline">Theme Search</button>.
                  </p>
                </div>

                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Search One Text</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Asks one work what it says about a subject, in plain words. It is Theme Search run inside that one work, and
                    the closest passages come back. See{' '}
                    <button onClick={() => setActiveSection('ask-a-work')} className="text-red-600 hover:underline">Search One Text</button>.
                  </p>
                </div>

                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Reader</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Shows a text with a gutter marking where the rest of the corpus connects to each line, and a panel with those
                    connections, the translation and the scholarship on the passage. See{' '}
                    <button onClick={() => setActiveSection('reader')} className="text-red-600 hover:underline">The Reader</button>.
                  </p>
                </div>

                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">People &amp; Places</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Lists every line where a person, place or god is named, in Latin, Greek and English. See{' '}
                    <button onClick={() => setActiveSection('mentions')} className="text-red-600 hover:underline">People &amp; Places</button>.
                  </p>
                </div>

                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Collections</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Adds inscriptions, papyri, events, coins and museum objects, switched on from the top row. See{' '}
                    <button onClick={() => setActiveSection('site-controls')} className="text-red-600 hover:underline">Collections, Beta marks and other controls</button>.
                  </p>
                </div>
              </div>

              <h4 className="text-lg font-semibold text-gray-900 mt-8 mb-2">Choosing a language and two texts</h4>
              <p className="text-gray-700 mb-3">
                The Intertextual Search page has one tab for each language (Latin, Greek, English, Coptic, Hebrew, Persian and
                Urdu) and a Cross-Language tab for a pair of languages. Seven pairs are open. If a pair is ever held back for
                rebuilding, the page says so under the pair buttons and the pair returns when the rebuild is done. No pair is held
                at present. The author, work and book menus accept typing, so a few letters of a name will find it. Choose a{' '}
                <strong>source</strong>, usually the earlier text, and a <strong>target</strong> that may echo it, and click "Find Parallels". Results are
                ranked by confidence, with the matched words highlighted and badges showing which methods found each pair. See{' '}
                <button onClick={() => setActiveSection('cross-lingual')} className="text-red-600 hover:underline">Cross-Language Search</button>{' '}
                and{' '}
                <button onClick={() => setActiveSection('results')} className="text-red-600 hover:underline">Reading the results</button>.
              </p>
              <div className="mt-4 bg-amber-50 p-4 rounded-lg">
                <p className="text-amber-700 text-sm">
                  <strong>Tip.</strong> Start with a smaller section, such as Book 1. Large comparisons, such as the whole Aeneid
                  against the Metamorphoses, take longer on the first run, and later searches of the same pair are cached.
                </p>
              </div>
              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <p className="text-gray-700 text-sm">
                  <strong>Example:</strong> Compare Vergil's Aeneid Book 1 (source) with Lucan's Civil War Book 1 (target) to find how
                  Lucan echoes Vergil.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'views' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Literature and History views</h3>
              <p className="text-gray-700 mb-4">
                The site has two views, Literature and History, switched by the two words at the left of the
                main menu. Literature opens on Search One Text, on the Aeneid, with the menu led by
                Search One Text and Intertextual Search. History opens on Search One Text, on Tacitus&rsquo;s Annals, with its own examples (prodigies in Livy, forced
                suicides in the Annals, warning dreams in Herodotus, Gallic and German customs in Caesar, besieged cities in Thucydides, omens of an emperor's death in Suetonius), with
                every collection on, the menu led by Search One Text and Read, and the Reader&rsquo;s side panel opening on
                Similar, then the coins, the commentaries and articles, Reuse, Verbal and Translation (the inscriptions and papyri appear
                as a group inside Reuse and Verbal). History also opens the Phrase Search on Livy against Tacitus in Latin and on
                Herodotus against Thucydides in Greek, and puts the inscriptions, papyri and events first in the Start here list.
              </p>
              <p className="text-gray-700 mb-4">
                A view changes the order and the starting points. Every search and every collection can be reached
                in both views, and the Collections button beside the switch still turns collections on and off.
                Choosing a view moves you to its opening page, and the site remembers the choice in this browser.
                To send someone a link that opens in History, add <code>?view=history</code> to the address.
                On a phone the view switch is a single button showing the current view, and the Collections control sits inside its menu.
              </p>
            </div>
          )}

          {activeSection === 'site-controls' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Collections, Beta marks and other controls</h3>
              <p className="text-gray-700 mb-4">
                The Collections button at the left of the top row decides which source collections the site
                shows. Literature is always on. Inscriptions, Papyri, Coins, Objects and Scholarship each have a
                switch. The switches decide what a search covers and which Reader tabs show. They do not hide any page
                from the People, Places &amp; Things menu, which lists all five pages in both views.
                The Literature and History buttons beside it each set a profile (Literary for Literature and
                Everything for History), and the switches can then be changed one at a time. The choice is
                remembered in this browser.
              </p>
              <p className="text-gray-700 mb-4">
                A Beta mark beside a page name in the top row means the page is new and still changing. Its results
                are worth using, and worth citing with care, because the wording, grouping or ranking on the page
                may still change. At present Search One Text and Events carry the mark.
              </p>
              <p className="text-gray-700 mb-4">
                The Suggest a change button in the header, on every page, opens a short form. Use it to report a
                wrong grouping or any other problem, to ask for a text that is missing, or to ask for a feature.
                The address of the page you were on goes with your note. Contact details are optional and are never
                published. The Requests made so far link inside the form opens the public list of earlier requests.
              </p>
              <p className="text-gray-700 mb-4">
                The site remembers the last page and address you were on, in your browser only and never on the
                server, and opens there when you visit the plain address of the site. A link to a particular page
                still opens that page. The administration, Downloads, privacy and credits pages are not remembered.
              </p>
              <p className="text-gray-700 mb-4">
                The Downloads page is under More at the right end of the top row. It offers the corpus texts by
                language, pre-computed data files for running your own copy, and the benchmark lists.
              </p>
            </div>
          )}

          {activeSection === 'how-well' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">How well does it work?</h3>
              <p className="text-gray-700 mb-4">
                Every figure below was measured against a published list of parallels or a test set, and
                each is dated, because the corpus and the scoring change. Recall is the share of a
                list's known parallels that the search returns within a cutoff. It says how much a
                search finds, not how good its first page is. Where a search or a language has not
                been measured yet, the table says so. Articles with full details, methods and data are
                in preparation. The Coptic data release and the benchmark lists for Latin, Greek and
                Cross-Language are already on the Downloads page.
              </p>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm text-left text-gray-700">
                  <thead className="text-xs uppercase text-gray-500 border-b border-gray-200">
                    <tr><th className="py-2 pr-4">Search</th><th className="py-2 pr-4">Language</th><th className="py-2 pr-4">Measured against</th><th className="py-2 pr-4">Result</th><th className="py-2">Date</th></tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 align-top">
                    {allMeasuredRows().map((m, i) => (
                      <tr key={i}><td className="py-2 pr-4">{m.search}</td><td className="py-2 pr-4">{m.language}</td><td className="py-2 pr-4">{m.against}</td><td className="py-2 pr-4">{m.result}</td><td className="py-2">{m.date}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-gray-700 mt-4">
                A published list is a test of what the search finds, and the lists that exist
                were made by scholars looking for particular kinds of parallel, so a high figure on one
                list says little about another kind. The first page also matters more to a reader than the
                whole ranking, and the Latin and Coptic first-ten figures above are the closest thing to a
                precision measure so far, and a human-graded precision test is under way.
              </p>
              <Invitation language="these languages" />
            </div>
          )}

          {activeSection === 'fusion-search' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">How Fusion Search Works</h3>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-sm text-blue-900">
                <strong>A note on examples:</strong> this section, and the ones that follow, uses <strong>Latin</strong> for its
                examples, but the same process applies to Greek, English, Coptic, Hebrew, Persian and Urdu. Where a language
                differs, it is noted along the way. English has no syntax data and Greek has it for about half its texts, Coptic is
                tuned for quotation, and Persian and Urdu add a refrain-and-rhyme channel for the ghazal.
              </div>
              <p className="text-gray-700 mb-4">
                Tesserae's default search, <strong>Phrases</strong>, runs <strong>up to eleven independent detection channels</strong> and combines their results. Persian and Urdu
                run nine: eight of the eleven, all but the synonym dictionary and the two syntax channels, which need resources
                those languages do not yet have, plus a refrain-and-rhyme channel of their own.
                Each channel looks for a different kind of textual similarity, such as shared vocabulary, phonetic echo, semantic meaning,
                grammatical structure, and more. By fusing these signals, the system finds parallels that no single method could detect alone.
                The diagram below walks through the whole process step by step.
              </p>

              <FusionFlowchart />


              <p className="text-gray-700 mb-3">
                For a catalog of what each of the eleven channels detects, and how to run a single one on its own, see{' '}
                <button onClick={() => setActiveSection('match-types')} className="text-red-600 hover:underline">Match Types</button>.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">How Results Are Combined</h4>
              <p className="text-gray-700 mb-3">
                Each channel produces its own candidate list with scores. The fusion step combines them using <strong>weighted score fusion</strong>.
                Each channel's score is multiplied by a weight reflecting its precision, and the weighted scores are summed. Channels that produce
                fewer but more reliable results (like sound and edit distance) receive higher weights. The single-word lemma channel, which
                casts a wider net, receives a lower weight.
              </p>
              <p className="text-gray-700 mb-3">
                A <strong>convergence bonus</strong> rewards pairs found independently by multiple channels. If six out of eleven channels all
                flag the same pair of lines, that agreement is strong evidence of a real connection, stronger than any single channel's
                score alone. The convergence bonus is weighted by word rarity. Pairs sharing rare vocabulary get the full bonus,
                while pairs whose weakest word is very common receive a reduced bonus proportional to that word's frequency.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Rarity Scoring and Function-Word Handling</h4>
              <p className="text-gray-700 mb-3">
                Not all shared words carry equal weight as evidence of allusion. Sharing the rare word <em>quercus</em> ("oak")
                is far more significant than sharing <em>et</em> ("and"). Fusion scoring applies a <strong>three-layer rarity system</strong>:
              </p>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2 mb-3">
                <li><strong>IDF multiplier:</strong> Each result's score is scaled by the geometric mean of its matched words' corpus
                  rarity (inverse document frequency). Common-word pairs are reduced proportionally. Rare-word pairs are preserved or boosted.</li>
                <li><strong>Convergence weighting:</strong> The convergence bonus is gated by the rarest word's IDF. Pairs containing
                  a very common word receive less convergence credit, since multiple channels agreeing on a common word is expected, not meaningful.</li>
                <li><strong>Rarity boost:</strong> Rare multi-channel matches, where distinctive vocabulary is confirmed by several
                  independent channels, receive a bonus that promotes them above common-word results.</li>
              </ul>
              <p className="text-gray-700 mb-3">
                To cleanly separate function words from content words, the scoring uses a <strong>curated stoplist</strong> of
                function words for each language (91 Latin, 195 Greek, 275 English, with lists for Coptic, Hebrew, Persian and Urdu), such as pronouns,
                conjunctions, prepositions, and common verbs like <em>sum</em>, all shown on the Stoplists page.
                Matches where all shared words are function words (e.g., sharing only <em>tum</em> + <em>inde</em>) are heavily
                penalized. Matches where a function word co-occurs with a content word (e.g., <em>nec</em> + <em>priorem</em>)
                are scored on the content word alone, because the function word adds no allusion signal.
                This approach is more precise than pure frequency-based filtering, because it correctly penalizes <em>tum</em> (a function word)
                without penalizing <em>pectore</em> (a content word that happens to be common).
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Frequency Baseline</h4>
              <p className="text-gray-700 mb-3">
                By default, word rarity is measured against the <strong>full Latin corpus</strong>.
                This means a word like <em>arma</em> that appears in 57% of all Latin texts gets a low rarity score.
                But among hexameter poetry specifically, <em>arma</em> appears in 89% of texts, so it is
                metrically convenient filler, not a distinctive vocabulary choice.
              </p>
              <p className="text-gray-700 mb-3">
                The <strong>Same meter</strong> frequency baseline (available under Advanced Settings for Latin fusion searches)
                computes rarity against only texts in the same metrical tradition (hexameter, elegiac, lyric, dramatic, or prose).
                This deflates vocabulary that is conventional within a meter while preserving the rarity of genuinely distinctive words.
                For example, when comparing two hexameter poems, <em>Neptunia proles</em> ("Neptune's offspring"), a standard
                epic epithet, receives less of a rarity boost under hexameter IDF, while a word rare even in hexameter
                retains its premium.
              </p>
              <p className="text-gray-700 mb-3 text-sm">
                The system automatically rescales meter-specific IDF values so that the scoring thresholds
                remain consistent regardless of which baseline you choose. Switching baselines does not affect recall. The
                same pairs are found, but it changes how they are ranked.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Sliding Windows</h4>
              <p className="text-gray-700 mb-3">
                Poets don't always confine allusions to a single line. To catch vocabulary split across line breaks (enjambment),
                the system also searches <strong>two-line sliding windows</strong>, each consecutive pair of lines merged into one unit.
                Window results that are genuinely new are appended after line-mode results, adding recall without diluting precision.
              </p>

              <div className="mt-6 bg-gray-50 p-4 rounded-lg">
                <h4 className="text-lg font-semibold text-gray-900 mb-2">Performance</h4>
                <p className="text-gray-700 text-sm">
                  Evaluated against five benchmark datasets (862 parallels from published commentaries), fusion search found <strong>92% of known Latin parallels</strong> in August 2026,
                  up from ~27% in Tesserae V3. That figure was measured before the Latin lemma table was corrected in October 2026 and has not been re-run since. Other languages are measured separately, on the How well does it work? page. On the Valerius Flaccus benchmark, 9 of the top 10 results are attested in scholarly commentary.
                </p>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 className="text-lg font-semibold text-gray-900 mb-2">The settings behind these results</h4>
                <p className="text-gray-700 text-sm">
                  Every choice this page summarizes is written down in full, with the measurement behind it:
                  what each channel does and how word rarity is judged in{' '}
                  <a href="https://github.com/tesserae/tesserae-v6/blob/main/docs/HOW_TESSERAE_SEARCHES.md"
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-700 underline hover:text-red-800">How Tesserae Searches</a>,
                  how the channels are weighted and combined in{' '}
                  <a href="https://github.com/tesserae/tesserae-v6/blob/main/docs/FUSION_ARCHITECTURE.md"
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-700 underline hover:text-red-800">Fusion Architecture</a>,
                  and why each setting is what it is, dated and with the numbers that decided it, in the{' '}
                  <a href="https://github.com/tesserae/tesserae-v6/blob/main/docs/DECISIONS.md"
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-700 underline hover:text-red-800">decisions log</a>.
                </p>
              </div>

              <div className="mt-4 bg-amber-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-amber-800 mb-2">Individual Channels</h4>
                <p className="text-amber-700 text-sm">
                  You can also run individual channels (Lemma, Exact, Semantic, etc.) by changing the Match Type dropdown.
                  This is useful when you want to isolate a specific kind of similarity, but fusion is recommended for general use.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'match-types' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Match Types</h3>
              <p className="text-gray-700 mb-4">
                The default Phrases search runs all channels together (<strong>Fusion</strong>). You can also run a
                <strong> single method</strong> on its own (choose it from the Match Type dropdown) when you want just one kind of
                match, such as only exact quotations or only sound. Here is what each method (channel) detects:
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">The Detection Channels</h4>
              <div className="space-y-3">
                <div className="border-l-4 border-gray-300 pl-3">
                  <p className="text-sm text-gray-700"><strong>Lemma (2-word):</strong> The classic Tesserae approach, which finds lines sharing two or more content-word dictionary forms. The workhorse channel for direct verbal echo.</p>
                </div>
                <div className="border-l-4 border-gray-300 pl-3">
                  <p className="text-sm text-gray-700"><strong>Lemma (1-word):</strong> Same method, but requires only one shared word. Catches allusions built around a single pivotal term, like Lucan's <em>canimus</em> echoing Vergil's <em>cano</em>.</p>
                </div>
                <div className="border-l-4 border-gray-300 pl-3">
                  <p className="text-sm text-gray-700"><strong>Exact:</strong> Matches identical surface forms (not lemmatized). Catches verbatim quotation and formulaic borrowing.</p>
                </div>
                <div className="border-l-4 border-gray-300 pl-3">
                  <p className="text-sm text-gray-700"><strong>Semantic (AI):</strong> Uses SPhilBERTa neural embeddings to detect lines with similar meaning, even with completely different vocabulary.</p>
                </div>
                <div className="border-l-4 border-gray-300 pl-3">
                  <p className="text-sm text-gray-700"><strong>Dictionary:</strong> Detects synonym substitution (<em>uariatio</em>) using about 29,500 curated Latin word pairs, such as <em>gladius/ensis</em>, <em>mare/pontus</em>.</p>
                </div>
                <div className="border-l-4 border-gray-300 pl-3">
                  <p className="text-sm text-gray-700"><strong>Sound:</strong> Measures phonetic similarity via character trigram patterns. Detects alliteration, assonance, and phonetic echo.</p>
                </div>
                <div className="border-l-4 border-gray-300 pl-3">
                  <p className="text-sm text-gray-700"><strong>Edit Distance:</strong> Fuzzy character-level matching for morphological variants, with <em>ferrea</em> matching <em>ferratos</em>, <em>belligeri</em> matching <em>belli</em>.</p>
                </div>
                <div className="border-l-4 border-gray-300 pl-3">
                  <p className="text-sm text-gray-700"><strong>Syntax:</strong> Compares grammatical dependency structures (parsed by LatinPipe) to detect parallel sentence construction. Includes a structural fingerprint path that matches lines with identical grammatical patterns even when they share no vocabulary, which catches allusions built on structural imitation with complete lexical substitution. Because many unrelated Latin lines share common syntactic patterns, structural matches are confirmed by a two-tier gate: they must have either a dictionary synonym pair between the two lines or high semantic similarity (cosine ≥ 0.70). In validation testing on Vergil's <em>Georgics</em> 3 vs. Lucretius <em>DRN</em> 6, this gate preserved all meaningful structural parallels while filtering over 90% of coincidental pattern matches.</p>
                </div>
                <div className="border-l-4 border-gray-300 pl-3">
                  <p className="text-sm text-gray-700"><strong>Rare Vocabulary:</strong> Flags shared words that appear in fewer than about one in eight works of the language (roughly 100 for Latin and Greek, 6 for English). A rare shared word is unlikely to be coincidence.</p>
                </div>
                <div className="border-l-4 border-gray-300 pl-3">
                  <p className="text-sm text-gray-700"><strong>Verbatim Quotation:</strong> Finds runs of three or more identical consecutive words, in every language. It carries the most weight of any channel, because an exact run is the strongest sign of quotation, and it matters most where authors quote their sources directly, as Coptic writers quote scripture without citation. See the <em>Coptic Search</em> section for an example.</p>
                </div>
              </div>
              <p className="text-gray-600 text-sm mt-3">
                Which channels run depends on the data a language has. The synonym dictionary needs a synonym list and the syntax channels need grammatical parses. Each language's page says which it has.
              </p>

              <p className="text-gray-700 mb-4">
                <strong>Line Search</strong> offers three match types: <strong>Lemma</strong> (dictionary forms), <strong>Exact</strong>
                (identical surface forms), and <strong>Regular expression</strong> (patterns &mdash; see below).
              </p>

              <p className="text-gray-700 mb-4">
                In Latin Lemma mode, a word that editors print either joined or apart (<em>quousque</em> or <em>quo usque</em>,
                <em> respublica</em> or <em>res publica</em>) is matched both ways, from a fixed list of about twenty such words.
                A line that prints the joined word answers a query that types the parts, the joined word is highlighted when it does,
                and a query that types the joined word finds lines that print the parts side by side.
              </p>

              <div className="mt-6 border-t pt-4" id="regex-help">
                <h4 className="text-lg font-semibold text-gray-900 mb-2">Regular Expressions (Line Search)</h4>
                <p className="text-gray-600 text-sm mb-3">
                  In Line Search mode, the <strong>Regular expression</strong> option lets you search with patterns instead of
                  literal text. A regular expression (or "regex") is a sequence of characters that defines a search pattern.
                  This is a powerful tool for finding words with variant spellings, partial forms, or structural patterns.
                </p>
                <div className="bg-gray-50 p-3 sm:p-4 rounded-lg text-sm space-y-2 overflow-x-auto">
                  <p className="font-medium text-gray-800">Common patterns:</p>
                  <table className="w-full text-left text-xs sm:text-sm">
                    <tbody className="divide-y divide-gray-200">
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">arm.</td><td className="py-1 text-gray-600">Matches "arma", "arms", "army". The dot matches any single character</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">amor|bellum</td><td className="py-1 text-gray-600">Matches lines containing "amor" OR "bellum"</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">ferr[aeiou]</td><td className="py-1 text-gray-600">Matches "ferra", "ferre", "ferri", "ferro", "ferru". Brackets match any one character listed</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">^arma</td><td className="py-1 text-gray-600">Matches "arma" only at the start of a line</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">cano$</td><td className="py-1 text-gray-600">Matches "cano" only at the end of a line</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">reg(is|em|i|e)</td><td className="py-1 text-gray-600">Matches "regis", "regem", "regi", "rege". Parentheses group alternatives</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">.*pietas.*arma.*</td><td className="py-1 text-gray-600">Matches any line containing "pietas" followed later by "arma". The pattern <code>.*</code> means "any characters"</td></tr>
                    </tbody>
                  </table>
                </div>
                <p className="text-gray-500 text-sm mt-2">
                  Regex search checks each line in the corpus for a match against your pattern.
                  It does not use lemmatization, and patterns match against the actual text as it appears.
                </p>
              </div>

              <div className="mt-6 border-t pt-4" id="string-search-help">
                <h4 className="text-lg font-semibold text-gray-900 mb-2">String Search patterns</h4>
                <p className="text-gray-600 text-sm mb-3">
                  String Search uses wildcards and boolean operators across the entire corpus, to find
                  specific words, word patterns or co-occurrences.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-sm">
                    <div className="bg-amber-50 p-3 rounded border border-amber-200">
                      <strong className="text-amber-800">Wildcards</strong>
                      <ul className="text-gray-600 mt-1 space-y-1">
                        <li><code className="bg-amber-100 px-1 rounded">*</code> - any characters (am* = amor, amicus...)</li>
                        <li><code className="bg-amber-100 px-1 rounded">?</code> - single character (?or = cor, for, mor)</li>
                        <li><code className="bg-amber-100 px-1 rounded">#</code> - word break (am# = am but not amor)</li>
                      </ul>
                    </div>
                    <div className="bg-amber-50 p-3 rounded border border-amber-200">
                      <strong className="text-amber-800">Boolean Operators</strong>
                      <ul className="text-gray-600 mt-1 space-y-1">
                        <li><code className="bg-amber-100 px-1 rounded">AND</code> - both words required</li>
                        <li><code className="bg-amber-100 px-1 rounded">OR</code> - either word matches</li>
                        <li><code className="bg-amber-100 px-1 rounded">NOT</code> - exclude a word</li>
                        <li><code className="bg-amber-100 px-1 rounded">~</code> - proximity (~100 chars apart)</li>
                      </ul>
                    </div>
                  </div>
                  <div className="bg-gray-50 p-3 rounded mt-3 text-sm">
                    <strong>Examples:</strong>
                    <ul className="mt-1 space-y-1 text-gray-600">
                      <li><code className="bg-gray-200 px-1 rounded">arma ~ virum</code> - finds "arma" within ~100 characters of "virum"</li>
                      <li><code className="bg-gray-200 px-1 rounded">mort* NOT vita</code> - words starting with "mort" but not in lines with "vita"</li>
                    </ul>
                  </div>
              </div>
            </div>
          )}

          {activeSection === 'settings' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Search Settings</h3>
              <div className="bg-amber-50 p-4 rounded-lg border border-amber-200 mb-4">
                <p className="text-amber-700 text-sm">
                  <strong>Note:</strong> In Fusion mode (the default), most settings below are managed automatically by the
                  eleven channels. Settings like Minimum Matches, Max Distance, and Stoplist apply when running individual match types.
                </p>
              </div>
              <dl className="space-y-4">
                <div>
                  <dt className="font-medium text-gray-900">Minimum Matches</dt>
                  <dd className="text-gray-600 text-sm mt-1">
                    Require at least N shared words (default: 2). Higher values find stronger parallels but fewer results.
                    In Fusion mode, each channel applies its own threshold (e.g., lemma requires 2, lemma-1-word requires 1).
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Max Distance</dt>
                  <dd className="text-gray-600 text-sm mt-1">
                    Maximum word span between matched terms within a line. Use 999 for no limit.
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Stoplist</dt>
                  <dd className="text-gray-600 text-sm mt-1">
                    Filter common words like "et", "in", "est" to reduce noise. The default setting combines
                    curated function words with automatic high-frequency detection.
                    <button
                      onClick={() => setActiveSection('stoplists')}
                      className="text-red-600 hover:underline ml-1"
                    >
                      See Stoplists section for details →
                    </button>
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Formulas</dt>
                  <dd className="text-gray-600 text-sm mt-1">
                    A result's shared words can repeat a set phrase, like a biblical narrative formula,
                    rather than a one-off echo. The Formulas setting can hide parallels whose shared
                    wording recurs in more than a chosen number of corpus works, or show only those.
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Unit Type (Line/Phrase)</dt>
                  <dd className="text-gray-600 text-sm mt-1">
                    Compare by poetic lines (default) or prose sentences. Phrase mode splits on punctuation.
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Max Results</dt>
                  <dd className="text-gray-600 text-sm mt-1">
                    Maximum number of results to return. The default, 0, returns them all.
                    For most comparisons, the top 5,000 results capture all significant parallels.
                  </dd>
                </div>
              </dl>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Advanced: Channels &amp; weights</h4>
              <p className="text-gray-700 text-sm mb-3">
                The Phrases (fusion) search blends several detection methods, called <em>channels</em> (shared words,
                sound, meaning, syntax, rare vocabulary, and more). Under <strong>Search Settings → Advanced →
                Channels &amp; weights</strong> you can tune how much each channel counts, or switch channels off
                entirely. Leaving this untouched uses Tesserae's tuned defaults, so your results are unchanged unless
                you deliberately adjust it.
              </p>
              <div className="bg-blue-50 p-4 rounded border border-blue-200">
                <dl className="space-y-3">
                  <div>
                    <dt className="font-medium text-gray-900">Weights</dt>
                    <dd className="text-gray-600 text-sm mt-1">
                      Raise or lower how much each channel contributes to a result's score. A higher weight makes that
                      kind of similarity count for more. The numbers are relative, not percentages.
                    </dd>
                  </div>
                  <div>
                    <dt className="font-medium text-gray-900">On / off switches</dt>
                    <dd className="text-gray-600 text-sm mt-1">
                      Turn a channel off to exclude it from the search entirely, for example to look for parallels
                      using only sound and syntax. Switching a channel <em>off</em> is different from setting its weight
                      to zero: a channel at weight 0 still runs and can pull a pair into the results when it agrees with
                      other channels, whereas an off channel does not run at all.
                    </dd>
                  </div>
                  <div>
                    <dt className="font-medium text-gray-900">Only the channels that apply</dt>
                    <dd className="text-gray-600 text-sm mt-1">
                      The panel shows only the channels available for your chosen language. For instance, English does
                      not show the syntax or dictionary channels, since those rely on data Tesserae doesn't have for English.
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          )}

          {activeSection === 'stoplists' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Stoplists</h3>
              <p className="text-gray-700 mb-4">
                {STOPLIST_INFO.description}
              </p>
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 mb-4">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">Stoplists in Fusion Mode</h4>
                <p className="text-gray-700 text-sm">
                  In Fusion mode, stoplists play a dual role. Individual channels run without stoplist filtering (to maximize recall),
                  but the <strong>fusion scoring layer</strong> uses the curated function-word stoplist to identify and penalize
                  matches built entirely on function words. This means that sharing <em>tum</em> + <em>nec</em> will be ranked
                  far below sharing <em>pectore</em> + <em>curas</em>, even though both are two-word matches. The stoplist gives
                  the scoring system a precise way to distinguish grammatical co-occurrence from genuine allusion.
                </p>
              </div>
              
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">How the Default Stoplist Works</h4>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-1 ml-2">
                {STOPLIST_INFO.howItWorks.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Curated Stop Words by Language</h4>
              <p className="text-gray-600 text-sm mb-3">
                Expand a language to see every curated entry. Greek entries are shown in polytonic (accented) form.
                The matcher itself filters on the accentless normalized form. Hebrew entries are consonantal (no vowel
                points), as the matcher compares them.
              </p>
              {curatedStoplists === null && !stoplistsError ? (
                <p className="text-sm text-gray-500" role="status">Loading the current curated stoplists…</p>
              ) : stoplistsError ? (
                <p className="text-sm text-red-700" role="alert">
                  The current curated stoplists could not be loaded. Please try again later.
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3">
                  {curatedStoplists.map(({ key, language, label, data }) => {
                    const isExpanded = Boolean(expandedStoplists[key]);
                    return (
                      <div key={key} className="bg-gray-50 rounded-lg p-3">
                        <div className="flex items-center justify-between gap-2">
                          <h5 className="font-medium text-gray-800">{label} ({data.words.length} words)</h5>
                          <button
                            type="button"
                            className="text-xs font-medium text-blue-700 hover:text-blue-900 whitespace-nowrap"
                            onClick={() => toggleStoplist(key)}
                            aria-expanded={isExpanded}
                            aria-controls={`${key}-curated-stoplist`}
                          >
                            {isExpanded ? 'Hide full list' : 'Show full list'}
                          </button>
                        </div>
                        {isExpanded ? (
                          <div
                            id={`${key}-curated-stoplist`}
                            className="mt-3 max-h-72 overflow-y-auto rounded border border-gray-200 bg-white p-2"
                          >
                            <div
                              className="flex flex-wrap gap-1"
                              aria-label={`Full curated ${label} stoplist`}
                              lang={language}
                              dir={data.dir}
                            >
                              {data.words.map((word, i) => (
                                <code key={word} className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
                                  {data.display?.[i] ?? word}
                                </code>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="text-xs text-gray-500 italic mt-1" lang={language} dir={data.dir}>
                            {(data.display ?? data.words).slice(0, 13).join(', ')}...
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Stoplist Options</h4>
              <dl className="space-y-3">
                <div>
                  <dt className="font-medium text-gray-700 text-sm">Default</dt>
                  <dd className="text-gray-600 text-sm">{STOPLIST_INFO.options.default}</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-700 text-sm">Manual number</dt>
                  <dd className="text-gray-600 text-sm">{STOPLIST_INFO.options.manual}</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-700 text-sm">Disabled (-1)</dt>
                  <dd className="text-gray-600 text-sm">{STOPLIST_INFO.options.disabled}</dd>
                </div>
              </dl>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Stoplist Basis</h4>
              <p className="text-gray-600 text-sm">
                Choose which text(s) to analyze for building the stoplist:
              </p>
              <ul className="list-disc list-inside text-gray-600 text-sm mt-2 ml-2 space-y-1">
                <li><strong>Source + Target</strong>: Uses word frequencies from both texts (recommended)</li>
                <li><strong>Source Only</strong>: Only considers frequencies in the source text</li>
                <li><strong>Target Only</strong>: Only considers frequencies in the target text</li>
                <li><strong>Full Corpus</strong>: Uses pre-computed frequencies from all texts in the corpus</li>
              </ul>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Custom Stopwords</h4>
              <p className="text-gray-600 text-sm">
                Add your own comma-separated list of words to exclude from matching. 
                These are added to whatever stoplist you've configured above.
              </p>
              <p className="text-gray-600 text-sm mt-2 font-medium">
                {STOPLIST_INFO.customStopwordsNote}
              </p>
            </div>
          )}

          {activeSection === 'results' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Reading the results</h3>
              <p className="text-gray-600 text-sm mb-4">
                Every badge on a result card opens a short explanation on hover, focus, or tap. This
                page gives the fuller version of each one.
              </p>
              <p className="text-gray-600 text-sm mb-4">
                One citation of Tesserae per publication is enough. Individual parallels do
                not need their own. See{' '}
                <button
                  type="button"
                  onClick={() => window.dispatchEvent(new CustomEvent('tesserae:open-how-to-cite'))}
                  className="text-red-600 hover:underline"
                >
                  How to cite Tesserae
                </button>.
              </p>
              <div className="space-y-4">
                <div id="score">
                  <h4 className="text-lg font-semibold text-gray-900">Score</h4>
                  <p className="text-gray-600 text-sm mb-2">
                    The score combines every channel that found the match into one ranking number. A higher
                    score is a stronger candidate for a real textual connection, but it is a ranking aid, not
                    a verdict. The scoring method depends on the search mode:
                  </p>
                  <div className="bg-red-50 p-3 rounded border border-red-200 mb-2">
                    <p className="text-sm text-gray-700">
                      <strong>Fusion mode (default):</strong> Each channel produces its own score, which is multiplied by a
                      channel-specific weight and summed. A <em>convergence bonus</em> rewards pairs detected by multiple
                      independent channels. The combined score is then scaled by the <em>rarity</em> of the matched vocabulary.
                      Pairs sharing rare content words score higher than pairs sharing common function words. A curated
                      stoplist of function words (like <em>et</em>, <em>tum</em>, <em>nec</em>) ensures that grammatical
                      co-occurrence does not inflate scores.
                    </p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded mb-2">
                    <p className="text-sm text-gray-700">
                      <strong>Individual channels:</strong> V3-style scoring using IDF (rare words score higher),
                      distance penalty (closer matched words score higher), and match count.
                    </p>
                  </div>
                  <p className="text-gray-600 text-sm mb-2">
                    The score ranks the results of a single search from most to least likely to be a real
                    connection. Read the list from the top and stop where the results stop being useful.
                    The order, and the point where the scores fall off, matter more than the exact number.
                  </p>
                  <div className="bg-red-50 p-3 rounded border border-red-200 mb-2">
                    <p className="text-sm text-gray-700">
                      <strong>The score is relative, not absolute.</strong> A score is only meaningful within
                      the search that produced it. There is no fixed number above which a result is
                      &ldquo;good,&rdquo; and a 5 in one comparison is not the same as a 5 in another, because
                      the score is calibrated to the particular pair of texts and to how common their
                      vocabulary is across the corpus. Look at the ranking and the shape of the drop-off
                      within your own search rather than for a universal cutoff.
                    </p>
                  </div>
                  <ul className="list-disc list-inside text-gray-600 text-sm mt-1 ml-4">
                    <li>Start at the top and read down. The results are ordered strongest first.</li>
                    <li>Watch for where the scores fall off. Above that point you are usually looking at
                        shared rare vocabulary and agreement across several channels. Below it you are
                        mostly looking at coincidental overlaps of common words, including function words
                        like conjunctions and pronouns.</li>
                    <li>Judge the passages, not the number. Tesserae finds candidates. Whether a parallel is
                        a real allusion, an echo, a shared formula, or a coincidence is a scholarly judgment
                        you make by reading the two passages in context.</li>
                  </ul>
                </div>
                <div id="channels">
                  <h4 className="text-lg font-semibold text-gray-900">Channels and channel badges</h4>
                  <p className="text-gray-600 text-sm">
                    Tesserae finds a match through one or more independent channels: shared
                    dictionary forms, identical words, sound, meaning, and the others described in{' '}
                    <button onClick={() => setActiveSection('fusion-search')} className="text-red-600 hover:underline">Intertextual Search, how it works</button>.
                    Agreement between independent channels is stronger evidence of a real
                    connection than any one channel alone. In Fusion mode, each result displays colored
                    badges showing which channels detected it, grouped by category:
                  </p>
                  <ul className="list-disc list-inside text-gray-600 text-sm mt-1 ml-4">
                    <li><span className="text-red-600 font-medium">Red</span>: Vocabulary channels (lemma, exact, dictionary, rare word)</li>
                    <li><span className="text-blue-600 font-medium">Blue</span>: Semantic channels (AI semantic)</li>
                    <li><span className="text-amber-600 font-medium">Amber</span>: Sound channels (sound, edit distance)</li>
                    <li><span className="text-purple-600 font-medium">Purple</span>: Structure channels (syntax)</li>
                  </ul>
                </div>
                <div id="works-count">
                  <h4 className="text-lg font-semibold text-gray-900">In N works</h4>
                  <p className="text-gray-600 text-sm">
                    This gray badge counts how many works in the whole corpus contain the shared wording
                    a result is built on. A high count marks a common expression or formula rather
                    than a pointed echo. The Formulas setting under Search Settings can hide results
                    built on wording that recurs in more than a chosen number of works, or show only them.
                  </p>
                </div>
                <div id="theme">
                  <h4 className="text-lg font-semibold text-gray-900">Theme</h4>
                  <p className="text-gray-600 text-sm">
                    This badge compares how alike two specific lines are in content against how
                    alike the two works are overall. A positive number means the lines resemble
                    each other in theme more than two random lines from the same two works would,
                    independent of the wording-based channels above.
                  </p>
                </div>
                <div id="refrain">
                  <h4 className="text-lg font-semibold text-gray-900">Refrain (radif)</h4>
                  <p className="text-gray-600 text-sm">
                    The refrain, or radif, is a word or short phrase repeated at the end of many
                    lines in both poems. Persian and Urdu ghazals often carry a refrain through the
                    whole poem, so two poems sharing one is good evidence that one answers or
                    echoes the other.
                  </p>
                </div>
                <div id="rhyme">
                  <h4 className="text-lg font-semibold text-gray-900">Rhyme (qafiya)</h4>
                  <p className="text-gray-600 text-sm">
                    The rhyme, or qafiya, is the syllable or word right before the refrain that
                    every line in a poem rhymes on. When only the final consonant matches rather
                    than the full syllable, the badge reads as a rhyme letter, or rawi, which is
                    weaker evidence.
                  </p>
                </div>
                <div id="meter">
                  <h4 className="text-lg font-semibold text-gray-900">Meter</h4>
                  <p className="text-gray-600 text-sm">
                    A shared named meter label is common on its own and proves little by itself.
                    Combined with a shared refrain or rhyme, it strengthens the case that one poem
                    answers the other. A separate metrical confirmation badge checks the two lines'
                    scansion directly, independent of which words they share.
                  </p>
                </div>
                <div id="refrain-lines">
                  <h4 className="text-lg font-semibold text-gray-900">Refrain lines</h4>
                  <p className="text-gray-600 text-sm">
                    A shared refrain usually recurs across many lines in both poems, not just the
                    one pair shown. This badge lists every line, from both works, where the two
                    poems carry the same refrain, so one result can stand for the whole set rather
                    than repeating it line by line.
                  </p>
                </div>
                <div id="form-count">
                  <h4 className="text-lg font-semibold text-gray-900">Form in N poems</h4>
                  <p className="text-gray-600 text-sm">
                    This badge counts how many poems in the whole corpus end on the same refrain
                    and rhyme as this result. A high count marks a common form that many poets
                    used, rather than one poem specifically answering another, and the score is
                    discounted accordingly. See{' '}
                    <button onClick={() => setActiveSection('poetics')} className="text-red-600 hover:underline">Poetic form</button>.
                  </p>
                </div>
                <div id="highlight-colors">
                  <h4 className="text-lg font-semibold text-gray-900">Highlight colors</h4>
                  <ul className="list-disc list-inside text-gray-600 text-sm mt-1">
                    <li><span className="bg-yellow-200 px-1 rounded">Yellow</span> marks a word both lines share: a matched lemma, an exact word, or a shared refrain.</li>
                    <li><span className="bg-indigo-200 px-1 rounded">Indigo</span> marks a synonym match (dictionary or semantic similarity).</li>
                    <li><span className="bg-rose-200 px-1 rounded">Rose</span> marks each line's rhyme word, the word right before the refrain. The two sides rhyme the same way but are usually different words.</li>
                  </ul>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">Actions</h4>
                  <ul className="list-disc list-inside text-gray-600 text-sm mt-1">
                    <li><strong>Export CSV</strong>: Download all results as a spreadsheet</li>
                    <li><strong>Search Corpus</strong>: Find these matched words across all texts</li>
                    <li><strong>Register</strong>: Save to the Intertext Repository</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'theme-search' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Theme Search</h3>
              <p className="text-gray-700 mb-4">
                Describe what happens in a passage, in your own words, and Theme Search finds
                passages that match the description rather than the wording. Because it works
                from content, results come back in every indexed language at once and usually
                share no vocabulary with what you typed, or with each other. The comparison is
                between your description and a short description written for each passage. A
                passage whose description also shares words with yours gets a small extra
                credit, which helps when a scene is described in the same terms you used. How the
                descriptions are written and compared is under{' '}
                <button onClick={() => setActiveSection('how-built')} className="text-red-600 hover:underline">How the system is built</button>.
              </p>
              <p className="text-gray-700 mb-4">
                Results open with the strongest matches first. A toggle switches to oldest-first
                for tracing a theme through time. Show more results extends the list in steps of
                25, and narrowing to one language shows more of that language. Two phrasing tips:
                naming names (&ldquo;Abraham sacrifices Isaac&rdquo;) finds a specific story, while
                generic phrasing (&ldquo;a parent sacrifices a child&rdquo;) finds the scene type
                across traditions.
              </p>
              <p className="text-gray-700 mb-4" id="theme-scholarship">
                When Scholarship is on in Collections, Theme Search offers a Scholarship choice
                beside the other collection choices. It searches the commentary notes and the
                journal sentences from the citation index and shows its own list, never mixed into
                the passage results. A note links to its passage in the Reader and a sentence from an
                article links to the article. Under the list, a Books and articles found online section asks OpenAlex,
                Crossref, CORE, Google Books and Semantic Scholar for articles whose title or
                abstract matches your words, from any year, and shows each service's answer as it arrives.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Names and paraphrases</h4>
              <p className="text-gray-700 mb-3">
                The descriptions name the people in a passage, so a name is precise and a
                paraphrase is broad. &ldquo;Tiresias&rdquo; finds the passages where he
                appears, while &ldquo;an old man prophesying&rdquo; finds prophets of every kind and
                can miss the ones the description calls by name. The same holds for places
                and gods. A query that names a category rather than a scene, such as
                &ldquo;recognition&rdquo; or &ldquo;reversal of fortune&rdquo;, matches little,
                because the descriptions record what happens. Say instead what happens on the
                page, for example &ldquo;a character learns the true identity of a stranger who
                turns out to be kin&rdquo;. When a search finds less than you expect, try the
                name, then the scene in its own words.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Which works Theme Search covers</h4>
              <p className="text-gray-700 mb-3">
                Theme Search and Similar Passages cover the works that have passage descriptions, about
                1,990 works and 685,000 passage windows, not the whole corpus. A work outside that
                index never appears in either feature. The list is in Browse Corpus:{' '}
                <a href="/corpus?theme=1&language=la" className="text-red-600 hover:underline">
                  See the list of covered works
                </a>. A small &ldquo;Theme Search&rdquo; badge marks each covered work there.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">The Similarity Map</h4>
              <p className="text-gray-700 mb-3">
                The &ldquo;Similarity Map&rdquo; tab beside Theme Search is a grid of how strongly authors, works, centuries
                or genres connect to one another, built from the same description comparison
                Theme Search and Similar Passages use. A dark cell means
                many passages of the two authors came out close in their descriptions. Authors
                run in chronological order along both edges, so the diagonal shows authors talking to their
                contemporaries and the far corners show links across the centuries.
              </p>
              <p className="text-gray-700 mb-3">
                &ldquo;Links&rdquo; colors a cell by the raw number of close passage pairs.
                &ldquo;Relative to size&rdquo; divides that number by what the two authors&rsquo; sizes alone
                would predict, which is the better view for spotting a small author who is unexpectedly
                close to another. Translation pairs, such as the Vulgate and the Septuagint, are hidden by
                default because that signal is so much stronger than allusion, and a switch shows them.
                Clicking a cell opens the pair work by work, then book by book, then passage by passage,
                and a passage pair opens in the Reader. The browser&rsquo;s Back button unwinds these steps one at a time.
                The map is computed in advance and stored. A line under the grid gives the date it was built,
                and &ldquo;Refresh map&rdquo; reloads it.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Comparing two works</h4>
              <p className="text-gray-700 mb-3">
                The &ldquo;Compare two works&rdquo; tab beside the search box reads two whole
                works, or two books, against each other rather than against a description you
                write. Pick a work on each side and the page finds which of their passage
                windows resemble each other most in content, across languages as well. A
                &ldquo;strong&rdquo; mark on a pair means it stands well above the two
                works&rsquo; general resemblance to each other, and the confidence line above
                the results says whether the two works genuinely echo one another or only
                resemble each other the ordinary amount most texts do. When a word-level search
                of the same two works has already been run, each pair also lists the shared
                wording found inside it.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Reading the results</h4>
              <ul className="list-disc pl-5 text-gray-700 space-y-2 mb-3">
                <li>
                  <strong>Results are ordered oldest first</strong> when that toggle is on, with the author&rsquo;s date at
                  the left, so you can see a subject move through time. Undated authors are
                  listed last.
                </li>
                <li>
                  <strong>Several passages from one work are grouped under it.</strong> The work is
                  named once. Each passage keeps its own reference and summary.
                </li>
                <li>
                  <strong>Click a reference</strong> to open the passage in the Reader, with the
                  translation panel open and your search shown above the text.
                </li>
                <li>
                  <strong>The confidence band</strong> at the top estimates whether the corpus
                  really contains what you asked for.
                </li>
                <li>
                  <strong>&ldquo;Weak neighbor&rdquo; beside a passage</strong> says that this one passage, on its own,
                  does not stand clearly above the corpus average. A strong band over a list of weak
                  neighbors is a common and meaningful outcome: the corpus holds the subject, but it is
                  spread across many passages of ordinary closeness rather than concentrated in one
                  outstanding hit. In the Persian and Urdu ghazal corpora, where longing, love and
                  separation recur in almost every poem, that is the usual shape of an answer.
                </li>
              </ul>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">What the confidence band means</h4>
              <p className="text-gray-700 mb-3">
                A search always returns its closest matches, even when the corpus holds nothing
                of the kind, so the band tells you which situation you are in. It combines how
                far the best result stands above the corpus average with how much the top
                results resemble each other. A real subject returns a cluster. An absent one
                returns scattered strays. The band is a rough guide, right about three times in four on
                test questions, and the passages themselves are the check. A strong band means the corpus
                probably holds the subject, not that every listed passage is about it. The lowest band,
                labeled &ldquo;Closest passages&rdquo;, means that the top results do not stand far above the
                background, so their order is less settled.
              </p>
              <p className="text-gray-700 mb-3">
                The list is shown whatever the band says. The band tells a real subject from nonsense,
                which is what it was fitted on, and does not tell a good list from a poor one. The one case
                still held back is a search nothing in the corpus resembles at all. A query none of whose
                words occurs in any passage description is told so and gets no list, and if only some of
                its words are unknown, the note names them.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Limits worth knowing</h4>
              <ul className="list-disc pl-5 text-gray-700 space-y-2">
                <li>
                  <strong>The summaries are machine-written.</strong> Treat them as a finding aid,
                  not as evidence, and read the passage before citing it.
                </li>
                <li>
                  <strong>Names are checked, and failures are shown.</strong> Where a summary names
                  someone the passage does not appear to name, the result says so. That is a flag
                  to check, not proof of error, because a passage may call Jupiter &ldquo;Pater&rdquo; or
                  refer to Achilles only as &ldquo;he&rdquo;.
                </li>
                <li>
                  <strong>Coptic descriptions were written from English translations</strong>, not
                  from the Coptic, because no available model reads Coptic well enough. They are
                  evidence at one remove.
                </li>
                <li>
                  <strong>Persian and Urdu intertextuality often works through form</strong>. A
                  poem answering another in the same meter, rhyme and radif, sometimes with almost
                  no shared vocabulary. These descriptions capture content, not form, so that
                  whole mode of response is invisible here.
                </li>
                <li>
                  A new search takes about eight seconds the first time, and a repeat of it takes about a second. The
                  first search after a long quiet period can take about twenty seconds while the passage index loads.
                </li>
              </ul>
            </div>
          )}

          {activeSection === 'mentions' && (
            <div className="prose max-w-none">
              <h3 id="mentions" className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">People &amp; Places</h3>
              <p className="text-gray-700 mb-4">
                People &amp; Places lists every line in the corpus where a named person, place or god is
                mentioned. Each person, place or god has one heading, and under it the lines are
                grouped by work. The page covers the Latin, Greek and English works. Inscriptions
                and papyri have their own table at the foot of an entry, listing the documents
                that carry the name.
              </p>
              <p className="text-gray-700 mb-4">
                The page sits under the People, Places &amp; Things menu in the top row, together with
                Events, Inscriptions &amp; Papyri, Coins and Objects, and all five are listed in both the
                Literature and the History view.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">How to search</h4>
              <p className="text-gray-700 mb-4">
                Type a name and press Search. An English name such as Rhodes or Lyon finds the
                ancient entity, Rhodos or Lugdunum. Latin and Greek spellings work too. For a
                longer name, spellings close to the one you typed are offered under Near spellings,
                so a small slip in spelling still reaches the right entry. When nothing matches,
                the page suggests the closest names.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">How a heading is chosen</h4>
              <p className="text-gray-700 mb-4">
                The heading is the most frequent nominative form of the name in the corpus, with
                the Greek form beside it where the corpus has one, for example Sarpedon with
                &Sigma;&alpha;&rho;&pi;&eta;&delta;&#974;&nu;. A heading may stand for several
                spellings that the page has grouped together.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Reading an entry</h4>
              <p className="text-gray-700 mb-4">
                Open an entry to see its works. Each work shows how many lines name the entity,
                and a click on the work shows the lines themselves, with the name marked in
                yellow. The reference above a line opens the Reader at that line. The figures at
                the head of an entry count lines, works and languages. A line that two
                overlapping passages both contain is counted once.
                A place&rsquo;s entry also lists, under Named by its adjective, the lines that name
                it only by an adjective formed from its name, such as Rusellanum for Rusellae.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">What to keep in mind</h4>
              <p className="text-gray-700 mb-4">
                The groupings are made by rules and a language model, so they can be wrong. A name
                shared by two people, such as Mars the god and Mars the Roman family, can belong to
                both, and the line is then marked as sharing its name with the other entry. A
                god&rsquo;s name standing for a thing (Mars for war) counts as a mention. A name
                shared by two people or places can still be grouped wrongly. If you find one, use{' '}
                <button type="button" onClick={() => setSuggestDialogOpen(true)} className="text-red-700 hover:underline">
                  Suggest a change
                </button>{' '}
                and say which entry and what it should be.
              </p>
              <p className="text-gray-700 mb-4">
                Inscriptions and papyri are matched by the forms of the name alone, without the
                language model&rsquo;s check. The Attic inscriptions from Attic Inscriptions Online are
                matched by stricter rules, because Athenian decrees and lists are full of private
                names that would otherwise be read as famous people or places. A demotic, the name of
                a citizen&rsquo;s deme (Rhamnousios, Phalereus), links to the deme. A god&rsquo;s name in a
                dedication links to the god. A man&rsquo;s name never links to a place that shares its
                stem (Apollonios is not Apollonia), and the name of the archon who dates a decree is
                left unlinked. Persons are not linked from these inscriptions at all, since an Athenian
                Alexander or Lykourgos in a list is almost never the famous one. A check of 100 links
                drawn at random found 95 right.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">How the entries were built</h4>
              <p className="text-gray-700 mb-4">
                The entries were built in stages and repaired on 2026-10-19. A name that two
                people or places share is first split into separate entries. A merge pass then
                puts back the splits that cut one person or place in two, using a spelling rule
                and a question put to a language model, and the project lead read the merges it
                made.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">From the Reader</h4>
              <p className="text-gray-700 mb-4">
                In the Reader, a result that shares names with another passage lists them as
                Shared names. Each name is a link that opens People &amp; Places at that name.
              </p>
            </div>
          )}

          {activeSection === 'ask-a-work' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Search One Text</h3>
              <p className="text-gray-700 mb-4">
                Search One Text asks what one work says about a subject. Pick a
                language, an author and a work, type the subject in plain words, and press Go.
                It is Theme Search run inside that one work, so your words are compared with the
                description written for each passage and the closest passages come back.
              </p>
              <p className="text-gray-700 mb-4">
                The list is ordered by score, the best match first. Each card gives the
                reference, the description, the first lines of the passage and a link that opens
                it in the Reader. Above the list, the strip called Where in the work lays the
                books of the work left to right and puts one mark at each passage found. A taller,
                darker mark is a better match. Tapping a mark takes you to its card. The strip
                shows position and the list shows score, so the two are in different orders on
                purpose.
              </p>
              <p className="text-gray-700 mb-4">
                Under the summary, a second paragraph called Scholarship is written from the
                scholarship collection: commentary notes on the work (Servius, Conington and
                Page on Latin epic, Allen on the Homeric Hymns, Paley, Verity, the rabbinic
                commentators on the Hebrew Bible) and the JSTOR Early Journal Content articles
                that name the work or its author, all published before 1923. It also reads
                articles that OpenAlex, Crossref, CORE, Google Books and Semantic Scholar list
                for the question, of any year. It knows those only from their abstracts or short open-access excerpts,
                and says so when it cites one. Those articles are listed beside the paragraph
                as Books and articles found online, each service's answer as it arrives, each marked book or article, and a link goes to a free copy where one exists,
                otherwise to the DOI. Each bracketed number in the paragraph links to its note
                or article. Greek and Hebrew words in the written paragraphs are kept in their own
                letters, with a transliteration in parentheses made by a fixed table of letters,
                and the link under the Scholarship box hides the transliterations or brings them back.
                A line in small type says what was found. Where nothing is found, as
                for Sappho, the paragraph is left out and the line says so. The assistant may cite
                only the sources it was given.
              </p>
              <p className="text-gray-700 mb-4">
                When a work is held in books, two small menus beside the Work menu choose the
                first and last book to search. They start at the whole work. A narrower range
                searches only those books, and the strip draws only those books.
              </p>
              <p className="text-gray-700 mb-4">
                When your question has a capitalised word after its first word, such as
                Sejanus, a second list called Passages that name Sejanus appears under the
                strip. It holds the passages whose description contains that name, the closest to
                your question first. When no description gives the name, as in works whose
                descriptions leave people unnamed, the text of the passages is searched for
                the name in Latin and Greek and the list says so. A content search can put a passage about a person low in the
                ranking, because the passage is about what he does and not about his name, so
                this list finds them by the word. Its marks are gray on the strip.
              </p>
              <p className="text-gray-700 mb-4">
                Above the strip, Tessa writes a short summary of what the work says, using the
                best twelve passages. Each reference in it is a link to its card. The summary
                is written from the descriptions of the passages and not from the text itself,
                so it can be wrong. Read the passages before relying on it. When Tessa is not
                running, the summary is left out and the rest of the page works as before.
              </p>
              <p className="text-gray-700 mb-4">
                A passage is a window of about twelve lines of verse, or a paragraph of long prose, so a subject spread thinly through
                a long chapter can be missed. The search matches content, so it does not find a
                name on its own as a word search would. The list of passages that name a person
                covers that for names. For any other word, use Line Search.
              </p>
              <p className="text-gray-700 mb-4">
                Measured in October 2026 on fifteen questions over the Aeneid, Thucydides 1 and 2
                and Annals 1 to 6, two judges reading the first twenty passages of each, a Sonnet model and
                the university gateway&rsquo;s Qwen model. A passage
                directly about the subject stood in the first five for 14 of the 15 questions, and
                of the first ten passages 0.44 were directly about it and 0.75 at least touched it.
                It was weakest when one account fills a few windows (the plague at Athens) and when
                the question asks for a named speaker&rsquo;s view, which came back in the
                narrator&rsquo;s voice. The two judges agreed on 69 percent of grades, the second being
                stricter on passages that only touch a subject, and both put the precision of the
                strong marks near nine in ten. Searches that name a person or a rare term are often
                better served by Line Search, and a search takes a few seconds.
              </p>
              <p className="text-gray-700 mb-4">
                Above the list, a banner rates the search. It reads how far the best passage
                stands above the work&rsquo;s typical score, and how closely the top twenty
                passages hang together, because a subject the work treats pulls a group of
                passages well above the rest. The lowest level, &ldquo;Closest passages&rdquo;, is a
                caution that the order is less certain than usual. It does not say the work
                lacks the subject, and the list is shown under every level. A passage is marked
                strong when it stands far above the work&rsquo;s typical score. The band was first
                fitted in October 2026 on three works and refitted the same month on eleven, from
                Sappho&rsquo;s fragments to the Shahnameh, with 55 subjects the works treat and 86
                they do not: it agrees with that set on 84 percent, and no single measure did
                better across works of such different lengths, so read it as a first estimate.
                Of the passages marked strong in the first measurement, 90 percent were at least
                partly about the subject, and the marks caught 42 percent of the passages judged
                directly about it.
              </p>
            </div>
          )}

          {activeSection === 'reader' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">The Reader</h3>
              <p className="text-gray-700 mb-4">
                The Reader shows a text one line at a time with two things beside it: a gutter of
                marks showing where the rest of the corpus connects to each line, and a panel of
                those connections for whatever you select. Each tab of the side panel explains itself
                under &ldquo;What this does&rdquo;. That box says what the tab searches, what it covers,
                where it is weak and how well it has been measured.
              </p>
              <p className="text-gray-700 mb-4">
                For works that have one, an <strong>About</strong> button in the header opens a
                short orientation note saying what the text is, who wrote it and when, and why a
                reader might care. The same notes appear behind the small ⓘ buttons in Browse
                Corpus. On a phone, the choice of text and book, Go to line and About this text are behind
                the title line at the top of the Reader, and the key to the margin marks is behind
                the Key button, so that the text has the width of the screen.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">The gutter</h4>
              <p className="text-gray-700 mb-3">
                Two narrow columns run down the left of the text, and the key above the text says
                what they are:
              </p>
              <ul className="list-disc pl-5 text-gray-700 space-y-2 mb-3">
                <li>
                  <strong>Red: verbal parallels.</strong> Another passage in the corpus uses
                  some of the same words as this line.
                </li>
                <li>
                  <strong>Purple: similar passages.</strong> Another passage describes
                  something similar, whether or not it shares any words.
                </li>
              </ul>
              <p className="text-gray-700 mb-3">
                A darker mark means more connections. The two columns fill in independently as
                each answer arrives. Clicking a mark selects that line and opens the matching panel
                tab: a red mark opens Verbal Parallels, a purple one opens Similar Passages.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">The quotation boxes</h4>
              <p className="text-gray-700 mb-3">
                A small numbered box beside a line means the line is quoted elsewhere in the
                corpus. The number is how many other works quote it. A <strong>solid box</strong> marks a
                quotation: another work shares two or more distinctive words with this line, or a longer
                run of its wording. A <strong>dashed box</strong> marks a possible echo, where another work
                shares one rare phrase with this line, which is weaker evidence and more often a coincidence.
                Click a box to open the <strong>Reuse</strong> tab. The boxes are built for Latin, Greek and English.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Moving around a long work</h4>
              <p className="text-gray-700 mb-3">
                Works held in books open one book at a time. The strip above the text moves to the
                previous or next book or to a typed line, and a small navigator at the bottom left
                of the screen (on a desktop) goes to the top or the end of the book or to its
                neighbors. A link into a long work opens the book that holds the line it points to.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Selecting text</h4>
              <p className="text-gray-700 mb-3">
                Select lines by clicking and dragging across them or by double-clicking a single word.
                A small toolbar appears under the selection with a three-way scope switch,{' '}
                <strong>Word / Line / Passage</strong>, which is set automatically from the size of
                what you selected and can be corrected in one click:
              </p>
              <ul className="list-disc pl-5 text-gray-700 space-y-2 mb-3">
                <li>
                  <strong>Word</strong> looks up one word across the whole corpus (String
                  Search). It needs a single double-clicked word.
                </li>
                <li>
                  <strong>Line</strong> takes the line to the full Line Search page to find
                  shared wording, with all its filters and charts.
                </li>
                <li>
                  <strong>Passage</strong> asks the panel for similar passages, a question about
                  content rather than wording.
                </li>
              </ul>
              <p className="text-gray-700 mb-3">
                To put a selection away, click anywhere outside the text and panel, press
                Escape, or use the toolbar&rsquo;s ×.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">The panel</h4>
              <h5 className="text-base font-semibold text-gray-900 mt-4 mb-1">Similar passages tab</h5>
              <p className="text-gray-700 mb-3">
                  Similar passages lists passages elsewhere in the corpus whose
                  content resembles your selection, across every served language, in two groups.
                  <strong> Same people and places</strong> comes first. It lists passages in other works that
                  name the same rare people or places as your selection, so Arrian's account of Alexander at
                  Celaenae appears beside Curtius'. <strong>Same kind of scene</strong> follows, ranked on
                  content alone. Fifteen passages show at first, and <strong>Show more matches</strong> extends
                  the list. Below it, <strong>In other languages</strong> offers a button for each language with few
                  matches in the list, which opens that language's five closest passages.
              </p>
              <h5 className="text-base font-semibold text-gray-900 mt-4 mb-1">Verbal parallels tab</h5>
              <p className="text-gray-700 mb-3">
                  Verbal parallels lists corpus lines that share your
                  selection&rsquo;s wording. A passage-sized selection is searched on its most distinctive
                  words, and the panel names which words those were. Matches that share nothing but very
                  common words (quid, ipse, varius) are hidden, with a note saying how many. The
                  full Line Search page applies no such filter. When Inscriptions or Papyri is
                  on, the same search also lists the inscriptions and papyri under the literary
                  parallels, each with its date and place and a link to the document&rsquo;s page.
              </p>
              <h5 className="text-base font-semibold text-gray-900 mt-4 mb-1">Translation tab</h5>
              <p className="text-gray-700 mb-3">
                  Translation shows the aligned English where one exists, with
                  the translator named under it. Most are public domain. A few are open translations
                  used with attribution under their non-commercial terms (Silius Italicus books 9 to
                  17, A. S. Kline). Coverage is partial (in August 2026, about 61 percent of the Greek lines and
                  48 percent of the Latin lines), so some passages have none. The translators are listed on the
                  Sources page under About.
              </p>
              <h5 className="text-base font-semibold text-gray-900 mt-4 mb-1">Reuse tab</h5>
              <p className="text-gray-700 mb-3">
                  Reuse lists other works that repeat a line closely enough to
                  count as a quotation or near-quotation, with the shared words marked. It comes from a
                  table built once over the whole corpus, not a live search, so it covers only Latin,
                  Greek and English.
              </p>
              <h5 id="scholarship-sources" className="text-base font-semibold text-gray-900 mt-4 mb-1">Scholarship tab</h5>
              <p className="text-gray-700 mb-3">
                  Scholarship lists the public-domain commentary notes the site holds,
                  then the articles, chapters and book pages that cite the passage, newest first. A result marked
                  open access has a free, legal copy through Unpaywall. A result with only a DOI opens through your
                  own library, once you set your library&rsquo;s link-resolver address under My library in this tab.
                  Every note and article has a Cite link that gives a plain reference, RIS for Zotero and EndNote,
                  and BibTeX, and each list has an Export citations link. Every source and its license are listed on
                  the Sources page under About. To search the notes and sentences by theme, use the Scholarship
                  choice on the Theme Search page.
              </p>
              <p className="text-gray-700 mb-3">
                The journals and years in each index, the terms of each source and the method behind each part of
                the results are on one page. <AboutSourcesLink anchor="methods" />
              </p>
              <p className="text-gray-700 mb-3">
                What the site does not hold matters as much. The two citation indexes stop at 1922 and
                resume in 1996, and the later one covers four American journals, so most of the twentieth
                century and nearly all European journals are absent from the citation lists. In-copyright
                books are not indexed at all. A search of the scholarship on a passage is not complete
                without L&rsquo;Ann&eacute;e philologique, your library&rsquo;s catalog and JSTOR&rsquo;s own
                search. The sources page says exactly what is missing and where to look for it.{' '}
                <AboutSourcesLink anchor="beyond" />
              </p>
              <p className="text-gray-700 mb-3">
                Arriving from Theme Search, the Reader opens on the translation, selects the whole
                passage that matched, and shows the search that brought you there, with a link
                back to the results. Opening a result from Similar passages, Verbal parallels or Reuse takes you to that
                passage in the other work, selected. A banner names the passage you came from with a
                <strong> back to</strong> link that returns to it, and the browser&rsquo;s Back button
                returns to the same line.
              </p>
              <p className="text-gray-700 mb-3">
                How the panel finds names, picks distinctive words and gathers scholarship is under{' '}
                <button onClick={() => setActiveSection('how-built')} className="text-red-600 hover:underline">How the system is built</button>.
              </p>
            </div>
          )}

          {activeSection === 'tessa' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Tessa, the assistant</h3>
              <p className="text-gray-700 mb-4">
                Tessa does two things. She <strong>explains how this site works</strong>, and she
                <strong> runs searches against this corpus and reports what came back</strong>.
                Ask her how to set up a search, what a result means, or where a phrase occurs.
                She brings a little general background to an answer, and what she reports is
                anchored to the searches she ran. The judgment about what a parallel means
                is yours.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">What she can do</h4>
              <ul className="list-disc pl-5 text-gray-700 space-y-2 mb-3">
                <li>
                  Explain how the site works, including how to connect your own AI to it. She
                  reads these Help pages, so what is documented here is what she knows.
                </li>
                <li>Find where a word or phrase occurs, and list the actual lines.</li>
                <li>Say what the corpus holds in a language, or by an author.</li>
                <li>
                  Set up a comparison of two texts. Name the works and, if you want, the books
                  (&ldquo;compare Lucretius book 1 with Ovid Met book 1&rdquo;), and she opens the
                  comparison page with those two books filled in, ready for you to press Search.
                  A short title after the author&rsquo;s name is understood (&ldquo;Met&rdquo; for the
                  Metamorphoses, &ldquo;Aen&rdquo; for the Aeneid). Name only the authors and she offers
                  everything by one against everything by the other, and says how to narrow it.
                </li>
                <li>
                  Report <strong>inflected variants</strong> you did not ask for. An exact search
                  for <em>arma virumque</em> misses Eobanus entirely, who has the phrase
                  twenty-one times in other cases. She will tell you they exist and offer to list
                  them.
                </li>
                <li>Follow up. Ask &ldquo;what about Eobanus?&rdquo; and she keeps the thread.</li>
              </ul>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">How to trust her</h4>
              <p className="text-gray-700 mb-3">
                Every answer is checked before you see it. Citations come from a search that
                ran, numbers appear in the results, and any line of text she quotes matches the
                passage word for word. She runs on an open model hosted on the university's own
                AI platform, so your questions stay on campus.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">For advanced analysis</h4>
              <p className="text-gray-700 mb-3">
                Tessa answers in a second or two. She reads the results a search returns and
                will say which parallels look like deliberate allusion and which like the common
                stock of a genre, and why one would matter. Everything she cites comes from the
                results in front of her, and anything she adds from general knowledge she marks
                as background. For advanced AI analysis of search results, such as weighing
                which parallels are genuine allusions or drafting an interpretation, connect
                your own latest-model AI directly to Tesserae and let it run the searches
                itself. The instructions are on the{' '}
                <button onClick={() => setActiveSection('ai-guide')} className="text-red-600 hover:underline">Use with your AI</button>{' '}
                page, and Tessa can walk you through the setup.
              </p>
            </div>
          )}

          {activeSection === 'events' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Events</h3>
              <p className="text-gray-700 mb-4">
                The Events page gathers what the site holds about one battle, siege, treaty or campaign:
                the passages in Latin and Greek historians and poets that tell of it or mention it (each
                opens in the Reader, and the Reader links back), the inscriptions and papyri dated to the
                same years and found near the place, the articles and commentary on those passages, and a
                map of the place and the findspots. The page is in the People, Places &amp; Things menu in
                both views, and an event page shows all four of its tabs whatever the Collections switches
                say. The Events entry is marked Beta in the top row while its lists are checked.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Where the events come from</h4>
              <p className="text-gray-700 mb-4">
                The events are every item in Wikidata (CC0) that is a battle, siege, treaty or military
                campaign dated between 800 BCE and 600 CE, and the page holds 1,485 of them. Wikidata names and places them,
                so two events can share a name (the Battle of Actium of 31 BCE and the sea battle off
                Actium of 435 BCE), and the list and the name box show the date and place beside each.
                The short description under an event&rsquo;s dates is the opening paragraph of its English
                Wikipedia article, shared under CC BY-SA 4.0, with a link to the article. Where Wikidata
                placed an event at the center of a whole region, sea or river (the Battle of Actium in the
                middle of the Ionian Sea), it has been moved to the battle&rsquo;s own site.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">The list</h4>
              <p className="text-gray-700 mb-4">
                The list opens in alphabetical order. The Order menu also sorts it by date, earliest first,
                or by the number of passages and documents. Type, century and a box for including events
                with no passages or documents narrow it. The name box works as a dropdown. A click opens
                every event with passages or documents in alphabetical order, typing narrows the list from
                the first letter, and Enter opens the one highlighted.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Passages</h4>
              <p className="text-gray-700 mb-4">
                An event&rsquo;s passages are found in two ways. For most events, the passages that name the
                event, its place or its participants are ranked by combining those names with the Theme
                Search score of the passage against the event&rsquo;s description. For some, no passage names
                the event well enough, and the Theme Search score alone ranks them. Each passage carries one
                of two labels. A Narrative passage recounts the event itself. A Mention passage names it in
                passing. An offline language model makes both judgments from the passage text and the
                event&rsquo;s description, and no person has checked them.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Inscriptions &amp; Papyri</h4>
              <p className="text-gray-700 mb-4">
                The tab lists documents dated to within ten years of the event and found within 100 km of
                its place, and leaves out any whose dating span is wider than fifty years. It lists first the
                documents that name one of the event&rsquo;s participants or its place, then the others.
                Within each group the most tightly dated document comes first (a stone dated to eight years
                before one dated to a century), and the nearer findspot breaks a tie. Each card shows the
                edition, written out in full, the record number, the place and date, the source, and the
                text of the inscription or papyrus, with the words that name a participant or the place
                highlighted. Findspots are given in English (&ldquo;near Cannae&rdquo;). The Attic
                inscriptions of Attic Inscriptions Online appear on the Athenian events.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Scholarship</h4>
              <p className="text-gray-700 mb-4">
                The tab lists the journal articles that cite the event&rsquo;s leading passages, each with the
                passage that brings it in, then the articles that cite another place in the same works
                between the first and the last of those passages. Each article carries a rating for this
                event, made by a language model (Claude Sonnet) from the article&rsquo;s title, its journal and
                the sentences in which it cites the passage, with a one-line reason shown under the row.
                YES means the event, its course, its participants&rsquo; part in it or the ancient account of
                it is a subject of the article. PARTLY means the article is about something else and touches
                the event in passing, and a small tag marks it. NO means it cites the passage for something
                else, such as grammar or a different subject, and those articles are kept under one line at
                the foot of the list. Within each group the articles are ordered by their rating (YES, then
                PARTLY and unrated, then NO), then by whether the title names the event, then by how many of
                the event&rsquo;s passages the article cites, then by the order of those passages. Articles come
                before commentaries.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Map</h4>
              <p className="text-gray-700 mb-4">
                The red dot is the event and the gray dots are the findspots of its documents, sized by the
                number of documents found at each. Where the event lies in the Roman world, the map opens on
                the Digital Atlas of the Roman Empire (Johan Åhlfeldt, CC BY), which labels places with
                their ancient names (Actium, Brundisium, Perusia). A switch at the corner shows the modern
                OpenStreetMap map instead, which is also the map for events outside the Roman world. Below
                the map a table gives each place with its coordinates and number of documents.
              </p>
            </div>
          )}

          {activeSection === 'coins' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Coins</h3>
              <p className="text-gray-700 mb-4">
                The Coins page lists 106,176 Greek and Roman coin types. The Roman types are 56,113 from the
                Online Coins of the Roman Empire (OCRE, from Augustus to the late fifth century) and 2,602
                from Coinage of the Roman Republic Online (CRRO). The Greek types are 13,399 from the IRIS
                skeleton types of Greek coinage, 11,913 from Corpus Nummorum (Thrace, Moesia, Mysia and the
                Troad), 8,694 from Seleucid Coins Online, 7,228 from PELLA (the Argead kings of Macedon),
                3,650 from Ptolemaic Coins Online, 2,107 from Coins of the Bactrian and Indo-Greek Rulers
                (BIGR) and 470 from Levantine Coinages Online.
                All are catalogs shared through nomisma.org. Corpus Nummorum is under a Creative
                Commons Attribution-NonCommercial-ShareAlike license and the other eight are under the Open
                Database License. A coin type is a catalog entry,
                not one coin. It records the legend on each side, the catalog&rsquo;s description of what each
                side shows, the mint, the dates, the issuing emperor or moneyer, the denomination and the
                metal. You can search the legends and descriptions together (try &ldquo;capricorn&rdquo;,
                &ldquo;harbor&rdquo; or a Greek legend typed without accents), narrow by authority, mint, denomination, material, source and date, and
                order the results by best match or by date. A mint that nomisma.org has matched to Pleiades
                links to its place page. Each card links to &ldquo;See images&rdquo; on the
                catalog&rsquo;s site, which lists the museum coins of that type with their photographs. This
                site stores no coin images. Catalogs call the front and back of a coin the obverse and
                the reverse, and the inscription on a side is its legend. The pages here say front, back
                and inscription.
              </p>
              <p className="text-gray-700 mb-4">
                With Coins on, the Reader gets a Coins tab beside Reuse. It shows two things, kept apart
                because they mean different things. &ldquo;Named on coins&rdquo; lists people who are named
                on a coin type, as the emperor or moneyer or as the portrait on the obverse, and are also
                named in the lines you selected. It is a name link, not an echo: the coin names the same
                person and does not quote the passage. Names are matched in Latin passages only, and a
                namesake (another Claudius, another Antonius) can match. &ldquo;Related imagery&rdquo; lists
                the five coin descriptions closest in meaning to a one-sentence summary of the passage, each
                with the dates, issuers and mint of the types that carry it. For a Latin passage the coins
                come from the two Roman catalogs (OCRE and CRRO), because in the test below the Greek
                catalogs took over half the places and brought almost no real matches. A Greek passage
                searches all nine. About one match in three is a
                real parallel. In a test on ten passages with known coin parallels, 17 of 50 matches were
                right, and the matches the tab calls &ldquo;closer&rdquo; were right about 7 times in 10 while
                the rest were right about 1 time in 4. The matches are descriptions of coin imagery, not coins
                known to refer to the passage, so read the coin before you rely on one. Theme Search gets a
                Coins choice too. It searches the coin descriptions and shows its own list, never mixed
                into the passage results. A query worded the way a catalog words an image
                (&ldquo;ship under full sail&rdquo;, &ldquo;infant on a goat&rdquo;) found about one right coin
                in two in the same test, and a vague or abstract query finds fewer.
              </p>
              <p className="text-gray-700 mb-4">
                The Coins page is always in the People, Places &amp; Things menu, in both views. The Coins switch in
                Collections (on in the Archaeological and Everything profiles) decides whether coins
                appear in the Reader tab and the Theme Search choice. Coin types never enter a
                phrase search, since they have their own page, the Reader tab and the Theme Search choice.
              </p>
            </div>
          )}

          {activeSection === 'objects' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Objects</h3>
              <p className="text-gray-700 mb-4">
                The Objects page lists Greek, Roman and Etruscan objects from three museums, each with the
                museum&rsquo;s own catalog description. It holds 1,361 objects. 305 come from the
                Cleveland Museum of Art, whose catalog records are released under CC0. 395 come from
                the Art Institute of Chicago, whose records are CC0 and whose descriptions are CC BY 4.0,
                so every card names the museum as the source of the text. 661 come from the Smithsonian
                Institution, mostly Greek vases and Roman lamps in the National Museum of Natural
                History&rsquo;s anthropology collection, also CC0. An object is listed only when its record
                has a description or note of at least 40 characters. Coins are left out, because they have
                their own collection, and so are Byzantine and later objects.
              </p>
              <p className="text-gray-700 mb-4">
                The descriptions are the museums&rsquo; own catalog texts. Tesserae did not write or
                correct them, and they vary a good deal. A Cleveland or Chicago curator&rsquo;s paragraph
                can run to several sentences about what a vase shows. A Smithsonian note is often a line
                from an old catalog card. You can search titles, descriptions, labels and inscriptions
                together (try &ldquo;Amazons&rdquo; or &ldquo;symposium&rdquo;), narrow by museum, object
                type, culture, material and date, and order the results by best match or by date. Each card
                shows the credit line and license, and links to &ldquo;Object page&rdquo; on the
                museum&rsquo;s own site. A museum&rsquo;s photograph appears only when the museum gives a web
                image that is free to reuse. For the Art Institute of Chicago that means objects it marks
                as public domain.
              </p>
              <p className="text-gray-700 mb-4">
                Theme Search gets an Objects choice beside Coins. It searches the object descriptions by
                meaning and shows its own list, never mixed into the passage results. Describe what an
                object shows or how it was used (&ldquo;a warrior arming before battle&rdquo;). We have not
                yet measured how often the nearest description is a real match, so read the object before
                you rely on one.
              </p>
              <p className="text-gray-700 mb-4">
                The Objects page is always in the People, Places &amp; Things menu, in both views. The Objects switch in
                Collections (on in the Archaeological and Everything profiles) decides whether objects
                appear in the Reader tab and the Theme Search choice. Objects
                never enter a phrase search.
              </p>
            </div>
          )}

          {activeSection === 'documents' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Inscriptions &amp; Papyri</h3>
              <p className="text-gray-700 mb-4">
                Collections decides what you see. The Collections button at the left of the main
                menu lists the source collections (literature, inscriptions, papyri, scholarship,
                coins and objects) with a switch for each, and four profiles
                that set the switches together: Literary, Historical, Archaeological and
                Everything. The view you are in (Literature or History) sets the profile, and the switches refine it.
                Your choice is remembered in this browser. This page is always in the People, Places &amp; Things
                menu, and the Scholarship tab in the Reader appears when Scholarship is on. Literary, the setting a new visitor starts with,
                shows the literary texts and the Scholarship tab, and no documents. This is a page for the documentary
                corpus, Latin and Greek inscriptions and papyri, searched the same way as the
                literary texts but shown with the markup and credit a documentary source needs. It opens
                already set to search the documents collection, with an option to search
                literature and documents together so a borrowing between the two shows up in one
                pass (an epitaph&rsquo;s &ldquo;sit tibi terra levis&rdquo; and its own literary
                echoes, for example).
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Filters and results</h4>
              <p className="text-gray-700 mb-3">
                A date range, region, place, text type, material and source narrow a search, and two
                checkboxes leave out a match resting only on an editorially restored word, or
                hide stock formulas (phrases such as &ldquo;dis manibus&rdquo; that recur in
                thousands of documents and would otherwise crowd out a genuine echo). Results
                carry their own date, place and credit line, with charts of how many came back
                by century and by region. Restored text (filled in by an editor where the stone
                or papyrus is damaged) is marked with a light dotted underline. A surviving
                fragment of a damaged word is set in gray italic. When a dictionary-form search
                of one word finds nothing, the page shows the documents whose text contains
                those letters instead and says so. Exact match finds the letters inside longer
                words, so a stem such as &ldquo;rusell&rdquo; finds every word that begins with it.
                The Place box takes the name of a findspot, ancient or modern, and suggests
                matching places as you type, with the number of documents found at each, so
                &ldquo;Rusellae&rdquo; finds what was found at Rusellae and not only the
                inscriptions that name the town.
              </p>
              <p className="text-gray-700 mb-3">
                The edition a document is published in is written out in full, with the usual
                abbreviation after it, so &ldquo;CIL&rdquo; reads Corpus Inscriptionum Latinarum (CIL)
                and &ldquo;Not. Sc.&rdquo; reads Notizie degli Scavi di Antichità (Not. Sc.). An
                abbreviation the site does not know is left as written. An Attic inscription is listed
                under its edition number (IG II&sup2; 18, not its AIO number), and its page shows the Greek
                text and AIO&rsquo;s English translation with the translator&rsquo;s name.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Browsing without a search term</h4>
              <p className="text-gray-700 mb-3">
                Below the search sits a facet tree for exploring the collection without already
                knowing a word to look for, by kind (inscriptions or papyri and ostraca), then
                region (for papyri, the Egyptian nome, with the findspot, the town or village,
                e.g. &ldquo;Karanis&rdquo;, nested under it), then century, with text type,
                material, object and language as flat filters at any level.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Sources</h4>
              <p className="text-gray-700 mb-3">
                Inscriptions come from the Epigraphic Database Heidelberg (EDH), the Epigraphic
                Database Roma (EDR), I.Sicily, and Attic Inscriptions Online (AIO, Greek texts with
                English translations, and the Berlin edition of the Inscriptiones Graecae for the Greek of
                2,095 more of AIO's inscriptions). The papyri and ostraca texts come from the Duke
                Databank of Documentary Papyri (DDbDP), and their records come from the Heidelberg
                Gesamtverzeichnis der griechischen Papyrusurkunden Ägyptens (HGV), both via
                papyri.info. Each result credits its own source and license. Where EDH and EDR
                both cover the same inscription, both are shown. Photographs are links to the
                institution that holds them (EDR, EDH, Ubi Erat Lupa, the CIL in Berlin and others,
                each named on the link). No image is copied here.
              </p>
              <p className="text-gray-700 mb-3">
                EDH is used under CC BY-SA 4.0, AIO under CC BY-SA 3.0, the Berlin Inscriptiones Graecae under CC BY 4.0, I.Sicily and the EDR deposit under CC BY 4.0, and
                the papyri.info texts and HGV records under CC BY 3.0, with copyright and attribution
                to the respective projects. Findspots link to Pleiades (CC BY 3.0). The full list,
                with the version and retrieval date of each, is under{' '}
                <a href="/text-credits" className="text-red-700 hover:underline">Sources and credits</a>.
              </p>
            </div>
          )}

          {activeSection === 'languages' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Languages</h3>
              <p className="text-gray-700 mb-5">
                Tesserae searches seven languages: Latin, Greek, English, Coptic, Hebrew, Persian and Urdu. Arabic is indexed and waiting for a specialist's review before it opens. They share the same search types, but differ in how much of the corpus
                is covered and which detection channels have data to work with. Each language has its own page in this
                section. Persian, Urdu and Arabic also share a page on poetic form.
              </p>
              <p className="text-gray-700 mb-5">
                The search page and the Reader open in the language you chose last. To always start in one language,
                set <strong>Open in</strong> at the end of the language tabs. The choice is kept in your browser only,
                with no account, and a link that names a language still opens in that language.
              </p>
              <div className="space-y-5">
                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Latin</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    The best-developed corpus: about 750 works (about 1,830 files, counting books held separately). All eleven channels
                    are available, and 1,433 of the files are grammatically parsed, so the syntax channels contribute for most pairs. Latin has the most thoroughly evaluated results
                    (about 92 percent recall across five standard Latin allusion benchmarks, as of August 2026;
                    see <button type="button" onClick={() => setActiveSection('how-well')} className="text-red-700 hover:underline">How well does it work?</button>).
                  </p>
                  <Invitation language="Latin" />
                </div>
                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Greek</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    A large corpus: about 870 works (about 1,330 files, counting books held separately). Vocabulary, sound, meaning, and
                    rare-word channels all work. Searches are accent-insensitive, so you can enter text with or without
                    diacritics. About half the Greek corpus is grammatically parsed (650 texts, Homer among them), so the
                    syntax channels contribute where both texts are parsed and nothing where either is not.
                    On 121 Homeric parallels in later epic, the search finds 69 percent searching whole works and
                    97 percent book by book (early 2026).
                  </p>
                  <Invitation language="Greek" />
                </div>
                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">English</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    About 40 works (164 files): the King James Bible, Spenser, Shakespeare, Milton, Bunyan, Swift and the
                    Romantic poets, among others. The vocabulary and meaning channels apply, and there is no syntax data.
                  </p>
                </div>
                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Coptic</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Sahidic and Bohairic (187 texts), the Coptic Bible plus monastic literature (Shenoute of Atripe and Besa).
                    Coptic is tuned for <strong>quotation and close reuse</strong> rather than allusion, with a verbatim-quotation
                    channel, sub-word lemmatization, and grammatical parses wired into the syntax channel. You can also search a
                    Coptic text against the Greek corpus to find its Greek source. See{' '}
                    <button onClick={() => setActiveSection('coptic')} className="text-red-600 hover:underline">the Coptic page</button>.
                  </p>
                </div>
                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Hebrew</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    The full Hebrew Bible (all 39 books of the Tanakh) in the Miqra according to the Masorah (Aleppo
                    Codex). Hebrew reads right-to-left, and its fully vowel-pointed text is matched on the consonantal
                    words, so vowel points and cantillation marks do not affect a match. You can also search the Hebrew
                    Bible against the Greek Septuagint and the Latin Vulgate. See{' '}
                    <button onClick={() => setActiveSection('hebrew')} className="text-red-600 hover:underline">the Hebrew page</button>.
                  </p>
                </div>
                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Persian</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Twenty-eight divans, about 943,000 lines, from Rudaki to Iqbal. Nine channels run, including the
                    refrain-and-rhyme channel that finds answer poems. Poem boundaries and meters for the major divans
                    come from Ganjoor. See{' '}
                    <button onClick={() => setActiveSection('persian')} className="text-red-600 hover:underline">the Persian page</button>
                    {' '}and{' '}
                    <button onClick={() => setActiveSection('poetics')} className="text-red-600 hover:underline">Poetic form</button>.
                  </p>
                </div>
                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Urdu</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Eighteen texts, about 59,000 lines: Wali, Mir, Sauda, Dard, Insha, Nazeer, Atish, Zauq, Zafar, Ghalib,
                    Anis, Dagh, Hali, Akbar Allahabadi and Iqbal. Nine channels run, refrain and rhyme among them, and the
                    Persian → Urdu cross-language search follows borrowed phrases. See{' '}
                    <button onClick={() => setActiveSection('urdu')} className="text-red-600 hover:underline">the Urdu page</button>.
                  </p>
                </div>
                {!arabicServed && (
                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Arabic (not yet open)</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    The Arabic corpus (the Qur'an, the pre-Islamic odes, the classical diwans and the Burda tradition)
                    is indexed but not yet searchable here. It opens once a specialist has graded its results, as two
                    rounds of review did for Persian and Urdu.
                  </p>
                </div>
                )}
                {arabicServed && (
                <div className="border-l-4 border-gray-300 pl-4">
                  <h4 className="text-lg font-semibold text-gray-900">Arabic</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    The Qur'an (one text per sura), the pre-Islamic odes, al-Mutanabbi and the classical diwans, the
                    Burda tradition, two hadith collections and the modern revival: 149 texts, about 31,700 lines. Ten
                    channels run, including a root channel for near-quotation and rhyme-and-meter matching of answer
                    poems. Arabic → Persian and Arabic → Urdu find Qur'anic and hadith phrases inside later verse. See{' '}
                    <button onClick={() => setActiveSection('arabic')} className="text-red-600 hover:underline">the Arabic page</button>.
                  </p>
                </div>
                )}
              </div>
              <div className="mt-5 bg-gray-50 p-4 rounded-lg text-sm text-gray-700">
                <strong>Across languages:</strong> when a language lacks data for a channel (for example, syntax for Greek and English),
                that channel simply contributes nothing, and the other channels still run.
              </div>
            </div>
          )}

          {activeSection === 'coptic' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Coptic Search</h3>
              <p className="text-gray-700 mb-4">
                Tesserae searches Sahidic Coptic alongside Latin, Greek, and English. The Coptic corpus combines the
                Coptic Bible with major works of monastic literature (the sermons and letters of Shenoute of Atripe
                and his successor Besa), so you can trace how Coptic authors quote scripture and reuse one another.
              </p>
              <p className="text-gray-700 mb-4">
                Coptic search is tuned differently from the classical languages. Where Latin and Greek search looks for
                allusion (shared rare vocabulary spread across a line), Coptic search is tuned for <strong>quotation
                and close reuse</strong>, the way Coptic monastic authors most often engage their sources.
              </p>
              <p className="text-gray-700 mb-2">
                How well it works, measured (August 2026): on the 22 marked citations of Isaiah in Romans, a test
                held out from all tuning, 59 percent are found in the first hundred results and eight of the
                first ten results are genuine citations. On a broad reference list of 124 scriptural parallels of
                every kind, 14.5 percent are found in the first hundred, the price of tuning for quotation. The
                data and the ranked runs are on the Downloads page.
              </p>
              <Invitation language="Coptic" />

              <div className="my-4 bg-gray-50 p-4 rounded-lg border border-gray-200">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">Verbatim-quotation detection</h4>
                <p className="text-gray-700 text-sm">
                  Coptic search's standout feature finds runs of identical consecutive words, catching direct
                  scriptural quotations even where the author gives no citation. The highest-ranked
                  Coptic results are reliable quotations.
                </p>
              </div>

              <p className="text-gray-700 mb-3">
                Alongside quotation detection, Coptic search runs the same battery of methods as the other languages:
              </p>
              <ul className="list-disc list-inside space-y-1 text-gray-700 text-sm mb-4">
                <li><strong>Shared vocabulary</strong>: lines that share two or more dictionary words.</li>
                <li><strong>Sound</strong>: words that sound alike, useful across spelling variation.</li>
                <li><strong>Synonyms</strong>: related words drawn from the Coptic WordNet.</li>
                <li><strong>Grammatical structure</strong>: lines built the same way.</li>
                <li><strong>Semantic (embeddings)</strong>: a model that recognizes the same idea in different words (a multilingual model, for Coptic).</li>
              </ul>

              <div className="mt-4 bg-blue-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-blue-800 mb-1">Coptic → Greek</h4>
                <p className="text-blue-800 text-sm">
                  Because much of Coptic scripture and literature was translated from Greek, you can search a Coptic
                  text against the Greek corpus to find the Greek source behind a translation. Choose the
                  Coptic → Greek pair on the Cross-Language tab.
                </p>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-1">Searching the whole corpus</h4>
                <p className="text-gray-700 text-sm">
                  From any result you can search the entire Coptic corpus for the words a parallel shares, to see
                  where else they occur. All of Shenoute's works are also available as a single combined text, so you
                  can search his whole surviving output at once.
                </p>
              </div>

              <div className="mt-4 bg-amber-50 border border-amber-200 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-amber-800 mb-1">Typing Coptic (Line Search &amp; String Search)</h4>
                <p className="text-amber-900 text-sm mb-2">
                  No Coptic keyboard is needed. On the word-entry boxes, type in Latin using the{' '}
                  <strong>Leipzig-Jerusalem</strong> transliteration and the Coptic appears as you type
                  (you can also paste Coptic directly). Most letters are intuitive; the ones to know:
                </p>
                <ul className="list-disc list-inside space-y-1 text-amber-900 text-sm mb-2">
                  <li><code className="bg-amber-100 px-1 rounded">sh</code> = shai, <code className="bg-amber-100 px-1 rounded">h</code> = hori, <code className="bg-amber-100 px-1 rounded">f</code> = fai, <code className="bg-amber-100 px-1 rounded">j</code> = djandja, <code className="bg-amber-100 px-1 rounded">c</code> = kjima, <code className="bg-amber-100 px-1 rounded">+</code> = ti, <code className="bg-amber-100 px-1 rounded">x</code> = khai (Bohairic)</li>
                  <li>Capital <code className="bg-amber-100 px-1 rounded">E</code> = eta (long e) and capital <code className="bg-amber-100 px-1 rounded">O</code> = omega (long o), and digraphs <code className="bg-amber-100 px-1 rounded">th ph kh ps ks</code> as expected.</li>
                </ul>
                <p className="text-amber-900 text-sm">
                  Coptic writes words joined into groups, so <strong>whole-word and phrase matching may miss a
                  word fused inside a group</strong>. In String Search, use a wildcard
                  (e.g. <code className="bg-amber-100 px-1 rounded">*rOme*</code>) to find a word wherever it sits.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'hebrew' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Hebrew Search</h3>
              <p className="text-gray-700 mb-4">
                Tesserae searches the Hebrew Bible alongside Latin, Greek, English, and Coptic. The corpus is the
                full Tanakh (all 39 books) in the Miqra according to the Masorah (MAM) edition, based on the
                Aleppo Codex. You can compare any two books to trace inner-biblical reuse, from a poem preserved in
                two places (Psalm 18 and 2 Samuel 22) to a phrase quoted in a later prophet.
              </p>
              <p className="text-gray-700 mb-2">
                How well it works, measured (August 2026): searching the 22 marked citations of Isaiah in Romans from
                the Hebrew, through the Septuagint, into the Greek New Testament finds 15 in the first hundred
                results and 9 in the first ten, while a direct word-for-word route found none. Inner-biblical Hebrew reuse
                has been checked on known pairs (Psalm 18 and 2 Samuel 22, Isaiah 12:2 and Exodus 15:2) but not
                yet against a published list.
              </p>
              <Invitation language="Hebrew" />

              <div className="my-4 bg-amber-50 border border-amber-200 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-amber-800 mb-1">Reading and matching Hebrew</h4>
                <ul className="list-disc list-inside space-y-1 text-amber-900 text-sm">
                  <li>Hebrew reads <strong>right-to-left</strong>, and results are shown that way.</li>
                  <li>The text is fully vowel-pointed. Word matching works on the <strong>consonantal words</strong>, with vowel points (nikkud) and cantillation marks set aside, so a match is found regardless of pointing. The dictionary form of a word is read from its points first, so words that share a spelling are told apart: אֶל "to", אַל "not" and אֵל "God" are three dictionary forms, shown as אל, אל² and אל³.</li>
                  <li>Words joined by a maqaf (the Hebrew hyphen) are treated as separate words.</li>
                  <li>Dictionary forms come from the <strong>ETCBC/BHSA</strong> morphology, looked up by pointed form for 99% of words and by consonants for the rest.</li>
                </ul>
              </div>

              <p className="text-gray-700 mb-3">
                Hebrew search runs the same battery of methods as the other languages:
              </p>
              <ul className="list-disc list-inside space-y-1 text-gray-700 text-sm mb-4">
                <li><strong>Shared vocabulary</strong>: lines that share two or more dictionary words.</li>
                <li><strong>Sound</strong>: words that sound alike, useful across spelling variation.</li>
                <li><strong>Rare words</strong>: shared uncommon vocabulary, the strongest sign of a real echo.</li>
                <li><strong>Semantic (embeddings)</strong>: MiqraBERT, a Biblical-Hebrew model fine-tuned in-house, which recognizes the same idea phrased in different words.</li>
              </ul>

              <div className="mt-4 bg-blue-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-blue-800 mb-1">Hebrew → Greek and Hebrew → Latin</h4>
                <p className="text-blue-800 text-sm mb-2">
                  On the Cross-Language tab you can search the Hebrew Bible against the Greek New Testament or the Latin
                  Vulgate, to see how a Hebrew passage was quoted, rendered, or echoed. Hebrew-to-Greek uses the
                  CATSS Masoretic-Septuagint alignment. Hebrew-to-Latin bridges that through Greek to the Vulgate.
                </p>
                <p className="text-blue-800 text-sm mb-2">
                  <strong>Searching for Old Testament quotations in the Greek New Testament routes through the
                  Septuagint.</strong> New Testament authors quote the Septuagint, the ancient Greek translation of the
                  Hebrew Bible, rather than translating the Hebrew themselves. So when you search a Hebrew book against
                  a Greek text, Tesserae finds the quotation Greek-to-Greek against the Septuagint version of that book,
                  where verbatim matching is at its strongest, and then maps each Septuagint verse back to the Hebrew
                  verse it translates. Each result shows the Septuagint line where the match was found together with
                  the Hebrew verse behind it, and a notice above the results says the routing was used.
                </p>
                <p className="text-blue-800 text-sm mb-2">
                  On a benchmark of the 22 explicitly marked citations of Isaiah in Romans, this routing finds 15 in
                  the top 100 results and 9 in the top ten, where the direct word-for-word route found none in the top
                  100. A few books are not routed because their Septuagint versification diverges too far from the
                  Hebrew (Jeremiah, Ezra-Nehemiah, Ecclesiastes, Lamentations). Those fall back to the direct
                  dictionary search.
                </p>
                <p className="text-blue-800 text-sm">
                  A Route control on a Hebrew → Greek search lets you choose how it is answered: through the
                  Septuagint (the default above), directly by dictionary only, or both at once with each result
                  labeled by the route that found it.
                </p>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-1">Where words recur, by book</h4>
                <p className="text-gray-700 text-sm">
                  From any result you can search the whole Hebrew Bible for the words a parallel shares. Because the
                  biblical books carry no fixed dates, the distribution chart groups the hits <strong>by book</strong>
                  instead of on a timeline.
                </p>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-1">Sources and licenses</h4>
                <p className="text-gray-700 text-sm">
                  The Hebrew text is from Sefaria (Miqra according to the Masorah / Aleppo Codex, CC-BY-SA). The
                  morphology is from ETCBC/BHSA (CC-BY-NC). The meaning model is MiqraBERT (D. M. Smiley), fine-tuned
                  on OpenBible.info cross-references. The Hebrew-Greek dictionary comes from the CATSS alignment
                  (E. Tov). Full source and license details are on the About page.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'persian' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Persian Search</h3>
              <p className="text-gray-700 mb-4">
                Tesserae searches classical Persian poetry: the divans of Rudaki, Ferdowsi, Manuchehri, Farrokhi,
                Naser Khosrow, Sanai, Anvari, Khaqani, Nizami, Attar, Rumi, Saadi, Hafez, Jami, Saeb and Bidel,
                Khayyam's quatrains, Parvin, and the Persian works of Muhammad Iqbal (Payam-e Mashriq, Zabur-e Ajam,
                Asrar-e Khudi, Rumuz-e Bekhudi, Javid Nama, Pas cheh bayad kard, Armaghan-e Hijaz and his Persian
                divan). About 943,000 lines in 28 texts. You can compare any two, for instance a classical divan
                against Iqbal to see how a twentieth-century poet answers his predecessors.
              </p>

              <div className="my-4 bg-amber-50 border border-amber-200 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-amber-800 mb-1">Reading and matching Persian</h4>
                <ul className="list-disc list-inside space-y-1 text-amber-900 text-sm">
                  <li>Persian reads <strong>right-to-left</strong>, and results are shown that way.</li>
                  <li><strong>Each line is a hemistich</strong> (misra), so a couplet occupies two consecutive lines and a
                    result may cite either half.</li>
                  <li>Matching works on <strong>normalized</strong> forms. Persian and Arabic letter variants (ye, kaf, the
                    alef forms) are folded together, so spelling differences between editions do not block a match.</li>
                  <li>Dictionary forms come from the Stanza Persian model. A curated list of about 90 function words
                    (prepositions, pronouns, the copula, the commonest auxiliaries) is set aside so that lines are not
                    matched on "was" and "is".</li>
                </ul>
              </div>

              <p className="text-gray-700 mb-2">
                A Persian search runs <strong>nine of the site's detection channels</strong>, each looking for a different kind of
                resemblance between two lines, then fuses their scores (see 
                <button onClick={() => setActiveSection('fusion-search')} className="text-red-600 hover:underline">How Fusion Search Works</button>
                 and the channel catalog under 
                <button onClick={() => setActiveSection('match-types')} className="text-red-600 hover:underline">Match Types</button>):
              </p>
              <ul className="list-disc ml-6 space-y-1 text-gray-700 text-sm mb-4">
                <li><strong>Shared vocabulary</strong> (two or more dictionary forms in common, and a second channel for a single shared form): the most heavily weighted evidence.</li>
                <li><strong>Exact words</strong>: the same surface forms, spelling and all.</li>
                <li><strong>Quotation</strong>: runs of three or more identical consecutive words: tazmin, iqtibas, a borrowed hemistich.</li>
                <li><strong>Rare words</strong>: shared uncommon vocabulary, weighted below Latin's because a divan is full of names and rare forms that coincide by chance.</li>
                <li><strong>Sound</strong> and <strong>spelling similarity</strong> (words that sound or look alike).</li>
                <li><strong>Semantic</strong>: lines the multilingual model finds alike in content even when they share no words.</li>
                <li><strong>Refrain &amp; rhyme</strong>: a channel of its own, run on every search in these languages: it segments each text into poems, reads each poem's refrain, rhyme and meter, and pairs poems that share them, so answer poems rise to the top even when their wording differs. It is explained in full, with the poetics behind it, under 
                  <button onClick={() => setActiveSection('poetics')} className="text-red-600 hover:underline">Poetic form: Persian, Urdu, Arabic</button>.</li>
              </ul>

              <div className="mt-4 bg-blue-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-blue-800 mb-1">Answer poems (javab, istiqbal)</h4>
                <p className="text-blue-800 text-sm mb-2">
                  Persian poets answer one another by writing a new ghazal in the same meter, with the same rhyme and the
                  same radif, the word or phrase that ends every couplet. A <em>refrain &amp; rhyme</em> method reads each
                  poem's radif, rhyme and meter (poem boundaries and meters come from Ganjoor for Hafez, Saadi, Rumi and
                  Iqbal) and pairs poems that share them, opening line against opening line, whatever their wording.
                  Iqbal's <em>andāz</em> ghazal, which keeps Hafez's form and changes the words, now leads a
                  Hafez-against-Zabur-e-Ajam search, and two poems on the same refrain but different meters are set
                  apart. Each pair of poems appears once in the results, with the poems' other refrain lines listed on the card, and a refrain and rhyme that many poems in the corpus share counts for less (the card says in how many). Refrain-less ghazals are not paired this way. Lines that share no words can still be paired by
                  the <em>semantic</em> method when their content is alike. That method is new and its weighting provisional.
                </p>
                <p className="text-blue-800 text-sm">
                  Good first searches: Hafez against Iqbal's Zabur-e Ajam, Rumi against Iqbal's Persian divan,
                  and Saadi against Ferdowsi. Persian → Urdu on the Cross-Language tab finds the Persian phrases Ghalib
                  carried into Urdu. When Arabic opens, Arabic → Persian will find Iqbal's Qur'anic quotations inside his Persian lines.
                </p>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-1">Sources and licenses</h4>
                <p className="text-gray-700 text-sm">
                  The classical divans come from the Chronological Persian Poetry Dataset, derived from Ganjoor.net
                  (CC-BY-SA 4.0 as declared by that dataset); Iqbal's Persian works from the Iqbal Demystified
                  dataset. Full source and license details are on the About page.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'urdu' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Urdu Search</h3>
              <p className="text-gray-700 mb-4">
                Tesserae searches eighteen Urdu texts, about 59,000 lines, by fifteen poets from Wali Dakhani to
                Iqbal: Wali, Mir Taqi Mir (the kulliyat, nearly 22,000 lines), Sauda, Dard, Insha, Nazeer Akbarabadi,
                Atish, Zauq, Bahadur Shah Zafar, Mirza Ghalib, Anis (the marsiyas), Dagh, Hali, Akbar Allahabadi and
                Muhammad Iqbal's Urdu collections (Bang-e Dara, Bal-e Jibril, Zarb-e Kalim, Armaghan-e Hijaz).
              </p>

              <div className="my-4 bg-amber-50 border border-amber-200 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-amber-800 mb-1">Reading and matching Urdu</h4>
                <ul className="list-disc list-inside space-y-1 text-amber-900 text-sm">
                  <li>Urdu reads <strong>right-to-left</strong>, and results are shown that way.</li>
                  <li><strong>Each line is a hemistich</strong>. The two halves of a couplet are consecutive lines.</li>
                  <li>Matching works on normalized forms. Urdu ye, kaf and he are folded to their Arabic-script
                    counterparts, so an edition's spelling habits do not block a match.</li>
                  <li>A curated list of 80 function words (postpositions, pronouns, the auxiliaries "is", "was",
                    "does") is set aside before matching.</li>
                  <li>Ghalib's divan is the Urdu Wikisource edition, numbered by ghazal and couplet as in the
                    standard printed divan, so a result can be cited by ghazal number.</li>
                </ul>
              </div>

              <p className="text-gray-700 mb-2">
                A Urdu search runs <strong>nine of the site's detection channels</strong>, each looking for a different kind of
                resemblance between two lines, then fuses their scores (see 
                <button onClick={() => setActiveSection('fusion-search')} className="text-red-600 hover:underline">How Fusion Search Works</button>
                 and the channel catalog under 
                <button onClick={() => setActiveSection('match-types')} className="text-red-600 hover:underline">Match Types</button>):
              </p>
              <ul className="list-disc ml-6 space-y-1 text-gray-700 text-sm mb-4">
                <li><strong>Shared vocabulary</strong> (two or more dictionary forms in common, and a second channel for a single shared form): the most heavily weighted evidence.</li>
                <li><strong>Exact words</strong>: the same surface forms, spelling and all.</li>
                <li><strong>Quotation</strong>: runs of three or more identical consecutive words: tazmin, iqtibas, a borrowed hemistich.</li>
                <li><strong>Rare words</strong>: shared uncommon vocabulary, weighted below Latin's because a divan is full of names and rare forms that coincide by chance.</li>
                <li><strong>Sound</strong> and <strong>spelling similarity</strong> (words that sound or look alike).</li>
                <li><strong>Semantic</strong>: lines the multilingual model finds alike in content even when they share no words.</li>
                <li><strong>Refrain &amp; rhyme</strong>: a channel of its own, run on every search in these languages: it segments each text into poems, reads each poem's refrain, rhyme and meter, and pairs poems that share them, so answer poems rise to the top even when their wording differs. It is explained in full, with the poetics behind it, under 
                  <button onClick={() => setActiveSection('poetics')} className="text-red-600 hover:underline">Poetic form: Persian, Urdu, Arabic</button>.</li>
              </ul>

              <div className="mt-4 bg-blue-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-blue-800 mb-1">Shared refrains between Ghalib and Mir</h4>
                <p className="text-blue-800 text-sm mb-2">
                  The Urdu ghazal answers earlier ghazals by taking over their radif, the refrain that ends every
                  couplet. When the refrain is distinctive (<em>rakhte hain</em>, <em>hotā hai</em>, <em>chāhiye</em>), a
                  Ghalib-against-Mir search puts the refrain-sharing couplets at the top of the list. When the refrain
                  is a single common word (<em>hai</em>, <em>kā</em>, <em>thā</em>), it is set aside as a function word and
                  the search falls back to the other words the couplets share, which is usually the right result.
                </p>
                <p className="text-blue-800 text-sm">
                  Good first searches: Ghalib (numbered edition) against Mir, and Iqbal's Bang-e Dara against Ghalib.
                  On the Cross-Language tab, Persian → Urdu searches the Persian divans against the Urdu ones through
                  their shared vocabulary and their shared refrains (Hafez against Ghalib puts Ghalib's ghazal in Hafez's
                  form and his Persian phrases at the top). When Arabic opens, Arabic → Urdu will find Qur'anic phrases inside Urdu lines.
                </p>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-1">Sources and licenses</h4>
                <p className="text-gray-700 text-sm">
                  Mir's kulliyat, Ghalib's divan and the twelve poets added in September come from Urdu Wikisource
                  (public-domain poetry, transcription CC-BY-SA 4.0); Iqbal's Urdu works from the Iqbal Demystified
                  dataset. Full details on the About page.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'arabic' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Arabic Search</h3>
              {!arabicServed && (
                <p className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-4">
                  Arabic is not yet open on this site. The corpus is indexed and waits for a specialist to grade its
                  results. This page describes how Arabic search works for when it opens.
                </p>
              )}
              <p className="text-gray-700 mb-4">
                Tesserae searches the Qur'an (all 114 suras, stored one sura per text) together with the poems of
                the Burda tradition, Ka'b ibn Zuhayr's <em>Banat Su'ad</em>, al-Busiri's <em>Qasidat al-Burda</em> and
                Ahmad Shawqi's <em>Nahj al-Burda</em>, the pre-Islamic odes, al-Mutanabbi and the classical poets, two hadith
                collections and the modern revival: 149 texts, about 31,700 lines.
              </p>

              <div className="my-4 bg-amber-50 border border-amber-200 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-amber-800 mb-1">Reading and matching Arabic</h4>
                <ul className="list-disc list-inside space-y-1 text-amber-900 text-sm">
                  <li>Arabic reads <strong>right-to-left</strong>, and results are shown that way.</li>
                  <li>Each poem line is a full verse (bayt) with its two hemistichs separated by a bar. Each Qur'an line
                    is one aya.</li>
                  <li>Matching works on normalized forms. Hamza variants are folded to alef, alef maqsura to ya, and
                    vowel marks are removed.</li>
                  <li>Dictionary forms come from the Stanza Arabic model. Attached particles (<em>wa-</em>, <em>fa-</em>,
                    <em>ka-</em>, <em>li-</em>, <em>bi-</em>) and pronoun endings stay on the word, so the function-word
                    list covers those forms too.</li>
                </ul>
              </div>

              <p className="text-gray-700 mb-2">
                A Arabic search runs <strong>ten of the site's detection channels</strong>, each looking for a different kind of
                resemblance between two lines, then fuses their scores (see 
                <button onClick={() => setActiveSection('fusion-search')} className="text-red-600 hover:underline">How Fusion Search Works</button>
                 and the channel catalog under 
                <button onClick={() => setActiveSection('match-types')} className="text-red-600 hover:underline">Match Types</button>):
              </p>
              <ul className="list-disc ml-6 space-y-1 text-gray-700 text-sm mb-4">
                <li><strong>Shared vocabulary</strong> (two or more dictionary forms in common, and a second channel for a single shared form): the most heavily weighted evidence.</li>
                <li><strong>Exact words</strong>: the same surface forms, spelling and all.</li>
                <li><strong>Quotation</strong>: runs of three or more identical consecutive words: tazmin, iqtibas, a borrowed hemistich.</li>
                <li><strong>Rare words</strong>: shared uncommon vocabulary, weighted below Latin's because a divan is full of names and rare forms that coincide by chance.</li>
                <li><strong>Sound</strong> and <strong>spelling similarity</strong> (words that sound or look alike).</li>
                <li><strong>Semantic</strong>: lines the multilingual model finds alike in content even when they share no words.</li>
                <li><strong>Roots</strong> (Arabic only): words of one root in different forms, the trace a near-quotation leaves. A single shared root counts on a small comparison, two on a large one.</li>
                <li><strong>Refrain &amp; rhyme</strong>: a channel of its own, run on every search in these languages: it segments each text into poems, reads each poem's refrain, rhyme and meter, and pairs poems that share them, so answer poems rise to the top even when their wording differs. It is explained in full, with the poetics behind it, under 
                  <button onClick={() => setActiveSection('poetics')} className="text-red-600 hover:underline">Poetic form: Persian, Urdu, Arabic</button>.</li>
              </ul>

              <div className="mt-4 bg-blue-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-blue-800 mb-1">Qur'anic quotation (iqtibas) and answer poems (mu'arada)</h4>
                <p className="text-blue-800 text-sm mb-2">
                  Searching the Burda against a sura finds the Qur'anic phrases woven into the poem: <em>qāba
                  qawsayn</em> (Q 53:9) at verse 107, the hidden pearl <em>lu'lu' maknūn</em> (Q 56:23) at verse 57,
                  the flood of the dam <em>sayl al-'arim</em> (Q 34:16) at verse 86, the sacred months, <em>zahrat
                  al-dunyā</em>, <em>qurrat 'ayn</em>. On a check of the two best-known quotations, both are the top two
                  results.
                </p>
                <p className="text-blue-800 text-sm">
                  A mu'arada answers an earlier poem in its meter and rhyme. Each poem's rhyme letter is read from its
                  verses and its meter from a classifier of classical Arabic verse. A single-poem text (the Burda, a
                  Mu'allaqa) is one poem, and a diwan (al-Mutanabbi's 286 poems, Shawqi's) is split on its poem
                  numbers, each poem with its own meter. So the Burda against Nahj al-Burda is tagged
                  <em>refrain &amp; rhyme</em> at the top (both <em>basīṭ</em>, rhyme <em>-mi</em>), while two poems that
                  share only a rhyme letter across different meters are not paired at all. Below the form tag, the wording matches
                  are the motifs the poems share: the slanderers, the lion, the camel-driver between Ka'b and Busiri.
                  A Qur'anic phrase used in a different grammatical form (same root) is matched through a root
                  dictionary, which is coarse. Many such near-quotations still rank low. Good first searches:
                  al-Waqi'a or an-Najm against the Burda, the Burda against Nahj al-Burda, and on the Cross-Language tab,
                  al-Baqara against Iqbal's Rumuz-e Bekhudi (Arabic → Persian).
                </p>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-1">Sources and licenses</h4>
                <p className="text-gray-700 text-sm">
                  The Qur'an text is the Tanzil Project's (CC-BY 3.0, verbatim). The Burda poems and the Mu'allaqat
                  come from Arabic Wikisource (public-domain poems, transcription CC-BY-SA 4.0). Full details on the
                  About page.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'poetics' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Poetic form in Persian, Urdu and Arabic, and how Tesserae reads it</h3>
              <nav className="my-3 text-sm text-gray-700" aria-label="On this page">
                <span className="font-semibold mr-2">On this page:</span>
                {[['poetics-forms', 'The forms'], ['poetics-line', 'How a line is built'], ['poetics-reuse', 'The kinds of reuse'],
                  ['poetics-reads', 'How Tesserae reads each of them'], ['poetics-measured', 'How well it works']].map(([id, label], k) => (
                  <span key={id}>{k > 0 && ' · '}<button onClick={() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="text-red-600 hover:underline">{label}</button></span>
                ))}
              </nav>
              <p className="text-gray-700 mb-4">
                Arabic, Persian and Urdu are three unrelated languages that share one script and one poetic system.
                Arabic supplied the script and the meters. Persian, an Indo-European language that adopted the Arabic
                script and much Arabic vocabulary after the Islamic conquest, built the ghazal and its refrain. Urdu,
                the spoken language of the north Indian cities, took the Persian system whole in the eighteenth century,
                forms, meters, images and words, while Persian remained the language of court and learning until the
                1830s, so a poet writing in both, as Ghalib and Iqbal did, is the ordinary case, much as Petrarch wrote
                Latin and Italian. This page explains the forms and the kinds of reuse they carry, and then how each
                Tesserae method reads them. The three language pages give the sources and the searches to try.
              </p>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 id="poetics-forms" className="text-base font-semibold text-gray-800 mb-2">The forms</h4>
                <ul className="list-disc ml-5 text-gray-700 text-sm space-y-1">
                  <li><strong>Ghazal.</strong> A short lyric of about five to fifteen couplets, each a self-contained thought. The
                    form of Hafez, Mir, Ghalib and Iqbal.</li>
                  <li><strong>Qasida.</strong> The long Arabic ode, often in praise. The <em>Burda</em> and <em>Banat Su'ad</em> are qasidas.</li>
                  <li><strong>Masnavi.</strong> Rhymed couplets, each with its own rhyme, for long narrative and didactic poems
                    (Rumi's <em>Masnavi</em>, Ferdowsi, Iqbal's <em>Asrar-e Khudi</em>).</li>
                  <li><strong>Rubai.</strong> The four-line quatrain (Khayyam).</li>
                </ul>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 id="poetics-line" className="text-base font-semibold text-gray-800 mb-2">How a line is built</h4>
                <p className="text-gray-700 text-sm mb-2">
                  The unit is the couplet (<em>bayt</em>), made of two half-lines (<em>misra</em>), each a complete
                  metrical line. Manuscripts write the two side by side, modern books one under the other. In a ghazal
                  or qasida the whole poem keeps one rhyme. In Persian and Urdu the rhyme has two parts: the
                  <em>qafia</em>, the rhyming syllable, and the <em>radif</em>, a word or phrase repeated identically
                  after it, a refrain built into the line. Both half-lines of the opening couplet carry rhyme and
                  refrain. After that only the second half-line of each couplet does. The last couplet usually names
                  the poet. Meter is quantitative, long and short syllables as in Latin and Greek, borrowed from Arabic,
                  and one meter runs through a whole poem. In our files Persian and Urdu lines are half-lines (a couplet
                  is two consecutive lines) except in Iqbal's collections, where a line is a couplet with a bar between
                  its halves. Arabic lines are whole verses.
                </p>
                <p className="text-gray-700 text-sm">
                  Example, Hafez (our lines 881 to 888), refrain <em>shumā</em> "you", rhyme <em>-ān</em>: "O radiance
                  of the moon of beauty, from your shining face, <em>rakhshān shumā</em> / the luster of loveliness
                  comes from the dimple of your chin, <em>zanakhdān shumā</em> / ... what is your command?
                  <em>farmān shumā</em>". Iqbal's answer to it (Zabur-e Ajam 118) keeps <em>-ān shumā</em> at every
                  couplet's end and shares almost no other word: "O youth of Persia, my life and your life,
                  <em>jān shumā</em> / like the tulip's lamp I burn in your avenue, <em>khiyābān shumā</em>".
                </p>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 id="poetics-reuse" className="text-base font-semibold text-gray-800 mb-2">The kinds of reuse</h4>
                <ul className="list-disc ml-5 text-gray-700 text-sm space-y-1">
                  <li><strong>Scriptural quotation</strong> (<em>iqtibas</em>): Qur'anic phrases woven into a poem, in Arabic
                    even inside a Persian or Urdu line. The Burda's "hidden pearl" (Q 56:23). Iqbal's <em>fī l-qiṣāṣ
                    ḥayāt</em> (Q 2:179).</li>
                  <li><strong>Answer poems</strong> (<em>javab</em>, <em>nazira</em> in Persian and Urdu. <em>Mu'arada</em> in
                    Arabic): a new poem in the model's meter, rhyme and refrain, honoring or contesting it, with little
                    shared wording. Iqbal answers Hafez. Ghalib writes on Mir's refrains. Shawqi's <em>Nahj al-Burda</em>
                    answers al-Busiri, whose <em>Burda</em> looks back to Ka'b's.</li>
                  <li><strong>Embedded lines</strong> (<em>tazmin</em>): a famous couplet quoted inside a new poem.</li>
                  <li><strong>The shared image stock</strong>: nightingale and rose, moth and candle, the fire and smoke of the
                    sigh, wine and the Magian tavern. Common property, weak evidence alone, strong in combination.</li>
                </ul>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 id="poetics-reads" className="text-base font-semibold text-gray-800 mb-2">How Tesserae reads each of them</h4>
                <ul className="list-disc ml-5 text-gray-800 text-sm space-y-2">
                  <li><strong>Quotation and embedded lines</strong> are found by the wording methods every language has:
                    shared dictionary forms, identical words, runs of three or more identical words in a row (the
                    <em>quotation</em> tag), rare shared words, sound and spelling similarity. Function words
                    (<em>ast</em>, <em>rā</em>, <em>hai</em>, <em>wa-</em>) are set aside by a curated list for each language.</li>
                  <li><strong>Answer poems</strong> are found by the <em>refrain &amp; rhyme</em> method, which runs on every
                    Persian, Urdu and Arabic search. It groups lines into poems (by the file's numbering where it has
                    one, by poem boundaries fetched from Ganjoor for the line-numbered Persian divans, which also give
                    each poem's meter, and for Arabic by a classifier of classical verse that gives each poem its meter, a
                    single-poem file counting as one poem and a diwan being split on its poem numbers), reads each
                    poem's refrain, rhyme and meter, and pairs poems that share them, opening line
                    against opening line, with the poem's other line pairs sharing a smaller part of the score. A form
                    that many poems carry (the Urdu refrain <em>hai</em>) is discounted by how common it is. A shared
                    refrain across two different meters keeps a small part of the score, since an answer keeps its
                    model's meter. In Arabic, where a qasida has no refrain, the signature is the rhyme letter and the
                    meter, and both must agree. Refrain-less ghazals are not paired this way, and Urdu has no meter
                    source yet.
                    In the result list such a pair carries <em>Refrain</em>, <em>Rhyme</em> and <em>Meter</em> badges.
                    The shared refrain is marked in yellow in both lines, the rhyme word before it in rose, and the
                    meter badge appears only when both poems carry the same label.</li>
                  <li><strong>Near-quotation in Arabic</strong> (the same root in a different form, <em>yastaghfirūn</em> /
                    <em>al-ghafūr</em>) is matched through roots from a rule-based stemmer, which is coarse. Many
                    documented near-quotations still rank low.</li>
                  <li><strong>Shared imagery</strong> is read by the <em>semantic</em> method. Each line has a vector from a
                    multilingual model, and lines whose vectors are alike beyond the top tenth of a percent of the
                    pair's line pairs are matched, with no words in common required. It does not see a quoted phrase
                    inside a line, and its weighting is provisional.</li>
                  <li><strong>Across the three languages</strong> (Cross-Language tab: Persian → Urdu now, Arabic → Persian and
                    Arabic → Urdu when Arabic opens), no dictionary is needed. The languages are matched through the vocabulary they share, after
                    the spelling conventions are reconciled (Urdu's extra letters, Arabic's <em>tā' marbūṭa</em>), on
                    both the dictionary form and the surface word, so a Qur'anic phrase inside a Persian line matches
                    the Arabic. A matched phrase extends through its function words so <em>innā lillāhi wa-innā
                    ilayhi rāji'ūn</em> is seen whole. A pair needs two shared words, and native Urdu words have no
                    Persian counterpart. Between Persian and Urdu, two poems that share refrain and rhyme are matched
                    too, as within one language, unless the refrain is only function words: Urdu
                    <em> huā</em> ("became") is spelled like Persian <em>havā</em> ("air"), so a shared spelling there
                    proves nothing. A refrain translated from Persian into Urdu (<em>ast</em> as <em>hai</em>) is not
                    matched, because without the meter, which the Urdu texts do not carry, those forms are too common
                    to be evidence.</li>
                </ul>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 id="poetics-measured" className="text-base font-semibold text-gray-800 mb-1">How well it works, measured so far</h4>
                <p className="text-gray-700 text-sm">
                  Persian, seven documented answer poems (Hafez to Iqbal): all seven in the top ten. Arabic, 44
                  documented Burda–Qur'an pairings: the verbatim quotations at ranks 1 to 3 and all six in the top
                  5,000. Near-quotations mostly deep in the list. Allusions out of reach. Urdu, 23 refrains Ghalib
                  shares with Mir: six in the top ten. Cross-language and imagery have no benchmark yet. On inspection,
                  Persian → Urdu puts the Persian phrases Ghalib carried into Urdu at the top, and Arabic → Persian, tested
                  before Arabic was held back, put Iqbal's Qur'anic quotations at the top. The Arabic figures above come from a
                  test copy of the site. The benchmarks are small and new. Where a documented
                  connection is missing, please tell us the loci.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'cross-lingual' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Cross-Language Search</h3>
              <p className="text-gray-700 mb-4">
                The Cross-Language tab compares a text in one language with a text in another. Seven pairs
                are open, and each works through what its two languages have in common:
              </p>
              <ul className="list-disc pl-5 text-gray-700 space-y-2 mb-4">
                <li><strong>Greek and Latin</strong>: a Greek-Latin dictionary plus a meaning model trained on
                  both languages, described in detail below.</li>
                <li><strong>Latin and English, Greek and English</strong>: the same approach, with the English
                  side matched through dictionary senses and meaning.</li>
                <li><strong>Coptic and Greek</strong>: Coptic's Greek loanwords and a Coptic-Greek dictionary,
                  aimed at finding a Coptic text's Greek source. See{' '}
                  <button onClick={() => setActiveSection('coptic')} className="text-red-600 hover:underline">Coptic</button>.</li>
                <li><strong>Hebrew and Greek, Hebrew and Latin</strong>: the Hebrew Bible against the Septuagint and
                  the Vulgate, through dictionaries and the Septuagint's own alignment with the Hebrew. See{' '}
                  <button onClick={() => setActiveSection('hebrew')} className="text-red-600 hover:underline">Hebrew</button>.</li>
                <li><strong>Persian and Urdu</strong>: no dictionary is needed. Urdu poetry borrows Persian
                  vocabulary and phrases, so the two are matched on the words they share once their spelling
                  conventions are reconciled, together with a meaning model that reads both. Hafez against Ghalib
                  puts Ghalib's reworkings of Hafez's phrases at the top. Refrain and rhyme are matched across the
                  pair as well, when an Urdu ghazal keeps a Persian ghazal's refrain and rhyme: Ghalib's ghazal 64
                  keeps Hafez's refrain <span dir="rtl">دوست</span> and his rhyme in -ār. Urdu refrains are usually
                  Urdu words, so such shared forms are rare, about ten poem pairs across the two corpora. See{' '}
                  <button onClick={() => setActiveSection('poetics')} className="text-red-600 hover:underline">Poetic form</button>.</li>
              </ul>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Greek and Latin in detail</h4>
              <p className="text-gray-700 mb-4">
                Greek and Latin search finds how Greek texts influenced Latin authors or the reverse. The search combines
                four channels, described below: AI semantic matching, a Greek-Latin dictionary, cross-lingual syntax and
                phonetic transliteration. Pairs detected by more than one channel receive a convergence bonus, pushing the
                most confident matches to the top.
              </p>
              <div className="space-y-4">
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                  <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">Channel 1: AI Semantic</h4>
                  <p className="text-gray-700 text-sm">
                    Uses the SPhilBERTa neural model, trained on parallel Greek-Latin texts, to find conceptually
                    similar passages. Detects thematic connections and paraphrased ideas even where
                    no direct vocabulary correspondence exists. Results show a cosine similarity percentage.
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                  <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">Channel 2: Greek↔Latin Dictionary</h4>
                  <p className="text-gray-700 text-sm mb-2">
                    Finds shared vocabulary across languages using four matching layers:
                  </p>
                  <ul className="text-gray-700 text-sm space-y-1 ml-4 list-disc list-inside">
                    <li><strong>Curated pairs</strong>: 925 hand-verified Greek-Latin translation equivalences across 17 semantic categories (e.g., ἀνήρ→vir, ἐνέπω→cano, μένος→furor)</li>
                    <li><strong>V3 dictionary</strong>: 34,500+ Greek-Latin word pairs from Lewis & Short / LSJ, with about 4,400 pairs added in V6 and the judged pairs loaded since October 2026</li>
                    <li><strong>Proper names</strong>: 1,500+ Greek-Latin name pairs from Wikidata and the Pleiades gazetteer (e.g., Ἀχιλλεύς→Achilles)</li>
                    <li><strong>Cognate detection</strong>: automatic transliteration matching (e.g., Greek <em>philosophia</em> → Latin <em>philosophia</em>)</li>
                  </ul>
                  <p className="text-gray-700 text-sm mt-2">
                    Matched dictionary words are highlighted in the results. Scores use word rarity (IDF)
                    so rare vocabulary matches rank higher than common ones.
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                  <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">Channel 3: Cross-Lingual Syntax</h4>
                  <p className="text-gray-700 text-sm">
                    Compares grammatical dependency structures across languages. Because Universal Dependencies labels
                    (nsubj, obj, obl, etc.) are language-independent, lines with identical dependency patterns are
                    matched directly, with no shared vocabulary needed.
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                  <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">Channel 4: Phonetic Transliteration</h4>
                  <p className="text-gray-700 text-sm">
                    Transliterates Greek tokens to Latin characters (e.g., μῆνιν → <em>menin</em>, Ἀχιλλεύς → <em>achileus</em>)
                    and compares them by edit distance against Latin tokens. Detects phonetic echoes across the script
                    boundary, such as Homer's μῆνιν echoed in Vergil's <em>Mene</em>. Acts as a convergence booster that
                    strengthens pairs already found by semantic or dictionary channels.
                  </p>
                </div>
                <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                  <h4 className="text-sm font-semibold uppercase tracking-wide text-blue-800 mb-2">Fusion &amp; Convergence</h4>
                  <p className="text-blue-800 text-sm">
                    Pairs found by multiple channels receive a convergence bonus that boosts their score. For example, <em>Odyssey</em> 1.1 /
                    {' '}<em>Aeneid</em> 1.1 is detected semantically (48% cosine) and confirmed by dictionary matches
                    (ἄνδρα→virum, ἔννεπε→cano), so the convergence bonus pushes it above pairs detected by only one channel.
                    The "Min Matches" setting lets you require a minimum number
                    of dictionary word matches. Set it to 1 to include semantic-only pairs, or raise it to focus on
                    vocabulary-confirmed parallels.
                  </p>
                </div>
              </div>
              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 className="text-lg font-semibold text-gray-900 mb-2">Greek Input</h4>
                <p className="text-gray-700 text-sm">
                  Greek text can be entered with or without diacritics (accents, breathings, iota subscript).
                  The search normalizes diacritics automatically, so <em>ἄνδρα</em> and <em>ανδρα</em> are treated identically.
                </p>
              </div>
              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <p className="text-gray-700 text-sm">
                  <strong>Example:</strong> Compare Homer's Iliad Book 1 (Greek) with Vergil's Aeneid Book 1 (Latin)
                  to discover how Vergil adapted Homeric themes and vocabulary.
                </p>
              </div>
              <div className="mt-4 bg-gray-50 p-4 rounded-lg border border-gray-200">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">What to Expect: Benchmark Results</h4>
                <p className="text-gray-700 text-sm mb-2">
                  Cross-lingual detection is substantially harder than same-language matching. Tested against
                  Knauer's catalog of 412 parallels between Vergil's <em>Aeneid</em> Book 1 and Homer's <em>Iliad</em>:
                </p>
                <ul className="text-gray-700 text-sm space-y-1 ml-4 list-disc list-inside">
                  <li><strong>~40%</strong> of gold-standard parallels found in top 50 (per-target-line ranking)</li>
                  <li><strong>~24%</strong> found in top 10</li>
                  <li>Only 31% of scholarly parallels have any shared vocabulary across languages</li>
                  <li>94% are found somewhere in the full ranking. Most of the parallels outside the top 50 share no words and are found through meaning, but rank lower</li>
                </ul>
                <p className="text-gray-700 text-sm mt-2">
                  For comparison, the Latin fusion system achieves 91.9% recall across five benchmarks using
                  eleven channels. Cross-lingual search uses four channels: semantic embeddings, dictionary,
                  cross-lingual syntax (structural fingerprint matching via Universal Dependencies),
                  and phonetic transliteration (Greek→Latin character mapping for detecting sound echoes like μῆνιν ≈ Mene).
                </p>
              </div>
            </div>
          )}

          {activeSection === 'ai-guide' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Use Tesserae with your AI assistant</h3>
              <p className="text-gray-700 mb-4">
                Any AI can help you with Tesserae. The free way, which works with any assistant including free ones and
                sandboxed apps like the standard Gemini, is to run the search here and let the AI interpret the results.
                To have the AI run the searches for you instead, with no copying and pasting, you need a basic paid AI
                subscription (see below).
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Free, with any AI <span className="text-sm font-normal text-gray-500">(you search, the AI interprets)</span></h4>
              <p className="text-gray-700 text-sm mb-2">
                This needs nothing beyond a chat window and works with any assistant, free or paid, including ones that
                cannot reach the API themselves:
              </p>
              <ol className="list-decimal list-inside text-gray-700 text-sm space-y-1 mb-2">
                <li>Run your search on this site: a two-text comparison, a line search, or a rare-word or rare-phrase search.</li>
                <li>Click <strong>Export CSV</strong> above the results to download them.</li>
                <li>Paste the prompt below into your AI, paste the CSV right after it, and send.</li>
              </ol>
              <CopyBlock text={INTERPRET_PROMPT} label="Copy the prompt" />
              <p className="text-gray-500 text-xs mt-1 mb-6">
                The CSV carries each parallel's loci, both lines, the score, the shared words, and which detection
                methods agreed, so the AI has what it needs to weigh them. You stay in control of the searching.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Have the AI run the searches for you</h4>
              <p className="text-gray-700 text-sm mb-4">
                To skip the copying and let the assistant search on its own, it has to reach the Tesserae API, which
                today means a <strong>basic paid subscription</strong> to Claude or ChatGPT. Sandboxed apps such as the
                standard Gemini cannot do this at any tier, so for Gemini use the free option above.
              </p>

              <h5 className="text-base font-semibold text-gray-900 mt-4 mb-2">Claude <span className="text-sm font-normal text-gray-500">(one URL, the smoothest route)</span></h5>
              <p className="text-gray-700 text-sm mb-2">
                Add Tesserae to Claude once, and regular chat Claude can run everything, including the full fusion
                search, with no Python and no guide-pasting. In <strong>Claude Desktop</strong> or <strong>claude.ai
                on a computer</strong>, go to <strong>Settings → Connectors → “Add custom connector”</strong> and paste
                this URL:
              </p>
              <CopyBlock text={MCP_CONNECTOR_URL} />
              <p className="text-gray-700 text-sm mt-2 mb-2">
                Then just ask, e.g.: “Use Tesserae to compare Aeneid 1 with Lucan's Civil War 1 and show the strongest
                parallels.” Adding a connector needs a paid plan, and the minimum that includes connectors is
                <strong> Claude Pro</strong>. Connectors are added on desktop or web, not the mobile app.
              </p>
              <details className="text-sm text-gray-600 mb-6">
                <summary className="cursor-pointer text-gray-700 font-medium">Advanced: run the connector locally instead (offline, no account or connector needed)</summary>
                <div className="mt-2 pl-1">
                  <p className="mb-2">Prefer to run the server on your own machine? Download <a href="/tesserae-data/tesserae_mcp.py" target="_blank" rel="noopener noreferrer" className="text-blue-700 underline">tesserae_mcp.py</a> and install its dependencies:</p>
                  <CopyBlock text={MCP_PIP} />
                  <p className="mt-3 mb-1"><strong>Claude Desktop:</strong> Settings → Developer → Edit Config, and add (use the real path to the file):</p>
                  <CopyBlock text={MCP_CONFIG} />
                  <p className="mt-3 mb-1"><strong>Claude Code:</strong> instead run:</p>
                  <CopyBlock text={MCP_CLAUDE_CODE} />
                  <p className="mt-3">Restart Claude, then ask it to use Tesserae.</p>
                </div>
              </details>

              <h5 className="text-base font-semibold text-gray-900 mt-6 mb-2">ChatGPT <span className="text-sm font-normal text-gray-500">(paste in the guide)</span></h5>

              {OFFICIAL_GPT_URL ? (
                <>
                  <p className="text-gray-700 text-sm mb-2 font-medium">Use the official Tesserae GPT, with no setup.</p>
                  <p className="mb-3">
                    <a href={OFFICIAL_GPT_URL} target="_blank" rel="noopener noreferrer"
                      className="inline-block bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-medium px-4 py-2 rounded no-underline">
                      Use Tesserae in ChatGPT →
                    </a>
                  </p>
                  <p className="text-gray-700 text-sm mb-4">
                    Open it and just ask it to find, compare, or investigate parallels. It calls the Tesserae API for you.
                    If it asks permission to contact <code>tesserae.caset.buffalo.edu</code>, choose <em>Allow</em>.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-gray-700 text-sm mb-2">
                    ChatGPT has no one-click Tesserae connector. Instead, open the paste-in guide below, copy it, and
                    paste it into a new ChatGPT chat as your first message. ChatGPT then runs Tesserae's searches over
                    the open API and follows the guide's workflow. This leans on ChatGPT's own browsing, so the minimum
                    plan is <strong>Plus</strong>. For a dedicated Tesserae GPT you build once and reuse, you need a
                    ChatGPT <strong>Business</strong> (or Team, Enterprise, or Edu) workspace, since OpenAI limits
                    custom-GPT creation to those (see below).
                  </p>
                  <p className="mb-4">
                    <a href="/static/downloads/ai-guide.html" target="_blank" rel="noopener noreferrer"
                      className="inline-block bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded no-underline">
                      Open the paste-in guide →
                    </a>
                  </p>
                </>
              )}

              <details className="text-sm text-gray-700 mb-4">
                <summary className="cursor-pointer text-gray-800 font-medium">Advanced: build your own Tesserae GPT</summary>
                <div className="mt-2 pl-1 space-y-2">
                  <p className="text-gray-600">
                    Optional, and note OpenAI now allows creating a custom GPT only in a ChatGPT <strong>Business, Team,
                    Enterprise, or Edu workspace</strong> (not on a personal Free/Plus/Pro account). If you have one, you can
                    build your own copy with custom instructions and share it within your workspace. Most users can just
                    paste the guide above instead.
                  </p>
                  <p>
                    <strong>Building or editing a GPT must be done in ChatGPT in a web browser</strong> at <code>chatgpt.com</code>.
                    The desktop app doesn't clearly expose the GPT-builder. (Once built, you and anyone you share it with
                    just chat with it normally, on any client, and you can edit it later.)
                  </p>
                  <ol className="list-decimal list-inside space-y-1">
                    <li>In ChatGPT (web browser): <strong>Explore GPTs → + Create → Configure</strong>. Name it <strong>Tesserae</strong>. (The <em>Preview</em> pane beside Configure is just for testing your draft.)</li>
                    <li>Paste the <em>Instructions</em> below into the Instructions box.</li>
                    <li><strong>Actions → Create new action → Import from URL</strong>, paste the schema URL below, set <strong>Authentication: None</strong>.</li>
                    <li>If you plan to share the GPT by link or publish it, add a <strong>Privacy policy</strong> URL (see the link below).</li>
                    <li>Test it (e.g. “List Vergil's texts”), then <strong>Create</strong>, privately or as a shared link.</li>
                  </ol>
                  <p className="font-medium mb-1">Schema URL (for the Action):</p>
                  <CopyBlock text={AI_SCHEMA_URL} />
                  <p className="font-medium mb-1 mt-2">Instructions (paste into the GPT):</p>
                  <CopyBlock text={GPT_INSTRUCTIONS} />
                  <p className="text-gray-600 text-xs mt-1">
                    Privacy policy URL (for the builder's “Privacy policy” field, required to share/publish):{' '}
                    <a href={API_PRIVACY_URL} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline break-all">{API_PRIVACY_URL}</a>
                  </p>
                  <p className="text-gray-500 text-xs">
                    A custom GPT can run everything, including the full fusion search. It polls the fusion job until the
                    results are ready. Building GPTs is included in ChatGPT Plus.
                  </p>
                </div>
              </details>

              <div className="border border-gray-200 bg-gray-50 rounded p-3 text-sm text-gray-700 mb-4">
                <strong>A note on the full fusion search.</strong> Tesserae's most comprehensive comparison (“full fusion”)
                usually takes about <strong>2–3 minutes</strong>. It keeps running on the Tesserae server even after your
                assistant has replied, and the finished result is cached. If it's still running, just ask your assistant to
                “<em>check the fusion search</em>” after a couple of minutes. It will retrieve and discuss the completed
                results. The faster “rare-pairs” and “rare-words” searches return in seconds.
              </div>

              <div className="bg-amber-50 p-4 rounded border border-amber-200">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-amber-800 mb-2">A note on scholarly use</h4>
                <p className="text-gray-700 text-sm">
                  Tesserae's results are transparent and reproducible. Anyone can re-run a search and inspect why a
                  parallel ranked where it did. Whatever your AI concludes from there is its own product. When you
                  publish, cite Tesserae for the parallels it found, and present the surrounding analysis as
                  AI-assisted interpretation you have checked.
                </p>
                <p className="text-gray-700 text-sm mt-2">
                  Tesserae hands your AI a link to the same results in the site's own interactive view, not a chart. You can
                  ask your AI to draw its own charts or a different cut of the results, whatever view you want. Those are your AI's own rendering, not
                  official Tesserae figures, so treat them like any AI output you would check before relying on it.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'syntax-texts' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Syntax</h3>
              <p className="text-gray-700 mb-3">
                Syntax matching compares the <strong>grammatical structure</strong> of two lines (how the words relate as
                subjects, objects, and modifiers) rather than which words they use. In the Fusion search it works as
                <strong> two channels</strong>:
              </p>
              <ul className="list-disc list-inside text-gray-700 text-sm space-y-1 mb-3">
                <li><strong>Shared-word syntax:</strong> when two lines already share vocabulary, it checks whether those words sit in the same grammatical roles, a small confirmation that the parallel is structural, not coincidental.</li>
                <li><strong>Structural fingerprint:</strong> matches two lines with the same dependency skeleton (e.g. subject–verb–object) even when they share <em>no</em> vocabulary. To avoid firing on ordinary grammar, it only counts when another channel (synonyms or meaning) also links the pair.</li>
              </ul>
              <p className="text-gray-700 mb-4">
                Both add to the fused score on a <strong>sliding scale</strong>, but with low weight. Syntax
                <strong> supplements</strong> the other channels rather than driving results. A separate <strong>Syntax</strong>{' '}
                checkbox in Search Settings can also apply it as a simple on/off boost.
              </p>

              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 mb-4">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">Latin: Full Coverage</h4>
                <p className="text-sm text-gray-700">
                  <strong>1,433 of about 1,830 Latin files</strong> (639,000+ lines) have been parsed for syntactic
                  dependencies using LatinPipe, a Latin dependency parser. Syntax matching works for any pair of
                  parsed texts. Works added since the parse contribute nothing to the syntax channels until they are parsed.
                </p>
              </div>

              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 mb-4">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">Coptic: Available</h4>
                <p className="text-sm text-gray-700">
                  The Coptic corpus (187 Sahidic and Bohairic texts, 186 of them parsed) is grammatically parsed and wired into the same syntax
                  channels, so Coptic searches use syntax the same way Latin does.
                </p>
              </div>
              <div className="bg-amber-50 p-4 rounded border border-amber-200 mb-4">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-amber-800 mb-2">Greek: Partial</h4>
                <p className="text-sm text-gray-700">
                  650 of the about 1,330 Greek files in the corpus have been parsed (239,000+ lines), using Stanza with
                  the {' '}<code className="bg-gray-200 px-1 rounded">grc_proiel</code> model. Homer is among them.
                  Syntax matching <strong>does</strong> work for Greek pairs where both texts are parsed, and contributes
                  nothing where either is not. The other channels run normally either way.
                </p>
              </div>
              <div className="bg-gray-50 p-4 rounded border border-gray-200 mb-4">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">English: Not Yet</h4>
                <p className="text-sm text-gray-700">
                  English texts have not been parsed for grammar, so the syntax channels contribute nothing for English.
                  Its other channels still run normally. (Because grammatical labels are language-independent,
                  cross-language structural matching becomes possible wherever both sides are parsed.)
                </p>
              </div>

              <div className="bg-gray-50 p-4 rounded mb-4">
                <h4 className="text-lg font-semibold text-gray-900 mb-2">How It Works</h4>
                <p className="text-sm text-gray-600">
                  Each line is represented as a set of dependency relation patterns (e.g., <code className="bg-gray-200 px-1 rounded">nsubj→VERB</code>,
                  {' '}<code className="bg-gray-200 px-1 rounded">amod→NOUN</code>). Lines with similar grammatical structures
                  receive high syntax similarity scores. This catches parallels where an author mirrors sentence
                  structure (subject-verb-object order, subordinate clause placement, participial constructions) without
                  reusing any of the same words.
                </p>
              </div>

              <div className="bg-blue-50 p-4 rounded border border-blue-200">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-blue-800 mb-2">Credits</h4>
                <p className="text-sm text-gray-700">
                  Latin syntactic annotations are produced by <strong>LatinPipe</strong> (Straka & Straková, Charles University),
                  a neural dependency parser trained on Universal Dependencies treebanks. The parser processes raw Latin text
                  into full dependency trees with part-of-speech tags and grammatical relations.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'best-practices' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Search Tips</h3>
              <p className="text-gray-700 mb-4">
                Tips for getting the most out of Tesserae. The default Fusion mode handles most settings
                automatically, but these strategies can help refine your results.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Getting Started</h4>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Use Fusion (the default)</strong>: It runs eleven channels and finds far more parallels than any single method. Start here.</li>
                <li><strong>Start small, then expand</strong>: Begin with a single book comparison, then broaden to complete works</li>
                <li><strong>Focus on the top results</strong>: Fusion ranks results by combined confidence. The highest-scoring results are overwhelmingly genuine parallels.</li>
                <li><strong>Check channel badges</strong>: Results flagged by many independent channels are the most reliable</li>
              </ul>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Narrowing Down Results</h4>
              <p className="text-gray-600 text-sm mb-2">When you have too many results or want more precision:</p>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Select smaller text sections</strong>: Choose individual books instead of complete works (e.g., "Aeneid, Book 1" rather than "Aeneid (Complete)")</li>
                <li><strong>Add custom stopwords</strong>: Exclude common thematic words that create noise (e.g., "bellum" in war narratives, "amor" in love poetry)</li>
                <li><strong>Sort by score</strong>: The highest scores represent the strongest parallels</li>
                <li><strong>Try individual channels</strong>: Switch from Fusion to a specific match type (Lemma, Semantic, etc.) to isolate one kind of similarity</li>
              </ul>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Expanding Results</h4>
              <p className="text-gray-600 text-sm mb-2">When you want to cast a wider net:</p>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Select complete works</strong>: Search entire texts rather than individual books</li>
                <li><strong>Results are not capped</strong>: by default every result is returned. Set Max Results to a number to keep only the top ones.</li>
                <li><strong>Use the Lines tab</strong>: Search a single line against every text in its language</li>
                <li><strong>Try Rare Words or Rare Pairs.</strong> These specialized modes find distinctive vocabulary connections that complement Fusion</li>
              </ul>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">General Tips</h4>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Export for analysis</strong>: Download CSV files to analyze results in spreadsheet software</li>
                <li><strong>Check the corpus</strong>: Use "Search Corpus" on a result to see where else those words co-occur</li>
                <li><strong>Register discoveries</strong>: Add significant parallels to the Repository for future reference</li>
                <li><strong>Greek diacritics are optional.</strong> You can search Greek with or without accents and breathings</li>
              </ul>
            </div>
          )}

          {activeSection === 'repository' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Repository</h3>
              <p className="text-gray-700 mb-4">
                Save discovered parallels to build a personal collection and optionally share with the scholarly community.
              </p>
              <div className="bg-blue-50 p-4 rounded border border-blue-200 mb-4">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-blue-800 mb-2">How to Register an Intertext</h4>
                <ol className="list-decimal list-inside text-gray-700 text-sm space-y-1">
                  <li>Click "Register" on any search result</li>
                  <li>Rate the scholarly significance (1-5 scale based on Coffee et al. 2012)</li>
                  <li>Add notes explaining the connection</li>
                  <li>Choose whether to share publicly</li>
                </ol>
              </div>
              <div className="bg-gray-50 p-4 rounded">
                <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-2">Scoring Scale (Coffee et al. 2012)</h4>
                <ul className="text-sm text-gray-600 space-y-1">
                  <li><strong>1</strong> - Minimal similarity, possibly coincidental</li>
                  <li><strong>2</strong> - Some shared vocabulary</li>
                  <li><strong>3</strong> - Clear parallel, likely intentional</li>
                  <li><strong>4</strong> - Strong allusion with thematic resonance</li>
                  <li><strong>5</strong> - Direct quotation or unmistakable reference</li>
                </ul>
              </div>
            </div>
          )}

          {activeSection === 'upload-text' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Upload Your Text</h3>
              <p className="text-gray-700 mb-4">
                Uploading a text now has its own page, with the formatting guidelines and the upload form.{' '}
                <a href="/upload-help" className="text-red-600 hover:underline">Open Upload Your Text</a>.
              </p>
            </div>
          )}

          {activeSection === 'faq' && (
            <div className="prose max-w-none">
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Frequently Asked Questions</h3>
              <div className="space-y-6">
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">What is Fusion search and should I use it?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Fusion is the default search mode. It runs eleven independent detection channels simultaneously
                    and combines their results, finding 92% of known parallels in the Latin benchmark tests of August 2026 (not re-run since the Latin lemma table was corrected in October 2026). Unless you need
                    to isolate a specific detection method, Fusion is recommended for general use.
                  </p>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">Why is my search taking so long?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Fusion search runs eleven channels, which takes longer than a single-channel search.
                    Try searching smaller sections (e.g., individual books) for faster results. Large text pairs
                    like the full Aeneid vs. Metamorphoses take longer on the first run but are cached
                    for subsequent searches. A progress timer is shown during the search.
                  </p>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">What does "Refresh results" do?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Search results are cached so that repeating the same search is instant. The "Refresh results"
                    button (shown at the top of your results) clears the cached results for that search and runs it
                    again from scratch. Use this if the search engine has been updated since your last search and you
                    want to see improved results.
                  </p>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">What does "Search queued" mean?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    When the server is already running heavy searches for other users, your search is placed in a
                    queue to prevent the server from running out of memory. You'll see a "Search queued" message
                    with a spinner. Your search will start automatically when a slot opens, typically within a few
                    minutes. You can cancel and retry later if you prefer.
                  </p>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">Can I request a text that's not in the corpus?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Yes! Use the{' '}
                    <a href="/upload-help" className="text-red-600 hover:underline">
                      Upload Your Text
                    </a>
                    {' '}page.
                  </p>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">Are all the texts in the corpus downloadable?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Most are, under the licenses listed on the Sources page under About. A text that comes to
                    us under a license for searching only is searchable like any other text and left out of
                    the per-language downloads. Its credit and license terms appear on the Sources page.
                  </p>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">How do I save my results?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Use "Export CSV" to download results as a spreadsheet, or "Register" to save individual parallels to the Intertext Repository.
                  </p>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">What's the difference between Phrases and Lines search?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Phrases compares two specific texts against each other. Lines searches a single line
                    (selected from a text or typed in) against every text in its language.
                  </p>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">How does the scoring work?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    In Fusion mode, each channel's score is multiplied by a weight and summed, with a convergence
                    bonus for pairs found by multiple channels. In individual channel mode, the V3-style algorithm
                    uses IDF (rare words score higher) and distance penalties (closer words score higher).
                  </p>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">Does syntax matching work for Greek and English?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    For Greek, yes, on about half the corpus: 650 of the about 1,330 Greek files are parsed,
                    Homer among them, so syntax matching works where both texts are parsed. For English, no, because
                    English is not parsed at all. Latin (1,433 of about 1,830 files) and Coptic (186 of 187) are parsed too. Where
                    parsing is unavailable the syntax channel contributes nothing and the other channels run
                    normally.
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'how-built' && (
            <section>
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">How the system is built</h3>
              <p className="text-gray-700 mb-4">
                Tesserae runs on one server at the University at Buffalo, with two small helper
                services beside it and, since autumn 2026, the university's shared AI platform
                (BullsAI) for the language model work. The diagram shows every machine part, what
                data each reads, and which jobs run on a schedule and which run once when the
                corpus changes. Solid lines are paths taken during a request, dashed lines are jobs. Nothing in the live site calls a paid service.
              </p>
              <SystemChart />
              <p className="text-gray-700 text-sm mt-4">
                The two BullsAI parts are reached in different ways, and the difference matters to
                anyone setting up a similar system. The gateway is a web address that serves
                several open language models. The server calls it with a key issued to the project,
                and the key carries a daily allowance of requests, so a large batch is planned
                around the allowance and a slow week costs nothing. The compute side allots whole
                graphics cards to jobs the server submits with a command-line tool. A person's
                sign-in to that tool expires after a few hours, which was enough for a job watched
                from a desk and not for a run that goes through the night. The platform's
                administrators therefore issued the project a service account, a machine identity
                with its own credential, that the server holds and uses to start jobs itself. No
                credential of either kind is in the public code or in this page.
              </p>
              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">Theme Search, in detail</h4>
              <p className="text-gray-700 text-sm mb-3">
                Every text in the corpus is cut into overlapping <strong>passage windows</strong>:
                twelve lines starting a new window every six, and a coarser thirty lines every
                fifteen. Since October 2026 a long prose work (about a thousand works) is cut instead into
                paragraph-sized windows, and its chapter-sized windows are dropped. The overlap matters, because a passage that straddles a boundary would
                otherwise be split down the middle and neither half would describe it.
              </p>
              <p className="text-gray-700 text-sm mb-3">
                A language model then writes a structured English description of each window.
                The description always has the same eight fields. One of them is fixed: the
                <strong> kind of passage</strong>, chosen from nine categories (narrative, speech,
                lyric, argument, description, catalog, prayer, prophecy, dialogue). The others
                are written freely in English: the setting, who is present, what happens step by
                step, the objects in it, two to five <strong>theme words</strong>, the dominant imagery and tone, and a one-sentence gist.
                Your query is compared against the whole description, all eight fields joined,
                not against the original words. Under each result the site shows the gist sentence as the summary and
                the theme words as tags. The tags are the model&rsquo;s own words for that window,
                not a controlled list, so &ldquo;transience&rdquo; on one passage and
                &ldquo;impermanence&rdquo; on another mean the same thing. There are about
                685,000 descriptions on the site, covering Latin, Greek, English, Coptic,
                Hebrew, Persian and Urdu, with a few works in Italian, Old French and Middle
                High German. This is why a Persian passage can answer an English description of a Greek scene.
                Nothing is being translated and no words are being matched.
              </p>
              <p className="text-gray-700 text-sm mb-3">
                Comparing descriptions is quick and shallow, so the first page is then read. A
                small model on our own server takes the 300 rows of the composed list (about a hundred
                works, three passages each),
                reads each one against your query, and gives it a score for how fully it is the
                scene you described. The page is ordered by that score. It was trained once on
                32,000 readings by a larger model and costs nothing to run, so it stays on. Only
                those 300 rows are read: a passage the comparison did not bring into the
                list cannot be promoted by the reading. On sixteen test themes judged against a
                scholar's grading rule, the share of the first ten results that is the scene rose
                from about 29 to about 43 percent (the larger paid model, on the hundred closest passages, reaches 71). The result
                citation names the reading model, and adding <code>&amp;reader=0</code> to a
                search address shows the order without it. A new search takes about eight seconds the first time because the small model reads
                the passages.
              </p>
              <p className="text-gray-700 text-sm mb-3">
                The confidence band&rsquo;s thresholds are fitted against test queries, two thirds of them subjects the
                corpus certainly holds and a third it certainly does not, and they are published
                with the code so anyone can check them. They were refitted in October 2026 after the index grew by a third. On 178
                test subjects in eight language settings the fit agreed with its test set on 86
                percent: 80 percent for Latin and for Greek, 73 percent for English, 94 percent
                for Persian, Urdu, Hebrew and Coptic. Almost every miss is a subject the corpus
                holds that reads in the lowest band, or a subject from the modern world that
                reads moderate over its nearest neighbors. Until October 2026 the lowest band held the
                passages back behind a link, and a test of sixty historical subjects (short
                phrases and full sentences, the top ten of each graded by a model) showed why
                that was wrong: of thirty-one searches the band marked low, twenty-seven had a
                relevant list. The hardest test cases are near misses: &ldquo;a farmer lifts potatoes out of the
                ground and sorts them for seed&rdquo; scores higher than eight genuinely classical
                subjects, because everything in it except the potato is deeply present in the
                corpus.
              </p>
              <p className="text-gray-700 text-sm mb-3">
                The Scholarship choice in Theme Search ranks each note twice, once by how close its meaning is to
                your words and once by the words it shares with them, and merges the two rankings. On fifteen test
                questions, thirteen had a strongly relevant note in the first ten.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">The Reader&rsquo;s panel, in detail</h4>
              <p className="text-gray-700 text-sm mb-3">
                In Similar passages, names are found by capital letters in Latin, Greek and English, by the
                part-of-speech tags of the Hebrew and Coptic corpora (proper nouns in the Hebrew Bible&rsquo;s morphology
                and in Coptic Scriptorium&rsquo;s annotation), and in Persian and Urdu, which have no capitals, by the
                tagger&rsquo;s proper-noun tags plus a short list of prophets, lovers of romance and, for Urdu, the
                figures of Karbala. Commentaries on a work are set aside, and the Same people and places group starts
                collapsed when the selection&rsquo;s names are few or very famous. The In other languages buttons exist
                because the largest corpora would otherwise fill the list, so an Urdu passage would show mostly Persian.
              </p>
              <p className="text-gray-700 text-sm mb-3">
                In Verbal parallels, a line or short phrase is searched on all of its content words, and a passage-sized
                selection on its most distinctive words, the rarest in the corpus by document frequency. Rare shared
                vocabulary is what marks a genuine echo, and a couple of common words shared with a long passage is a
                commonplace. Matches survive by sharing at least one distinctive word, or three or more words together.
                Inscriptions and papyri are searched under the same rules.
              </p>
              <p className="text-gray-700 text-sm mb-3">
                In Scholarship, four open services supply the online results. OpenAlex and Crossref are searched by title and
                abstract. Semantic Scholar and CORE are searched in the full text of open-access papers. The site&rsquo;s own
                index of citations in journals from before 1923 reads JSTOR&rsquo;s Early Journal Content and covers 24
                philology, archaeology and biblical journals from 1827 to 1922. The same journals supply the Scholarship
                section on an inscription or papyrus page (956 citing sentences from 288 articles). Where the site has the
                library&rsquo;s agreement, a second index reads the journals on Project MUSE from 1996 on under that license
                and lists each article that cites the passage with one sentence and a DOI link. Google Books finds a citation
                on a book page. The RIS export goes to the clipboard, read by Zotero&rsquo;s File menu, Import from Clipboard,
                or as a file. A commentary note cites the edition the text comes from, with the passage it comments on. The
                HathiTrust link runs the same search in that library&rsquo;s book scans and tells you which books and page
                numbers mention the citation, without showing you the text itself.
              </p>

              <p className="text-gray-600 text-sm mt-4">
                The code is public at{' '}
                <a href="https://github.com/tesserae/tesserae-v6" className="text-red-700 hover:underline" target="_blank" rel="noopener noreferrer">
                  github.com/tesserae/tesserae-v6
                </a>
                . The changelog there lists every change to the live site, and docs/DATA_OPERATIONS.md
                records each rebuild of the indexes and caches.
              </p>
            </section>
          )}

          {activeSection === 'feedback' && (
            <div>
              <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Send Feedback</h3>
              <p className="text-gray-600 mb-4">Have a suggestion, found a bug, or want to share your experience? We'd love to hear from you.</p>
              
              <form onSubmit={submitFeedback} className="space-y-4 max-w-lg">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Your Name (optional)</label>
                    <input type="text" value={feedbackName} onChange={e => setFeedbackName(e.target.value)}
                      className="w-full border rounded px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Email (optional)</label>
                    <input type="email" value={feedbackEmail} onChange={e => setFeedbackEmail(e.target.value)}
                      className="w-full border rounded px-3 py-2 text-sm" />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Feedback Type</label>
                  <select value={feedbackType} onChange={e => setFeedbackType(e.target.value)}
                    className="w-full border rounded px-3 py-2 text-sm">
                    <option value="suggestion">Suggestion</option>
                    <option value="bug">Bug Report</option>
                    <option value="question">Question</option>
                    <option value="praise">Praise</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Your Message *</label>
                  <textarea value={feedbackMessage} onChange={e => setFeedbackMessage(e.target.value)}
                    placeholder="Tell us what's on your mind..."
                    rows={5} required className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                {feedbackStatus && (
                  <div className={`p-3 rounded text-sm ${feedbackStatus.type === 'success' ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700'}`}>
                    {feedbackStatus.text}
                  </div>
                )}
                <button type="submit" disabled={feedbackSubmitting}
                  className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50">
                  {feedbackSubmitting ? 'Sending...' : 'Send Feedback'}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
      <RequestDialog
        isOpen={suggestDialogOpen}
        onClose={() => setSuggestDialogOpen(false)}
        type="suggestion"
        context={{ page_url: typeof window !== 'undefined' ? window.location.href : '' }}
      />
    </div>
  );
}
