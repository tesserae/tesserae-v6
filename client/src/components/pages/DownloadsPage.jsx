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
              <div key={lang.code} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-gray-50 rounded">
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
              <div key={lang.code} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-gray-50 rounded">
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
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Lucan BC 1 vs Vergil Aeneid - Benchmark 1</span>
                    <span className="text-gray-500 ml-2">(hand-ranked)</span>
                  </div>
                  <a href="/static/downloads/benchmarks/Lucan.BC1-Verg.Aeneid.benchmark1.xlsx"
                     target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                    XLSX
                  </a>
                </div>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Lucan BC 1 vs Vergil Aeneid - Benchmark 2</span>
                    <span className="text-gray-500 ml-2">(hand-ranked)</span>
                  </div>
                  <a href="/static/downloads/benchmarks/Lucan.BC1-Verg.Aeneid.benchmark2.xlsx"
                     target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                    XLSX
                  </a>
                </div>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Lucan BC 1 vs Vergil Aeneid - Evaluation Pairs</span>
                    <span className="text-gray-500 ml-2">(213 parallels)</span>
                  </div>
                  <div className="flex gap-2">
                    <a href="/static/downloads/benchmarks/lucan_vergil_benchmark.csv"
                       target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV
                    </a>
                    <a href="/static/downloads/benchmarks/lucan_vergil_benchmark.json"
                       target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      JSON
                    </a>
                  </div>
                </div>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Lucan BC 1 vs Vergil Aeneid - Tesserae V3 Scored Results</span>
                    <span className="text-gray-500 ml-2">(3,410 pairs)</span>
                  </div>
                  <div className="flex gap-2">
                    <a href="/static/downloads/benchmarks/lucan_vergil_scored.csv"
                       target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV
                    </a>
                    <a href="/static/downloads/benchmarks/Lucan.BC1-Verg.Aeneid.tess_.results2.xlsx"
                       target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      XLSX
                    </a>
                  </div>
                </div>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Lucan BC 1 vs Vergil Aeneid - 2010 Benchmark</span>
                    <span className="text-gray-500 ml-2">(formatted with match-words)</span>
                  </div>
                  <a href="/static/downloads/benchmarks/Tesserae-2010-Benchmark1.xlsx"
                     target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                    XLSX
                  </a>
                </div>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Lucan BC II-IX vs Vergil Aeneid</span>
                    <span className="text-gray-500 ml-2">(raw)</span>
                  </div>
                  <a href="/static/downloads/benchmarks/Lucan.BC_.rest-Verg.Aeneid.benchmark.xlsx"
                     target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                    XLSX
                  </a>
                </div>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Statius Achilleid vs Various</span>
                    <span className="text-gray-500 ml-2">(Geneva Seminar)</span>
                  </div>
                  <a href="/static/downloads/benchmarks/Stat.Achilleid1.benchmark.xlsx"
                     target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                    XLSX
                  </a>
                </div>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Valerius Flaccus Argonautica 1 vs Latin Epic</span>
                    <span className="text-gray-500 ml-2">(521 evaluation pairs)</span>
                  </div>
                  <div className="flex gap-2">
                    <a href="/static/downloads/benchmarks/vf_benchmark.csv"
                       target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV
                    </a>
                    <a href="/static/downloads/benchmarks/vf_benchmark.json"
                       target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      JSON
                    </a>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Dexter et al. (2023). References to Vergil, Ovid, Lucan, and Statius from Kleywegt,
                  Spaltenstein, and Zissos commentaries.
                  {' '}<a href="https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.153"
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-600 hover:underline">Article</a>
                  {' | '}
                  <a href="https://doi.org/10.7910/DVN/S6RD4M"
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-600 hover:underline">Full Dataset</a>
                </p>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-800 mb-2">Greek to Greek</h4>
            <div className="space-y-2 text-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Apollonius Argonautica vs Homer</span>
                  <span className="text-gray-500 ml-2">(Hunter commentary, hand-ranked)</span>
                </div>
                <a href="/static/downloads/benchmarks/Ap.Argonautica-Homer.benchmark.xlsx"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  XLSX
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Apollonius Argonautica III vs Homer</span>
                  <span className="text-gray-500 ml-2">(complete)</span>
                </div>
                <a href="/static/downloads/benchmarks/Ap.Argonautica3-Homer.benchmark.xlsx"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  XLSX
                </a>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-800 mb-2">Greek to Latin (Cross-lingual)</h4>
            <div className="space-y-2 text-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Vergil Aeneid I vs Homer Iliad</span>
                  <span className="text-gray-500 ml-2">(Knauer 1964, hand-ranked)</span>
                </div>
                <a href="/static/downloads/benchmarks/Verg.Aeneid1-Iliad.benchmark.xlsx"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  XLSX
                </a>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Vergil Aeneid I vs Homer Iliad - Raw Data</span>
                    <span className="text-gray-500 ml-2">(with Greek text)</span>
                  </div>
                  <div className="flex gap-2">
                    <a href="/static/downloads/benchmarks/knauer_aeneid1_iliad_raw1.csv"
                       target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV 1
                    </a>
                    <a href="/static/downloads/benchmarks/knauer_aeneid1_iliad_raw2.csv"
                       target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV 2
                    </a>
                  </div>
                </div>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Vergil Aeneid I vs Homer Odyssey</span>
                  <span className="text-gray-500 ml-2">(Knauer 1964)</span>
                </div>
                <a href="/static/downloads/benchmarks/Verg.Aeneid1-Odyssey.benchmark.xlsx"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  XLSX
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Vergil Aeneid vs Apollonius Argonautica</span>
                  <span className="text-gray-500 ml-2">(Neils 2001)</span>
                </div>
                <a href="/static/downloads/benchmarks/Verg.Aeneid-Ap.Argonautica.benchmark.Neils2001.pdf"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  PDF
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Vergil Georgics IV vs Various</span>
                  <span className="text-gray-500 ml-2">(partially ranked)</span>
                </div>
                <a href="/static/downloads/benchmarks/Verg.Georgics4.benchmark.xlsx"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
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

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Coptic Text-Reuse Study</h3>
        <p className="text-sm text-gray-600 mb-4">
          Complete evaluation data for the article &ldquo;Multi-Channel Feature Fusion for Finding
          Coptic Text Reuse&rdquo;: gold-standard benchmarks, ranked search outputs,
          weight-optimization logs, and the scripts that reproduce them. Because the Sahidica New
          Testament is licensed for academic use only, its line text is replaced with verse
          references throughout; every result is reproducible with the freely obtainable Sahidica
          text. See the README for the full inventory and licensing.
        </p>
        <ul className="space-y-2 text-sm">
          <li>
            <a href="/static/downloads/coptic_article/coptic_v6_data_release_2026-08-29.zip"
               className="text-red-600 hover:underline font-medium" download>
              Complete release (zip, ~280 KB)
            </a>
            {' '}&mdash; all files below in one archive, with MANIFEST.csv checksums.
          </li>
          <li>
            <a href="/static/downloads/coptic_article/README.md"
               className="text-red-600 hover:underline">README</a>
            {' '}&mdash; inventory, methods, licensing, and the run-to-run variation note.
          </li>
          <li>
            <a href="/static/downloads/coptic_article/gold/romans_isaiah_gold_22.csv"
               className="text-red-600 hover:underline">Held-out benchmark: Romans&ndash;Isaiah citations (22 pairs)</a>
            {' '}&mdash; the explicit formula-marked citations, fixed before any output was seen.
          </li>
          <li>
            <a href="/static/downloads/coptic_article/gold/tsk_hebrews_psalms_gold_124.csv"
               className="text-red-600 hover:underline">Development benchmark: Hebrews&ndash;Psalms cross-references (124 pairs)</a>
            {' '}&mdash; derived from the OpenBible.info dataset, vote-filtered, LXX-numbered.
          </li>
          <li>
            <a href="/static/downloads/coptic_article/outputs/romans_isaiah_ranked_10000.jsonl"
               className="text-red-600 hover:underline">Ranked output: Romans &times; Isaiah (top 10,000)</a>
            {' '}&mdash; the single held-out run the article reports; reproduces its Table 4 exactly.
          </li>
          <li>
            <a href="/static/downloads/coptic_article/outputs/hebrews_psalms_ranked_10000.jsonl"
               className="text-red-600 hover:underline">Ranked output: Hebrews &times; Psalms (top 10,000)</a>
          </li>
          <li>
            <a href="/static/downloads/coptic_article/outputs/shenoute_abraham_bible_top50.csv"
               className="text-red-600 hover:underline">Ranked output: Shenoute, Abraham Our Father &times; Sahidic Bible (top 50)</a>
          </li>
        </ul>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">V6 Benchmark Evaluation Subsets</h3>
        <p className="text-sm text-gray-600 mb-4">
          Machine-readable evaluation subsets extracted from the scholarly benchmark sets above. Each file
          contains the commentary-attested parallel passages used for V6 recall evaluation, with provenance metadata.
          Available as CSV (with comment header) and JSON.
        </p>

        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-800 mb-2">Latin to Latin</h4>
            <div className="space-y-2 text-sm">
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Lucan BC 1 vs Vergil Aeneid</span>
                    <span className="text-gray-500 ml-2">(213 pairs, types 4-5)</span>
                  </div>
                  <div className="flex gap-2">
                    <a href="/static/downloads/benchmarks/v6_gold/lucan_vergil_gold.csv"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV
                    </a>
                    <a href="/static/downloads/benchmarks/v6_gold/lucan_vergil_gold.json"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      JSON
                    </a>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Parent:{' '}
                  <a href="/static/downloads/benchmarks/bench41.txt"
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-600 hover:underline">bench41.txt</a>
                  {' '}(3,410 entries). Commentators: Roche, Wick/Viansino, Haskins, Teubner-Braun.
                </p>
              </div>

              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">VF Argonautica 1 vs Vergil Aeneid</span>
                    <span className="text-gray-500 ml-2">(521 pairs, commentary-attested)</span>
                  </div>
                  <div className="flex gap-2">
                    <a href="/static/downloads/benchmarks/v6_gold/vf_vergil_gold.csv"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV
                    </a>
                    <a href="/static/downloads/benchmarks/v6_gold/vf_vergil_gold.json"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      JSON
                    </a>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Parent:{' '}
                  <a href="https://doi.org/10.7910/DVN/S6RD4M"
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-600 hover:underline">Dexter et al. 2024 dataset</a>
                  {' '}(945 entries). Commentators: Kleywegt, Zissos, Spaltenstein.
                </p>
              </div>

              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Achilleid vs Vergil, Ovid Met, Thebaid</span>
                    <span className="text-gray-500 ml-2">(128 pairs, 2+ commentators)</span>
                  </div>
                  <div className="flex gap-2">
                    <a href="/static/downloads/benchmarks/v6_gold/achilleid_gold.csv"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV
                    </a>
                    <a href="/static/downloads/benchmarks/v6_gold/achilleid_gold.json"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      JSON
                    </a>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Parent:{' '}
                  <a href="/static/downloads/benchmarks/Stat.Achilleid1.benchmark.xlsx"
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-600 hover:underline">Geneva 2015 seminar dataset</a>
                  {' '}(904 entries). Commentators: Dilke, Nuzzo, Ripoll-Soubiran, Uccellini.
                  53 vs Vergil, 23 vs Ovid Met, 52 vs Thebaid.
                </p>
              </div>

              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Jerome/Lactantius vs Classical Authors</span>
                    <span className="text-gray-500 ml-2">(421 pairs, type 4)</span>
                  </div>
                  <div className="flex gap-2">
                    <a href="/static/downloads/benchmarks/v6_gold/loci_similes_gold.csv"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV
                    </a>
                    <a href="/static/downloads/benchmarks/v6_gold/loci_similes_gold.json"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      JSON
                    </a>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Parent:{' '}
                  <a href="https://huggingface.co/datasets/Heidelberg-NLP/loci-similes"
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-600 hover:underline">Schelb et al. 2026 loci similes</a>.
                  Jerome Epistulae, Lactantius Divinae Institutiones, and others vs classical Latin.
                </p>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-800 mb-2">Greek to Greek</h4>
            <div className="space-y-2 text-sm">
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Apollonius Argonautica 3 vs Homer</span>
                    <span className="text-gray-500 ml-2">(448 pairs; 121 type 4+5)</span>
                  </div>
                  <div className="flex gap-2">
                    <a href="/static/downloads/benchmarks/v6_gold/apollonius_homer_gold.csv"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV
                    </a>
                    <a href="/static/downloads/benchmarks/v6_gold/apollonius_homer_gold.json"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      JSON
                    </a>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Parent: Hunter (1989) <em>Argonautica Book III</em> commentary.
                  All 448 entries included; 121 are types 4-5 (strong parallels) used as the evaluation standard.
                </p>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-800 mb-2">Cross-Lingual (Greek to Latin)</h4>
            <div className="space-y-2 text-sm">
              <div className="p-2 bg-gray-50 rounded">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">Knauer Aeneid 1 vs Homer Iliad</span>
                    <span className="text-gray-500 ml-2">(412 pairs)</span>
                  </div>
                  <div className="flex gap-2">
                    <a href="/static/downloads/benchmarks/v6_gold/knauer_aeneid1_iliad_gold.csv"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      CSV
                    </a>
                    <a href="/static/downloads/benchmarks/v6_gold/knauer_aeneid1_iliad_gold.json"
                       target="_blank" rel="noopener noreferrer"
                       className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                      JSON
                    </a>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Parent:{' '}
                  <a href="/static/downloads/benchmarks/Verg.Aeneid1-Iliad.benchmark.xlsx"
                     target="_blank" rel="noopener noreferrer"
                     className="text-red-600 hover:underline">Knauer (1964) catalog</a>.
                  Vergil Aeneid Book 1 vs Homer Iliad. Includes source/target text where available.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-500">
            <strong>Format:</strong> CSV files include a comment header (lines starting with #) with provenance metadata.
            JSON files are flat arrays of objects. See{' '}
            <a href="https://github.com/tesserae/tesserae-v6/blob/main/evaluation/benchmarks/BENCHMARK_METHODOLOGY.md"
               target="_blank" rel="noopener noreferrer"
               className="text-red-600 hover:underline">BENCHMARK_METHODOLOGY.md</a>
            {' '}for full documentation.
          </p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">V6 Evaluation Results</h3>
        <p className="text-sm text-gray-600 mb-4">
          Ranked fusion search results used in the V6 evaluation article. Each CSV contains all scored pairs
          with rank, references, text, fused score, channel details, and matched words. Benchmark pairs
          are annotated where applicable. Companion data for Coffee et al. (forthcoming).
        </p>

        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-800 mb-2">Latin Benchmarks</h4>
            <p className="text-xs text-gray-500 mb-2">
              Full ranked output with benchmark annotations. Recall: 792/862 (91.9%) across 5 benchmarks.
            </p>
            <div className="space-y-2 text-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Lucan BC 1 vs Vergil Aeneid</span>
                  <span className="text-gray-500 ml-2">(189/213, 88.7%)</span>
                </div>
                <a href="/static/downloads/evaluation/lucan_vergil_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">VF Argonautica 1 vs Vergil Aeneid</span>
                  <span className="text-gray-500 ml-2">(479/521, 91.9%)</span>
                </div>
                <a href="/static/downloads/evaluation/vf_vergil_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Achilleid vs Vergil Aeneid</span>
                  <span className="text-gray-500 ml-2">(50/53, 94.3%)</span>
                </div>
                <a href="/static/downloads/evaluation/achilleid_vergil_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Achilleid vs Ovid Metamorphoses</span>
                  <span className="text-gray-500 ml-2">(21/23, 91.3%)</span>
                </div>
                <a href="/static/downloads/evaluation/achilleid_ovid_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Achilleid vs Statius Thebaid</span>
                  <span className="text-gray-500 ml-2">(50/52, 96.2%)</span>
                </div>
                <a href="/static/downloads/evaluation/achilleid_thebaid_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-800 mb-2">Greek Benchmark</h4>
            <div className="space-y-2 text-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Apollonius Argonautica 3 vs Homer</span>
                  <span className="text-gray-500 ml-2">(Hunter type 4+5, per-book methodology)</span>
                </div>
                <a href="/static/downloads/evaluation/apollonius_homer_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-800 mb-2">Cross-Lingual Benchmark</h4>
            <div className="space-y-2 text-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Knauer Aeneid 1 vs Iliad — Benchmark Summary</span>
                  <span className="text-gray-500 ml-2">(412 pairs, per-target-line ranks)</span>
                </div>
                <a href="/static/downloads/evaluation/knauer_gold_summary.csv"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV
                </a>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-800 mb-2">Case Studies</h4>
            <p className="text-xs text-gray-500 mb-2">
              Ranked results for text pairs cited in the article with specific rank claims.
            </p>
            <div className="space-y-2 text-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Aeneid 7 vs Punica 2</span>
                  <span className="text-gray-500 ml-2">(Acheronta movebo)</span>
                </div>
                <a href="/static/downloads/evaluation/aen7_punica2_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Aeneid 1 vs Bellum Civile 1</span>
                  <span className="text-gray-500 ml-2">(pectore curas)</span>
                </div>
                <a href="/static/downloads/evaluation/aen1_bc1_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Aeneid 5 vs Thebaid 6</span>
                  <span className="text-gray-500 ml-2">(obstipuere animi)</span>
                </div>
                <a href="/static/downloads/evaluation/aen5_theb6_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Georgics 3 vs DRN 6</span>
                  <span className="text-gray-500 ml-2">(Thomas plague / tricolon)</span>
                </div>
                <a href="/static/downloads/evaluation/georg3_drn6_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Georgics vs DRN — Full Works</span>
                  <span className="text-gray-500 ml-2">(Thomas tricolon full-works rank)</span>
                </div>
                <a href="/static/downloads/evaluation/georg_drn_full_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Hinds Incipits — Summary</span>
                  <span className="text-gray-500 ml-2">(6 cross-lingual pairs, semantic + fusion ranks)</span>
                </div>
                <a href="/static/downloads/evaluation/hinds_incipits_ranks.csv"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV
                </a>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">Odyssey 11 vs Aeneid 6</span>
                  <span className="text-gray-500 ml-2">(shade embrace, cross-lingual)</span>
                </div>
                <a href="/static/downloads/evaluation/od11_aen6_crosslingual_ranked.csv.gz"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV.GZ
                </a>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-800 mb-2">Recall Summary</h4>
            <div className="space-y-2 text-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-medium">All Benchmarks — Recall Summary</span>
                  <span className="text-gray-500 ml-2">(aggregated results)</span>
                </div>
                <a href="/static/downloads/evaluation/recall_summary.csv"
                   target="_blank" rel="noopener noreferrer"
                   className="px-3 py-1 bg-red-700 text-white rounded hover:bg-red-800 text-xs self-start sm:self-auto whitespace-nowrap">
                  CSV
                </a>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-500">
            <strong>Columns:</strong> rank, source_ref, target_ref, source_text, target_text, fused_score,
            channels, channel_count, matched_words, is_gold, gold_index. Cross-lingual CSVs include cosine,
            dict_count, dict_words, phonetic_count. Compressed with gzip.
          </p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Developer Data Files</h3>
        <p className="text-sm text-gray-600 mb-4">
          To run Tesserae V6 locally, you need the Git repository plus pre-built search indexes
          (too large for GitHub). The repository itself is ~4 GB because it includes the corpus texts
          (~308 MB) and pre-computed semantic embeddings (~3.5 GB). The search indexes add another ~6.3 GB.
        </p>

        <div className="bg-gray-50 rounded p-4 mb-4 overflow-x-auto">
          <p className="text-xs sm:text-sm font-mono text-gray-700 mb-1">
            <span className="text-gray-500"># 1. Clone the repository (~4 GB, includes texts + embeddings):</span>
          </p>
          <p className="text-xs sm:text-sm font-mono text-gray-800 mb-3 whitespace-nowrap">git clone https://github.com/tesserae/tesserae-v6.git</p>
          <p className="text-xs sm:text-sm font-mono text-gray-700 mb-1">
            <span className="text-gray-500"># 2. Download search indexes (~1.3 GB compressed, ~6.3 GB uncompressed):</span>
          </p>
          <p className="text-xs sm:text-sm font-mono text-gray-800 mb-3">python scripts/download_data.py</p>
          <p className="text-xs sm:text-sm font-mono text-gray-700 mb-1">
            <span className="text-gray-500"># 3. Check that all files are present:</span>
          </p>
          <p className="text-xs sm:text-sm font-mono text-gray-800">python scripts/download_data.py --check</p>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          The download script fetches all required files automatically. You can also download individual
          files manually using the links below.
        </p>

        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">Latin Search Index</span>
              <span className="text-sm text-gray-500 ml-2">(1,429 texts, 2.2 GB)</span>
            </div>
            <a
              href="https://tesserae.caset.buffalo.edu/tesserae-data/la_index.db.tar.gz"
              target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm"
            >
              Download
            </a>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">Greek Search Index</span>
              <span className="text-sm text-gray-500 ml-2">(659 texts, 1.4 GB)</span>
            </div>
            <a
              href="https://tesserae.caset.buffalo.edu/tesserae-data/grc_index.db.tar.gz"
              target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm"
            >
              Download
            </a>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">English Search Index</span>
              <span className="text-sm text-gray-500 ml-2">(14 texts, 79 MB)</span>
            </div>
            <a
              href="https://tesserae.caset.buffalo.edu/tesserae-data/en_index.db.tar.gz"
              target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm"
            >
              Download
            </a>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">Latin Syntax Parses</span>
              <span className="text-sm text-gray-500 ml-2">(LatinPipe UD annotations, 1.6 GB)</span>
            </div>
            <a
              href="https://tesserae.caset.buffalo.edu/tesserae-data/syntax_latin.db.tar.gz"
              target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm"
            >
              Download
            </a>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">Greek Syntax Parses</span>
              <span className="text-sm text-gray-500 ml-2">(650 texts, UD annotations, 967 MB)</span>
            </div>
            <a
              href="https://tesserae.caset.buffalo.edu/tesserae-data/syntax_greek.db.tar.gz"
              target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm"
            >
              Download
            </a>
          </div>
        </div>

        <p className="text-xs text-gray-500 mt-4">
          Total: ~10 GB (repository + indexes). The download script reads DATA_MANIFEST.json and
          skips files already present. See the{' '}
          <a
            href="https://github.com/tesserae/tesserae-v6/blob/main/docs/DATA_FILES_REFERENCE.md"
            target="_blank"
            rel="noopener noreferrer"
            className="text-red-600 hover:underline"
          >
            Data Files Reference
          </a>{' '}
          for full documentation.
        </p>
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
