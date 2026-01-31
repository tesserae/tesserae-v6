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

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Benchmark Sets</h3>
        <p className="text-sm text-gray-600 mb-4">
          Hand-curated datasets for evaluating intertextual detection algorithms. Includes hand-ranked parallels 
          from scholarly commentaries (Hunter, Knauer, Neils) and Tesserae results with scoring.
        </p>
        
        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-800 mb-2">Latin to Latin</h4>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Lucan BC1 vs Vergil Aeneid - Benchmark 1</span>
                  <span className="text-gray-500 ml-2">(hand-ranked)</span>
                </div>
                <a href="/static/downloads/benchmarks/Lucan.BC1-Verg.Aeneid.benchmark1.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Lucan BC1 vs Vergil Aeneid - Benchmark 2</span>
                  <span className="text-gray-500 ml-2">(hand-ranked)</span>
                </div>
                <a href="/static/downloads/benchmarks/Lucan.BC1-Verg.Aeneid.benchmark2.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Lucan BC1 vs Vergil Aeneid - Tesserae Results</span>
                  <span className="text-gray-500 ml-2">(scored, XLSX)</span>
                </div>
                <a href="/static/downloads/benchmarks/Lucan.BC1-Verg.Aeneid.tess_.results2.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Lucan BC1 vs Vergil Aeneid - Tesserae Results</span>
                  <span className="text-gray-500 ml-2">(scored, TXT)</span>
                </div>
                <a href="/static/downloads/benchmarks/bench41.txt" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  TXT
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Lucan BC1 vs Vergil Aeneid - 2010 Benchmark</span>
                  <span className="text-gray-500 ml-2">(formatted with match-words)</span>
                </div>
                <a href="/static/downloads/benchmarks/Tesserae-2010-Benchmark1.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Lucan BC II-IX vs Vergil Aeneid</span>
                  <span className="text-gray-500 ml-2">(raw)</span>
                </div>
                <a href="/static/downloads/benchmarks/Lucan.BC_.rest-Verg.Aeneid.benchmark.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Statius Achilleid vs Various</span>
                  <span className="text-gray-500 ml-2">(Geneva Seminar)</span>
                </div>
                <a href="/static/downloads/benchmarks/Stat.Achilleid1.benchmark.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium">Valerius Flaccus Argonautica 1 vs Latin Epic</span>
                    <span className="text-gray-500 ml-2">(945 intertexts)</span>
                  </div>
                  <a href="/static/downloads/benchmarks/vf_intertext_dataset_2.0.tab" 
                     className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                    TAB
                  </a>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Dexter et al. (2023). References to Vergil's Aeneid, Ovid's Metamorphoses, Lucan's Bellum Civile, 
                  and Statius' Thebaid from Kleywegt, Spaltenstein, and Zissos commentaries.
                  {' '}<a href="https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.153" 
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-600 hover:underline">Article</a>
                  {' | '}
                  <a href="https://doi.org/10.7910/DVN/S6RD4M" 
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-600 hover:underline">Dataset</a>
                </p>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-800 mb-2">Greek to Greek</h4>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Apollonius Argonautica vs Homer</span>
                  <span className="text-gray-500 ml-2">(Hunter commentary, hand-ranked)</span>
                </div>
                <a href="/static/downloads/benchmarks/Ap.Argonautica-Homer.benchmark.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Apollonius Argonautica III vs Homer</span>
                  <span className="text-gray-500 ml-2">(complete)</span>
                </div>
                <a href="/static/downloads/benchmarks/Ap.Argonautica3-Homer.benchmark.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-800 mb-2">Greek to Latin (Cross-lingual)</h4>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Vergil Aeneid I vs Homer Iliad</span>
                  <span className="text-gray-500 ml-2">(Knauer 1964, hand-ranked)</span>
                </div>
                <a href="/static/downloads/benchmarks/Verg.Aeneid1-Iliad.benchmark.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Vergil Aeneid I vs Homer Iliad - Raw 1</span>
                  <span className="text-gray-500 ml-2">(raw data)</span>
                </div>
                <a href="/static/downloads/benchmarks/Verg.Aeneid1-Iliad.benchmark.raw_.1.txt" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  TXT
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Vergil Aeneid I vs Homer Iliad - Raw 2</span>
                  <span className="text-gray-500 ml-2">(raw data)</span>
                </div>
                <a href="/static/downloads/benchmarks/Verg.Aeneid1-Iliad.benchmark.raw_.2.txt" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  TXT
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Vergil Aeneid I vs Homer Odyssey</span>
                  <span className="text-gray-500 ml-2">(Knauer 1964)</span>
                </div>
                <a href="/static/downloads/benchmarks/Verg.Aeneid1-Odyssey.benchmark.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Vergil Aeneid vs Apollonius Argonautica</span>
                  <span className="text-gray-500 ml-2">(Neils 2001)</span>
                </div>
                <a href="/static/downloads/benchmarks/Verg.Aeneid-Ap.Argonautica.benchmark.Neils2001.pdf" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  PDF
                </a>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Vergil Georgics IV vs Various</span>
                  <span className="text-gray-500 ml-2">(partially ranked)</span>
                </div>
                <a href="/static/downloads/benchmarks/Verg.Georgics4.benchmark.xlsx" 
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs">
                  XLSX
                </a>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-500">
            <strong>Bibliography:</strong> Hunter (1989) <em>Apollonius of Rhodes: Argonautica Book III</em>; 
            Knauer (1964) <em>Die Aeneis und Homer</em>; Neils (2001) <em>Vergil's Aeneid and the Argonautica</em>.
          </p>
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
