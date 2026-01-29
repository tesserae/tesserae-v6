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
│   └── lemma_tables/        # Latin/Greek lookup tables
├── texts/
│   ├── latin/               # Latin .tess files
│   ├── greek/               # Greek .tess files
│   └── english/             # English .tess files
├── dist/                    # Built frontend (React)
├── main.py                  # Entry point
├── requirements.txt
└── backend/
    └── app.py               # Flask application
```

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

1. Back up your database
2. Extract new code (preserve your data directories)
3. Update Python packages: `pip install -r requirements.txt`
4. Restart the service: `sudo systemctl restart tesserae`

## Contact

For issues with this deployment, check the application logs:
```bash
sudo journalctl -u tesserae -f
```
