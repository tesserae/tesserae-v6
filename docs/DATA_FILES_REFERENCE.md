# Tesserae V6 Data Files Reference

## Quick Summary

Most data files are included in the Git repository (texts, lemma tables, descriptions). The files you need to build or download separately are the **SQLite search indexes** (~6.3 GB total) and the **per-line semantic vectors** in `backend/embeddings/` (about 2 GB, untracked since 2026-10-19; build them with the scripts in `embedding_toolkit/` or take them from the downloads page). A script handles the indexes automatically.

```bash
git clone https://github.com/tesserae/tesserae-v6.git    # ~4 GB
cd tesserae-v6
pip install -r requirements.txt
python scripts/download_data.py    # Downloads ~6.3 GB of index files
python scripts/download_data.py --check   # Verify all files present
python main.py                     # Ready to go
```

To check what's present or missing without downloading:
```bash
python scripts/download_data.py --check
```

---

## What's in Git vs. What Needs Downloading

### Included in the Git Repository

| Directory | Size | Contents |
|-----------|------|----------|
| `texts/` | ~308 MB | 3,531 `.tess` text files in eight language folders (Latin, Greek, English, Coptic, Hebrew, Italian, Old French, Middle High German). The Persian, Urdu and Arabic texts are not in git |
| `data/lemma_tables/*.json` | ~40 MB | Lemma lookup tables (Latin, Greek) |
| `data/pedecerto/` | ~5 MB | Metrical scansion XML data |
| `cache/` | ~5 MB | Pre-computed rare words and bigrams |
| `backend/proper_names/` | ~400 KB | Greek-Latin proper name gazetteer (persons, deities, places) |

### NOT in Git — Download Separately

These are SQLite database files (blocked by `*.db` in `.gitignore`). They are hosted at `https://tesserae.caset.buffalo.edu/tesserae-data/`.

| File | Size | Required? | Description |
|------|------|-----------|-------------|
| `data/inverted_index/la_index.db` | 2.0 GB | Yes | Latin search index, rebuilt 18 October 2026 |
| `data/inverted_index/grc_index.db` | 2.9 GB | Yes | Greek search index, 18 October 2026 |
| `data/inverted_index/en_index.db` | 227 MB | Yes | English search index, 15 October 2026 |
| `data/inverted_index/cop_index.db` | 234 MB | No | Coptic search index, 153 texts, 19 October 2026. The public copy leaves out the Sahidica New Testament. The text is at Coptic Scriptorium (copticscriptorium.org) |
| `data/inverted_index/syntax_latin.db` | 1.6 GB | Yes | Latin syntax parses (LatinPipe UD annotations) |
| `data/inverted_index/syntax_greek.db` | 967 MB | Yes | Greek syntax parses (650 texts, UD annotations) |
| `data/inverted_index/he_index.db` | 47 MB | No | Biblical Hebrew search index (Tanakh, BHSA, CC BY-NC 4.0) |
| `data/inverted_index/fa_index.db` | 870 MB | No | Persian search index |
| `data/inverted_index/syntax_coptic.db` | 351 MB | No | Coptic syntax parses |
| `data/passage_index/` slices (`passage_index_la`, `_grc`, `_en`, `_fa`, `_ur`, `_cop`, `_he` `.tar.gz`) | 497 MB, 355 MB, 62 MB, 476 MB, 32 MB, 26 MB, 12 MB | No | The passage window index (descriptions, vectors) cut by language because the licenses differ. Windows per slice are in `index.json` beside them. Reassemble with `scripts/merge_index.py`. The Coptic slice leaves out the Sahidica New Testament |
| `data/passage_index/window_texts.db` (`window_texts.db.tar.gz`, 319 MB) | 1.9 GB | No | The text of each passage window. The project lead withdrew it on 2026-10-19. It held 1,800 windows of the Sahidica New Testament, whose license allows academic use only. A filtered copy is owed (gated item D7) |
| Core bundle `tesserae-public-core-20261014.tar.zst` | 3.3 GB | No | The project lead withdrew it on 2026-10-19 for the same reason, because it held the Sahidica texts. A rebuilt bundle without them is owed |

The Persian and Urdu archives above exist in the data folder. The decision of 2026-10-11 keeps Persian and Urdu out of the bundle and the Downloads page does not list them.

**Total to download: about 8 GB for the indexes and parses** (the passage window slices come on top, about 1.5 GB)

Embeddings (`backend/embeddings/`, about 2 GB for Latin and Greek, more for the other languages) are not in git since 2026-10-19. Build them with the scripts in `embedding_toolkit/` or take the Latin and Greek ZIP files from the Downloads page.

The manifest of all downloadable files, including URLs, sizes, and checksums, is maintained in `DATA_MANIFEST.json` at the project root.

---

## How the Download System Works

### For Collaborators (after cloning from GitHub)

```bash
python scripts/download_data.py              # Download all files
python scripts/download_data.py --check      # Check status only
python scripts/download_data.py --file la    # Download Latin index only
python scripts/download_data.py --file grc   # Download Greek index only
python scripts/download_data.py --force      # Re-download everything
```

The script reads `DATA_MANIFEST.json`, downloads compressed archives from Marvin, extracts them to the correct directories, and verifies SHA256 checksums.

### For Maintainers (after rebuilding indexes on Marvin)

After rebuilding an index, re-package the data files for download:

```bash
bash scripts/package_data.sh
```

This compresses each `.db` file, generates checksums, updates `DATA_MANIFEST.json`, copies everything to the Apache public directory, and creates an HTML index page. Then commit the updated `DATA_MANIFEST.json` to Git so collaborators get the new checksums.

---

## Rebuilding Data Files

If you need to rebuild any of these files from scratch:

| Data | How to Rebuild | Time |
|------|---------------|------|
| **Latin index** | `python scripts/build_inverted_index.py --language la --use-syntax-db --force` | ~30 min |
| **Greek index** | `python scripts/build_inverted_index.py --language grc --fast --force` | ~10 min |
| **English index** | `python scripts/build_inverted_index.py --language en --force` | ~2 min |
| **Latin syntax DB** | `python scripts/marvin_latinpipe/build_latinpipe_syntax.py` (on Marvin) | ~1-2 hours |
| **Greek syntax DB** | `python scripts/build_greek_syntax_db.py` | ~20 min |
| **Lemma tables** | `python scripts/build_lemmas.py` | ~5 min |
| **Embeddings** | Embedding generation scripts in `embedding_toolkit/` | ~30 min/language |
| **Cache** | Auto-rebuilds on first use | Automatic |

---

## Keeping Data Files Updated

Most of the time, nothing changes. The index files only need updating when you add new texts, rebuild an index with improved lemmatization, or re-parse the syntax database.

### When You Update an Index (Maintainer Workflow)

1. **Rebuild the index on Marvin** using the build scripts above
2. **Re-run the packaging script:**
   ```bash
   bash scripts/package_data.sh
   ```
   This re-compresses the updated `.db` files, generates new SHA256 checksums, updates `DATA_MANIFEST.json`, and replaces the old downloads on the Apache server.
3. **Commit the updated `DATA_MANIFEST.json` to Git:**
   ```bash
   git add DATA_MANIFEST.json
   git commit -m "Update data manifest with new index checksums"
   git push
   ```
   This ensures collaborators see the new checksums when they pull.

### When a Collaborator Needs the Latest Data

1. **Pull the latest code** (which includes the updated manifest):
   ```bash
   git pull
   ```
2. **Re-run the download script:**
   ```bash
   python scripts/download_data.py --force
   ```
   Without `--force`, the script skips files that already exist locally. Use `--force` to replace them with the latest versions, or delete the specific `.db` file and re-run without `--force`.

### What Triggers an Update?

| Event | What to Rebuild | How Often |
|-------|----------------|-----------|
| New texts added to corpus | Inverted index for that language | Occasionally |
| Lemmatization improvements | Inverted index (full rebuild) | Rarely |
| LatinPipe re-parse | `syntax_latin.db` | Rarely |
| Greek treebank updates | `syntax_greek.db` | Rarely |
| New embedding model | Embeddings (built, not in Git) | Very rarely |

There is no automatic notification when indexes are updated. Inform collaborators when you push a new manifest ("Pull and re-run the download script").

---

## Proper Name Gazetteer

`backend/proper_names/` contains a curated gazetteer of Greek and Latin proper names compiled from three sources:

- **Wikidata** (~660 mythology figures): Greek-Latin name pairs queried from Wikidata's Ancient Greek and Latin labels for mythological characters
- **Pleiades** (~840 places): Greek-Latin place name pairs from the [Pleiades gazetteer](https://pleiades.stoa.org/) of ancient world locations, filtered to classically attested places
- **Manual curation** (~57 entries): Major epic heroes missing from Wikidata (Achilles, Hector, Odysseus), Olympian deities with Roman equivalents (Zeus/Jupiter, Athena/Minerva, etc.), patronymics (Pelides, Atrides), and key literary places (Troy, Carthage, Olympus)

All Greek forms are normalized: polytonic diacritics stripped, lowercased, matching the lemmatization output used in searches.

Two files serve complementary purposes:

| File | Purpose |
|------|---------|
| `cross_lingual_pairs.json` | Greek→Latin name mappings for cross-lingual dictionary matching (1,532 Greek entries → 1,937 Latin forms) |
| `proper_names.json` | Flat lookup lists of all Greek (1,532) and Latin (1,643) name forms for proper name identification and filtering |

---

## Notes

1. **`.gitignore` blocks `*.db` files** — This is why the SQLite indexes don't end up on GitHub even though their parent directories are tracked.
2. **The texts are on GitHub.** Unlike many large NLP projects, the corpus texts for eight languages are committed to Git (~308 MB, 3,531 `.tess` files).
3. **Embeddings are not on GitHub** since 2026-10-19. They were committed until then for ease of setup, but the copies on GitHub fell behind the ones in production after text repairs, so they are now built or downloaded like the indexes.
4. **Index rebuilds require texts** — You need the text corpus present before rebuilding any search index.
5. **Latin syntax DB requires LatinPipe** — `syntax_latin.db` can only be rebuilt on Marvin where the LatinPipe model is available. `syntax_greek.db` is built from pre-existing treebank data and can be rebuilt anywhere.
