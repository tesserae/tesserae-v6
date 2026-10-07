import SearchableSelect from './SearchableSelect';

/**
 * A thin wrapper over SearchableSelect for the author shape callers already
 * use ({author_key, author} rows) -- kept so existing callers (TextSelector,
 * CrossLingualSearch, ThemeSearchPage) do not have to change (2026-10-06,
 * when SearchableSelect itself was generalised out of this component).
 *
 * The `filter`/`setFilter`/`showDropdown`/`setShowDropdown` props some
 * callers still pass (to coordinate with an outer input, e.g. TextSelector's
 * author/work pairing) are accepted for backward compatibility but no longer
 * drive anything: SearchableSelect owns its own open/filter state now.
 */
const SearchableAuthorSelect = ({
  value,
  onChange,
  authors,
  ariaLabel,
}) => {
  const safeAuthors = Array.isArray(authors) ? authors : [];
  const options = safeAuthors.map((a) => ({ value: a.author_key, label: a.author }));

  return (
    <SearchableSelect
      value={value}
      onChange={onChange}
      options={options}
      ariaLabel={ariaLabel}
      placeholder="Select author..."
    />
  );
};

export default SearchableAuthorSelect;
