# Tesserae V6 Embedding Toolkit

A standalone tool to pre-compute AI embeddings for classical texts outside of Replit.

## Setup (5 minutes)

### 1. Install Python 3.9+ if not already installed
```bash
python --version  # Should show 3.9 or higher
```

### 2. Install dependencies
```bash
pip install sentence-transformers numpy torch
```

### 3. Copy your corpus folder
Copy the `corpus/` folder from the Tesserae project to this directory:
```
embedding_toolkit/
├── corpus/
│   ├── la/           # Latin texts
│   ├── grc/          # Greek texts
│   └── en/           # English texts
├── compute_embeddings.py
└── README.md
```

## Usage

### Compute embeddings for a single text:
```bash
python compute_embeddings.py corpus/la/vergil.aeneid.tess
```

### Compute embeddings for all Latin texts:
```bash
python compute_embeddings.py corpus/la/
```

### Compute embeddings for all Greek texts:
```bash
python compute_embeddings.py corpus/grc/
```

### Compute everything:
```bash
python compute_embeddings.py corpus/
```

## Output

Embeddings are saved to `embeddings/{language}/{text}.npy`:
```
embeddings/
├── la/
│   ├── vergil.aeneid.npy
│   ├── vergil.aeneid.meta.json
│   └── ...
├── grc/
│   ├── homer.iliad.npy
│   └── ...
└── manifest.json
```

## Estimated Time

- ~1-2 minutes per 1,000 lines of text (on CPU)
- ~10-20 seconds per 1,000 lines (with GPU)
- Full Latin corpus (~180k lines): ~3-6 hours on CPU
- Full Greek corpus (~90k lines): ~1.5-3 hours on CPU

## After Computing

1. Copy the entire `embeddings/` folder back to Replit
2. Place it at `backend/embeddings/` in your project
3. The semantic search will automatically use these pre-computed embeddings

## Models Used

- **Latin/Greek**: SPhilBERTa (bowphs/SPhilBerta) - 768-dimensional vectors
- **English**: all-MiniLM-L6-v2 - 384-dimensional vectors

## Troubleshooting

**Out of memory?** Process texts in smaller batches:
```bash
python compute_embeddings.py corpus/la/vergil.aeneid.tess --batch-size 16
```

**Want to use GPU?** Install CUDA-enabled PyTorch:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```
