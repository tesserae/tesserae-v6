import React, { useEffect, useState } from 'react';
import { fetchFusionDefaultWeights } from '../../utils/api';

// Fusion channels shown in the Advanced weights panel, with plain-English
// labels. `quotation` is intentionally omitted — it is 0 for Latin/Greek/
// English and is managed by the Coptic biblical profile, not a user knob.
const CHANNEL_LABELS = [
  ['lemma', 'Shared words'],
  ['lemma_min1', 'Single word'],
  ['exact', 'Exact'],
  ['sound', 'Sound'],
  ['edit_distance', 'Spelling'],
  ['semantic', 'Meaning'],
  ['dictionary', 'Synonyms'],
  ['syntax', 'Syntax'],
  ['syntax_structural', 'Structure'],
  ['rare_word', 'Rare words'],
];

const SearchSettings = ({ settings, setSettings, showAdvanced, setShowAdvanced, language = 'la' }) => {
  const stopwordExamples = {
    la: 'pietas not pietate, bellum not bello',
    grc: 'λόγος not λόγον, θεός not θεῷ',
    en: 'king not kings, speak not speaking',
    cop: 'use lemmatized (sub-word) dictionary forms, not inflected forms'
  };

  // Advanced channel-weights panel state.
  const [showChannelWeights, setShowChannelWeights] = useState(false);
  const [defaultWeights, setDefaultWeights] = useState(null);
  const [weightRange, setWeightRange] = useState({ min: 0, max: 20 });

  // Fetch the tuned defaults for the active language so the inputs pre-fill
  // with them (and so "Reset to defaults" knows what to restore).
  useEffect(() => {
    if (settings.match_type !== 'fusion') return;
    let cancelled = false;
    fetchFusionDefaultWeights(language)
      .then((d) => {
        if (cancelled) return;
        setDefaultWeights(d.weights || {});
        setWeightRange({ min: d.min ?? 0, max: d.max ?? 20 });
      })
      .catch(() => { /* non-fatal: panel just won't pre-fill */ });
    return () => { cancelled = true; };
  }, [language, settings.match_type]);

  const channelWeights = settings.channel_weights || {};
  const overrideCount = Object.keys(channelWeights).length;

  // Displayed value: user override if set, otherwise the language default.
  const weightValue = (ch) => {
    if (channelWeights[ch] !== undefined) return channelWeights[ch];
    if (defaultWeights && defaultWeights[ch] !== undefined) return defaultWeights[ch];
    return '';
  };

  const setChannelWeight = (ch, raw) => {
    setSettings((prev) => {
      const next = { ...(prev.channel_weights || {}) };
      if (raw === '' || raw === null || raw === undefined) {
        // Empty input clears the override for this channel (back to default).
        delete next[ch];
      } else {
        let num = parseFloat(raw);
        if (Number.isNaN(num)) return prev;
        num = Math.max(weightRange.min, Math.min(weightRange.max, num));
        next[ch] = num;
      }
      return { ...prev, channel_weights: next };
    });
  };

  const resetChannelWeights = () => {
    setSettings((prev) => ({ ...prev, channel_weights: {} }));
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

  useEffect(() => {
    // Reset freq_basis to 'corpus' if it is currently 'meter' and language is not Latin
    if (language !== 'la' && settings.freq_basis === 'meter') {
      handleChange('freq_basis', 'corpus');
    }
  }, [language, settings.freq_basis]);

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
            className="w-full border rounded px-2 py-2 text-base sm:text-sm"
          >
            <option value="fusion">Fusion — All Channels (best recall)</option>
            <option value="lemma">Dictionary Form (Lemma)</option>
            <option value="exact">Exact Match</option>
            <option value="semantic">AI Semantic</option>
            <option value="dictionary">Dictionary (V3 Synonyms)</option>
            <option value="sound">Sound Matching (slower)</option>
            <option value="edit_distance">Edit Distance (slower)</option>
          </select>
          {settings.match_type === 'fusion' && (
            <p className="text-xs text-gray-500 mt-1">
              Runs 9 channels with weighted scoring. Best recall but slower.
              Large text comparisons (e.g., {language === 'grc' ? 'full Odyssey vs. Argonautica' : language === 'en' ? 'full Paradise Lost vs. Faerie Queene' : language === 'cop' ? 'Sahidic Bible vs. Shenoute' : 'full Aeneid vs. Metamorphoses'}) may take up to 15 minutes on first run; subsequent searches are cached.
            </p>
          )}
        </div>

        {settings.match_type !== 'fusion' && (
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
            className="w-full border rounded px-2 py-2 text-base sm:text-sm"
          />
        </div>
        )}
      </div>

      {showAdvanced && (
        <div className="mt-4 pt-4 border-t grid grid-cols-1 sm:grid-cols-2 gap-4">
          {settings.match_type !== 'fusion' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Stoplist Basis
            </label>
            <select
              value={settings.stoplist_basis}
              onChange={(e) => handleChange('stoplist_basis', e.target.value)}
              className="w-full border rounded px-2 py-2 text-base sm:text-sm"
            >
              <option value="source_target">Source + Target</option>
              <option value="source">Source Only</option>
              <option value="target">Target Only</option>
              <option value="corpus">Full Corpus</option>
            </select>
          </div>
          )}

          {settings.match_type !== 'fusion' && (
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
              className="w-full border rounded px-2 py-2 text-base sm:text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">Default = curated list + high-frequency words</p>
          </div>
          )}

          {settings.match_type === 'fusion' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Frequency Baseline
            </label>
            <select
              value={
                // Reset 'meter' to 'corpus' if not on Latin (meter is Latin-only)
                (settings.freq_basis === 'meter' && language !== 'la')
                  ? 'corpus'
                  : (settings.freq_basis || 'corpus')
              }
              onChange={(e) => handleChange('freq_basis', e.target.value)}
              className="w-full border rounded px-2 py-2 text-base sm:text-sm"
            >
              <option value="corpus">Full corpus</option>
              {language === 'la' && <option value="meter">Same meter</option>}
              <option value="text_pair">Text pair only</option>
            </select>
            <p className="text-xs text-gray-400 mt-1">
              {settings.freq_basis === 'meter'
                ? 'IDF computed from texts in the same meter (e.g., hexameter only). Falls back to full corpus if texts differ in meter.'
                : settings.freq_basis === 'text_pair'
                ? 'IDF computed only from the two compared texts (source and target).'
                : 'IDF computed from all texts in the corpus (default).'}
            </p>
          </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Source Unit Type
            </label>
            <select
              value={settings.source_unit_type}
              onChange={(e) => handleChange('source_unit_type', e.target.value)}
              className="w-full border rounded px-2 py-2 text-base sm:text-sm"
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
              className="w-full border rounded px-2 py-2 text-base sm:text-sm"
            >
              <option value="line">Line</option>
              <option value="phrase">Phrase</option>
            </select>
          </div>

          {settings.match_type !== 'fusion' && (
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
              className="w-full border rounded px-2 py-2 text-base sm:text-sm"
            />
          </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Results (0 = unlimited)
            </label>
            <input
              type="number"
              min="0"
              value={settings.max_results}
              onChange={(e) => handleChange('max_results', parseInt(e.target.value) || 0)}
              className="w-full border rounded px-2 py-2 text-base sm:text-sm"
            />
          </div>

          {settings.match_type !== 'fusion' && (
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Custom Stopwords (comma-separated)
            </label>
            <input
              type="text"
              value={settings.custom_stopwords}
              onChange={(e) => handleChange('custom_stopwords', e.target.value)}
              className="w-full border rounded px-2 py-2 text-base sm:text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">Use dictionary forms (lemmata): {stopwordExamples[language] || stopwordExamples.la}</p>
          </div>
          )}

          <div className="sm:col-span-2 pt-2 border-t">
            <p className="text-xs text-gray-500 mb-2">{settings.match_type === 'fusion' ? 'Fusion score boosting:' : 'Score boosting and matching features:'}</p>
            <div className="flex flex-wrap gap-4">
              {settings.match_type !== 'fusion' && (
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={settings.bigram_boost || false}
                  onChange={(e) => handleChange('bigram_boost', e.target.checked)}
                  className="rounded border-gray-300" />
                <span>Bigram frequency boost</span>
                <span className="text-xs text-gray-400">(rare word pairs)</span>
              </label>
              )}
              {settings.match_type !== 'fusion' && (
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={settings.use_pos || false}
                  onChange={(e) => handleChange('use_pos', e.target.checked)}
                  className="rounded border-gray-300" />
                Part-of-speech filtering
              </label>
              )}
              {language === 'la' && (
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={settings.use_meter || false}
                  onChange={(e) => handleChange('use_meter', e.target.checked)}
                  className="rounded border-gray-300" />
                Metrical patterns
              </label>
              )}
              {settings.match_type !== 'fusion' && (
              <label className="flex items-center gap-2 text-sm text-gray-700 group relative">
                <input type="checkbox" checked={settings.use_syntax || false}
                  onChange={(e) => handleChange('use_syntax', e.target.checked)}
                  className="rounded border-gray-300" />
                <span>Syntax matching <span className="text-gray-400 text-xs">(limited texts)</span></span>
                <span className="invisible group-hover:visible absolute left-0 top-6 z-10 bg-gray-800 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
                  See User Guide for list of texts with syntax data
                </span>
              </label>
              )}
            </div>
            {settings.match_type !== 'fusion' && (
            <p className="text-xs text-gray-400 mt-1">Note: Some features require pre-computed linguistic annotations for selected texts.</p>
            )}
          </div>

          {settings.match_type === 'fusion' && (
          <div className="sm:col-span-2 pt-2 border-t">
            <button
              type="button"
              onClick={() => setShowChannelWeights((v) => !v)}
              className="flex items-center gap-1 text-sm font-medium text-gray-700 hover:text-gray-900"
            >
              <span className="text-xs">{showChannelWeights ? '▼' : '▶'}</span>
              Advanced — Channel weights
              {overrideCount > 0 && (
                <span className="ml-1 text-xs text-red-600">({overrideCount} custom)</span>
              )}
            </button>

            {showChannelWeights && (
            <div className="mt-3">
              <p className="text-xs text-gray-500 mb-3">
                Advanced — the defaults are optimized; custom weights can reduce recall.
                Each channel contributes to a match's score in proportion to its weight
                (range {weightRange.min}–{weightRange.max}). Leave a field at its default to keep it unchanged.
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3">
                {CHANNEL_LABELS.map(([ch, label]) => (
                  <div key={ch}>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      {label}
                      {channelWeights[ch] !== undefined && (
                        <span className="text-red-600"> *</span>
                      )}
                    </label>
                    <input
                      type="number"
                      min={weightRange.min}
                      max={weightRange.max}
                      step="0.1"
                      value={weightValue(ch)}
                      onChange={(e) => setChannelWeight(ch, e.target.value)}
                      className="w-full border rounded px-2 py-1.5 text-sm"
                    />
                  </div>
                ))}
              </div>
              <div className="mt-3 flex items-center gap-3">
                <button
                  type="button"
                  onClick={resetChannelWeights}
                  disabled={overrideCount === 0}
                  className="text-sm text-red-600 hover:text-red-800 disabled:text-gray-300 disabled:cursor-not-allowed"
                >
                  Reset to defaults
                </button>
                {overrideCount > 0 && (
                  <span className="text-xs text-gray-400">
                    {overrideCount} channel{overrideCount === 1 ? '' : 's'} overridden
                  </span>
                )}
              </div>
            </div>
            )}
          </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SearchSettings;
