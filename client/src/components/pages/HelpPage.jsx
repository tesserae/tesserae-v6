import { useState } from 'react';
import { STOPLIST_INFO } from '../../data/stoplists';

export default function HelpPage() {
  const [activeSection, setActiveSection] = useState('getting-started');
  const [requestName, setRequestName] = useState('');
  const [requestEmail, setRequestEmail] = useState('');
  const [requestAuthor, setRequestAuthor] = useState('');
  const [requestWork, setRequestWork] = useState('');
  const [requestLanguage, setRequestLanguage] = useState('latin');
  const [requestNotes, setRequestNotes] = useState('');
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
  const [formatterTextType, setFormatterTextType] = useState('poetry');
  const [formatterStartBook, setFormatterStartBook] = useState('1');
  const [formatterStartLine, setFormatterStartLine] = useState('1');
  const [formatterRawText, setFormatterRawText] = useState('');
  const [formatterOutput, setFormatterOutput] = useState('');
  const [formatterCopied, setFormatterCopied] = useState(false);

  const formatToTess = () => {
    if (!formatterAuthor.trim() || !formatterWork.trim() || !formatterRawText.trim()) {
      return;
    }
    
    const author = formatterAuthor.toLowerCase().replace(/\s+/g, '_');
    const work = formatterWork.toLowerCase().replace(/\s+/g, '_');
    const lines = formatterRawText.split('\n').filter(line => line.trim());
    
    let currentBook = parseInt(formatterStartBook) || 1;
    let currentLine = parseInt(formatterStartLine) || 1;
    
    const formatted = lines.map((line, idx) => {
      const trimmedLine = line.trim();
      
      // Check for book/section markers (e.g., "Book 2", "BOOK II", "Liber 3")
      const bookMatch = trimmedLine.match(/^(book|liber|chapter|act)\s*(\d+|[ivxlc]+)/i);
      if (bookMatch) {
        const bookNum = bookMatch[2].match(/^\d+$/) 
          ? parseInt(bookMatch[2]) 
          : romanToInt(bookMatch[2]);
        currentBook = bookNum;
        currentLine = 1;
        return null; // Skip the book marker line
      }
      
      // Skip empty lines after trimming
      if (!trimmedLine) return null;
      
      let tag;
      if (formatterTextType === 'poetry') {
        tag = `<${author}.${work} ${currentBook}.${currentLine}>`;
        currentLine++;
      } else if (formatterTextType === 'prose') {
        tag = `<${author}.${work} ${currentBook}.${currentLine}>`;
        currentLine++;
      } else if (formatterTextType === 'drama') {
        // For drama: act.scene.line format
        tag = `<${author}.${work} ${currentBook}.1.${currentLine}>`;
        currentLine++;
      }
      
      return `${tag} ${trimmedLine}`;
    }).filter(Boolean);
    
    setFormatterOutput(formatted.join('\n'));
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

  const sections = [
    { id: 'getting-started', label: 'Getting Started' },
    { id: 'search-modes', label: 'Search Modes' },
    { id: 'match-types', label: 'Match Types' },
    { id: 'settings', label: 'Search Settings' },
    { id: 'stoplists', label: 'Stoplists' },
    { id: 'results', label: 'Understanding Results' },
    { id: 'best-practices', label: 'Search Tips' },
    { id: 'cross-lingual', label: 'Cross-Lingual Search' },
    { id: 'syntax-texts', label: 'Syntax Matching Texts' },
    { id: 'repository', label: 'Repository' },
    { id: 'faq', label: 'FAQ' },
    { id: 'upload-text', label: 'Upload Your Text' },
    { id: 'feedback', label: 'Send Feedback' }
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
            {sections.map(section => (
              <li key={section.id}>
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

        <div className="flex-1 p-6">
          {activeSection === 'getting-started' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Getting Started</h3>
              <ol className="list-decimal list-inside space-y-4 text-gray-700">
                <li><strong>Select a Language:</strong> Choose Latin, Greek, or English from the language tabs.</li>
                <li><strong>Choose Source Text:</strong> Select the "source" text - typically the earlier text.</li>
                <li><strong>Choose Target Text:</strong> Select the "target" text - the later text that may contain the allusion.</li>
                <li><strong>Adjust Settings (Optional):</strong> Configure match type, minimum matches, and other parameters.</li>
                <li><strong>Run Search:</strong> Click "Find Parallels" to discover textual connections.</li>
              </ol>
              <div className="mt-6 bg-amber-50 p-4 rounded-lg">
                <h4 className="font-medium text-amber-800 mb-2">Tip</h4>
                <p className="text-amber-700 text-sm">Start with a smaller section (e.g., Book 1) rather than complete works for faster results.</p>
              </div>
              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <p className="text-gray-700 text-sm">
                  <strong>Example:</strong> Compare Vergil's Aeneid Book 1 (source) with Lucan's Civil War Book 1 (target) to find how Lucan echoes Vergil.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'search-modes' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Search Modes</h3>
              <p className="text-gray-700 mb-6">Tesserae offers five main search modes, accessible via tabs:</p>
              
              <div className="space-y-6">
                <div className="border-l-4 border-red-500 pl-4">
                  <h4 className="font-medium text-gray-900">Phrases (Parallel Search)</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    The default search mode. Finds passages that share multiple words between source and target texts. 
                    Uses lemma matching by default so "amor" matches "amorem", "amores", etc.
                  </p>
                  <p className="text-gray-500 text-sm mt-2">
                    <strong>Use for:</strong> Discovering allusions, quotations, and thematic parallels between texts.
                  </p>
                </div>

                <div className="border-l-4 border-blue-500 pl-4">
                  <h4 className="font-medium text-gray-900">Lines (Line Search)</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Search for parallels to a specific line across the entire corpus. Select a line from any text, 
                    or type/paste Latin or Greek text directly.
                  </p>
                  <p className="text-gray-500 text-sm mt-2">
                    <strong>Use for:</strong> Finding all passages in the corpus that share vocabulary with a specific line of interest.
                  </p>
                  <div className="bg-gray-50 p-3 rounded mt-2 text-sm">
                    <strong>Example:</strong> Search for "arma virumque cano" to find all lines sharing "arma" and "vir".
                  </div>
                </div>

                <div className="border-l-4 border-amber-500 pl-4">
                  <h4 className="font-medium text-gray-900">Rare Words</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Finds words that appear rarely across the entire corpus but are shared between your source 
                    and target texts. These low-frequency words often indicate meaningful textual connections.
                  </p>
                  <p className="text-gray-500 text-sm mt-2">
                    <strong>Use for:</strong> Identifying distinctive vocabulary that suggests direct borrowing or influence.
                  </p>
                  <div className="bg-gray-50 p-3 rounded mt-2 text-sm">
                    <strong>Example:</strong> If "laticlavius" appears only 3 times in the corpus, and both Vergil and Lucan use it, that's significant.
                  </div>
                </div>

                <div className="border-l-4 border-purple-500 pl-4">
                  <h4 className="font-medium text-gray-900">Word Pairs (Bigram Search)</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Discovers unusual word combinations (bigrams) that appear together in very few texts. 
                    Even if individual words are common, their pairing may be distinctive.
                  </p>
                  <p className="text-gray-500 text-sm mt-2">
                    <strong>Use for:</strong> Detecting stylistic fingerprints, <em>kakemphaton</em>, or formulaic expressions shared between authors.
                  </p>
                </div>

                <div className="border-l-4 border-green-500 pl-4">
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
              </div>
            </div>
          )}

          {activeSection === 'match-types' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Match Types</h3>
              <p className="text-gray-700 mb-4">Within Phrases search, choose how words are matched:</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900">Lemma (default)</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Matches words with the same dictionary form. "amor" matches "amorem", "amores", etc.
                    Best for finding semantic parallels.
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900">Exact</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Only identical word forms match. Good for finding direct quotations or formulaic phrases.
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900">Sound (Trigrams)</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Matches based on phonetic similarity using character patterns. Detects alliteration, 
                    rhyme, assonance, and consonance.
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900">Edit Distance</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Fuzzy matching for character-similar words. Finds morphological variants and spelling 
                    variations: "bellum" matches "bello", "bella".
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg md:col-span-2">
                  <h4 className="font-medium text-gray-900">Semantic (AI)</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Uses deep learning embeddings to find passages with similar meaning, even with different vocabulary.
                    Powered by the SPhilBERTa model trained on classical texts. Includes 54,000+ synonym pairs.
                    Examples: numen~deus, bellum~proelium, ignis~flamma.
                  </p>
                </div>
              </div>
              <p className="text-gray-600 text-sm mt-4">
                <strong>Tip:</strong> Sound and Edit Distance can also be enabled as feature boosts when using Lemma or Exact matching.
              </p>
            </div>
          )}

          {activeSection === 'settings' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Search Settings</h3>
              <dl className="space-y-4">
                <div>
                  <dt className="font-medium text-gray-900">Minimum Matches</dt>
                  <dd className="text-gray-600 text-sm mt-1">
                    Require at least N shared words (default: 2). Higher values find stronger parallels but fewer results.
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
              </dl>
            </div>
          )}

          {activeSection === 'stoplists' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Stoplists</h3>
              <p className="text-gray-700 mb-4">
                {STOPLIST_INFO.description}
              </p>
              
              <h4 className="font-medium text-gray-900 mt-6 mb-2">How the Default Stoplist Works</h4>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-1 ml-2">
                {STOPLIST_INFO.howItWorks.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>

              <h4 className="font-medium text-gray-900 mt-6 mb-2">Curated Stop Words by Language</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3">
                <div className="bg-gray-50 rounded-lg p-3">
                  <h5 className="font-medium text-gray-800 mb-1">Latin ({STOPLIST_INFO.latin.count} words)</h5>
                  <p className="text-xs text-gray-500 italic">
                    {STOPLIST_INFO.latin.examples.join(', ')}...
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <h5 className="font-medium text-gray-800 mb-1">Greek ({STOPLIST_INFO.greek.count} words)</h5>
                  <p className="text-xs text-gray-500 italic">
                    {STOPLIST_INFO.greek.examples.join(', ')}...
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <h5 className="font-medium text-gray-800 mb-1">English ({STOPLIST_INFO.english.count} words)</h5>
                  <p className="text-xs text-gray-500 italic">
                    {STOPLIST_INFO.english.examples.join(', ')}...
                  </p>
                </div>
              </div>

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
                  <p className="text-gray-600 text-sm">
                    Higher scores indicate more significant parallels. The score combines:
                  </p>
                  <ul className="list-disc list-inside text-gray-600 text-sm mt-1 ml-4">
                    <li>IDF (Inverse Document Frequency) - rare words score higher</li>
                    <li>Distance penalty - closer matched words score higher</li>
                    <li>Number of matches - more shared words score higher</li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">Highlighting</h4>
                  <ul className="list-disc list-inside text-gray-600 text-sm mt-1">
                    <li><span className="bg-yellow-200 px-1 rounded">Yellow</span> - Matched lemmas (dictionary forms)</li>
                    <li><span className="bg-indigo-200 px-1 rounded">Indigo</span> - Synonym matches (semantic similarity)</li>
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
                Tips for refining your searches to find the most relevant parallels.
              </p>

              <h4 className="font-medium text-gray-900 mt-6 mb-3">Narrowing Down Results</h4>
              <p className="text-gray-600 text-sm mb-2">Use these strategies when you have too many results or want more precision:</p>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Select smaller text sections</strong>: Choose individual books instead of complete works (e.g., "Aeneid, Book 1" rather than "Aeneid (Complete)")</li>
                <li><strong>Increase minimum matches</strong>: Require 3+ shared words instead of the default 2</li>
                <li><strong>Add custom stopwords</strong>: Exclude common thematic words that create noise (e.g., "bellum" in war narratives, "amor" in love poetry)</li>
                <li><strong>Reduce max distance</strong>: Lower from 999 to require matched words to appear closer together</li>
                <li><strong>Enable score boosts</strong>: Turn on "Bigram frequency boost" to prioritize rare word pairs</li>
                <li><strong>Use syntax matching</strong>: For supported texts, require grammatical structure similarity</li>
                <li><strong>Sort by score</strong>: Focus on highest-scoring results first</li>
              </ul>

              <h4 className="font-medium text-gray-900 mt-6 mb-3">Expanding Results</h4>
              <p className="text-gray-600 text-sm mb-2">Use these strategies when you want to cast a wider net:</p>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Select complete works</strong>: Search entire texts rather than individual books</li>
                <li><strong>Lower minimum matches</strong>: Set to 2 (the minimum) to catch more parallels</li>
                <li><strong>Disable stoplist</strong>: Enter -1 in Stoplist Size to include all words (not recommended for large texts)</li>
                <li><strong>Use semantic matching</strong>: Switch to "AI Semantic" match type to find conceptually similar passages</li>
                <li><strong>Try sound matching</strong>: "Sound Matching" finds words that sound alike across texts</li>
                <li><strong>Increase max results</strong>: Set to 0 for unlimited results, or raise the limit</li>
              </ul>

              <h4 className="font-medium text-gray-900 mt-6 mb-3">General Tips</h4>
              <ul className="list-disc list-inside text-gray-600 text-sm space-y-2 ml-2">
                <li><strong>Start small, then expand</strong>: Begin with a single book comparison, then broaden your search</li>
                <li><strong>Save interesting searches</strong>: Use "Save Search" to bookmark productive queries</li>
                <li><strong>Export for analysis</strong>: Download CSV files to analyze results in spreadsheet software</li>
                <li><strong>Check the corpus</strong>: Use "Search Corpus" on a result to see where else those words co-occur</li>
                <li><strong>Register discoveries</strong>: Add significant parallels to the Repository for future reference</li>
              </ul>
            </div>
          )}

          {activeSection === 'cross-lingual' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Cross-Lingual Search (Greek↔Latin)</h3>
              <p className="text-gray-700 mb-4">
                The Greek↔Latin tab enables searching for parallels <em>across languages</em> - 
                finding how Greek texts influenced Latin authors or vice versa.
              </p>
              <div className="space-y-4">
                <div className="bg-amber-50 p-4 rounded-lg border border-amber-200">
                  <h4 className="font-medium text-amber-800 mb-2">AI Semantic Mode</h4>
                  <p className="text-amber-700 text-sm">
                    Uses the SPhilBERTa model trained on parallel Greek-Latin texts to find conceptually 
                    similar passages. Best for discovering thematic connections and paraphrased ideas.
                  </p>
                </div>
                <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                  <h4 className="font-medium text-green-800 mb-2">Dictionary Mode</h4>
                  <p className="text-green-700 text-sm">
                    Uses a curated vocabulary of 50,000+ Greek-Latin word pairs from V3 scholars. 
                    Scores matches by word rarity (IDF). Shows exact word correspondences with highlighting.
                  </p>
                </div>
              </div>
              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <p className="text-gray-700 text-sm">
                  <strong>Example:</strong> Compare Homer's Iliad Book 1 (Greek) with Vergil's Aeneid Book 1 (Latin) 
                  to discover how Vergil adapted Homeric themes and vocabulary.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'syntax-texts' && (
            <div className="prose max-w-none">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Texts with Syntax Matching</h3>
              <p className="text-gray-700 mb-4">
                Syntax matching uses Universal Dependencies (UD) treebank data to compare grammatical structures 
                between passages. This feature is only available for texts that have been annotated in UD treebanks.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div className="bg-red-50 p-4 rounded border border-red-200">
                  <h4 className="font-medium text-red-800 mb-2">Latin Texts (UD-Latin-Perseus)</h4>
                  <ul className="text-sm text-gray-700 space-y-1">
                    <li>Vergil, Aeneid</li>
                    <li>Ovid, Metamorphoses (selections)</li>
                    <li>Propertius, Elegies</li>
                    <li>Petronius, Satyricon</li>
                    <li>Cicero, Letters to Atticus (selections)</li>
                  </ul>
                </div>
                <div className="bg-red-50 p-4 rounded border border-red-200">
                  <h4 className="font-medium text-red-800 mb-2">Latin Texts (UD-Latin-PROIEL)</h4>
                  <ul className="text-sm text-gray-700 space-y-1">
                    <li>Cicero, Letters to Atticus</li>
                    <li>Jerome, Vulgate (Genesis, Revelation, Ephesians)</li>
                    <li>Palladius, Opus Agriculturae</li>
                    <li>Caesar, Commentarii de Bello Gallico</li>
                  </ul>
                </div>
                <div className="bg-amber-50 p-4 rounded border border-amber-200">
                  <h4 className="font-medium text-amber-800 mb-2">Greek Texts (UD-Ancient_Greek-Perseus)</h4>
                  <ul className="text-sm text-gray-700 space-y-1">
                    <li>Homer, Iliad and Odyssey</li>
                    <li>Hesiod, Works and Days, Theogony, Shield</li>
                    <li>Aeschylus, Agamemnon, Eumenides, Libation Bearers, Persians, Prometheus Bound, Seven Against Thebes, Suppliants</li>
                    <li>Sophocles, Ajax, Antigone, Electra, Oedipus at Colonus, Oedipus Tyrannus, Philoctetes, Trachiniae</li>
                    <li>Plato, Euthyphro</li>
                  </ul>
                </div>
                <div className="bg-amber-50 p-4 rounded border border-amber-200">
                  <h4 className="font-medium text-amber-800 mb-2">Greek Texts (UD-Ancient_Greek-PROIEL)</h4>
                  <ul className="text-sm text-gray-700 space-y-1">
                    <li>New Testament (all books)</li>
                    <li>Herodotus, Histories</li>
                    <li>Sphrantzes, Chronicle</li>
                  </ul>
                </div>
              </div>
              <div className="bg-gray-100 p-4 rounded mb-4">
                <p className="text-sm text-gray-600">
                  <strong>Note:</strong> Syntax matching will only produce results when both the source and target 
                  texts have UD treebank annotations. For best results, select texts from the same treebank source.
                </p>
              </div>

              <div className="bg-blue-50 p-4 rounded border border-blue-200">
                <h4 className="font-medium text-blue-800 mb-2">Data Sources & Credits</h4>
                <p className="text-sm text-gray-700 mb-2">
                  Syntactic annotations are provided by the <a href="https://universaldependencies.org/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Universal Dependencies</a> project:
                </p>
                <ul className="text-sm text-gray-700 space-y-1 ml-4">
                  <li><strong>UD-Latin-Perseus</strong>: Treebank from the <a href="http://www.perseus.tufts.edu/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Perseus Digital Library</a>, converted by Giuseppe G. A. Celano</li>
                  <li><strong>UD-Latin-PROIEL</strong>: From the <a href="https://proiel.github.io/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">PROIEL Treebank</a> (Pragmatic Resources in Old Indo-European Languages), Dag Haug et al.</li>
                  <li><strong>UD-Ancient_Greek-Perseus</strong>: Greek treebank from the <a href="http://www.perseus.tufts.edu/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Perseus Digital Library</a>, converted by Giuseppe G. A. Celano</li>
                  <li><strong>UD-Ancient_Greek-PROIEL</strong>: From the <a href="https://proiel.github.io/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">PROIEL Treebank</a>, Dag Haug et al.</li>
                </ul>
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
                  <h4 className="font-medium text-gray-900">Why is my search taking so long?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Try searching smaller sections (e.g., individual books) for faster results. 
                    Semantic and cross-lingual searches take longer than lemma matching.
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">Can I request a text that's not in the corpus?</h4>
                  <p className="text-gray-600 text-sm mt-1">Yes! Use the "Request a Text" section in this Help page.</p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">How do I save my results?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Use "Export CSV" to download results, or "Register" to save parallels to the Repository.
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">What's the difference between Phrases and Lines search?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    Phrases compares two specific texts. Lines searches a single line against the entire corpus.
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">How does the scoring work?</h4>
                  <p className="text-gray-600 text-sm mt-1">
                    The V3-style algorithm uses IDF (rare words score higher) and distance penalties 
                    (closer words score higher). More matching words also increase the score.
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
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
                <h4 className="font-semibold text-green-900 mb-3">Text Formatter Utility</h4>
                <p className="text-green-800 text-sm mb-4">
                  Paste your plain text below and we'll convert it to .tess format automatically.
                </p>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                  <div>
                    <label className="block text-xs font-medium text-green-800 mb-1">Author</label>
                    <input 
                      type="text" 
                      value={formatterAuthor} 
                      onChange={e => setFormatterAuthor(e.target.value)}
                      placeholder="e.g., Vergil"
                      className="w-full border border-green-300 rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-green-800 mb-1">Work</label>
                    <input 
                      type="text" 
                      value={formatterWork} 
                      onChange={e => setFormatterWork(e.target.value)}
                      placeholder="e.g., Aeneid"
                      className="w-full border border-green-300 rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-green-800 mb-1">Text Type</label>
                    <select 
                      value={formatterTextType} 
                      onChange={e => setFormatterTextType(e.target.value)}
                      className="w-full border border-green-300 rounded px-2 py-1 text-sm"
                    >
                      <option value="poetry">Poetry (book.line)</option>
                      <option value="prose">Prose (section.para)</option>
                      <option value="drama">Drama (act.scene.line)</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium text-green-800 mb-1">Start Book</label>
                      <input 
                        type="number" 
                        min="1"
                        value={formatterStartBook} 
                        onChange={e => setFormatterStartBook(e.target.value)}
                        className="w-full border border-green-300 rounded px-2 py-1 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-green-800 mb-1">Start Line</label>
                      <input 
                        type="number" 
                        min="1"
                        value={formatterStartLine} 
                        onChange={e => setFormatterStartLine(e.target.value)}
                        className="w-full border border-green-300 rounded px-2 py-1 text-sm"
                      />
                    </div>
                  </div>
                </div>
                
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-green-800 mb-1">Paste Raw Text (one line per row)</label>
                    <textarea 
                      value={formatterRawText}
                      onChange={e => setFormatterRawText(e.target.value)}
                      placeholder="Arma virumque cano, Troiae qui primus ab oris&#10;Italiam, fato profugus, Laviniaque venit&#10;litora, multum ille et terris iactatus et alto"
                      rows={8}
                      className="w-full border border-green-300 rounded px-2 py-2 text-sm font-mono"
                    />
                    <p className="text-xs text-green-700 mt-1">
                      Tip: Lines starting with "Book", "Liber", "Chapter", or "Act" followed by a number will start a new section.
                    </p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-green-800 mb-1">Formatted .tess Output</label>
                    <textarea 
                      value={formatterOutput}
                      readOnly
                      rows={8}
                      className="w-full border border-green-300 rounded px-2 py-2 text-sm font-mono bg-white"
                      placeholder="Formatted output will appear here..."
                    />
                    {formatterOutput && (
                      <div className="flex gap-2 mt-2">
                        <button 
                          type="button"
                          onClick={copyFormatterOutput}
                          className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
                        >
                          {formatterCopied ? 'Copied!' : 'Copy to Clipboard'}
                        </button>
                        <button 
                          type="button"
                          onClick={downloadFormatterOutput}
                          className="px-3 py-1 text-xs bg-green-700 text-white rounded hover:bg-green-800"
                        >
                          Download .tess File
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                
                <button 
                  type="button"
                  onClick={formatToTess}
                  disabled={!formatterAuthor.trim() || !formatterWork.trim() || !formatterRawText.trim()}
                  className="mt-3 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Format Text
                </button>
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
                      className="w-full border rounded px-3 py-2 text-sm">
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                  <textarea value={requestNotes} onChange={e => setRequestNotes(e.target.value)}
                    placeholder="Source edition, date, or any additional information..."
                    rows={3} className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                {requestMessage && (
                  <div className={`p-3 rounded text-sm ${requestMessage.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
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
                  <div className={`p-3 rounded text-sm ${feedbackStatus.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
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
