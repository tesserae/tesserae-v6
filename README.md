# Tesserae V6

A web-based intertextual analysis tool for Latin, Greek, English, Coptic, and Biblical Hebrew texts. Tesserae identifies textual parallels, allusions, quotations, and reuse across a corpus of 3,500+ literary works, combining lexical, sub-lexical, semantic, and syntactic evidence in a single interpretable score.

## Features

### Search Modes
- **Parallel Phrases**: Compare two texts to find shared vocabulary and allusions
- **Line Search**: Search a single line against the entire corpus
- **Rare Words (Hapax)**: Find rare vocabulary shared between texts
- **Word Pairs (Bigrams)**: Discover unique word combinations
- **String Search**: Wildcard and boolean text search across all works
- **Theme Search**: Describe the content you want in plain language and find passages across the corpus, in any indexed language
- **Similar Passages**: From any passage in the Reader, find others like it

### Match Types
- **Lemma**: Two or more shared dictionary headwords (default, V3-style matching)
- **Lemma (single)**: One shared headword, high recall and noisy
- **Exact**: Identical surface forms
- **Rare Word**: Shared low-frequency vocabulary
- **Sound**: Character trigram overlap
- **Edit Distance**: Fuzzy matching (Levenshtein similarity)
- **Quotation**: Runs of consecutive identical tokens, the signature of direct citation
- **Semantic**: Embedding similarity (SPhilBERTa for Latin/Greek/English, multilingual-e5 for Coptic, a fine-tuned MiqraBERT for Hebrew)
- **Dictionary**: Curated synonym pairs, including Coptic Wordnet
- **Syntax**: Dependency pattern matching at shared lemma positions
- **Syntax (structural)**: Matching dependency patterns with no shared lemmas
- **Fusion**: All 11 channels combined with weighted scoring, under weight profiles fitted to text types (Latin epic, biblical prose). Channel availability varies by language: one without a syntax database or a synonym dictionary runs the channels it has.

### Cross-Lingual Search
- Greek↔Latin parallel detection
- Hebrew→Greek, routed through the Septuagint, and Hebrew→Latin against the Vulgate
- Dictionary-based and semantic matching available

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

# 3. Set up environment variables (copy the template, then edit as needed)
cp .env.example .env
# NOTE: for local development, .env must set DEPLOYMENT_ENV=dev (or provide a
# SESSION_SECRET). Otherwise the app will refuse to start — this is a safeguard
# against running a real deployment without a proper session secret.

# 4. Download search index files (~3.1 GB from tesserae.caset.buffalo.edu,
#    ~11.2 GB once extracted; --file la fetches just one)
python scripts/download_data.py

# 5. Start the application
python main.py
```

The Git repository contains all source code, texts, embeddings, and lemma tables. The only additional download is the pre-built search indexes (~3.1 GB compressed, ~11.2 GB extracted). The download script handles this automatically.

Published: inverted indexes for Latin, Greek, English, Coptic, and Hebrew; syntax databases for Latin, Greek, and Coptic; the passage index behind Theme Search and Similar Passages; and the passage text those results display. Theme Search additionally needs the query encoder service (`services/embed_server.py`) running. The passage text covers the five languages whose sources ship in `texts/`: Persian and Urdu windows are in the index but their texts are not published, so those results show a description without the passage. Data and scripts for the Coptic study are published separately under Downloads on the site.

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
| NLP | CLTK, NLTK, Stanza |
| Embeddings | SPhilBERTa, multilingual-e5-large, MiqraBERT (the query encoder runs as its own service) |

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
│   │   ├── assistant.py    # Tessa, the site assistant
│   │   ├── corpus.py       # Corpus management and text descriptions
│   │   ├── fusion.py       # Fusion search endpoint (SSE streaming)
│   │   ├── hapax.py        # Rare words/bigrams search
│   │   ├── intertext.py    # Repository management
│   │   ├── mcp_http.py     # MCP connector (Claude and other clients)
│   │   ├── passages.py     # Theme Search, Similar Passages, the Reader
│   │   └── search.py       # Search endpoints
│   ├── fusion.py           # 11-channel fusion engine
│   ├── passage_index.py    # Passage window index behind Theme Search
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
├── texts/                   # .tess text files (3,500+ works)
├── evaluation/              # Evaluation scripts and benchmarks
├── research/                # Scholarly work, studies, session notes
├── docs/                    # Documentation
└── embedding_toolkit/       # Semantic embedding tools
```

## Corpus

The Tesserae corpus includes texts in:
- **Latin** (1,861 works) - Plautus through the Latin Middle Ages
- **Greek** (1,288 works) - Homer through the Byzantine period, including the Septuagint and the SBL Greek New Testament
- **Coptic** (187 works) - Sahidic and Bohairic, biblical and monastic
- **English** (162 works) - Shakespeare, Milton, Cowper, and public-domain translations
- **Biblical Hebrew** (39 works) - the Tanakh, in Sefaria's Miqra according to the Masorah
- A small number of medieval vernacular texts (Italian, Old French, Middle High German)

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
