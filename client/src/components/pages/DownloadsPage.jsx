import { useState } from 'react';

const DownloadsPage = () => {
  const [downloading, setDownloading] = useState({});

  const handleDownload = async (type, language) => {
    const key = `${type}-${language}`;
    setDownloading(prev => ({ ...prev, [key]: true }));
    
    try {
      const url = `/api/downloads/${type}/${language}`;
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error('Download failed');
      }
      
      const blob = await response.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `tesserae_${type}_${language}.zip`;
      a.click();
      URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      alert('Download failed: ' + err.message);
    }
    
    setDownloading(prev => ({ ...prev, [key]: false }));
  };

  const languages = [
    { code: 'la', name: 'Latin', texts: '~1,444', embeddings: true },
    { code: 'grc', name: 'Greek', texts: '~650', embeddings: true },
    { code: 'en', name: 'English', texts: '~14', embeddings: false }
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Downloads</h2>
        <p className="text-gray-600">
          Download the Tesserae corpus texts and pre-computed embeddings for offline analysis.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Corpus Texts</h3>
          <p className="text-sm text-gray-600 mb-4">
            Download all texts in .tess format for a language. Texts are organized by author and work.
          </p>
          <div className="space-y-3">
            {languages.map(lang => (
              <div key={lang.code} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">{lang.name}</span>
                  <span className="text-sm text-gray-500 ml-2">({lang.texts} texts)</span>
                </div>
                <button
                  onClick={() => handleDownload('texts', lang.code)}
                  disabled={downloading[`texts-${lang.code}`]}
                  className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50 text-sm"
                >
                  {downloading[`texts-${lang.code}`] ? 'Downloading...' : 'Download ZIP'}
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Semantic Embeddings</h3>
          <p className="text-sm text-gray-600 mb-4">
            Pre-computed sentence embeddings for semantic search. Uses SPhilBERTa for Latin/Greek.
          </p>
          <div className="space-y-3">
            {languages.filter(l => l.embeddings).map(lang => (
              <div key={lang.code} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">{lang.name}</span>
                  <span className="text-sm text-gray-500 ml-2">(embeddings)</span>
                </div>
                <button
                  onClick={() => handleDownload('embeddings', lang.code)}
                  disabled={downloading[`embeddings-${lang.code}`]}
                  className="px-4 py-2 bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-50 text-sm"
                >
                  {downloading[`embeddings-${lang.code}`] ? 'Downloading...' : 'Download ZIP'}
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <h4 className="font-medium text-amber-900 mb-2">License Information</h4>
        <p className="text-sm text-amber-800">
          Texts are provided for research and educational use. Many texts derive from public domain sources 
          (Perseus, CSEL, PHI Latin Texts). Metrical scansion data from MQDQ/Pede Certo is licensed under CC-BY-NC-ND 4.0.
        </p>
      </div>
    </div>
  );
};

export default DownloadsPage;
