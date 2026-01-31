const SearchSettings = ({ settings, setSettings, showAdvanced, setShowAdvanced, language = 'la' }) => {
  const stopwordExamples = {
    la: 'pietas not pietate, bellum not bello',
    grc: 'λόγος not λόγον, θεός not θεῷ',
    en: 'king not kings, speak not speaking'
  };
  const handleChange = (key, value) => {
    const updates = { [key]: value };
    
    // Auto-set stoplist defaults when match type changes
    if (key === 'match_type') {
      if ((value === 'edit_distance' || value === 'sound') && settings.stoplist_size === 0) {
        updates.stoplist_size = 200;
      } else if (value === 'exact' && settings.stoplist_size === 0) {
        updates.stoplist_size = 100;
      }
    }
    
    setSettings(prev => ({ ...prev, ...updates }));
  };

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="flex justify-between items-center mb-3">
        <h4 className="font-medium text-gray-900">Search Settings</h4>
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-sm text-red-600 hover:text-red-800"
        >
          {showAdvanced ? 'Hide Advanced' : 'Show Advanced'}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Match Type
          </label>
          <select
            value={settings.match_type}
            onChange={(e) => handleChange('match_type', e.target.value)}
            className="w-full border rounded px-2 py-2 text-sm"
          >
            <option value="lemma">Dictionary Form (Lemma)</option>
            <option value="exact">Exact Match</option>
            <option value="semantic">AI Semantic</option>
            <option value="sound">Sound Matching (slower)</option>
            <option value="edit_distance">Edit Distance (slower)</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Minimum Matches
          </label>
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            value={settings.min_matches}
            onChange={(e) => {
              const val = e.target.value.replace(/[^0-9]/g, '');
              handleChange('min_matches', val === '' ? '' : Math.min(10, Math.max(1, parseInt(val))));
            }}
            onBlur={(e) => {
              if (settings.min_matches === '' || settings.min_matches < 1) {
                handleChange('min_matches', 2);
              }
            }}
            className="w-full border rounded px-2 py-2 text-sm"
          />
        </div>
      </div>

      {showAdvanced && (
        <div className="mt-4 pt-4 border-t grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Stoplist Basis
            </label>
            <select
              value={settings.stoplist_basis}
              onChange={(e) => handleChange('stoplist_basis', e.target.value)}
              className="w-full border rounded px-2 py-2 text-sm"
            >
              <option value="source_target">Source + Target</option>
              <option value="source">Source Only</option>
              <option value="target">Target Only</option>
              <option value="corpus">Full Corpus</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Stoplist Size
            </label>
            <input
              type="text"
              inputMode="numeric"
              value={settings.stoplist_size === 0 ? 'Default' : settings.stoplist_size}
              onChange={(e) => {
                const val = e.target.value.replace(/[^0-9]/g, '');
                if (val === '' || e.target.value.toLowerCase() === 'default') {
                  handleChange('stoplist_size', 0);
                } else {
                  handleChange('stoplist_size', Math.min(500, parseInt(val)));
                }
              }}
              onBlur={() => {
                if (settings.stoplist_size === '' || settings.stoplist_size === 'Default') {
                  handleChange('stoplist_size', 0);
                }
              }}
              onFocus={(e) => {
                if (settings.stoplist_size === 0) {
                  e.target.select();
                }
              }}
              placeholder="Default"
              className="w-full border rounded px-2 py-2 text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">Default = curated list + high-frequency words</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Source Unit Type
            </label>
            <select
              value={settings.source_unit_type}
              onChange={(e) => handleChange('source_unit_type', e.target.value)}
              className="w-full border rounded px-2 py-2 text-sm"
            >
              <option value="line">Line</option>
              <option value="phrase">Phrase</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Target Unit Type
            </label>
            <select
              value={settings.target_unit_type}
              onChange={(e) => handleChange('target_unit_type', e.target.value)}
              className="w-full border rounded px-2 py-2 text-sm"
            >
              <option value="line">Line</option>
              <option value="phrase">Phrase</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Distance (words)
            </label>
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={settings.max_distance}
              onChange={(e) => {
                const val = e.target.value.replace(/[^0-9]/g, '');
                handleChange('max_distance', val === '' ? '' : Math.min(999, Math.max(1, parseInt(val))));
              }}
              onBlur={() => {
                if (settings.max_distance === '' || settings.max_distance < 1) handleChange('max_distance', 999);
              }}
              className="w-full border rounded px-2 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Results (0 = unlimited)
            </label>
            <input
              type="number"
              min="0"
              value={settings.max_results}
              onChange={(e) => handleChange('max_results', parseInt(e.target.value) || 0)}
              className="w-full border rounded px-2 py-2 text-sm"
            />
          </div>

          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Custom Stopwords (comma-separated)
            </label>
            <input
              type="text"
              value={settings.custom_stopwords}
              onChange={(e) => handleChange('custom_stopwords', e.target.value)}
              className="w-full border rounded px-2 py-2 text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">Use dictionary forms (lemmata): {stopwordExamples[language] || stopwordExamples.la}</p>
          </div>

          <div className="sm:col-span-2 pt-2 border-t">
            <p className="text-xs text-gray-500 mb-2">Score boosting and matching features:</p>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={settings.bigram_boost || false}
                  onChange={(e) => handleChange('bigram_boost', e.target.checked)}
                  className="rounded border-gray-300" />
                <span>Bigram frequency boost</span>
                <span className="text-xs text-gray-400">(rare word pairs)</span>
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={settings.use_pos || false}
                  onChange={(e) => handleChange('use_pos', e.target.checked)}
                  className="rounded border-gray-300" />
                Part-of-speech filtering
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={settings.use_meter || false}
                  onChange={(e) => handleChange('use_meter', e.target.checked)}
                  className="rounded border-gray-300" />
                Metrical patterns
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 group relative">
                <input type="checkbox" checked={settings.use_syntax || false}
                  onChange={(e) => handleChange('use_syntax', e.target.checked)}
                  className="rounded border-gray-300" />
                <span>Syntax matching <span className="text-gray-400 text-xs">(limited texts)</span></span>
                <span className="invisible group-hover:visible absolute left-0 top-6 z-10 bg-gray-800 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
                  See User Guide for list of texts with syntax data
                </span>
              </label>
            </div>
            <p className="text-xs text-gray-400 mt-1">Note: Some features require pre-computed linguistic annotations for selected texts.</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchSettings;
