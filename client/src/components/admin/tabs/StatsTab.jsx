import { LANG_NAMES } from '../adminConstants';

export default function StatsTab({ corpusStats }) {
  return (
    <div className="space-y-4">
      <h3 className="font-medium text-gray-900">Corpus Statistics</h3>
      {corpusStats ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {['la', 'grc', 'en', 'he', 'cop'].map(lang => (
            <div key={lang} className="bg-gray-50 p-4 rounded">
              <div className="text-lg font-medium text-gray-900 mb-2">
                {LANG_NAMES[lang]}
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Texts:</span>
                  <span className="font-medium">{(corpusStats[lang] || 0).toLocaleString()}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-gray-500 text-sm">Loading corpus statistics...</p>
      )}
    </div>
  );
}
