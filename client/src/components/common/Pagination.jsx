import { PAGE_SIZE_OPTIONS } from '../../hooks/usePagination';

/**
 * Compact page-number window, always at most 7 slots.
 * Returns page numbers interleaved with the ELLIPSIS marker.
 */
export const ELLIPSIS = '…';

export const getPageWindow = (currentPage, totalPages) => {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5, ELLIPSIS, totalPages];
  }
  if (currentPage >= totalPages - 3) {
    return [
      1,
      ELLIPSIS,
      totalPages - 4,
      totalPages - 3,
      totalPages - 2,
      totalPages - 1,
      totalPages,
    ];
  }
  return [1, ELLIPSIS, currentPage - 1, currentPage, currentPage + 1, ELLIPSIS, totalPages];
};

const navButtonClass =
  'px-3 py-1 text-xs rounded border border-gray-300 text-gray-700 hover:bg-gray-50 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent';

const pageButtonClass = (isActive) =>
  isActive
    ? 'px-3 py-1 text-xs rounded border border-red-700 bg-red-700 text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed'
    : navButtonClass;

/**
 * Presentational pagination controls.
 *
 * Owns no results and performs no data fetching — every interaction is handed
 * back to the caller, which slices an array it already holds in memory.
 *
 * @param {number} currentPage    1-based active page.
 * @param {number} totalPages     Total page count (>= 1).
 * @param {number} totalResults   Length of the full result array.
 * @param {number} pageSize       Active page size.
 * @param {Function} onPageChange     Receives a page number.
 * @param {Function} onPageSizeChange Receives a page size as a number.
 * @param {'full'|'nav'} variant  'full' shows selector + summary + navigation;
 *                                'nav' shows navigation only (bottom of a list).
 * @param {boolean} disabled      Disables every control (e.g. while streaming).
 * @param {string} idPrefix       Keeps label/select ids unique across instances.
 * @param {string} itemLabel      Noun used in the summary line.
 */
const Pagination = ({
  currentPage,
  totalPages,
  totalResults,
  pageSize,
  onPageChange,
  onPageSizeChange,
  variant = 'full',
  disabled = false,
  idPrefix = 'pagination',
  itemLabel = 'results',
}) => {
  if (!totalResults || totalResults <= 0) return null;

  const showNavigation = totalResults > pageSize;

  // The bottom instance exists only to repeat the navigation controls.
  if (variant === 'nav' && !showNavigation) return null;

  const rangeStart = (currentPage - 1) * pageSize + 1;
  const rangeEnd = Math.min(currentPage * pageSize, totalResults);
  const selectId = `${idPrefix}-page-size`;

  const navigation = showNavigation ? (
    <nav
      aria-label="Search results pagination"
      className="flex items-center gap-1 flex-wrap justify-center"
    >
      <button
        type="button"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={disabled || currentPage <= 1}
        className={navButtonClass}
      >
        Previous
      </button>

      {getPageWindow(currentPage, totalPages).map((slot, i) =>
        slot === ELLIPSIS ? (
          <span
            key={`ellipsis-${i}`}
            aria-hidden="true"
            className="px-2 py-1 text-xs text-gray-400 select-none"
          >
            {ELLIPSIS}
          </span>
        ) : (
          <button
            key={slot}
            type="button"
            onClick={() => onPageChange(slot)}
            disabled={disabled}
            aria-current={slot === currentPage ? 'page' : undefined}
            aria-label={`Go to page ${slot}`}
            className={pageButtonClass(slot === currentPage)}
          >
            {slot}
          </button>
        )
      )}

      <button
        type="button"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={disabled || currentPage >= totalPages}
        className={navButtonClass}
      >
        Next
      </button>
    </nav>
  ) : null;

  if (variant === 'nav') {
    return <div className="flex justify-center mt-4">{navigation}</div>;
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 py-3 border-t border-b mb-4">
      <div className="flex items-center gap-2">
        <label htmlFor={selectId} className="text-xs sm:text-sm text-gray-600">
          Show
        </label>
        <select
          id={selectId}
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          disabled={disabled}
          className="border rounded px-2 py-1.5 text-xs sm:text-sm disabled:opacity-50"
        >
          {PAGE_SIZE_OPTIONS.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
        <span
          aria-live="polite"
          className="text-xs sm:text-sm text-gray-600 whitespace-nowrap"
        >
          {`Showing ${rangeStart.toLocaleString()}–${rangeEnd.toLocaleString()} of ${totalResults.toLocaleString()} ${itemLabel}`}
        </span>
      </div>

      {navigation}
    </div>
  );
};

export default Pagination;
