# Tesserae V6 Data Files Reference

## Purpose
This document tracks all large data files that are **excluded from GitHub** but **required for the application to run**. These files must be shared separately when collaborating or deploying.

---

## Files Excluded from GitHub

The following directories are listed in `.gitignore` and will NOT sync to GitHub:

### 1. Semantic Embeddings (~2 GB)
**Location:** `backend/embeddings/`

**Contents:**
- Pre-computed vector embeddings for semantic search
- Latin embeddings (SPhilBERTa model)
- Greek embeddings (SPhilBERTa model)  
- English embeddings (MiniLM model)

**What happens without it:** Semantic match type won't work, but all other search types function normally.

**How to rebuild:** Run embedding generation scripts (~30 min per language). Requires sentence-transformers installed. See `scripts/` folder or ask for guidance.

---

### 2. Search Index (~2.4 GB)
**Location:** `data/inverted_index/`

**Contents:**
- Pre-built inverted index for fast lemma lookups
- Line content tables (~528k Latin lines, ~201k Greek lines, ~62k English lines)

**What happens without it:** Searches will be extremely slow or fail entirely.

**How to rebuild:** Admin panel → "Rebuild Index" (takes ~10 minutes)

---

### 3. Lemma Lookup Tables (~40 MB)
**Location:** `data/lemma_tables/`

**Contents:**
- `latin_lemmas.json` - 39,291 Latin lemma entries
- `greek_lemmas.json` - Greek lemma mappings
- Maps word forms to their dictionary headwords

**What happens without it:** Lemma-based matching won't work; only exact matches available.

**How to rebuild:** Run `scripts/build_lemmas.py` (requires texts to be present)

---

### 4. Text Corpus (~308 MB)
**Location:** `texts/`

**Contents:**
- All .tess format text files
- Organized by language: `texts/la/`, `texts/grc/`, `texts/en/`
- Over 2,100 texts total

**What happens without it:** No texts to search.

**How to rebuild:** Re-download from original Tesserae GitHub repositories

---

### 5. Cache Files (~5 MB)
**Location:** `cache/`

**Contents:**
- `cache/rare_words/` - Pre-computed rare words by language
- `cache/bigrams/` - Bigram frequency data (rebuilt as needed)

**What happens without it:** Rare words features slower on first load; rebuilds automatically.

**How to rebuild:** Auto-rebuilds on first use, no action needed

---

## Summary Table

| Directory | Size | Basic Search? | Semantic Search? | Can Rebuild? |
|-----------|------|---------------|------------------|--------------|
| `backend/embeddings/` | ~2 GB | Not needed | **REQUIRED** | Difficult |
| `data/inverted_index/` | ~2.4 GB | **REQUIRED** | **REQUIRED** | Yes (Admin) |
| `data/lemma_tables/` | ~40 MB | **REQUIRED** | **REQUIRED** | Yes (script) |
| `texts/` | ~308 MB | **REQUIRED** | **REQUIRED** | Re-download |
| `cache/` | ~5 MB | Not needed | Not needed | Auto-rebuilds |

**Total excluded: ~4.7 GB**

---

## Recovery Procedure

If you lose the data files, here's what to do:

| Data | Recovery Method | Difficulty |
|------|-----------------|------------|
| **Texts** | Re-download from original Tesserae GitHub | Easy |
| **Lemma tables** | Run `scripts/build_lemmas.py` (requires texts) | Easy |
| **Inverted index** | Admin panel → "Rebuild Index" (~10 min) | Easy |
| **Cache** | Auto-rebuilds on first use | Automatic |
| **Embeddings** | Run embedding scripts (~30 min/language, needs sentence-transformers) | Moderate |

### What Takes the Most Time?
1. **Embeddings** - About 30 minutes per language to regenerate (Latin, Greek, English). Not hard, just slow.
2. **Original texts** - Can be re-downloaded from Tesserae GitHub repositories

### What Can Be Rebuilt?
- Inverted index, lemma tables, and cache can all be regenerated from the texts

---

## How to Share These Files

### For Graduate Students / Collaborators:
1. Download the complete project from Replit as a .zip file
2. The .zip includes ALL files (both code and data)
3. Students extract and have everything needed to run locally

### For GitHub Collaboration:
1. Code goes to GitHub (automatic via .gitignore rules)
2. Data files shared separately via:
   - Dropbox/Google Drive link
   - University file share
   - Direct .zip download from Replit

### For Server Deployment:
1. Download .zip from Replit (includes everything)
2. Extract to server
3. Follow `docs/DEPLOYMENT_GUIDE.md`

---

## Important Notes

1. **These files are static** - They only change if you:
   - Add new texts to the corpus
   - Rebuild the search index (Admin panel)
   - Regenerate embeddings (rare)

2. **Students should NOT modify these files** - Establish that only you handle corpus/index changes to prevent data divergence.

3. **The .gitignore protects you** - Even if you accidentally try to push, Git will skip these large files.

4. **Rollback still works** - Replit checkpoints include these data files, so you can always restore.

5. **Embeddings can be regenerated** - Takes ~30 min per language if needed. Not hard, just requires sentence-transformers to be installed.
