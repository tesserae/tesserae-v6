import { useState, useEffect, useRef, useMemo } from 'react';

const SearchableAuthorSelect = ({ 
  value, 
  onChange, 
  authors,
  filter: externalFilter,
  setFilter: externalSetFilter,
  showDropdown: externalShowDropdown,
  setShowDropdown: externalSetShowDropdown
}) => {
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const [internalFilter, setInternalFilter] = useState('');
  const [internalShowDropdown, setInternalShowDropdown] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  
  const filter = externalFilter !== undefined ? externalFilter : internalFilter;
  const setFilter = externalSetFilter || setInternalFilter;
  const showDropdown = externalShowDropdown !== undefined ? externalShowDropdown : internalShowDropdown;
  const setShowDropdown = externalSetShowDropdown || setInternalShowDropdown;
  
  const safeAuthors = Array.isArray(authors) ? authors : [];
  
  const filteredAuthors = useMemo(() => 
    safeAuthors.filter(a => a.author && a.author.toLowerCase().includes(filter.toLowerCase())),
    [safeAuthors, filter]
  );
  const selectedAuthor = safeAuthors.find(a => a.author_key === value);
  
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setShowDropdown(false);
        setIsEditing(false);
        setFilter('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [setShowDropdown, setFilter]);
  
  const displayValue = isEditing ? filter : (selectedAuthor ? selectedAuthor.author : '');
  
  return (
    <div ref={containerRef} className="relative">
      <input
        ref={inputRef}
        type="text"
        placeholder="Type to search..."
        value={displayValue}
        onChange={e => { setFilter(e.target.value); setShowDropdown(true); setIsEditing(true); }}
        onFocus={() => { setShowDropdown(true); setIsEditing(true); setFilter(''); }}
        onBlur={() => { if (!showDropdown) { setIsEditing(false); setFilter(''); } }}
        className="w-full border rounded px-2 py-2 text-sm"
      />
      {showDropdown && (
        <div className="absolute z-50 w-full mt-1 bg-white border rounded shadow-lg max-h-48 overflow-y-auto">
          {filteredAuthors.length > 0 ? filteredAuthors.map(a => (
            <div key={a.author_key} 
              onMouseDown={(e) => { e.preventDefault(); onChange(a.author_key); setFilter(''); setShowDropdown(false); setIsEditing(false); }}
              className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-100 cursor-pointer ${value === a.author_key ? 'bg-gray-50 font-medium' : ''}`}>
              {a.author}
            </div>
          )) : <div className="px-3 py-2 text-sm text-gray-500">No matches</div>}
        </div>
      )}
    </div>
  );
};

export default SearchableAuthorSelect;
