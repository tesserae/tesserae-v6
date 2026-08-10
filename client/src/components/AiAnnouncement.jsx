// Permanent (non-dismissible) flag on the main app pointing users to the
// "Use with your AI" Help section. Clicking it opens Help at that section.
const AiAnnouncement = ({ onOpen }) => {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 flex items-center gap-3 text-left hover:bg-amber-100 transition-colors"
    >
      <span className="text-lg leading-none" aria-hidden="true">✨</span>
      <span className="flex-1 text-sm text-amber-900">
        <strong>New — use your own AI with Tesserae.</strong>{' '}
        Have ChatGPT or Claude run searches and help interpret results.
      </span>
      <span className="text-sm font-semibold text-amber-800 whitespace-nowrap">Learn how →</span>
    </button>
  );
};

export default AiAnnouncement;
