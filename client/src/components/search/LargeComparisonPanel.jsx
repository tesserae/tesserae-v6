import { largeComparisonWarning } from '../../utils/fusionParts';

// Shown before a large pairwise comparison is sent. The text and the two
// buttons are fixed; nothing shows unless the estimate says the search runs in parts; the numbers come from /api/fusion-estimate.
const LargeComparisonPanel = ({ sourceName, targetName, estimate, onRun, onChoose }) => (
  !estimate?.in_parts ? null : (
  <div
    role="region"
    aria-label="Large comparison"
    className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-gray-800"
  >
    <p>{largeComparisonWarning(sourceName, targetName, estimate)}</p>
    <div className="mt-3 flex flex-wrap gap-3">
      <button
        type="button"
        onClick={onRun}
        className="px-4 py-2 bg-red-700 text-white rounded-lg hover:bg-red-800"
      >
        Run the full comparison
      </button>
      <button
        type="button"
        onClick={onChoose}
        className="px-4 py-2 bg-gray-100 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-200"
      >
        Choose books instead
      </button>
    </div>
  </div>
  )
);

export default LargeComparisonPanel;
