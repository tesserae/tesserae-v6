# Tesserae V6 Developer Guide

This guide covers setup, architecture, and development practices for Tesserae V6.

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL database
- Git

## Quick Setup (Replit)

The project is configured to run on Replit with minimal setup:

1. Fork the Replit project
2. Database is auto-provisioned via `DATABASE_URL`
3. Click "Run" to start the application

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/tesserae/tesserae-v6.git
cd tesserae-v6
```

### 2. Python Environment

```bash
# Install Python dependencies
pip install -r requirements.txt

# Download NLTK data
python -c "import nltk; nltk.download('wordnet'); nltk.download('averaged_perceptron_tagger')"
```

### 3. Frontend Setup

```bash
cd client
npm install
npm run build
cd ..
```

### 4. Database Setup

Set the `DATABASE_URL` environment variable:

```bash
export DATABASE_URL="postgresql://user:password@host:5432/database"
```

Tables are created automatically on first run.

### 5. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string |
| ADMIN_PASSWORD | Yes | Admin panel password |
| SESSION_SECRET | No | Flask session secret (auto-generated) |

### 6. Run the Application

```bash
python main.py
```

The app runs on `http://localhost:5000`.

---

## Architecture Overview

### Backend (Flask)

```
backend/
├── app.py              # Main Flask application
├── matcher.py          # Text matching algorithms
├── scorer.py           # V3-style scoring system
├── text_processor.py   # Parsing and lemmatization
├── inverted_index.py   # Corpus search index
├── feature_extractor.py # POS, sound, meter features
├── utils.py            # Utilities and display names
├── replit_auth.py      # Authentication handling
└── blueprints/
    ├── admin.py        # Admin endpoints
    ├── corpus.py       # Corpus management
    ├── hapax.py        # Rare words/bigrams
    ├── intertext.py    # Repository CRUD
    ├── search.py       # Search endpoints
    └── batch.py        # Batch processing
```

### Frontend (React + Vite)

```
client/src/
├── components/
│   ├── search/         # Search interfaces
│   │   ├── SearchForm.jsx
│   │   ├── SearchResults.jsx
│   │   ├── LineSearch.jsx
│   │   └── CrossLingualSearch.jsx
│   ├── corpus/         # Corpus browser
│   │   └── CorpusBrowser.jsx
│   ├── repository/     # Intertext repository
│   ├── admin/          # Admin panel
│   ├── pages/          # Static pages
│   │   ├── HelpPage.jsx
│   │   ├── AboutPage.jsx
│   │   └── DownloadsPage.jsx
│   ├── layout/         # Navigation, footer
│   └── common/         # Shared components
├── utils/
│   └── formatting.js   # Text formatting utilities
└── App.jsx             # Main React app
```

---

## Key Systems

### 1. Text Matching (`matcher.py`)

The matcher supports multiple matching strategies:

```python
from backend.matcher import Matcher

matcher = Matcher()

# Find matches between parsed text units
matches = matcher.find_matches(
    source_units,      # Parsed source text (from TextProcessor)
    target_units,      # Parsed target text
    settings={'match_type': 'lemma'}  # or: exact, sound
)
```

**Match Types:**
- `lemma`: Dictionary form matching (default)
- `exact`: Exact string matching
- `sound`: Phonetic similarity via character trigrams

### 2. Scoring Algorithm (`scorer.py`)

V3-style distance-based scoring:

```python
from backend.scorer import Scorer

scorer = Scorer()

# Score a set of matches between source and target units
scored_results = scorer.score_matches(
    matches,           # List of match objects from matcher
    source_units,      # Parsed source text units
    target_units,      # Parsed target text units
    settings={'frequency_source': 'corpus'}
)
```

**Scoring factors:**
- **IDF**: Rare words score higher (inverse document frequency)
- **Distance**: Closer word matches score higher
- **Match count**: More matching words increase score

### 3. Inverted Index (`inverted_index.py`)

Pre-built SQLite index for fast corpus-wide searches:

```python
from backend.inverted_index import lookup_lemmas, is_index_available

# Check if index exists
if is_index_available('la'):
    # Find all occurrences of lemmas
    results = lookup_lemmas(['amor', 'bellum'], 'la')
    # Returns: {(text_id, ref) -> {'lemmas': [...], 'positions': [...]}}
```

### 4. Text Processing (`text_processor.py`)

Language-specific lemmatization and tokenization:

```python
from backend.text_processor import TextProcessor

processor = TextProcessor()

# Parse and lemmatize text
units = processor.parse_text(text_content, language='la')
# Returns: [{'loc': '1.1', 'text': '...', 'tokens': [...], 'lemmas': [...]}]

# Get lemmas for a single line
lemmas = processor.lemmatize("Arma virumque cano", language='la')
# Returns: ['arma', 'vir', 'cano']
```

---

## Database Schema

### Core Tables

```sql
-- User saved searches
CREATE TABLE saved_searches (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    name VARCHAR(255),
    search_config JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Intertext repository
CREATE TABLE intertexts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    source_text VARCHAR(255),
    source_loc VARCHAR(100),
    source_line TEXT,
    target_text VARCHAR(255),
    target_loc VARCHAR(100),
    target_line TEXT,
    score INTEGER,
    notes TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Text upload requests
CREATE TABLE text_requests (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255),
    author VARCHAR(255),
    work VARCHAR(255),
    language VARCHAR(10),
    notes TEXT,
    content TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Adding New Features

### Adding a New Search Mode

1. Create backend endpoint in `backend/blueprints/`:

```python
@search_bp.route('/my-new-search', methods=['POST'])
def my_new_search():
    data = request.get_json()
    # Implement search logic
    return jsonify({'results': results})
```

2. Register blueprint in `backend/app.py`:

```python
from backend.blueprints.search import search_bp
app.register_blueprint(search_bp, url_prefix='/api')
```

3. Create React component in `client/src/components/search/`:

```jsx
export default function MyNewSearch() {
    const [results, setResults] = useState([]);
    
    const runSearch = async () => {
        const res = await fetch('/api/my-new-search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ /* params */ })
        });
        const data = await res.json();
        setResults(data.results);
    };
    
    return (/* JSX */);
}
```

4. Add route in `client/src/App.jsx`:

```jsx
<Route path="/search/my-new" element={<MyNewSearch />} />
```

### Adding a New Match Type

1. Add matching logic in `backend/matcher.py`:

```python
def match_my_type(self, source_tokens, target_tokens):
    matches = []
    # Implement matching logic
    return matches
```

2. Register in matcher dispatch:

```python
if match_type == 'my_type':
    return self.match_my_type(source, target)
```

3. Add to frontend match type selector.

---

## Testing

### Run Backend Tests

```bash
pytest backend/tests/
```

### Run Frontend Tests

```bash
cd client
npm test
```

### Manual Testing

1. Start the app: `python main.py`
2. Open `http://localhost:5000`
3. Test search with known text pairs

---

## Corpus Management

### Text Format (.tess)

```
<author.work section> Text content here
<vergil.aeneid 1.1> Arma virumque cano, Troiae qui primus ab oris
```

### Adding Texts

1. Place `.tess` file in `data/texts/<language>/`
2. Run frequency recalculation: `POST /api/frequencies/recalculate`
3. Rebuild inverted index if needed

### Directory Structure

```
data/
├── texts/
│   ├── la/           # Latin texts
│   ├── grc/          # Greek texts
│   └── en/           # English texts
├── inverted_index/   # Pre-built search indexes (SQLite)
└── embeddings/       # Pre-computed embeddings
```

---

## Deployment

### Replit Deployment

1. Click "Deploy" in Replit
2. Choose "Autoscale" deployment type
3. Set production environment variables
4. Deploy

### Manual Deployment

1. Build frontend: `cd client && npm run build`
2. Set `FLASK_ENV=production`
3. Use Gunicorn: `gunicorn -b 0.0.0.0:5000 main:app`

---

## Performance Tips

1. **Use inverted index** for corpus-wide searches
2. **Cache results** - repeated searches hit cache
3. **Limit max_results** for faster response
4. **Pre-compute embeddings** for semantic search

---

## Troubleshooting

### CLTK Models Missing

```bash
python -c "from cltk.data.fetch import FetchCorpus; FetchCorpus('lat').import_corpus('lat_models_cltk')"
python -c "from cltk.data.fetch import FetchCorpus; FetchCorpus('grc').import_corpus('grc_models_cltk')"
```

### Port Already in Use

```bash
kill $(lsof -t -i:5000)
python main.py
```

### Frontend Not Updating

```bash
cd client
npm run build
# Hard refresh browser (Ctrl+Shift+R)
```

---

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes with tests
4. Submit pull request

## Code Style

- Python: Follow PEP 8
- JavaScript: Use ESLint configuration
- Commits: Use conventional commit messages

---

## Recent Technical Changes (January 2026)

### Edit Distance Matching Optimization

- **Problem:** Edit distance search was O(n²), comparing every token pair. For large texts like Aeneid vs Pharsalia (~10k × ~8k = 80M comparisons), this caused timeouts.
- **Solution:** Trigram-based candidate filtering using `feature_extractor.get_trigrams()`
- **Algorithm:**
  1. Pre-compute trigrams for all target tokens (e.g., "arma" → {"arm", "rma"})
  2. Build inverted index: trigram → set of target indices
  3. For each source token, only compare against targets sharing ≥1 trigram
  4. Filter further by length difference before computing Levenshtein distance
- **Result:** Reduced comparisons from ~80M to ~13M (84% reduction), completing in ~2 minutes
- **Limitation:** Corpus-wide edit distance search not yet supported; "Search Corpus" button hidden for edit_distance results
- **Files:** `backend/matcher.py`, `client/src/components/search/SearchResults.jsx`

### Rare Words Search Text Display Fix

- **Problem:** Rare Words search results showed line references but not actual text
- **Solution:** Added `get_line_text_from_file()` helper to read text from .tess files
- **Files:** `backend/blueprints/hapax.py`

### Admin Blueprint Routing Fix

- **Problem:** Admin routes had hardcoded `/api` prefix that duplicated with Marvin's Apache WSGIScriptAlias
- **Solution:** Routes now use `API_PREFIX` variable based on `DEPLOYMENT_ENV` environment variable
- **Files:** `backend/blueprints/admin.py`, `backend/app.py`

### Password Authentication for Marvin

- **Feature:** Email/password login for Marvin deployment (Replit uses OpenID Connect)
- **Components:** Registration, login, logout with bcrypt password hashing
- **Requires on Marvin:** `password_hash` column in users table, `SESSION_SECRET` environment variable
- **Files:** `backend/marvin_auth.py`, `backend/app.py`, `client/src/components/layout/Header.jsx`
