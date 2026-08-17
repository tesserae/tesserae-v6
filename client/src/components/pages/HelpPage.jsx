import { useEffect, useState, useRef } from 'react';
import { STOPLIST_INFO } from '../../data/stoplists';
import FusionFlowchart from '../search/FusionFlowchart';

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

const GPT_INSTRUCTIONS = `You are Tesserae, an assistant for finding intertextual parallels (allusions, echoes, quotations, borrowings) in classical literature, using the provided Tesserae actions. Follow the user's lead; they are the scholar. Show actual passages and loci; be candid about weak or ambiguous matches. Language codes: la (Latin), grc (Greek), en (English), cop (Coptic).

WHICH SEARCH TO USE
- General, unqualified two-text request ("find intertextual parallels between Aeneid 4 and Georgics 4"): use the FULL FUSION search (fusionSearchPoll) — Tesserae's comprehensive comparison, combining ten similarity signals (shared words, sound, meaning, rare vocabulary, syntax, and more). See FULL FUSION below for how to handle its timing. For a question about ONE book or poem of a larger work, either use that part's id directly (e.g. vergil.eclogues.part.1.tess) or pass source_ref_prefix/target_ref_prefix to filter the full result set by ref (a trailing dot pins the number, e.g. "ecl. 1." matches poem 1, not 10); use offset/limit to page deeper, since genuine parallels also appear below the top 100. Scores are relative to each pairing (baselines are per comparison), so compare ranks within a run, not absolute scores across runs.
- Requests emphasizing "distinctive", "rare", "unusual" shared vocabulary/phrases, or a fast exploratory scan: use rarePairsSearch (rare shared word-pairs) or rareWordsSearch (rare shared single words) — fast, and targeted at distinctive vocabulary.
- How widespread or distinctive a candidate expression is across the whole corpus: use lineSearch. Report distinct_loci (total is now deduplicated to match it — the corpus lists some whole works and their parts separately); pass a small max_results/limit. Exact search matches whole words (an enclitic on the final word is allowed, so "arma virum" still finds "arma virumque"). Use this to test the strongest candidates from a rare-pairs/rare-words scan.
- A specific word, form, or pattern the scholar names: stringSearch (wildcards, AND/OR/NOT, "phrases").
- Cross-language (e.g. a Greek model behind a Latin passage): crossLanguageSearch (POST only; separate source_language/target_language).

PRESENTATION (how to show results)
- Merge results into ONE list ranked by how interesting each parallel is (your synthesis of score, rarity, and cross-method convergence), not grouped by which search produced it. Quote the COMPLETE line of BOTH passages with their loci, never a paraphrase, and mark the shared words in bold on both sides (bold each form when the shared word wears different forms, e.g. "tua **rura manebunt**" against "**manet** divini gloria **ruris**").
- EVERY entry carries its corpus-wide context, in plain words: run lineSearch with count_only:true on the shared words for how common they are (cheap). When that count is small (roughly under 40), also say who else uses it and when; above that, give the number and call it commonplace. If a count cannot be retrieved, say "unquantified"; if the response is capped, say "at least N", never "N+".
- Write for a reader, not a pipeline: translate the numbers into plain English ("these words occur together in only 8 places in all of surviving Latin"), and keep technical terms (lemma, distinct loci, channels) for when the user asks how a figure was produced.
- Never describe results you have not fetched — do not claim the tail is "all common words" or empty; genuine parallels appear deep in the ranking. Close with an open offer to continue, page deeper (offset), filter to a section (ref prefix), or search elsewhere.
- When the user is recording a count for use elsewhere (a paper, a note), quote the corpus_version stamp with it, e.g. "8 places, corpus version 2026-08-16".

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

export default function HelpPage({ initialSection = null, onSectionConsumed } = {}) {
  const [activeSection, setActiveSection] = useState(initialSection || 'getting-started');
  const contentRef = useRef(null);

  // If opened at a specific section (e.g. via the "use your own AI" flag),
  // apply it once on mount and let the parent clear the request. On mobile the
  // section list stacks above the content, so scroll to the content itself —
  // otherwise the deep-link lands on the section nav, not the section.
  useEffect(() => {
    if (initialSection) {
      setActiveSection(initialSection);
      if (onSectionConsumed) onSectionConsumed();
      // Land at the very top of the page so the site header and the section
      // heading are both visible, rather than scrolling the content up under
      // the sticky nav (which cut off the heading).
      requestAnimationFrame(() => {
        window.scrollTo({ top: 0 });
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [expandedStoplists, setExpandedStoplists] = useState({});
  const [curatedStoplists, setCuratedStoplists] = useState(null);
  const [stoplistsError, setStoplistsError] = useState(null);
  const [requestName, setRequestName] = useState('');
  const [requestEmail, setRequestEmail] = useState('');
  const [requestAuthor, setRequestAuthor] = useState('');
  const [requestWork, setRequestWork] = useState('');
  const [requestLanguage, setRequestLanguage] = useState('');
  const [requestNotes, setRequestNotes] = useState('');
  const [requestESource, setRequestESource] = useState('');
  const [requestESourceUrl, setRequestESourceUrl] = useState('');
  const [requestPrintSource, setRequestPrintSource] = useState('');
  const [requestFile, setRequestFile] = useState(null);
  const [requestSubmitting, setRequestSubmitting] = useState(false);
  const [requestMessage, setRequestMessage] = useState(null);
  const [feedbackName, setFeedbackName] = useState('');
  const [feedbackEmail, setFeedbackEmail] = useState('');
  const [feedbackType, setFeedbackType] = useState('suggestion');
  const [feedbackMessage, setFeedbackMessage] = useState('');
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState(null);
  
  // Formatter utility state
  const [formatterAuthor, setFormatterAuthor] = useState('');
  const [formatterWork, setFormatterWork] = useState('');
  const [formatterTextType, setFormatterTextType] = useState('');
  const [formatterSubsectionCount, setFormatterSubsectionCount] = useState('1');
  const [formatterSlots, setFormatterSlots] = useState([
    { id: 1, startValues: ['1'], rawText: '' }
  ]);
  const [formatterOutput, setFormatterOutput] = useState('');
  const [formatterCopied, setFormatterCopied] = useState(false);

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
        const languageCards = [
          ['la', 'latin'],
          ['grc', 'greek'],
          ['en', 'english']
        ].map(([language, key]) => {
          const stoplist = payload.stoplists?.[language];
          if (!stoplist || !Array.isArray(stoplist.words)) {
            throw new Error('The stoplist response is incomplete');
          }
          return { key, label: stoplist.label, data: stoplist };
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

  const updateFormatterSlot = (slotId, field, value) => {
    setFormatterCopied(false);
    setFormatterSlots(prev => prev.map(slot => (
      slot.id === slotId ? { ...slot, [field]: value } : slot
    )));
  };

  const resizeStartValues = (values, count) => (
    Array.from({ length: count }, (_, index) => values?.[index] || '1')
  );

  const handleFormatterSubsectionCountChange = (value) => {
    const count = Math.min(5, Math.max(1, parseInt(value) || 1));
    setFormatterSubsectionCount(String(count));
    setFormatterCopied(false);
    setFormatterOutput('');
    setFormatterSlots(prev => prev.map(slot => ({
      ...slot,
      startValues: resizeStartValues(slot.startValues, count)
    })));
  };

  const updateFormatterStartValue = (slotId, index, value) => {
    setFormatterCopied(false);
    setFormatterOutput('');
    setFormatterSlots(prev => prev.map(slot => {
      if (slot.id !== slotId) return slot;
      const nextStartValues = resizeStartValues(slot.startValues, parseInt(formatterSubsectionCount) || 1);
      nextStartValues[index] = value;
      return { ...slot, startValues: nextStartValues };
    }));
  };

  const addFormatterSlot = () => {
    const count = parseInt(formatterSubsectionCount) || 1;
    setFormatterCopied(false);
    setFormatterOutput('');
    setFormatterSlots(prev => ([
      ...prev,
      {
        id: prev.length ? Math.max(...prev.map(slot => slot.id)) + 1 : 1,
        startValues: resizeStartValues(null, count),
        rawText: ''
      }
    ]));
  };

  const removeFormatterSlot = (slotId) => {
    setFormatterCopied(false);
    setFormatterOutput('');
    setFormatterSlots(prev => prev.filter(slot => slot.id !== slotId));
  };

  const handleFormatterTextTypeChange = (value) => {
    setFormatterTextType(value);
    setFormatterCopied(false);
    setFormatterOutput('');
    if (!value) {
      setFormatterSubsectionCount('1');
      setFormatterSlots([{ id: 1, startValues: ['1'], rawText: '' }]);
    }
  };

  const formatFormatterSlot = (author, work, slot) => {
    const lines = slot.rawText.split('\n').filter(line => line.trim());

    const subsectionDepth = Math.min(5, Math.max(1, parseInt(formatterSubsectionCount) || 1));
    const baseRefParts = resizeStartValues(slot.startValues, subsectionDepth);
    let currentLine = parseInt(baseRefParts[baseRefParts.length - 1]) || 1;

    return lines.map((line) => {
      const trimmedLine = line.trim();

      if (!trimmedLine) return null;

      const refParts = [...baseRefParts];
      refParts[refParts.length - 1] = String(currentLine);
      const tag = `<${author}.${work} ${refParts.join('.')}>`;
      currentLine++;

      return `${tag} ${trimmedLine}`;
    }).filter(Boolean).join('\n');
  };

  const formatToTess = () => {
    if (!formatterAuthor.trim() || !formatterWork.trim() || !formatterTextType) {
      return;
    }

    const author = formatterAuthor.toLowerCase().replace(/\s+/g, '_');
    const work = formatterWork.toLowerCase().replace(/\s+/g, '_');

    const combinedOutput = formatterSlots
      .map(slot => formatFormatterSlot(author, work, slot))
      .filter(Boolean)
      .join('\n');

    setFormatterCopied(false);
    setFormatterOutput(combinedOutput);
  };
  
  const romanToInt = (roman) => {
    const romanNumerals = { i: 1, v: 5, x: 10, l: 50, c: 100 };
    let result = 0;
    const r = roman.toLowerCase();
    for (let i = 0; i < r.length; i++) {
      const curr = romanNumerals[r[i]] || 0;
      const next = romanNumerals[r[i + 1]] || 0;
      result += curr < next ? -curr : curr;
    }
    return result || 1;
  };
  
  const copyFormatterOutput = () => {
    navigator.clipboard.writeText(formatterOutput);
    setFormatterCopied(true);
    setTimeout(() => setFormatterCopied(false), 2000);
  };
  
  const downloadFormatterOutput = () => {
    const author = formatterAuthor.toLowerCase().replace(/\s+/g, '_');
    const work = formatterWork.toLowerCase().replace(/\s+/g, '_');
    const blob = new Blob([formatterOutput], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${author}.${work}.tess`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const hasFormatterRawText = formatterSlots.some(slot => slot.rawText.trim());

  const toggleStoplist = (language) => {
    setExpandedStoplists((current) => ({
      ...current,
      [language]: !current[language]
    }));
  };

  const sections = [
    { id: 'getting-started', label: 'Getting Started', group: 'Start here' },
    { id: 'search-modes', label: 'The Types of Search', group: 'Start here' },

    { id: 'fusion-search', label: 'How Fusion Search Works', group: 'The Fusion (Phrases) search' },
    { id: 'match-types', label: 'Match Types', group: 'The Fusion (Phrases) search' },
    { id: 'settings', label: 'Search Settings', group: 'The Fusion (Phrases) search' },
    { id: 'stoplists', label: 'Stoplists', group: 'The Fusion (Phrases) search' },
    { id: 'results', label: 'Understanding Results', group: 'The Fusion (Phrases) search' },

    { id: 'languages', label: 'Languages', group: 'Languages' },
    { id: 'coptic', label: 'Coptic (in depth)', group: 'Languages' },
    { id: 'cross-lingual', label: 'Cross-Language Search', group: 'Languages' },

    { id: 'ai-guide', label: 'Use with your AI', group: 'Reference & tools' },
    { id: 'syntax-texts', label: 'Syntax', group: 'Reference & tools' },
    { id: 'best-practices', label: 'Search Tips', group: 'Reference & tools' },
    { id: 'repository', label: 'Repository', group: 'Reference & tools' },
    { id: 'upload-text', label: 'Upload Your Text', group: 'Reference & tools' },
    { id: 'faq', label: 'FAQ', group: 'Reference & tools' },
    { id: 'feedback', label: 'Send Feedback', group: 'Reference & tools' }
  ];

  const submitTextRequest = async (e) => {
    e.preventDefault();
    if (!requestAuthor.trim() || !requestWork.trim()) {
      setRequestMessage({ type: 'error', text: 'Please enter author and work title' });
      return;
    }
    setRequestSubmitting(true);
    setRequestMessage(null);
    try {
      const formData = new FormData();
      formData.append('name', requestName);
      formData.append('email', requestEmail);
      formData.append('author', requestAuthor);
      formData.append('work', requestWork);
      formData.append('language', requestLanguage);
      formData.append('notes', requestNotes);
      formData.append('e_source', requestESource);
      formData.append('e_source_url', requestESourceUrl);
      formData.append('print_source', requestPrintSource);
      if (requestFile) {
        formData.append('file', requestFile);
      }
      const res = await fetch('/api/request', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        setRequestMessage({ type: 'success', text: 'Text uploaded successfully! We will review and add it to the corpus soon.' });
        setRequestAuthor('');
        setRequestWork('');
        setRequestNotes('');
        setRequestESource('');
        setRequestESourceUrl('');
        setRequestPrintSource('');
        setRequestFile(null);
      } else {
        setRequestMessage({ type: 'error', text: data.error || 'Failed to submit text' });
      }
    } catch (err) {
      setRequestMessage({ type: 'error', text: 'Failed to submit request' });
    }
    setRequestSubmitting(false);
  };

  const submitFeedback = async (e) => {
    e.preventDefault();
    if (!feedbackMessage.trim()) {
      setFeedbackStatus({ type: 'error', text: 'Please enter your feedback' });
      return;
    }
    setFeedbackSubmitting(true);
    setFeedbackStatus(null);
    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: feedbackName,
          email: feedbackEmail,
          type: feedbackType,
          message: feedbackMessage
        })
      });
      const data = await res.json();
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

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="flex flex-col md:flex-row">
        <nav className="md:w-64 p-4 bg-gray-50 border-b md:border-b-0 md:border-r">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Help Topics</h2>
          <ul className="space-y-1">
            {sections.map((section, i) => (
              <li key={section.id}>
                {(i === 0 || sections[i - 1].group !== section.group) && (
                  <p className="px-3 pt-4 pb-1 text-[0.68rem] font-semibold uppercase tracking-wider text-gray-400 first:pt-1">
                    {section.group}
                  </p>
                )}
                <button
                  onClick={() => setActiveSection(section.id)}
                  className={`w-full text-left px-3 py-2 rounded text-sm ${
                    activeSection === section.id
                      ? 'bg-red-100 text-red-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {section.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div ref={contentRef} className="flex-1 p-6">
          {activeSection === 'getting-started' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Getting Started</h3>
              <p className="text-gray-700 mb-4">
                Tesserae offers several kinds of search. Most people start with the default — <strong>Phrases</strong>, which
                compares two texts and finds the passages most similar to each other. Here is the quick path:
              </p>
              <ol className="list-decimal list-inside space-y-4 text-gray-700">
                <li><strong>Select a language:</strong> Latin, Greek, English, or Coptic, from the tabs.</li>
                <li><strong>Choose a search type:</strong> the default is <strong>Phrases</strong> (compare two texts). See{' '}
                  <button onClick={() => setActiveSection('search-modes')} className="text-red-600 hover:underline">The Types of Search</button>{' '}
                  for the others (Lines, String Search, Rare Pairs, Rare Words).</li>
                <li><strong>Choose your texts:</strong> a <strong>source</strong> (usually the earlier text) and a <strong>target</strong> that may echo it.</li>
                <li><strong>Run the search:</strong> click "Find Parallels." Results are ranked by confidence, matched words are highlighted, and badges show which methods detected each pair.</li>
              </ol>
              <div className="mt-6 bg-amber-50 p-4 rounded-lg">
                <h4 className="font-medium text-amber-800 mb-2">Tip</h4>
                <p className="text-amber-700 text-sm">Start with a smaller section (e.g., Book 1) rather than complete works for faster results. Large comparisons like the full Aeneid vs. Metamorphoses can take up to 15 minutes on first run; subsequent searches are cached.</p>
              </div>
              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <p className="text-gray-700 text-sm">
                  <strong>Example:</strong> Compare Vergil's Aeneid Book 1 (source) with Lucan's Civil War Book 1 (target) to find how Lucan echoes Vergil.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'languages' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Languages</h3>
              <p className="text-gray-700 mb-5">
                Tesserae searches four languages. They share the same search types, but differ in how much of the corpus
                is covered and which detection channels have data to work with.
              </p>
              <div className="space-y-5">
                <div className="border-l-4 border-red-500 pl-4">
                  <h4 className="font-medium text-gray-900">Latin</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    The largest and best-developed corpus (~1,400 texts). All ten channels are available, and every text has been
                    grammatically parsed, so the syntax channels contribute. Latin has the most thoroughly evaluated results
                    (roughly 92% recall on the standard allusion benchmarks).
                  </p>
                </div>
                <div className="border-l-4 border-blue-500 pl-4">
                  <h4 className="font-medium text-gray-900">Greek</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    A large corpus (~650 texts). Vocabulary, sound, meaning, and rare-word channels all work; searches are
                    accent-insensitive, so you can enter text with or without diacritics. Greek does not yet have grammatical
                    parses, so the syntax channels contribute nothing for Greek.
                  </p>
                </div>
                <div className="border-l-4 border-emerald-500 pl-4">
                  <h4 className="font-medium text-gray-900">English</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    A small corpus (about a dozen texts), useful mainly for translations and demonstrations. The vocabulary and
                    meaning channels apply; there is no syntax data.
                  </p>
                </div>
                <div className="border-l-4 border-amber-500 pl-4">
                  <h4 className="font-medium text-gray-900">Coptic</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Sahidic and Bohairic (~180 texts) — the Coptic Bible plus monastic literature (Shenoute of Atripe and Besa).
                    Coptic is tuned for <strong>quotation and close reuse</strong> rather than allusion, with a verbatim-quotation
                    channel, sub-word lemmatization, and grammatical parses wired into the syntax channel. You can also search a
                    Coptic text against the Greek corpus to surface its Greek source. See{' '}
                    <button onClick={() => setActiveSection('coptic')} className="text-red-600 hover:underline">Coptic (in depth)</button>.
                  </p>
                </div>
              </div>
              <div className="mt-5 bg-gray-50 p-4 rounded-lg text-sm text-gray-700">
                <strong>Across languages:</strong> when a language lacks data for a channel (for example, syntax for Greek and English),
                that channel simply contributes nothing — the other channels still run.
              </div>
            </div>
          )}

          {activeSection === 'coptic' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Coptic Search</h3>
              <p className="text-gray-700 mb-4">
                Tesserae searches Sahidic Coptic alongside Latin, Greek, and English. The Coptic corpus combines the
                Coptic Bible with major works of monastic literature — the sermons and letters of Shenoute of Atripe
                and his successor Besa — so you can trace how Coptic authors quote scripture and reuse one another.
              </p>
              <p className="text-gray-700 mb-4">
                Coptic search is tuned differently from the classical languages. Where Latin and Greek search looks for
                allusion — shared rare vocabulary spread across a line — Coptic search is tuned for <strong>quotation
                and close reuse</strong>, the way Coptic monastic authors most often engage their sources.
              </p>

              <div className="my-4 bg-green-50 border border-green-200 p-4 rounded-lg">
                <h4 className="font-medium text-green-800 mb-1">Verbatim-quotation detection</h4>
                <p className="text-green-800 text-sm">
                  Coptic search's standout feature finds runs of identical consecutive words, catching direct
                  scriptural quotations even where the author gives no citation. In practice the highest-ranked
                  Coptic results are reliable quotations.
                </p>
              </div>

              <p className="text-gray-700 mb-3">
                Alongside quotation detection, Coptic search runs the same battery of methods as the other languages:
              </p>
              <ul className="list-disc list-inside space-y-1 text-gray-700 text-sm mb-4">
                <li><strong>Shared vocabulary</strong> — lines that share two or more dictionary words.</li>
                <li><strong>Sound</strong> — words that sound alike, useful across spelling variation.</li>
                <li><strong>Synonyms</strong> — related words drawn from the Coptic WordNet.</li>
                <li><strong>Grammatical structure</strong> — lines built the same way.</li>
                <li><strong>Meaning (AI)</strong> — a model that recognizes the same idea in different words (a multilingual model, for Coptic).</li>
              </ul>

              <div className="mt-4 bg-blue-50 p-4 rounded-lg">
                <h4 className="font-medium text-blue-800 mb-1">Coptic → Greek</h4>
                <p className="text-blue-800 text-sm">
                  Because much of Coptic scripture and literature was translated from Greek, you can search a Coptic
                  text against the Greek corpus to surface the Greek source behind a translation. Choose the
                  Coptic → Greek pair on the Cross-Language tab.
                </p>
              </div>

              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 className="font-medium text-gray-800 mb-1">Searching the whole corpus</h4>
                <p className="text-gray-700 text-sm">
                  From any result you can search the entire Coptic corpus for the words a parallel shares, to see
                  where else they occur. All of Shenoute's works are also available as a single combined text, so you
                  can search his whole surviving output at once.
                </p>
              </div>

              <div className="mt-4 bg-amber-50 border border-amber-200 p-4 rounded-lg">
                <h4 className="font-medium text-amber-900 mb-1">Typing Coptic (Line Search &amp; String Search)</h4>
                <p className="text-amber-900 text-sm mb-2">
                  No Coptic keyboard is needed. On the word-entry boxes, type in Latin using the{' '}
                  <strong>Leipzig-Jerusalem</strong> transliteration and the Coptic appears as you type
                  (you can also paste Coptic directly). Most letters are intuitive; the ones to know:
                </p>
                <ul className="list-disc list-inside space-y-1 text-amber-900 text-sm mb-2">
                  <li><code className="bg-amber-100 px-1 rounded">sh</code> = shai, <code className="bg-amber-100 px-1 rounded">h</code> = hori, <code className="bg-amber-100 px-1 rounded">f</code> = fai, <code className="bg-amber-100 px-1 rounded">j</code> = djandja, <code className="bg-amber-100 px-1 rounded">c</code> = kjima, <code className="bg-amber-100 px-1 rounded">+</code> = ti, <code className="bg-amber-100 px-1 rounded">x</code> = khai (Bohairic)</li>
                  <li>Capital <code className="bg-amber-100 px-1 rounded">E</code> = eta (long e) and capital <code className="bg-amber-100 px-1 rounded">O</code> = omega (long o); digraphs <code className="bg-amber-100 px-1 rounded">th ph kh ps ks</code> as expected.</li>
                </ul>
                <p className="text-amber-900 text-sm">
                  Coptic writes words joined into groups, so <strong>whole-word and phrase matching may miss a
                  word fused inside a group</strong>. In String Search, use a wildcard
                  (e.g. <code className="bg-amber-100 px-1 rounded">*rOme*</code>) to find a word wherever it sits.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'fusion-search' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">How Fusion Search Works</h3>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-sm text-blue-900">
                <strong>A note on examples:</strong> this section — and the ones that follow — uses <strong>Latin</strong> for its
                examples, but the same process applies to Greek, English, and Coptic. Where a language differs (for instance, Greek
                and English have no syntax data, and Coptic is tuned for quotation), it is noted along the way.
              </div>
              <p className="text-gray-700 mb-4">
                Tesserae's default search — <strong>Phrases</strong> — runs <strong>ten independent detection channels</strong> and combines their results.
                Each channel looks for a different kind of textual similarity — shared vocabulary, phonetic echo, semantic meaning,
                grammatical structure, and more. By fusing these signals, the system finds parallels that no single method could detect alone.
                The diagram below walks through the whole process step by step.
              </p>

              <FusionFlowchart />


              <p className="text-gray-700 mb-3">
                For a catalog of what each of the ten channels detects — and how to run a single one on its own — see{' '}
                <button onClick={() => setActiveSection('match-types')} className="text-red-600 hover:underline">Match Types</button>.
              </p>

              <h4 className="text-lg font-medium text-gray-900 mt-6 mb-3">How Results Are Combined</h4>
              <p className="text-gray-700 mb-3">
                Each channel produces its own candidate list with scores. The fusion step combines them using <strong>weighted score fusion</strong>:
                each channel's score is multiplied by a weight reflecting its precision, and the weighted scores are summed. Channels that produce
                fewer but more reliable results (like sound and edit distance) receive higher weights. The single-word lemma channel, which
                casts a wider net, receives a lower weight.
              </p>
              <p className="text-gray-700 mb-3">
                A <strong>convergence bonus</strong> rewards pairs found independently by multiple channels. If six out of ten channels all
                flag the same pair of lines, that agreement is strong evidence of a real connection — stronger than any single channel's
                score alone. The convergence bonus is weighted by word rarity: pairs sharing rare vocabulary get the full bonus,
                while pairs whose weakest word is very common receive a reduced bonus proportional to that word's frequency.
              </p>

              <h4 className="text-lg font-medium text-gray-900 mt-6 mb-3">Rarity Scoring and Function-Word Handling</h4>
              <p className="text-gray-700 mb-3">
                Not all shared words carry equal weight as evidence of allusion. Sharing the rare word <em>quercus</em> ("oak")
                is far more significant than sharing <em>et</em> ("and"). Fusion scoring applies a <strong>three-layer rarity system</strong>:
              </p>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2 mb-3">
                <li><strong>IDF multiplier:</strong> Each result's score is scaled by the geometric mean of its matched words' corpus
                  rarity (inverse document frequency). Common-word pairs are reduced proportionally; rare-word pairs are preserved or boosted.</li>
                <li><strong>Convergence weighting:</strong> The convergence bonus is gated by the rarest word's IDF. Pairs containing
                  a very common word receive less convergence credit, since multiple channels agreeing on a common word is expected, not meaningful.</li>
                <li><strong>Rarity boost:</strong> Rare multi-channel matches — where distinctive vocabulary is confirmed by several
                  independent channels — receive a bonus that promotes them above common-word results.</li>
              </ul>
              <p className="text-gray-700 mb-3">
                To cleanly separate function words from content words, the scoring uses a <strong>curated stoplist</strong> of
                66 Latin, 88 Greek, and 60 English function words (pronouns, conjunctions, prepositions, and common verbs like <em>sum</em>).
                Matches where all shared words are function words (e.g., sharing only <em>tum</em> + <em>inde</em>) are heavily
                penalized. Matches where a function word co-occurs with a content word (e.g., <em>nec</em> + <em>priorem</em>)
                are scored on the content word alone — the function word adds no allusion signal.
                This approach is more precise than pure frequency-based filtering: it correctly penalizes <em>tum</em> (a function word)
                without penalizing <em>pectore</em> (a content word that happens to be common).
              </p>

              <h4 className="text-lg font-medium text-gray-900 mt-6 mb-3">Frequency Baseline</h4>
              <p className="text-gray-700 mb-3">
                By default, word rarity is measured against the <strong>full Latin corpus</strong> (1,605 texts).
                This means a word like <em>arma</em> that appears in 57% of all Latin texts gets a low rarity score.
                But among hexameter poetry specifically, <em>arma</em> appears in 89% of texts — it is
                metrically convenient filler, not a distinctive vocabulary choice.
              </p>
              <p className="text-gray-700 mb-3">
                The <strong>Same meter</strong> frequency baseline (available under Advanced Settings for Latin fusion searches)
                computes rarity against only texts in the same metrical tradition — hexameter, elegiac, lyric, dramatic, or prose.
                This deflates vocabulary that is conventional within a meter while preserving the rarity of genuinely distinctive words.
                For example, when comparing two hexameter poems, <em>Neptunia proles</em> ("Neptune's offspring") — a standard
                epic epithet — receives less of a rarity boost under hexameter IDF, while a word rare even in hexameter
                retains its premium.
              </p>
              <p className="text-gray-700 mb-3 text-sm">
                The system automatically rescales meter-specific IDF values so that the scoring thresholds
                remain consistent regardless of which baseline you choose. Switching baselines does not affect recall — the
                same pairs are found — but it changes how they are ranked.
              </p>

              <h4 className="text-lg font-medium text-gray-900 mt-6 mb-3">Sliding Windows</h4>
              <p className="text-gray-700 mb-3">
                Poets don't always confine allusions to a single line. To catch vocabulary split across line breaks (enjambment),
                the system also searches <strong>two-line sliding windows</strong> — each consecutive pair of lines merged into one unit.
                Window results that are genuinely new are appended after line-mode results, adding recall without diluting precision.
              </p>

              <div className="mt-6 bg-gray-50 p-4 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-2">Performance</h4>
                <p className="text-gray-700 text-sm">
                  Evaluated against five benchmark datasets (862 parallels from published commentaries), fusion search finds <strong>92% of known parallels</strong> —
                  up from ~27% in Tesserae V3. On the Valerius Flaccus benchmark, 9 of the top 10 results are attested in scholarly commentary.
                </p>
              </div>

              <div className="mt-4 bg-amber-50 p-4 rounded-lg">
                <h4 className="font-medium text-amber-800 mb-2">Individual Channels</h4>
                <p className="text-amber-700 text-sm">
                  You can also run individual channels (Lemma, Exact, Semantic, etc.) by changing the Match Type dropdown.
                  This is useful when you want to isolate a specific kind of similarity, but fusion is recommended for general use.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'search-modes' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Search Modes</h3>
              <p className="text-gray-700 mb-6">Tesserae offers six search modes, accessible via tabs at the top of the search page:</p>

              <div className="space-y-6">
                <div className="border-l-4 border-red-500 pl-4">
                  <h4 className="font-medium text-gray-900">Phrases (Parallel Search)</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Compare a source text against a target text. The default match type is <strong>Fusion — All Channels</strong>, which
                    runs nine independent detection methods (lemma, exact, semantic, dictionary, sound, edit distance, syntax,
                    and rare vocabulary) and combines their results for the best recall.
                    You can also select individual match types (Lemma, Exact, Sound, etc.) from the dropdown.
                  </p>
                  <p className="text-gray-500 text-sm mt-2">
                    <strong>Use for:</strong> Discovering allusions, quotations, and thematic parallels between texts.
                    See{' '}
                    <button onClick={() => setActiveSection('match-types')} className="text-red-600 hover:underline">Match Types</button>{' '}for what each of the ten channels detects.
                  </p>
                </div>

                <div className="border-l-4 border-blue-500 pl-4">
                  <h4 className="font-medium text-gray-900">Lines (Line Search)</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Search for parallels to a specific line across the entire corpus. Select a line from any text,
                    or type/paste Latin or Greek text directly. For Greek, you can enter text with or without diacritics.
                    Three match types are available: <strong>Lemma</strong> (matches dictionary forms), <strong>Exact</strong> (identical
                    surface forms only), and <strong>Regular expression</strong> (pattern matching — see{' '}
                    <button onClick={() => setActiveSection('match-types')} className="text-red-600 hover:underline">
                      Match Types
                    </button>{' '}for details and examples).
                  </p>
                  <p className="text-gray-500 text-sm mt-2">
                    <strong>Use for:</strong> Finding all passages in the corpus that share vocabulary with a specific line of interest.
                  </p>
                  <div className="bg-gray-50 p-3 rounded mt-2 text-sm">
                    <strong>Example:</strong> Search for "arma virumque cano" to find all lines sharing "arma" and "vir" across 500+ results.
                  </div>
                </div>

                <div className="border-l-4 border-amber-500 pl-4">
                  <h4 className="font-medium text-gray-900">Rare Words</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Finds words that appear in fewer than 50 texts corpus-wide but are shared between your source
                    and target texts. These low-frequency words often indicate meaningful textual connections.
                  </p>
                  <p className="text-gray-500 text-sm mt-2">
                    <strong>Use for:</strong> Identifying distinctive vocabulary that suggests direct borrowing or influence.
                  </p>
                  <div className="bg-gray-50 p-3 rounded mt-2 text-sm">
                    <strong>Example:</strong> If "spumifer" appears in only 3 texts corpus-wide, and both Statius and Vergil use it, that's significant.
                  </div>
                </div>

                <div className="border-l-4 border-purple-500 pl-4">
                  <h4 className="font-medium text-gray-900">Rare Pairs</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Discovers unusual word combinations (bigrams) that appear together in very few texts.
                    Even if individual words are common, their pairing may be distinctive.
                  </p>
                  <p className="text-gray-500 text-sm mt-2">
                    <strong>Use for:</strong> Detecting stylistic fingerprints, <em>kakemphaton</em>, or formulaic expressions shared between authors.
                  </p>
                </div>

                <div className="border-l-4 border-amber-500 pl-4">
                  <h4 className="font-medium text-gray-900">String Search</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Wildcard and boolean search across the entire corpus. Perfect for finding
                    specific words, word patterns, or co-occurrences.
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

                <div className="border-l-4 border-blue-500 pl-4">
                  <h4 className="font-medium text-gray-900">Greek↔Latin (Cross-Lingual Search)</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Finds parallels across languages — Greek source vs. Latin target. Combines
                    AI semantic matching (SPhilBERTa neural embeddings) with a four-layer Greek-Latin
                    dictionary (925 curated pairs, 34,500+ V3 entries, proper names, and cognate detection).
                    Pairs detected by multiple channels receive a convergence bonus.
                  </p>
                  <p className="text-gray-500 text-sm mt-2">
                    <strong>Use for:</strong> Tracing how Latin authors adapted Greek sources — e.g., Vergil echoing Homer.
                    See{' '}
                    <button onClick={() => setActiveSection('cross-lingual')} className="text-red-600 hover:underline">
                      Cross-Lingual Search
                    </button>
                    {' '}for details.
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'match-types' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Match Types</h3>
              <p className="text-gray-700 mb-4">
                The default Phrases search runs all channels together (<strong>Fusion</strong>). You can also run a
                <strong> single method</strong> on its own — choose it from the Match Type dropdown — when you want just one kind of
                match, such as only exact quotations or only sound. Here is what each method (channel) detects:
              </p>
              <h4 className="text-lg font-medium text-gray-900 mt-6 mb-3">The Detection Channels</h4>
              <div className="space-y-3">
                <div className="border-l-4 border-red-400 pl-3">
                  <p className="text-sm text-gray-700"><strong>Lemma (2-word):</strong> The classic Tesserae approach — finds lines sharing two or more content-word dictionary forms. The workhorse channel for direct verbal echo.</p>
                </div>
                <div className="border-l-4 border-red-400 pl-3">
                  <p className="text-sm text-gray-700"><strong>Lemma (1-word):</strong> Same method, but requires only one shared word. Catches allusions built around a single pivotal term, like Lucan's <em>canimus</em> echoing Vergil's <em>cano</em>.</p>
                </div>
                <div className="border-l-4 border-red-400 pl-3">
                  <p className="text-sm text-gray-700"><strong>Exact:</strong> Matches identical surface forms (not lemmatized). Catches verbatim quotation and formulaic borrowing.</p>
                </div>
                <div className="border-l-4 border-blue-400 pl-3">
                  <p className="text-sm text-gray-700"><strong>Semantic (AI):</strong> Uses SPhilBERTa neural embeddings to detect lines with similar meaning, even with completely different vocabulary.</p>
                </div>
                <div className="border-l-4 border-blue-400 pl-3">
                  <p className="text-sm text-gray-700"><strong>Dictionary:</strong> Detects synonym substitution (<em>uariatio</em>) using 23,833 curated Latin word pairs — e.g., <em>gladius/ensis</em>, <em>mare/pontus</em>.</p>
                </div>
                <div className="border-l-4 border-amber-400 pl-3">
                  <p className="text-sm text-gray-700"><strong>Sound:</strong> Measures phonetic similarity via character trigram patterns. Detects alliteration, assonance, and phonetic echo.</p>
                </div>
                <div className="border-l-4 border-amber-400 pl-3">
                  <p className="text-sm text-gray-700"><strong>Edit Distance:</strong> Fuzzy character-level matching for morphological variants — <em>ferrea</em> matching <em>ferratos</em>, <em>belligeri</em> matching <em>belli</em>.</p>
                </div>
                <div className="border-l-4 border-purple-400 pl-3">
                  <p className="text-sm text-gray-700"><strong>Syntax:</strong> Compares grammatical dependency structures (parsed by LatinPipe) to detect parallel sentence construction. Includes a structural fingerprint path that matches lines with identical grammatical patterns even when they share no vocabulary — catching allusions built on structural imitation with complete lexical substitution. Because many unrelated Latin lines share common syntactic patterns, structural matches are confirmed by a two-tier gate: they must have either a dictionary synonym pair between the two lines or high semantic similarity (cosine ≥ 0.70). In validation testing on Vergil's <em>Georgics</em> 3 vs. Lucretius <em>DRN</em> 6, this gate preserved all meaningful structural parallels while filtering over 90% of coincidental pattern matches.</p>
                </div>
                <div className="border-l-4 border-purple-400 pl-3">
                  <p className="text-sm text-gray-700"><strong>Rare Vocabulary:</strong> Flags shared words that appear in fewer than 100 texts corpus-wide. A rare shared word is unlikely to be coincidence.</p>
                </div>
                <div className="border-l-4 border-green-500 pl-3">
                  <p className="text-sm text-gray-700"><strong>Verbatim Quotation (Coptic):</strong> Finds runs of three or more identical consecutive words. This channel is used for Coptic, where authors most often engage their sources by direct quotation — it catches scriptural quotations even when the author gives no citation. See the <em>Coptic Search</em> section for details.</p>
                </div>
              </div>
              <p className="text-gray-600 text-sm mt-3">
                These channels run for Latin, Greek, and English; Coptic adds the verbatim-quotation channel above.
              </p>

              <p className="text-gray-700 mb-4">
                <strong>Line Search</strong> offers three match types: <strong>Lemma</strong> (dictionary forms), <strong>Exact</strong>
                (identical surface forms), and <strong>Regular expression</strong> (patterns &mdash; see below).
              </p>

              <div className="mt-6 border-t pt-4" id="regex-help">
                <h4 className="font-medium text-gray-900 mb-2">Regular Expressions (Line Search)</h4>
                <p className="text-gray-600 text-sm mb-3">
                  In Line Search mode, the <strong>Regular expression</strong> option lets you search with patterns instead of
                  literal text. A regular expression (or "regex") is a sequence of characters that defines a search pattern.
                  This is a powerful tool for finding words with variant spellings, partial forms, or structural patterns.
                </p>
                <div className="bg-gray-50 p-3 sm:p-4 rounded-lg text-sm space-y-2 overflow-x-auto">
                  <p className="font-medium text-gray-800">Common patterns:</p>
                  <table className="w-full text-left text-xs sm:text-sm">
                    <tbody className="divide-y divide-gray-200">
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">arm.</td><td className="py-1 text-gray-600">Matches "arma", "arms", "army" — the dot matches any single character</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">amor|bellum</td><td className="py-1 text-gray-600">Matches lines containing "amor" OR "bellum"</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">ferr[aeiou]</td><td className="py-1 text-gray-600">Matches "ferra", "ferre", "ferri", "ferro", "ferru" — brackets match any one character listed</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">^arma</td><td className="py-1 text-gray-600">Matches "arma" only at the start of a line</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">cano$</td><td className="py-1 text-gray-600">Matches "cano" only at the end of a line</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">reg(is|em|i|e)</td><td className="py-1 text-gray-600">Matches "regis", "regem", "regi", "rege" — parentheses group alternatives</td></tr>
                      <tr><td className="py-1 pr-4 font-mono text-red-700 whitespace-nowrap">.*pietas.*arma.*</td><td className="py-1 text-gray-600">Matches any line containing "pietas" followed later by "arma" — <code>.*</code> means "any characters"</td></tr>
                    </tbody>
                  </table>
                </div>
                <p className="text-gray-500 text-sm mt-2">
                  Regex search checks each line in the corpus for a match against your pattern.
                  It does not use lemmatization — patterns match against the actual text as it appears.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'settings' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Search Settings</h3>
              <div className="bg-amber-50 p-4 rounded-lg border border-amber-200 mb-4">
                <p className="text-amber-700 text-sm">
                  <strong>Note:</strong> In Fusion mode (the default), most settings below are managed automatically by the
                  ten channels. Settings like Minimum Matches, Max Distance, and Stoplist apply when running individual match types.
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
                  <dt className="font-medium text-gray-900">Unit Type (Line/Phrase)</dt>
                  <dd className="text-gray-600 text-sm mt-1">
                    Compare by poetic lines (default) or prose sentences. Phrase mode splits on punctuation.
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Max Results</dt>
                  <dd className="text-gray-600 text-sm mt-1">
                    Maximum number of results to return (default: 5,000). Set to 0 for unlimited.
                    For most comparisons, the top 5,000 results capture all significant parallels.
                  </dd>
                </div>
              </dl>

              <h4 className="text-lg font-semibold text-gray-900 mt-8 mb-2">Advanced: Channels &amp; weights</h4>
              <p className="text-gray-700 text-sm mb-3">
                The Phrases (fusion) search blends several detection methods — called <em>channels</em> (shared words,
                sound, meaning, syntax, rare vocabulary, and more). Under <strong>Search Settings → Advanced —
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
                      kind of similarity count for more; the numbers are relative, not percentages.
                    </dd>
                  </div>
                  <div>
                    <dt className="font-medium text-gray-900">On / off switches</dt>
                    <dd className="text-gray-600 text-sm mt-1">
                      Turn a channel off to exclude it from the search entirely — for example, to look for parallels
                      using only sound and syntax. Switching a channel <em>off</em> is different from setting its weight
                      to zero: a channel at weight 0 still runs and can pull a pair into the results when it agrees with
                      other channels, whereas an off channel does not run at all.
                    </dd>
                  </div>
                  <div>
                    <dt className="font-medium text-gray-900">Only the channels that apply</dt>
                    <dd className="text-gray-600 text-sm mt-1">
                      The panel shows only the channels available for your chosen language — for instance, English does
                      not show the syntax or dictionary channels, since those rely on data Tesserae doesn't have for English.
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          )}

          {activeSection === 'stoplists' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Stoplists</h3>
              <p className="text-gray-700 mb-4">
                {STOPLIST_INFO.description}
              </p>
              <div className="bg-red-50 p-4 rounded-lg border border-red-200 mb-4">
                <h4 className="font-medium text-red-900 mb-1">Stoplists in Fusion Mode</h4>
                <p className="text-gray-700 text-sm">
                  In Fusion mode, stoplists play a dual role. Individual channels run without stoplist filtering (to maximize recall),
                  but the <strong>fusion scoring layer</strong> uses the curated function-word stoplist to identify and penalize
                  matches built entirely on function words. This means that sharing <em>tum</em> + <em>nec</em> will be ranked
                  far below sharing <em>pectore</em> + <em>curas</em>, even though both are two-word matches. The stoplist gives
                  the scoring system a precise way to distinguish grammatical co-occurrence from genuine allusion.
                </p>
              </div>
              
              <h4 className="font-medium text-gray-900 mt-6 mb-2">How the Default Stoplist Works</h4>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-1 ml-2">
                {STOPLIST_INFO.howItWorks.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>

              <h4 className="font-medium text-gray-900 mt-6 mb-2">Curated Stop Words by Language</h4>
              <p className="text-gray-600 text-sm mb-3">
                Expand a language to see every curated entry. Greek entries are shown in polytonic (accented) form;
                the matcher itself filters on the accentless normalized form.
              </p>
              {curatedStoplists === null && !stoplistsError ? (
                <p className="text-sm text-gray-500" role="status">Loading the current curated stoplists…</p>
              ) : stoplistsError ? (
                <p className="text-sm text-red-700" role="alert">
                  The current curated stoplists could not be loaded. Please try again later.
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3">
                  {curatedStoplists.map(({ key, label, data }) => {
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
                            <div className="flex flex-wrap gap-1" aria-label={`Full curated ${label} stoplist`}>
                              {data.words.map((word, i) => (
                                <code key={word} className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
                                  {data.display?.[i] ?? word}
                                </code>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="text-xs text-gray-500 italic mt-1">
                            {(data.display ?? data.words).slice(0, 13).join(', ')}...
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              <h4 className="font-medium text-gray-900 mt-6 mb-2">Stoplist Options</h4>
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

              <h4 className="font-medium text-gray-900 mt-6 mb-2">Stoplist Basis</h4>
              <p className="text-gray-600 text-sm">
                Choose which text(s) to analyze for building the stoplist:
              </p>
              <ul className="list-disc list-inside text-gray-600 text-sm mt-2 ml-2 space-y-1">
                <li><strong>Source + Target</strong>: Uses word frequencies from both texts (recommended)</li>
                <li><strong>Source Only</strong>: Only considers frequencies in the source text</li>
                <li><strong>Target Only</strong>: Only considers frequencies in the target text</li>
                <li><strong>Full Corpus</strong>: Uses pre-computed frequencies from all texts in the corpus</li>
              </ul>

              <h4 className="font-medium text-gray-900 mt-6 mb-2">Custom Stopwords</h4>
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
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Understanding Results</h3>
              <div className="space-y-4">
                <div>
                  <h4 className="font-medium text-gray-900">Score</h4>
                  <p className="text-gray-600 text-sm mb-2">
                    Higher scores indicate more significant parallels. The scoring method depends on the search mode:
                  </p>
                  <div className="bg-red-50 p-3 rounded border border-red-200 mb-2">
                    <p className="text-sm text-gray-700">
                      <strong>Fusion mode (default):</strong> Each channel produces its own score, which is multiplied by a
                      channel-specific weight and summed. A <em>convergence bonus</em> rewards pairs detected by multiple
                      independent channels. The combined score is then scaled by the <em>rarity</em> of the matched vocabulary:
                      pairs sharing rare content words score higher than pairs sharing common function words. A curated
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
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">Reading the Scores</h4>
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
                    <li>Judge the passages, not the number. Tesserae finds candidates; whether a parallel is
                        a real allusion, an echo, a shared formula, or a coincidence is a scholarly judgment
                        you make by reading the two passages in context.</li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">Channel Badges</h4>
                  <p className="text-gray-600 text-sm">
                    In Fusion mode, each result displays colored badges showing which channels detected it.
                    More badges generally indicates a stronger, more reliable parallel. Badges are grouped by category:
                  </p>
                  <ul className="list-disc list-inside text-gray-600 text-sm mt-1 ml-4">
                    <li><span className="text-red-600 font-medium">Red</span> — Vocabulary channels (lemma, exact, dictionary, rare word)</li>
                    <li><span className="text-blue-600 font-medium">Blue</span> — Semantic channels (AI semantic)</li>
                    <li><span className="text-amber-600 font-medium">Amber</span> — Sound channels (sound, edit distance)</li>
                    <li><span className="text-purple-600 font-medium">Purple</span> — Structure channels (syntax)</li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">Highlighting</h4>
                  <ul className="list-disc list-inside text-gray-600 text-sm mt-1">
                    <li><span className="bg-yellow-200 px-1 rounded">Yellow</span> — Matched lemmas (shared dictionary forms)</li>
                    <li><span className="bg-indigo-200 px-1 rounded">Indigo</span> — Synonym matches (dictionary or semantic similarity)</li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">Actions</h4>
                  <ul className="list-disc list-inside text-gray-600 text-sm mt-1">
                    <li><strong>Export CSV</strong>: Download all results as a spreadsheet</li>
                    <li><strong>Search Corpus</strong>: Find these matched words across all texts</li>
                    <li><strong>Register</strong>: Save to the Intertext Repository</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'best-practices' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Search Tips</h3>
              <p className="text-gray-700 mb-4">
                Tips for getting the most out of Tesserae. The default Fusion mode handles most settings
                automatically, but these strategies can help refine your results.
              </p>

              <h4 className="font-medium text-gray-900 mt-6 mb-3">Getting Started</h4>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Use Fusion (the default)</strong>: It runs ten channels and finds far more parallels than any single method. Start here.</li>
                <li><strong>Start small, then expand</strong>: Begin with a single book comparison, then broaden to complete works</li>
                <li><strong>Focus on the top results</strong>: Fusion ranks results by combined confidence. The highest-scoring results are overwhelmingly genuine parallels.</li>
                <li><strong>Check channel badges</strong>: Results flagged by many independent channels are the most reliable</li>
              </ul>

              <h4 className="font-medium text-gray-900 mt-6 mb-3">Narrowing Down Results</h4>
              <p className="text-gray-600 text-sm mb-2">When you have too many results or want more precision:</p>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Select smaller text sections</strong>: Choose individual books instead of complete works (e.g., "Aeneid, Book 1" rather than "Aeneid (Complete)")</li>
                <li><strong>Add custom stopwords</strong>: Exclude common thematic words that create noise (e.g., "bellum" in war narratives, "amor" in love poetry)</li>
                <li><strong>Sort by score</strong>: The highest scores represent the strongest parallels</li>
                <li><strong>Try individual channels</strong>: Switch from Fusion to a specific match type (Lemma, Semantic, etc.) to isolate one kind of similarity</li>
              </ul>

              <h4 className="font-medium text-gray-900 mt-6 mb-3">Expanding Results</h4>
              <p className="text-gray-600 text-sm mb-2">When you want to cast a wider net:</p>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Select complete works</strong>: Search entire texts rather than individual books</li>
                <li><strong>Increase max results</strong>: The default is 5,000. Set to 0 for unlimited results.</li>
                <li><strong>Use the Lines tab</strong>: Search a single line against the entire 2,100+ text corpus</li>
                <li><strong>Try Rare Words or Rare Pairs</strong>: These specialized modes find distinctive vocabulary connections that complement Fusion</li>
              </ul>

              <h4 className="font-medium text-gray-900 mt-6 mb-3">General Tips</h4>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Export for analysis</strong>: Download CSV files to analyze results in spreadsheet software</li>
                <li><strong>Check the corpus</strong>: Use "Search Corpus" on a result to see where else those words co-occur</li>
                <li><strong>Register discoveries</strong>: Add significant parallels to the Repository for future reference</li>
                <li><strong>Greek diacritics are optional</strong>: You can search Greek with or without accents and breathings</li>
              </ul>
            </div>
          )}

          {activeSection === 'cross-lingual' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Cross-Lingual Search (Greek↔Latin)</h3>
              <p className="text-gray-700 mb-4">
                The Greek↔Latin tab enables searching for parallels <em>across languages</em> —
                finding how Greek texts influenced Latin authors or vice versa. The search uses
                two-channel fusion, combining AI semantic matching with dictionary-based vocabulary
                lookup. Pairs detected by both channels receive a convergence bonus, pushing the
                most confident matches to the top.
              </p>
              <div className="space-y-4">
                <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                  <h4 className="font-medium text-blue-800 mb-2">Channel 1: AI Semantic</h4>
                  <p className="text-blue-700 text-sm">
                    Uses the SPhilBERTa neural model, trained on parallel Greek-Latin texts, to find conceptually
                    similar passages. Detects thematic connections and paraphrased ideas even where
                    no direct vocabulary correspondence exists. Results show a cosine similarity percentage.
                  </p>
                </div>
                <div className="bg-amber-50 p-4 rounded-lg border border-amber-200">
                  <h4 className="font-medium text-amber-900 mb-2">Channel 2: Greek↔Latin Dictionary</h4>
                  <p className="text-amber-700 text-sm mb-2">
                    Finds shared vocabulary across languages using four matching layers:
                  </p>
                  <ul className="text-amber-700 text-sm space-y-1 ml-4 list-disc list-inside">
                    <li><strong>Curated pairs</strong> — 925 hand-verified Greek-Latin translation equivalences across 17 semantic categories (e.g., ἀνήρ→vir, ἐνέπω→cano, μένος→furor)</li>
                    <li><strong>V3 dictionary</strong> — 34,500+ Greek-Latin word pairs from Lewis & Short / LSJ</li>
                    <li><strong>Proper names</strong> — 1,500+ Greek-Latin name pairs from Wikidata and the Pleiades gazetteer (e.g., Ἀχιλλεύς→Achilles)</li>
                    <li><strong>Cognate detection</strong> — automatic transliteration matching (e.g., Greek <em>philosophia</em> → Latin <em>philosophia</em>)</li>
                  </ul>
                  <p className="text-amber-700 text-sm mt-2">
                    Matched dictionary words are highlighted in the results. Scores use word rarity (IDF)
                    so rare vocabulary matches rank higher than common ones.
                  </p>
                </div>
                <div className="bg-teal-50 p-4 rounded-lg border border-teal-200">
                  <h4 className="font-medium text-teal-900 mb-2">Channel 3: Cross-Lingual Syntax</h4>
                  <p className="text-teal-700 text-sm">
                    Compares grammatical dependency structures across languages. Because Universal Dependencies labels
                    (nsubj, obj, obl, etc.) are language-independent, lines with identical dependency patterns are
                    matched directly — no shared vocabulary needed.
                  </p>
                </div>
                <div className="bg-violet-50 p-4 rounded-lg border border-violet-200">
                  <h4 className="font-medium text-violet-900 mb-2">Channel 4: Phonetic Transliteration</h4>
                  <p className="text-violet-700 text-sm">
                    Transliterates Greek tokens to Latin characters (e.g., μῆνιν → <em>menin</em>, Ἀχιλλεύς → <em>achileus</em>)
                    and compares them by edit distance against Latin tokens. Detects phonetic echoes across the script
                    boundary, such as Homer's μῆνιν echoed in Vergil's <em>Mene</em>. Acts as a convergence booster —
                    strengthens pairs already found by semantic or dictionary channels.
                  </p>
                </div>
                <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                  <h4 className="font-medium text-green-800 mb-2">Fusion &amp; Convergence</h4>
                  <p className="text-green-700 text-sm">
                    Pairs found by multiple channels receive a convergence bonus that boosts their score. For example, <em>Odyssey</em> 1.1 /
                    {' '}<em>Aeneid</em> 1.1 is detected semantically (48% cosine) and confirmed by dictionary matches
                    (ἄνδρα→virum, ἔννεπε→cano), so the convergence bonus pushes it above pairs detected by only one channel.
                    The "Min Dictionary Matches" filter lets you require a minimum number
                    of dictionary word matches — set to 1 to include semantic-only pairs, or raise it to focus on
                    vocabulary-confirmed parallels.
                  </p>
                </div>
              </div>
              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-2">Greek Input</h4>
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
              <div className="mt-4 bg-purple-50 p-4 rounded-lg border border-purple-200">
                <h4 className="font-medium text-purple-800 mb-2">What to Expect: Benchmark Results</h4>
                <p className="text-purple-700 text-sm mb-2">
                  Cross-lingual detection is substantially harder than same-language matching. Tested against
                  Knauer's catalog of 412 parallels between Vergil's <em>Aeneid</em> Book 1 and Homer's <em>Iliad</em>:
                </p>
                <ul className="text-purple-700 text-sm space-y-1 ml-4 list-disc list-inside">
                  <li><strong>~40%</strong> of gold-standard parallels found in top 50 (per-target-line ranking)</li>
                  <li><strong>~24%</strong> found in top 10</li>
                  <li>Only 31% of scholarly parallels have any shared vocabulary across languages</li>
                  <li>The remaining ~60% are thematic/narrative echoes beyond the reach of current lexical and AI methods</li>
                </ul>
                <p className="text-purple-700 text-sm mt-2">
                  For comparison, the Latin fusion system achieves 91.9% recall across five benchmarks using
                  ten channels. Cross-lingual search uses four channels: semantic embeddings, dictionary,
                  cross-lingual syntax (structural fingerprint matching via Universal Dependencies),
                  and phonetic transliteration (Greek→Latin character mapping for detecting sound echoes like μῆνιν ≈ Mene).
                </p>
              </div>
            </div>
          )}

          {activeSection === 'syntax-texts' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Syntax</h3>
              <p className="text-gray-700 mb-3">
                Syntax matching compares the <strong>grammatical structure</strong> of two lines — how the words relate as
                subjects, objects, and modifiers — rather than which words they use. In the Fusion search it works as
                <strong> two channels</strong>:
              </p>
              <ul className="list-disc list-inside text-gray-700 text-sm space-y-1 mb-3">
                <li><strong>Shared-word syntax:</strong> when two lines already share vocabulary, it checks whether those words sit in the same grammatical roles — a small confirmation that the parallel is structural, not coincidental.</li>
                <li><strong>Structural fingerprint:</strong> matches two lines with the same dependency skeleton (e.g. subject–verb–object) even when they share <em>no</em> vocabulary. To avoid firing on ordinary grammar, it only counts when another channel (synonyms or meaning) also links the pair.</li>
              </ul>
              <p className="text-gray-700 mb-4">
                Both add to the fused score on a <strong>sliding scale</strong>, but with low weight — syntax
                <strong> supplements</strong> the other channels rather than driving results. A separate <strong>Syntax</strong>{' '}
                checkbox in Search Settings can also apply it as a simple on/off boost.
              </p>

              <div className="bg-red-50 p-4 rounded border border-red-200 mb-4">
                <h4 className="font-medium text-red-800 mb-2">Latin — Full Coverage</h4>
                <p className="text-sm text-gray-700">
                  All <strong>1,429 Latin texts</strong> in the corpus (542,000+ lines) have been parsed for syntactic
                  dependencies using LatinPipe, a state-of-the-art Latin dependency parser. This means syntax matching
                  works for <em>any</em> Latin text pair — not just a curated subset.
                </p>
              </div>

              <div className="bg-amber-50 p-4 rounded border border-amber-200 mb-4">
                <h4 className="font-medium text-amber-800 mb-2">Coptic — Available</h4>
                <p className="text-sm text-gray-700">
                  The Coptic corpus (~180 Sahidic and Bohairic texts) is grammatically parsed and wired into the same syntax
                  channels, so Coptic searches use syntax the same way Latin does.
                </p>
              </div>
              <div className="bg-gray-50 p-4 rounded border border-gray-200 mb-4">
                <h4 className="font-medium text-gray-800 mb-2">Greek &amp; English — Not Yet</h4>
                <p className="text-sm text-gray-700">
                  Greek and English texts have not yet been parsed for grammar, so the syntax channels contribute nothing for
                  those languages — their other channels still run normally. (Because grammatical labels are language-independent,
                  cross-language structural matching becomes possible once Greek parses are added.)
                </p>
              </div>

              <div className="bg-gray-50 p-4 rounded mb-4">
                <h4 className="font-medium text-gray-900 mb-2">How It Works</h4>
                <p className="text-sm text-gray-600">
                  Each line is represented as a set of dependency relation patterns (e.g., <code className="bg-gray-200 px-1 rounded">nsubj→VERB</code>,
                  {' '}<code className="bg-gray-200 px-1 rounded">amod→NOUN</code>). Lines with similar grammatical structures
                  receive high syntax similarity scores. This catches parallels where an author mirrors sentence
                  structure — subject-verb-object order, subordinate clause placement, participial constructions — without
                  reusing any of the same words.
                </p>
              </div>

              <div className="bg-blue-50 p-4 rounded border border-blue-200">
                <h4 className="font-medium text-blue-800 mb-2">Credits</h4>
                <p className="text-sm text-gray-700">
                  Latin syntactic annotations are produced by <strong>LatinPipe</strong> (Straka & Straková, Charles University),
                  a neural dependency parser trained on Universal Dependencies treebanks. The parser processes raw Latin text
                  into full dependency trees with part-of-speech tags and grammatical relations.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'ai-guide' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Use Tesserae with your AI assistant</h3>
              <p className="text-gray-700 mb-4">
                You can let an AI assistant (ChatGPT or Claude) run Tesserae searches for you — comparing texts, testing
                parallels for uniqueness across the corpus, and helping you interpret the results. Tesserae does the
                searching, free, on its open API; the assistant orchestrates and interprets. The simplest, no-setup routes
                are the <strong>paste-in guide</strong>, which works in ChatGPT, Gemini, or any assistant, and the one-URL
                <strong>Claude connector</strong>.
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">1 · Paste-in guide <span className="text-sm font-normal text-gray-500">— any AI, no setup</span></h4>
              <p className="text-gray-700 text-sm mb-2">
                Works with any assistant that can browse the web (ChatGPT, Claude, Gemini, or an agent that makes HTTP
                requests). Open the guide, copy it, and paste it into your assistant as its first message — it teaches
                the assistant Tesserae's full toolbox and a step-by-step research workflow.
              </p>
              <p className="mb-6">
                <a href="/tesserae-data/ai-guide.html" target="_blank" rel="noopener noreferrer"
                  className="inline-block bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded no-underline">
                  Open the paste-in guide →
                </a>
              </p>

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">2 · Claude connector <span className="text-sm font-normal text-gray-500">— one URL, full fusion search built in</span></h4>
              <p className="text-gray-700 text-sm mb-2">
                Add Tesserae to Claude once, and regular chat Claude can run everything — including the full fusion
                search — with no Python and no guide-pasting. In <strong>Claude Desktop</strong> or <strong>claude.ai
                on a computer</strong>, go to <strong>Settings → Connectors → “Add custom connector”</strong> and paste
                this URL:
              </p>
              <CopyBlock text={MCP_CONNECTOR_URL} />
              <p className="text-gray-700 text-sm mt-2 mb-2">
                Then just ask, e.g.: “Use Tesserae to compare Aeneid 1 with Lucan's Civil War 1 and show the strongest
                parallels.” Custom connectors need a paid Claude plan and are added on desktop or web (not the mobile app).
              </p>
              <details className="text-sm text-gray-600 mb-6">
                <summary className="cursor-pointer text-gray-700 font-medium">Advanced: run the connector locally instead (offline; no account/connector needed)</summary>
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

              <h4 className="text-lg font-semibold text-gray-900 mt-6 mb-2">3 · ChatGPT <span className="text-sm font-normal text-gray-500">— paste the guide</span></h4>

              {OFFICIAL_GPT_URL ? (
                <>
                  <p className="text-gray-700 text-sm mb-2 font-medium">Use the official Tesserae GPT — no setup.</p>
                  <p className="mb-3">
                    <a href={OFFICIAL_GPT_URL} target="_blank" rel="noopener noreferrer"
                      className="inline-block bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-medium px-4 py-2 rounded no-underline">
                      Use Tesserae in ChatGPT →
                    </a>
                  </p>
                  <p className="text-gray-700 text-sm mb-4">
                    Open it and just ask it to find, compare, or investigate parallels — it calls the Tesserae API for you.
                    If it asks permission to contact <code>tesserae.caset.buffalo.edu</code>, choose <em>Allow</em>.
                  </p>
                </>
              ) : (
                <p className="text-gray-700 text-sm mb-4">
                  ChatGPT has no one-click Tesserae GPT, but the <strong>paste-in guide (option 1 above)</strong> works in
                  ChatGPT with no setup: open it, copy it, and paste it into a new ChatGPT chat as your first message.
                  ChatGPT then runs Tesserae's searches over the open API and follows the guide's workflow. Works on any
                  ChatGPT plan. If you have a ChatGPT Business, Team, Enterprise, or Edu workspace, you can also build your
                  own GPT (see below).
                </p>
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
                    <strong>Building or editing a GPT must be done in ChatGPT in a web browser</strong> at <code>chatgpt.com</code>
                    — the desktop app doesn't clearly expose the GPT-builder. (Once built, you and anyone you share it with
                    just chat with it normally, on any client, and you can edit it later.)
                  </p>
                  <ol className="list-decimal list-inside space-y-1">
                    <li>In ChatGPT (web browser): <strong>Explore GPTs → + Create → Configure</strong>. Name it <strong>Tesserae</strong>. (The <em>Preview</em> pane beside Configure is just for testing your draft.)</li>
                    <li>Paste the <em>Instructions</em> below into the Instructions box.</li>
                    <li><strong>Actions → Create new action → Import from URL</strong>, paste the schema URL below, set <strong>Authentication: None</strong>.</li>
                    <li>If you plan to share the GPT by link or publish it, add a <strong>Privacy policy</strong> URL (see the link below).</li>
                    <li>Test it (e.g. “List Vergil's texts”), then <strong>Create</strong> — privately or as a shared link.</li>
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
                    A custom GPT can run everything, including the full fusion search — it polls the fusion job until the
                    results are ready. Building GPTs is included in ChatGPT Plus.
                  </p>
                </div>
              </details>

              <div className="border border-gray-200 bg-gray-50 rounded p-3 text-sm text-gray-700 mb-4">
                <strong>A note on the full fusion search.</strong> Tesserae's most comprehensive comparison (“full fusion”)
                usually takes about <strong>2–3 minutes</strong>. It keeps running on the Tesserae server even after your
                assistant has replied, and the finished result is cached. If it's still running, just ask your assistant to
                “<em>check the fusion search</em>” after a couple of minutes — it will retrieve and discuss the completed
                results. The faster “rare-pairs” and “rare-words” searches return in seconds.
              </div>

              <div className="bg-amber-50 p-4 rounded border border-amber-200">
                <h4 className="font-medium text-amber-900 mb-2">A note on scholarly use</h4>
                <p className="text-gray-700 text-sm">
                  Tesserae's results are transparent and reproducible — anyone can re-run a search and inspect why a
                  parallel ranked where it did. Whatever your AI concludes from there is its own product. When you
                  publish, cite Tesserae for the parallels it found, and present the surrounding analysis as
                  AI-assisted interpretation you have checked.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'repository' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Intertext Repository</h3>
              <p className="text-gray-700 mb-4">
                Save discovered parallels to build a personal collection and optionally share with the scholarly community.
              </p>
              <div className="bg-blue-50 p-4 rounded border border-blue-200 mb-4">
                <h4 className="font-medium text-blue-800 mb-2">How to Register an Intertext</h4>
                <ol className="list-decimal list-inside text-gray-700 text-sm space-y-1">
                  <li>Click "Register" on any search result</li>
                  <li>Rate the scholarly significance (1-5 scale based on Coffee et al. 2012)</li>
                  <li>Add notes explaining the connection</li>
                  <li>Choose whether to share publicly</li>
                </ol>
              </div>
              <div className="bg-gray-50 p-4 rounded">
                <h4 className="font-medium text-gray-800 mb-2">Scoring Scale (Coffee et al. 2012)</h4>
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

          {activeSection === 'faq' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Frequently Asked Questions</h3>
              <div className="space-y-6">
                <div>
                  <h4 className="font-medium text-gray-900">What is Fusion search and should I use it?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Fusion is the default search mode. It runs nine independent detection channels simultaneously
                    and combines their results, finding 92% of known parallels in benchmark tests. Unless you need
                    to isolate a specific detection method, Fusion is recommended for general use.
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">Why is my search taking so long?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Fusion search runs ten channels, which takes longer than a single-channel search.
                    Try searching smaller sections (e.g., individual books) for faster results. Large text pairs
                    like the full Aeneid vs. Metamorphoses can take up to 15 minutes on first run but are cached
                    for subsequent searches. A progress timer is shown during the search.
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">What does "Refresh results" do?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Search results are cached so that repeating the same search is instant. The "Refresh results"
                    button (shown at the top of your results) clears the cached results for that search and runs it
                    again from scratch. Use this if the search engine has been updated since your last search and you
                    want to see improved results.
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">What does "Search queued" mean?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    When the server is already running heavy searches for other users, your search is placed in a
                    queue to prevent the server from running out of memory. You'll see a "Search queued" message
                    with a spinner. Your search will start automatically when a slot opens — typically within a few
                    minutes. You can cancel and retry later if you prefer.
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">Can I request a text that's not in the corpus?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Yes! Use the{' '}
                    <button onClick={() => setActiveSection('upload-text')} className="text-red-600 hover:underline">
                      Upload Your Text
                    </button>
                    {' '}section in this Help page.
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">How do I save my results?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Use "Export CSV" to download results as a spreadsheet, or "Register" to save individual parallels to the Intertext Repository.
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">What's the difference between Phrases and Lines search?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Phrases compares two specific texts against each other. Lines searches a single line
                    (selected from a text or typed in) against the entire corpus of 2,100+ texts.
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">How does the scoring work?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    In Fusion mode, each channel's score is multiplied by a weight and summed, with a convergence
                    bonus for pairs found by multiple channels. In individual channel mode, the V3-style algorithm
                    uses IDF (rare words score higher) and distance penalties (closer words score higher).
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">Does syntax matching work for Greek and English?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    All 1,429 Latin texts have full syntax coverage. Greek syntax parsing is in progress —
                    major texts including Homer are already parsed, with more being added. English syntax
                    parsing is planned but not yet started. The syntax channel contributes no results for
                    text pairs where parsing is unavailable.
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'upload-text' && (
            <div>
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Upload Your Text</h3>
              <p className="text-gray-600 mb-4">
                Have a text you'd like to add to the Tesserae corpus? Upload it here and we'll review it for inclusion.
                Pre-formatting your text speeds up the process significantly.
              </p>
              
              {/* Formatting Instructions */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                <h4 className="font-semibold text-blue-900 mb-2">Text Formatting Guidelines</h4>
                <p className="text-blue-800 text-sm mb-3">
                  Tesserae uses a simple <code className="bg-blue-100 px-1 rounded">.tess</code> format. 
                  Each line should have a section tag followed by the text content.
                </p>
                
                <div className="bg-white rounded p-3 mb-3 font-mono text-xs overflow-x-auto">
                  <div className="text-gray-500 mb-2"># Example format (Latin poetry):</div>
                  <div>&lt;vergil.aeneid 1.1&gt; Arma virumque cano, Troiae qui primus ab oris</div>
                  <div>&lt;vergil.aeneid 1.2&gt; Italiam, fato profugus, Laviniaque venit</div>
                  <div>&lt;vergil.aeneid 1.3&gt; litora, multum ille et terris iactatus et alto</div>
                  <div className="text-gray-500 mt-3 mb-2"># Example format (Greek prose):</div>
                  <div>&lt;plato.republic 1.327a&gt; Κατέβην χθὲς εἰς Πειραιᾶ μετὰ Γλαύκωνος</div>
                  <div className="text-gray-500 mt-3 mb-2"># Example format (English):</div>
                  <div>&lt;shakespeare.hamlet 1.1.1&gt; Who's there?</div>
                </div>
                
                <div className="text-sm text-blue-800 space-y-2">
                  <p><strong>Tag Format:</strong> <code className="bg-blue-100 px-1 rounded">&lt;author.work section&gt;</code></p>
                  <ul className="list-disc list-inside ml-2 space-y-1">
                    <li>Use lowercase author and work names with periods as separators</li>
                    <li>For poetry: use line numbers (e.g., <code className="bg-blue-100 px-1 rounded">1.1</code> for Book 1, Line 1)</li>
                    <li>For prose: use standard section references (e.g., <code className="bg-blue-100 px-1 rounded">1.327a</code>)</li>
                    <li>For drama: use act.scene.line (e.g., <code className="bg-blue-100 px-1 rounded">1.1.1</code>)</li>
                    <li>Plain text only - no HTML, markdown, or special formatting</li>
                    <li>UTF-8 encoding for Greek characters</li>
                  </ul>
                </div>
              </div>
              
              {/* Text Formatter Utility */}
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
                <h4 className="font-semibold text-amber-900 mb-3">Text Formatter Utility</h4>
                <p className="text-amber-900 text-sm mb-4">
                  Paste your plain text below and we'll convert it to .tess format automatically.
                </p>
                
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
                  <div>
                    <label className="block text-xs font-medium text-amber-900 mb-1">Author</label>
                    <input 
                      type="text" 
                      value={formatterAuthor} 
                      onChange={e => setFormatterAuthor(e.target.value)}
                      placeholder="e.g., Vergil"
                      className="w-full border border-amber-300 rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-amber-900 mb-1">Work</label>
                    <input 
                      type="text" 
                      value={formatterWork} 
                      onChange={e => setFormatterWork(e.target.value)}
                      placeholder="e.g., Aeneid"
                      className="w-full border border-amber-300 rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-amber-900 mb-1">Text Type</label>
                    <select 
                      value={formatterTextType} 
                      onChange={e => handleFormatterTextTypeChange(e.target.value)}
                      className="w-full border border-amber-300 rounded px-2 py-1 text-sm"
                    >
                      <option value="">Select text type</option>
                      <option value="poetry">Poetry</option>
                      <option value="prose">Prose</option>
                      <option value="drama">Drama</option>
                    </select>
                  </div>
                  {formatterTextType && (
                    <div>
                      <label className="block text-xs font-medium text-amber-900 mb-1">Subsections</label>
                      <select
                        value={formatterSubsectionCount}
                        onChange={e => handleFormatterSubsectionCountChange(e.target.value)}
                        className="w-full border border-amber-300 rounded px-2 py-1 text-sm"
                      >
                        {[1, 2, 3, 4, 5].map(count => (
                          <option key={count} value={count}>{count}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>

                {formatterTextType && (
                  <>
                    <div className="space-y-4">
                      {formatterSlots.map((slot, index) => (
                        <div key={slot.id} className="rounded-lg border border-amber-200 bg-white/70 p-3">
                          <div className="flex items-center justify-between gap-3 mb-3">
                            <div className="text-xs font-semibold uppercase tracking-wide text-amber-900">
                              Text Slot {index + 1}
                            </div>
                            {index > 0 && (
                              <button
                                type="button"
                                onClick={() => removeFormatterSlot(slot.id)}
                                className="text-xs font-medium text-amber-800 underline underline-offset-2 hover:text-amber-950"
                              >
                                Close
                              </button>
                            )}
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 mb-3">
                            {resizeStartValues(slot.startValues, parseInt(formatterSubsectionCount) || 1).map((value, partIndex) => (
                              <div key={partIndex}>
                                <label className="block text-xs font-medium text-amber-900 mb-1">
                                  Subsection {partIndex + 1}
                                </label>
                                <input
                                  type="number"
                                  min="1"
                                  value={value}
                                  onChange={e => updateFormatterStartValue(slot.id, partIndex, e.target.value)}
                                  className="w-full border border-amber-300 rounded px-2 py-1 text-sm"
                                />
                              </div>
                            ))}
                          </div>

                          <div>
                            <label className="block text-xs font-medium text-amber-900 mb-1">Paste Raw Text (one line per row)</label>
                            <textarea
                              value={slot.rawText}
                              onChange={e => updateFormatterSlot(slot.id, 'rawText', e.target.value)}
                              placeholder="Arma virumque cano, Troiae qui primus ab oris&#10;Italiam, fato profugus, Laviniaque venit&#10;litora, multum ille et terris iactatus et alto"
                              rows={8}
                              className="w-full border border-amber-300 rounded px-2 py-2 text-sm font-mono"
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="flex flex-wrap gap-2 mt-4">
                      <button
                        type="button"
                        onClick={addFormatterSlot}
                        className="px-4 py-2 bg-white text-amber-900 border border-amber-300 rounded hover:bg-amber-100"
                      >
                        Add More
                      </button>
                      <button
                        type="button"
                        onClick={formatToTess}
                        disabled={!formatterAuthor.trim() || !formatterWork.trim() || !hasFormatterRawText}
                        className="px-4 py-2 bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Format Text
                      </button>
                    </div>

                    <div className="mt-4">
                      <label className="block text-xs font-medium text-amber-900 mb-1">Formatted .tess Output</label>
                      <textarea
                        value={formatterOutput}
                        readOnly
                        rows={10}
                        className="w-full border border-amber-300 rounded px-2 py-2 text-sm font-mono bg-white"
                        placeholder="Formatted output will appear here..."
                      />
                      {formatterOutput && (
                        <div className="flex gap-2 mt-2">
                          <button
                            type="button"
                            onClick={copyFormatterOutput}
                            className="px-3 py-1 text-xs bg-amber-600 text-white rounded hover:bg-amber-700"
                          >
                            {formatterCopied ? 'Copied!' : 'Copy to Clipboard'}
                          </button>
                          <button
                            type="button"
                            onClick={downloadFormatterOutput}
                            className="px-3 py-1 text-xs bg-amber-700 text-white rounded hover:bg-amber-800"
                          >
                            Download .tess File
                          </button>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
              
              <h4 className="font-semibold text-gray-900 mb-3">Submit Your Formatted Text</h4>
              <form onSubmit={submitTextRequest} className="space-y-4 max-w-lg">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Your Name (optional)</label>
                    <input type="text" value={requestName} onChange={e => setRequestName(e.target.value)}
                      className="w-full border rounded px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Email (optional)</label>
                    <input type="email" value={requestEmail} onChange={e => setRequestEmail(e.target.value)}
                      className="w-full border rounded px-3 py-2 text-sm" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Author *</label>
                    <input type="text" value={requestAuthor} onChange={e => setRequestAuthor(e.target.value)}
                      placeholder="e.g., Tacitus" required className="w-full border rounded px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Language *</label>
                    <select value={requestLanguage} onChange={e => setRequestLanguage(e.target.value)}
                      required className="w-full border rounded px-3 py-2 text-sm">
                      <option value="">Select language...</option>
                      <option value="latin">Latin</option>
                      <option value="greek">Greek</option>
                      <option value="english">English</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Work Title *</label>
                  <input type="text" value={requestWork} onChange={e => setRequestWork(e.target.value)}
                    placeholder="e.g., Annales" required className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Upload Text File</label>
                  <input 
                    type="file" 
                    accept=".txt,.tess"
                    onChange={e => setRequestFile(e.target.files[0])}
                    className="w-full border rounded px-3 py-2 text-sm file:mr-3 file:py-1 file:px-3 file:border-0 file:bg-gray-100 file:text-gray-700 file:rounded file:cursor-pointer" 
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Accepts .txt or .tess files. Pre-formatted files are processed faster.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">e-Source</label>
                  <input
                    type="text"
                    value={requestESource}
                    onChange={e => setRequestESource(e.target.value)}
                    placeholder="e.g., Perseus"
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">e-Source URL</label>
                  <input
                    type="url"
                    value={requestESourceUrl}
                    onChange={e => setRequestESourceUrl(e.target.value)}
                    placeholder="https://..."
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Print Source (citation)</label>
                  <textarea
                    value={requestPrintSource}
                    onChange={e => setRequestPrintSource(e.target.value)}
                    placeholder="Edition/citation details"
                    rows={2}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                  <textarea value={requestNotes} onChange={e => setRequestNotes(e.target.value)}
                    placeholder="Source edition, date, or any additional information..."
                    rows={3} className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                {requestMessage && (
                  <div className={`p-3 rounded text-sm ${requestMessage.type === 'success' ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700'}`}>
                    {requestMessage.text}
                  </div>
                )}
                <button type="submit" disabled={requestSubmitting}
                  className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50">
                  {requestSubmitting ? 'Uploading...' : 'Upload Text'}
                </button>
              </form>
            </div>
          )}

          {activeSection === 'feedback' && (
            <div>
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Send Feedback</h3>
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
    </div>
  );
}
