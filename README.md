# Tesserae V6

A web-based intertextual analysis tool for classical Latin, Greek, and English texts. Tesserae identifies textual parallels using advanced matching algorithms across a large corpus of classical literary works.

## Features

### Search Modes
- **Parallel Phrases**: Compare two texts to find shared vocabulary and allusions
- **Line Search**: Search a single line against the entire corpus
- **Rare Words (Hapax)**: Find rare vocabulary shared between texts
- **Word Pairs (Bigrams)**: Discover unique word combinations
- **String Search**: Wildcard and boolean text search across all works

### Match Types
- **Lemma**: Match by dictionary form (default)
- **Exact**: Match identical word forms only
- **Sound**: Phonetic similarity (character trigram overlap)
- **Edit Distance**: Fuzzy matching (Levenshtein similarity)
- **Semantic**: AI embedding similarity (SPhilBERTa)
- **Dictionary**: Curated V3 synonym pairs
- **Syntax**: Dependency tree pattern matching
- **Rare Word**: Shared low-frequency vocabulary
- **Fusion**: All 9 channels combined with weighted scoring

### Cross-Lingual Search (Experimental)
- Greek↔Latin parallel detection
- Dictionary-based and AI semantic matching available

### Additional Features
- Intertext Repository for saving and sharing discoveries
- Metrical scansion display for Latin poetry
- CSV export of search results
- Saved searches with shareable URLs
- User authentication via Replit
- Corpus browser with chronological/alphabetical sorting

## Quick Start

### For Users
1. Visit the Tesserae V6 website
2. Navigate to **Search** > **Latin** or **Greek**
3. Select a Source text and Target text
4. Click **Run Search** to find parallels

### For Developers

```bash
# 1. Clone the repository (includes texts, embeddings, and lemma tables)
git clone https://github.com/tesserae/tesserae-v6.git
cd tesserae-v6

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Download search index files (~5.3 GB from tesserae.caset.buffalo.edu)
python scripts/download_data.py

# 4. Start the application
python main.py
```

The Git repository contains all source code, texts, embeddings, and lemma tables. The only additional download is the pre-built search indexes (SQLite databases, ~5.3 GB). The download script handles this automatically.

To check which data files are present or missing:
```bash
python scripts/download_data.py --check
```

See [docs/DATA_FILES_REFERENCE.md](docs/DATA_FILES_REFERENCE.md) for full details on data files, rebuilding indexes, and the code-vs-data separation.

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Flask (Python 3.11) |
| Database | PostgreSQL (Neon) |
| NLP | CLTK, NLTK |

## Documentation

- [API Reference](docs/API.md) - REST API endpoints
- [Developer Guide](docs/DEVELOPER.md) - Setup and architecture

## Project Structure

```
tesserae-v6/
├── backend/                 # Flask backend
│   ├── app.py              # Main application
│   ├── blueprints/         # Modular API routes
│   │   ├── admin.py        # Admin endpoints
│   │   ├── corpus.py       # Corpus management
│   │   ├── fusion.py       # Fusion search endpoint (SSE streaming)
│   │   ├── hapax.py        # Rare words/bigrams search
│   │   ├── intertext.py    # Repository management
│   │   └── search.py       # Search endpoints
│   ├── fusion.py           # 9-channel fusion engine
│   ├── matcher.py          # Text matching algorithms
│   ├── scorer.py           # V3-style scoring
│   ├── semantic_similarity.py  # AI semantic + dictionary matching
│   ├── text_processor.py   # Parsing and lemmatization
│   └── utils.py            # Utilities and helpers
├── client/                  # React frontend
│   └── src/
│       ├── components/     # UI components
│       │   ├── search/     # Search interfaces (fusion + classic)
│       │   ├── corpus/     # Corpus browser
│       │   ├── repository/ # Intertext repository
│       │   └── pages/      # Static pages
│       └── utils/          # Frontend utilities
├── data/                    # Corpus and data files
│   ├── inverted_index/     # Pre-built search indexes
│   └── lemma_tables/       # Latin/Greek lemma lookup tables
├── texts/                   # .tess text files (2,100+ works)
├── evaluation/              # Evaluation scripts and benchmarks
├── research/                # Scholarly work, studies, session notes
├── docs/                    # Documentation
└── embedding_toolkit/       # Semantic embedding tools
```

## Corpus

The Tesserae corpus includes texts in:
- **Latin** - Plautus through Medieval authors
- **Greek** - Homer through Byzantine period
- **English** - Shakespeare, Milton, Cowper, and more

Texts use the `.tess` format with section tags:
```
<vergil.aeneid 1.1> Arma virumque cano, Troiae qui primus ab oris
```

## Credits

Tesserae is a collaboration between [Neil Coffee](https://www.buffalo.edu/cas/english/faculty/faculty_directory.host.html/content/shared/cas/english/faculty-staff/faculty/coffee.detail.html) (University at Buffalo) and [Walter Scheirer](https://www.wjscheirer.com/) (University of Notre Dame). Neil created V6 and the team collaborates on its ongoing development.

**V3 Lead Developer**: [Chris Forstall](https://mta.ca/directory/chris-forstall) (Mount Allison University)

## License

MIT License - free to use, modify, and redistribute.

## Contributing

To contribute a text to the corpus, visit the "Upload Your Text" page in the Help section. Pre-formatted `.tess` files are processed faster.

## Links

- [Original Tesserae Project](http://tesserae.caset.buffalo.edu/)
- [Tesserae GitHub](https://github.com/tesserae)
