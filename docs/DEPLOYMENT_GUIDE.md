# Tesserae V6 Deployment Guide

This guide covers deploying Tesserae V6 to a university server or any Linux-based environment.

## System Requirements

- **Python**: 3.11 or later
- **PostgreSQL**: 14 or later
- **RAM**: Minimum 4GB (8GB+ recommended for full features)
- **Disk Space**: 
  - Base installation: ~10GB
  - With full features (semantic search + CLTK): ~20GB

**Base installation breakdown:**
- Application code: ~500MB
- Embeddings: ~2GB (pre-computed, included in .zip)
- Inverted Index: ~2.4GB
- Syntax Index: ~200-400MB (LatinPipe parses)
- Text Corpus: ~500MB
- Python packages: ~2GB

**Additional for full features:**
- sentence-transformers + PyTorch: ~3GB
- CLTK + spaCy models: ~2GB

## Quick Start

### 1. Extract the Project

```bash
unzip tesserae-v6.zip -d /var/www/tesserae
cd /var/www/tesserae
```

### 2. Create Python Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Set Up PostgreSQL Database

```bash
# Create database and user
sudo -u postgres psql
CREATE DATABASE tesserae;
CREATE USER tesserae_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE tesserae TO tesserae_user;
\q
```

### 4. Configure Environment Variables

Create a `.env` file or set these in your environment:

```bash
export DATABASE_URL="postgresql://tesserae_user:your_secure_password@localhost:5432/tesserae"
export SESSION_SECRET="your-random-secret-key-here"
export ADMIN_PASSWORD="your-admin-password"
export FLASK_ENV="production"
```

### 5. Initialize the Database

The application creates tables automatically on first run. You can also initialize manually:

```bash
source venv/bin/activate
python -c "from backend.app import app, db; app.app_context().push(); db.create_all()"
```

### 6. Test the Application

```bash
source venv/bin/activate
python main.py
```

Visit http://localhost:5000 to verify it works.

## Enabling Full Features

The base installation works with all core search features. For full functionality including AI-powered semantic search and enhanced text processing, install these optional components:

### Semantic Search (AI-Powered Similarity)

Enables the "semantic" and "semantic_cross" match types that find conceptually similar passages even when words don't match.

**Requirements:**
- Additional ~3GB disk space
- 8GB+ RAM recommended
- Pre-computed embeddings are included in the .zip (`backend/embeddings/`)

**Installation:**

1. Add sentence-transformers to your environment:
   ```bash
   source venv/bin/activate
   pip install sentence-transformers>=2.6.0
   ```

2. Verify it works:
   ```bash
   python -c "from sentence_transformers import SentenceTransformer; print('OK')"
   ```

3. Restart the application. Semantic search options will now be available in the UI.

**What this enables:**
- Semantic match type (finds conceptually similar Latin/Greek passages)
- Cross-lingual semantic search (finds Greek passages similar to Latin and vice versa)
- Uses SPhilBERTa model for Latin/Greek and all-MiniLM-L6-v2 for English

### CLTK (Enhanced Latin/Greek Processing)

Enables advanced lemmatization and metrical scanning for texts not in the pre-computed MQDQ database.

**Requirements:**
- Additional ~2GB disk space (includes spaCy models)
- 6GB+ RAM recommended

**Installation:**

1. Add CLTK to your environment:
   ```bash
   source venv/bin/activate
   pip install cltk==1.2.0
   ```

2. Download the language models:
   ```bash
   python -c "from cltk.data.fetch import FetchCorpus; FetchCorpus('lat').import_corpus('lat_models_cltk')"
   python -c "from cltk.data.fetch import FetchCorpus; FetchCorpus('grc').import_corpus('grc_models_cltk')"
   ```

3. Restart the application.

**What this enables:**
- Enhanced lemmatization for rare/novel vocabulary (~5% of words not in lookup tables)
- Metrical scanning for texts NOT in the MQDQ database (minor/medieval Latin poets)
- Slightly better accuracy for morphological analysis

**Note:** Without CLTK, the application uses pre-built lemma lookup tables from Universal Dependencies treebanks, which cover the vast majority of classical vocabulary. CLTK is only needed for edge cases.

### Full Installation Summary

For a complete installation with all features:

```bash
source venv/bin/activate
pip install -r requirements.txt
pip install sentence-transformers>=2.6.0 cltk==1.2.0

# Download CLTK models
python -c "from cltk.data.fetch import FetchCorpus; FetchCorpus('lat').import_corpus('lat_models_cltk')"
python -c "from cltk.data.fetch import FetchCorpus; FetchCorpus('grc').import_corpus('grc_models_cltk')"
```

**Total disk space with all features:** ~20GB
**Recommended RAM:** 8GB+

## Production Deployment with Gunicorn

### Install Gunicorn

```bash
pip install gunicorn
```

### Run with Gunicorn

```bash
gunicorn --bind 0.0.0.0:5000 \
         --workers 2 \
         --timeout 300 \
         --worker-class sync \
         "backend.app:app"
```

**Important settings:**
- `--timeout 300`: Semantic searches can take time
- `--workers 2`: Keep low due to memory usage (~2GB per worker)
- `--worker-class sync`: Required for the lazy-loading to work properly

### Systemd Service (Recommended)

Create `/etc/systemd/system/tesserae.service`:

```ini
[Unit]
Description=Tesserae V6
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/tesserae
Environment="PATH=/var/www/tesserae/venv/bin"
Environment="DATABASE_URL=postgresql://tesserae_user:password@localhost:5432/tesserae"
Environment="SESSION_SECRET=your-secret-key"
Environment="ADMIN_PASSWORD=your-admin-password"
ExecStart=/var/www/tesserae/venv/bin/gunicorn \
          --bind 127.0.0.1:5000 \
          --workers 2 \
          --timeout 300 \
          "backend.app:app"
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tesserae
sudo systemctl start tesserae
```

## Nginx Reverse Proxy (Recommended)

Create `/etc/nginx/sites-available/tesserae`:

```nginx
server {
    listen 80;
    server_name tesserae.youruniversity.edu;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Serve static files directly (optional optimization)
    location /static {
        alias /var/www/tesserae/dist;
        expires 7d;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/tesserae /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## SSL/HTTPS with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tesserae.youruniversity.edu
```

## Directory Structure

Ensure these directories exist and contain data:

```
tesserae/
├── backend/
│   └── embeddings/          # ~2GB - Pre-computed semantic embeddings
├── data/
│   ├── inverted_index/      # ~2.4GB - Search index
│   │   └── syntax_latin.db  # ~200-400MB - LatinPipe syntax parses
│   └── lemma_tables/        # Latin/Greek lookup tables
├── texts/
│   ├── la/                  # Latin .tess files (1,429 texts)
│   ├── grc/                 # Greek .tess files (310 texts)
│   └── en/                  # English .tess files (14 texts)
├── dist/                    # Built frontend (React)
├── main.py                  # Entry point
└── requirements.txt
```

## Syntax Index Data

The syntax index (`data/inverted_index/syntax_latin.db`) contains Universal Dependencies parses for all Latin texts, produced by LatinPipe (EvaLatin 2024 winner).

**How it works:** The syntax data is stored as a standalone SQLite file (`syntax_latin.db`). The application reads directly from this file at runtime — no merge step is needed. (A merge script exists at `scripts/marvin_latinpipe/merge_syntax_index.py` for optionally combining syntax data into `la_index.db`, but standalone mode is the default.)

**Deploying the syntax index:**
1. Copy `syntax_latin.db` to `data/inverted_index/` on the target server
2. The application auto-detects and reads from it when available
3. Without it, syntax-based features are simply unavailable; all other search types work normally

**Adding syntax for new texts (after initial index build):**
When a new Latin text is approved via the admin panel, syntax parsing is automatically triggered using the LatinPipe REST API (no local model installation required). For bulk re-indexing, use the build script on Marvin (see `scripts/marvin_latinpipe/MARVIN_SETUP_GUIDE.md`).

**Provenance:** LatinPipe `latinpipe-evalatin24-240520`, built February 6, 2026 on Marvin server.

## Startup Behavior

The application uses **lazy loading** for performance:

1. **Immediate** (during import):
   - Flask app initialization
   - Database connection
   - Lemma lookup tables (~100k entries)

2. **Background thread** (after server starts):
   - Frequency caches for stoplist generation

3. **On first search** (lazy):
   - CLTK/NLTK NLP models
   - Semantic embeddings (loaded per-search)

This means the server responds quickly to health checks while heavy models load in the background.

## Troubleshooting

### "Module not found" errors
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Database connection errors
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check DATABASE_URL format
- Ensure database exists and user has permissions

### Out of memory
- Reduce Gunicorn workers to 1
- Ensure server has 4GB+ RAM
- Check for memory leaks with: `ps aux --sort=-%mem | head`
- Tune the concurrency gate (see below)

### Search concurrency gate

Heavy searches (fusion, sound, edit distance, semantic, cross-lingual) are limited by a file-based concurrency gate to prevent OOM crashes when multiple users search simultaneously.

**How it works:** Each active search holds an exclusive `flock` on a file in a lock directory. Before starting, new searches count active locks. If the limit is reached or available RAM is too low, the search waits and sends "queued" messages to the user's browser. The gate is crash-safe: when a process dies, the OS releases its flock automatically, and stale lock files are cleaned up on the next search attempt.

**Configuration (environment variables):**

| Variable | Default | Description |
|----------|---------|-------------|
| `TESSERAE_MAX_HEAVY_SEARCHES` | 2 | Max concurrent heavy searches across all processes |
| `TESSERAE_MEMORY_THRESHOLD_GB` | 8 | Min available RAM (GB) to start a new search |
| `TESSERAE_LOCK_DIR` | `{PROJECT_ROOT}/tmp/search_slots` | Directory for lock files (must be writable by Apache user) |

**Tuning:**
- On a server with 32GB+ RAM: set `TESSERAE_MAX_HEAVY_SEARCHES=3` or `4`
- On a server with 8–16GB RAM: keep at `2` (default)
- On a server with < 8GB RAM: set to `1` and raise `TESSERAE_MEMORY_THRESHOLD_GB` to `4`
- The lock directory must be on a local filesystem (not NFS) for `flock` to work correctly

**Adding to your environment:**
```bash
# In .env or systemd service file:
export TESSERAE_MAX_HEAVY_SEARCHES=2
export TESSERAE_MEMORY_THRESHOLD_GB=8
```

**Implementation:** `backend/concurrency_gate.py`

### Searches timeout
- Increase Gunicorn timeout: `--timeout 600`
- Increase Nginx proxy timeout: `proxy_read_timeout 600s;`

### CLTK models not loading
This is normal if CLTK data isn't installed. The app falls back to NLTK automatically. CLTK provides slightly better lemmatization but NLTK works fine for most use cases.

To install CLTK models (optional):
```bash
python -c "from cltk.data.fetch import FetchCorpus; FetchCorpus('lat').import_corpus('lat_models_cltk')"
python -c "from cltk.data.fetch import FetchCorpus; FetchCorpus('grc').import_corpus('grc_models_cltk')"
```

## Updating the Application

### Pre-Update Checks

Before deploying code updates, run this check to prevent API routing issues:

```bash
# Check for hardcoded /api prefixes in blueprints - should return nothing
grep "url_prefix='/api" backend/blueprints/*.py
```

If this returns any matches, those blueprints need fixing. The `/api` prefix is added automatically by `app.py` - blueprints should not duplicate it.

### Update Steps

1. Back up your database
2. Run pre-update checks (above)
3. Extract new code (preserve your data directories)
4. Update Python packages: `pip install -r requirements.txt`
5. Restart the service: `sudo systemctl restart tesserae`

## Apache + WSGI Deployment (Marvin)

On the Marvin server (tesserae.caset.buffalo.edu), Apache serves static files and Flask handles API requests separately.

### How It Works

- **Static files** (HTML, JS, CSS): Apache serves from `/var/www/tess-new/`
- **API requests** (`/api/*`): Apache forwards to Flask via `WSGIScriptAlias /api`
- **Flask app code**: Lives in `/var/www/tesseraev6_flask/`
- **Vite build output**: Goes to `/var/www/tesseraev6_flask/dist/`

These are **separate directories**. A `git pull` updates `dist/` but Apache serves from `tess-new/`.

### Deploying Frontend Changes

After any `git pull` that includes frontend changes (files in `dist/`):

```bash
cd /var/www/tesseraev6_flask
git pull
cp dist/index.html /var/www/tess-new/index.html
mkdir -p /var/www/tess-new/assets
cp dist/assets/* /var/www/tess-new/assets/
sudo systemctl restart apache2
```

### Deploying Backend-Only Changes

If only Python files changed (no `dist/` changes), just restart Apache:

```bash
cd /var/www/tesseraev6_flask
git pull
sudo systemctl restart apache2
```

### Recommended Permanent Fix

To eliminate the manual copy step, replace `/var/www/tess-new` with a symlink:

```bash
sudo mv /var/www/tess-new /var/www/tess-new-backup
sudo ln -s /var/www/tesseraev6_flask/dist /var/www/tess-new
sudo systemctl restart apache2
```

After this, `git pull` automatically updates what Apache serves. No manual copying needed.

To undo: `sudo rm /var/www/tess-new && sudo mv /var/www/tess-new-backup /var/www/tess-new`

## Contact

For issues with this deployment, check the application logs:
```bash
sudo journalctl -u tesserae -f
```
