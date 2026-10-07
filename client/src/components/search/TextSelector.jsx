import { useState, useEffect, useMemo, useCallback } from 'react';
import { SearchableAuthorSelect, SearchableSelect } from '../common';

const TextSelector = ({
  label,
  language,
  authors,
  selectedAuthor,
  setSelectedAuthor,
  selectedText,
  setSelectedText,
  hierarchy,
  fetchTexts
}) => {
  const [filter, setFilter] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [texts, setTexts] = useState([]);

  useEffect(() => {
    if (selectedAuthor) {
      fetchTexts(selectedAuthor).then(data => {
        setTexts(data.texts || []);
      });
    }
  }, [selectedAuthor, fetchTexts]);

  const authorHierarchy = useMemo(() => {
    if (!hierarchy) return null;
    return hierarchy.find(a => a.author_key === selectedAuthor);
  }, [hierarchy, selectedAuthor]);

  // Flattened for SearchableSelect, which filters by label rather than by
  // an optgroup's visual grouping; the work name is folded into each
  // section's own label instead (as the old optgroup's option text already
  // did), so "Book 3" is still found by typing the work's name.
  const workOptions = useMemo(() => {
    if (!authorHierarchy || !authorHierarchy.works) return [];
    const opts = [];
    for (const work of authorHierarchy.works) {
      for (const section of work.sections) {
        let displayLabel;
        if (section.label === '(Complete)' || section.label === work.work) {
          displayLabel = `${work.work} (Complete)`;
        } else if (section.label.startsWith('Book ') || section.label.startsWith('Part ')) {
          displayLabel = `${work.work}, ${section.label}`;
        } else {
          displayLabel = section.label.includes(work.work) ? section.label : `${work.work}, ${section.label}`;
        }
        opts.push({ value: section.file, label: displayLabel });
      }
    }
    return opts;
  }, [authorHierarchy]);

  const textOptions = useMemo(
    () => texts.map(text => ({ value: text.id, label: text.title })),
    [texts]
  );

  // When the author changes, clear the selected work so the user must pick one
  const handleAuthorChange = useCallback((newAuthor) => {
    if (newAuthor !== selectedAuthor) {
      setSelectedText('');
    }
    setSelectedAuthor(newAuthor);
  }, [selectedAuthor, setSelectedAuthor, setSelectedText]);

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {label} Author
        </label>
        <SearchableAuthorSelect
          ariaLabel={`${label} author`}
          value={selectedAuthor}
          onChange={handleAuthorChange}
          filter={filter}
          setFilter={setFilter}
          showDropdown={showDropdown}
          setShowDropdown={setShowDropdown}
          authors={authors}
        />
      </div>
      
      {authorHierarchy && authorHierarchy.works && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {label} Work
          </label>
          <SearchableSelect
            ariaLabel={`${label} Work`}
            value={selectedText}
            onChange={setSelectedText}
            options={workOptions}
            placeholder="Select a work..."
            className="w-full border rounded px-2 py-2 text-base sm:text-sm"
          />
        </div>
      )}

      {!authorHierarchy && texts.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {label} Text
          </label>
          <SearchableSelect
            ariaLabel={`${label} Text`}
            value={selectedText}
            onChange={setSelectedText}
            options={textOptions}
            placeholder="Select a text..."
            className="w-full border rounded px-2 py-2 text-base sm:text-sm"
          />
        </div>
      )}
    </div>
  );
};

export default TextSelector;
