// One-click example searches (DOCUMENT_EXAMPLE_SEARCHES), shared by
// LineSearch.jsx's documents mode and the Inscriptions & Papyri page.
export default function DocumentExampleButtons({ examples, onRun, label = 'Try an example:' }) {
  if (!examples || examples.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <span className="text-xs text-gray-500">{label}</span>
      {examples.map((example) => (
        <button
          key={example.query}
          type="button"
          onClick={() => onRun(example)}
          title={example.hint}
          className="text-xs px-2.5 py-1 rounded-full border border-gray-300 bg-white text-gray-700 hover:border-gray-400 hover:text-gray-900"
        >
          {example.label}
        </button>
      ))}
    </div>
  );
}
