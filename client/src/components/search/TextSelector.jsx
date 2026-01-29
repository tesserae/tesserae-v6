import { useState, useEffect, useMemo } from 'react';
import { SearchableAuthorSelect } from '../common';

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

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {label} Author
        </label>
        <SearchableAuthorSelect
          value={selectedAuthor}
          onChange={setSelectedAuthor}
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
          <select
            value={selectedText}
            onChange={(e) => setSelectedText(e.target.value)}
            className="w-full border rounded px-2 py-2 text-sm"
          >
            <option value="">Select a work...</option>
            {authorHierarchy.works.map(work => (
              <optgroup key={work.work_key} label={work.work}>
                {work.sections.map(section => {
                  let displayLabel;
                  if (section.label === '(Complete)' || section.label === work.work) {
                    displayLabel = `${work.work} (Complete)`;
                  } else if (section.label.startsWith('Book ') || section.label.startsWith('Part ')) {
                    displayLabel = `${work.work}, ${section.label}`;
                  } else {
                    displayLabel = section.label.includes(work.work) ? section.label : `${work.work}, ${section.label}`;
                  }
                  return (
                    <option key={section.file} value={section.file}>
                      {displayLabel}
                    </option>
                  );
                })}
              </optgroup>
            ))}
          </select>
        </div>
      )}

      {!authorHierarchy && texts.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {label} Text
          </label>
          <select
            value={selectedText}
            onChange={(e) => setSelectedText(e.target.value)}
            className="w-full border rounded px-2 py-2 text-sm"
          >
            <option value="">Select a text...</option>
            {texts.map(text => (
              <option key={text.id} value={text.id}>
                {text.title}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
};

export default TextSelector;
