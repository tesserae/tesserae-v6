import { useState } from 'react';
import { Modal } from '../common';

const SavedSearches = ({ 
  sourceAuthor, sourceText, targetAuthor, targetText, 
  settings, activeTab,
  onLoad
}) => {
  const [showModal, setShowModal] = useState(false);
  const [savedSearches, setSavedSearches] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('tesserae_saved_searches') || '[]');
    } catch {
      return [];
    }
  });
  const [saveName, setSaveName] = useState('');

  const handleSave = () => {
    if (!saveName.trim()) return;
    const newSearch = {
      id: Date.now(),
      name: saveName.trim(),
      created_at: new Date().toISOString(),
      language: activeTab,
      sourceAuthor,
      sourceText,
      targetAuthor,
      targetText,
      settings
    };
    const updated = [...savedSearches, newSearch];
    setSavedSearches(updated);
    localStorage.setItem('tesserae_saved_searches', JSON.stringify(updated));
    setSaveName('');
    setShowModal(false);
  };

  const handleLoad = (search) => {
    onLoad(search);
    setShowModal(false);
  };

  const handleDelete = (id) => {
    const updated = savedSearches.filter(s => s.id !== id);
    setSavedSearches(updated);
    localStorage.setItem('tesserae_saved_searches', JSON.stringify(updated));
  };

  const canSave = sourceAuthor && sourceText && targetAuthor && targetText;

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className="text-sm text-gray-600 hover:text-red-700 underline"
      >
        Saved Searches ({savedSearches.length})
      </button>

      {showModal && (
        <Modal onClose={() => setShowModal(false)} title="Saved Searches">
          <div className="space-y-4">
            {canSave && (
              <div className="bg-gray-50 p-4 rounded border">
                <h4 className="font-medium text-sm mb-2">Save Current Search</h4>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={saveName}
                    onChange={e => setSaveName(e.target.value)}
                    placeholder="Enter search name..."
                    className="flex-1 border rounded px-3 py-2 text-sm"
                  />
                  <button
                    onClick={handleSave}
                    disabled={!saveName.trim()}
                    className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50 text-sm"
                  >
                    Save
                  </button>
                </div>
                <div className="text-xs text-gray-500 mt-2">
                  Current: {sourceAuthor} vs {targetAuthor}
                </div>
              </div>
            )}

            {savedSearches.length === 0 ? (
              <p className="text-gray-500 text-center py-4">No saved searches yet.</p>
            ) : (
              <div className="divide-y max-h-80 overflow-y-auto">
                {savedSearches.map(search => (
                  <div key={search.id} className="py-3 flex items-center justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-900 truncate">{search.name}</div>
                      <div className="text-xs text-gray-500">
                        {search.sourceAuthor} vs {search.targetAuthor} | {
                          search.language === 'la' ? 'Latin' : 
                          search.language === 'grc' ? 'Greek' : 'English'
                        }
                      </div>
                      <div className="text-xs text-gray-400">
                        Saved {new Date(search.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleLoad(search)}
                        className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 text-sm"
                      >
                        Load
                      </button>
                      <button
                        onClick={() => handleDelete(search.id)}
                        className="px-3 py-1.5 bg-red-100 text-red-700 rounded hover:bg-red-200 text-sm"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}
    </>
  );
};

export default SavedSearches;
