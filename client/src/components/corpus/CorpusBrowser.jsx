import { useState, useEffect, useMemo } from 'react';
import { LoadingSpinner } from '../common';

export default function CorpusBrowser() {
  const [language, setLanguage] = useState('la');
  const [corpus, setCorpus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchFilter, setSearchFilter] = useState('');
  const [selectedEra, setSelectedEra] = useState('all');
  const [sortOrder, setSortOrder] = useState('chronological');
  const [expandedAuthors, setExpandedAuthors] = useState(new Set());
  const [stats, setStats] = useState(null);
  const [selectedSource, setSelectedSource] = useState(null);
  const [selectedTarget, setSelectedTarget] = useState(null);

  const languageTabs = [
    { code: 'la', label: 'Latin' },
    { code: 'grc', label: 'Greek' },
    { code: 'en', label: 'English' }
  ];

  const erasByLanguage = {
    la: [
      { id: 'all', label: 'All Eras' },
      { id: 'republic', label: 'Republic' },
      { id: 'augustan', label: 'Augustan' },
      { id: 'early_imperial', label: 'Early Imperial' },
      { id: 'later_imperial', label: 'Later Imperial' },
      { id: 'late_antique', label: 'Late Antique' },
      { id: 'early_medieval', label: 'Early Medieval' },
      { id: 'carolingian', label: 'Carolingian' },
      { id: 'unknown', label: 'Unknown' }
    ],
    grc: [
      { id: 'all', label: 'All Eras' },
      { id: 'archaic', label: 'Archaic' },
      { id: 'classical', label: 'Classical' },
      { id: 'hellenistic', label: 'Hellenistic' },
      { id: 'early_imperial', label: 'Early Imperial' },
      { id: 'later_imperial', label: 'Later Imperial' },
      { id: 'late_antique', label: 'Late Antique' },
      { id: 'unknown', label: 'Unknown' }
    ],
    en: [
      { id: 'all', label: 'All Eras' },
      { id: 'medieval', label: 'Medieval' },
      { id: 'renaissance', label: 'Renaissance' },
      { id: 'early_modern', label: 'Early Modern' },
      { id: 'restoration', label: 'Restoration' },
      { id: 'eighteenth_century', label: '18th Century' },
      { id: 'romantic', label: 'Romantic' },
      { id: 'victorian', label: 'Victorian' },
      { id: 'unknown', label: 'Unknown' }
    ]
  };
  
  const eras = erasByLanguage[language] || erasByLanguage.la;

  const formatEraLabel = (era) => {
    if (!era || era === 'unknown') return '';
    return era.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  useEffect(() => {
    loadCorpus();
  }, [language]);

  useEffect(() => {
    loadStats();
  }, []);

  const loadCorpus = async () => {
    setLoading(true);
    setExpandedAuthors(new Set());
    try {
      const res = await fetch(`/api/texts?language=${language}`);
      const data = await res.json();
      setCorpus(data || []);
    } catch (err) {
      console.error('Failed to load corpus:', err);
    }
    setLoading(false);
  };

  const loadStats = async () => {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  const groupedByAuthor = useMemo(() => {
    const groups = {};
    corpus.forEach(text => {
      const author = text.author || 'Unknown';
      if (!groups[author]) {
        groups[author] = {
          author,
          author_key: text.author_key,
          era: text.era || 'unknown',
          year: text.year,
          texts: []
        };
      }
      groups[author].texts.push(text);
    });
    return Object.values(groups);
  }, [corpus]);

  // Era ordering for all languages (roughly chronological across cultures)
  const eraOrder = [
    // Greek
    'archaic', 'classical', 'hellenistic',
    // Latin  
    'republic', 'augustan', 'early_imperial', 'later_imperial', 'late_antique',
    // Medieval (Latin & English)
    'early_medieval', 'carolingian', 'medieval',
    // English
    'renaissance', 'early_modern', 'restoration', 'eighteenth_century', 'romantic', 'victorian',
    // Fallback
    'unknown'
  ];

  const sortedAuthors = useMemo(() => {
    const sorted = [...groupedByAuthor];
    if (sortOrder === 'alphabetical') {
      return sorted.sort((a, b) => a.author.localeCompare(b.author));
    } else {
      return sorted.sort((a, b) => {
        const eraA = eraOrder.indexOf(a.era);
        const eraB = eraOrder.indexOf(b.era);
        if (eraA !== eraB) return eraA - eraB;
        // Within same era, sort by year (earliest first), then alphabetically
        const yearA = a.year ?? 9999;
        const yearB = b.year ?? 9999;
        if (yearA !== yearB) return yearA - yearB;
        return a.author.localeCompare(b.author);
      });
    }
  }, [groupedByAuthor, sortOrder]);

  const normalizeEra = (era) => {
    if (!era) return 'unknown';
    return era.toLowerCase().replace(/\s+/g, '_');
  };

  const filteredAuthors = useMemo(() => {
    return sortedAuthors.filter(group => {
      const matchesSearch = !searchFilter || 
        group.author.toLowerCase().includes(searchFilter.toLowerCase()) ||
        group.texts.some(t => t.title?.toLowerCase().includes(searchFilter.toLowerCase()));
      const matchesEra = selectedEra === 'all' || normalizeEra(group.era) === selectedEra;
      return matchesSearch && matchesEra;
    });
  }, [sortedAuthors, searchFilter, selectedEra]);

  const toggleAuthor = (author) => {
    const newExpanded = new Set(expandedAuthors);
    if (newExpanded.has(author)) {
      newExpanded.delete(author);
    } else {
      newExpanded.add(author);
    }
    setExpandedAuthors(newExpanded);
  };

  const handleSourceSelect = (text, author) => {
    if (selectedSource?.text.id === text.id) {
      setSelectedSource(null);
    } else {
      setSelectedSource({ text, author, language });
      sessionStorage.setItem('tesserae_compareSource', JSON.stringify({ 
        textId: text.id, 
        authorKey: author.author_key || author.author?.toLowerCase().replace(/\s+/g, '_'),
        language 
      }));
    }
  };

  const handleTargetSelect = (text, author) => {
    if (selectedTarget?.text.id === text.id) {
      setSelectedTarget(null);
    } else {
      setSelectedTarget({ text, author, language });
      sessionStorage.setItem('tesserae_compareTarget', JSON.stringify({ 
        textId: text.id, 
        authorKey: author.author_key || author.author?.toLowerCase().replace(/\s+/g, '_'),
        language 
      }));
    }
  };

  const goToCompare = () => {
    if (selectedSource && selectedTarget) {
      sessionStorage.setItem('tesserae_activeTab', language);
      sessionStorage.setItem('tesserae_sourceAuthor', selectedSource.author.author_key || '');
      sessionStorage.setItem('tesserae_sourceText', selectedSource.text.id);
      sessionStorage.setItem('tesserae_targetAuthor', selectedTarget.author.author_key || '');
      sessionStorage.setItem('tesserae_targetText', selectedTarget.text.id);
      window.location.href = '/';
    }
  };

  const getLanguageName = (lang) => {
    const names = { la: 'Latin', grc: 'Greek', en: 'English' };
    return names[lang] || lang;
  };

  return (
    <div className="space-y-4">
      <div className="flex overflow-x-auto scrollbar-hide border-b">
        {languageTabs.map(tab => (
          <button
            key={tab.code}
            onClick={() => { setLanguage(tab.code); setSelectedEra('all'); }}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap ${
              language === tab.code 
                ? 'text-red-700 border-b-2 border-red-700' 
                : 'text-gray-600 hover:text-red-600'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {(selectedSource || selectedTarget) && (
        <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="font-medium text-amber-800">Compare:</span>
            <span>
              <span className="text-gray-500">Source:</span>{' '}
              {selectedSource ? (
                <span className="font-medium">{selectedSource.author.author}, {selectedSource.text.title}</span>
              ) : (
                <span className="text-gray-400">none</span>
              )}
            </span>
            <span>
              <span className="text-gray-500">Target:</span>{' '}
              {selectedTarget ? (
                <span className="font-medium">{selectedTarget.author.author}, {selectedTarget.text.title}</span>
              ) : (
                <span className="text-gray-400">none</span>
              )}
            </span>
            <div className="flex gap-2 ml-auto">
              <button
                onClick={() => { setSelectedSource(null); setSelectedTarget(null); }}
                className="text-gray-500 hover:text-gray-700 text-xs"
              >
                Clear
              </button>
              <button
                onClick={goToCompare}
                disabled={!selectedSource || !selectedTarget}
                className="px-3 py-1 bg-red-700 text-white text-xs rounded hover:bg-red-800 disabled:opacity-50"
              >
                Search
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            {getLanguageName(language)} Corpus
          </h2>
          <p className="text-sm text-gray-500">
            {stats?.[language]?.texts || corpus.length} texts
          </p>
        </div>
        <div className="flex flex-wrap gap-2 w-full sm:w-auto">
          <input
            type="text"
            placeholder="Filter..."
            value={searchFilter}
            onChange={e => setSearchFilter(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm flex-1 sm:flex-none sm:w-48"
          />
          <select
            value={selectedEra}
            onChange={e => setSelectedEra(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm"
          >
            {eras.map(era => (
              <option key={era.id} value={era.id}>{era.label}</option>
            ))}
          </select>
          <select
            value={sortOrder}
            onChange={e => setSortOrder(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm"
          >
            <option value="alphabetical">A-Z</option>
            <option value="chronological">By Era</option>
          </select>
        </div>
      </div>

      <div className="text-xs text-gray-500 mb-2">
        Click author to expand works. Use checkboxes to select Source (S) or Target (T).
      </div>

      {loading ? (
        <LoadingSpinner text="Loading corpus..." />
      ) : (
        <div className="border rounded bg-white divide-y max-h-[600px] overflow-y-auto">
          {filteredAuthors.map(group => (
            <div key={group.author}>
              <div
                onClick={() => toggleAuthor(group.author)}
                className="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer"
              >
                <span className="text-gray-400 text-xs w-4">
                  {expandedAuthors.has(group.author) ? '▼' : '▶'}
                </span>
                <span className="font-medium text-gray-900 flex-1">{group.author}</span>
                <span className="text-xs text-gray-400">
                  {group.texts.length} {group.texts.length === 1 ? 'work' : 'works'}
                </span>
                {group.era && group.era !== 'unknown' && (
                  <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                    {formatEraLabel(group.era)}
                  </span>
                )}
              </div>
              
              {expandedAuthors.has(group.author) && (
                <div className="bg-gray-50 border-t">
                  {group.texts.map(text => {
                    const isSource = selectedSource?.text.id === text.id;
                    const isTarget = selectedTarget?.text.id === text.id;
                    return (
                      <div
                        key={text.id}
                        className={`flex items-center gap-2 px-3 py-1.5 pl-8 text-sm border-b border-gray-100 last:border-b-0 ${
                          isSource ? 'bg-amber-50' : isTarget ? 'bg-red-50' : ''
                        }`}
                      >
                        <label className="flex items-center gap-1 cursor-pointer" title="Set as Source">
                          <input
                            type="checkbox"
                            checked={isSource}
                            onChange={() => handleSourceSelect(text, group)}
                            className="w-3.5 h-3.5 accent-amber-600"
                          />
                          <span className="text-xs text-amber-700 font-medium">S</span>
                        </label>
                        <label className="flex items-center gap-1 cursor-pointer" title="Set as Target">
                          <input
                            type="checkbox"
                            checked={isTarget}
                            onChange={() => handleTargetSelect(text, group)}
                            className="w-3.5 h-3.5 accent-red-600"
                          />
                          <span className="text-xs text-red-700 font-medium">T</span>
                        </label>
                        <span className="text-gray-700 flex-1">{text.title}</span>
                        {text.line_count && (
                          <span className="text-xs text-gray-400">{text.line_count} lines</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ))}

          {filteredAuthors.length === 0 && (
            <div className="text-center py-6 text-gray-500 text-sm">
              No texts match your filter.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
