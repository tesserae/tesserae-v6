import { useState } from 'react';

// Upload Your Text, moved out of the Help page onto its own page (2026-10-19).
export default function UploadTextPage() {
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
    } catch {
      setRequestMessage({ type: 'error', text: 'Failed to submit request' });
    }
    setRequestSubmitting(false);
  };

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

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 pb-2 border-b border-gray-200 mb-4">Upload Your Text</h3>
        <p className="text-gray-600 mb-4">
          Have a text you'd like to add to the Tesserae corpus? Upload it here and we'll review it for inclusion.
          Pre-formatting your text speeds up the process significantly.
        </p>
        
        {/* Formatting Instructions */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-blue-800 mb-2">Text Formatting Guidelines</h4>
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
          <h4 className="text-sm font-semibold uppercase tracking-wide text-amber-800 mb-3">Text Formatter Utility</h4>
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
        
        <h4 className="text-lg font-semibold text-gray-900 mb-3">Submit Your Formatted Text</h4>
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
    </div>
  );
}
