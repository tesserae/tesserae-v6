import { largeComparisonLine } from '../../utils/fusionParts';

// One plain line shown while a large pairwise comparison runs (it starts on
// the first click). The numbers come from /api/fusion-estimate. Nothing shows
// unless the estimate says the search runs in parts.
const LargeComparisonNotice = ({ sourceName, targetName, estimate, onChoose }) => (
  !estimate?.in_parts ? null : (
  <div
    role="region"
    aria-label="Large comparison"
    className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-800"
  >
    <p>
      {largeComparisonLine(sourceName, targetName, estimate)}{' '}
      <button
        type="button"
        onClick={onChoose}
        className="text-red-700 underline hover:text-red-800"
      >
        Compare chosen books instead
      </button>
    </p>
  </div>
  )
);

export default LargeComparisonNotice;
