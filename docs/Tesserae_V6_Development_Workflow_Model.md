# Tesserae V6 Development Workflow Model

## Overview
This document outlines how to collaborate with graduate students on Tesserae V6 development while continuing to work in Replit.

## Project Structure for GitHub

### What Goes to GitHub (Code - ~50 MB)
- All Python backend code (`backend/`)
- React frontend code (`client/`)
- Configuration files (`main.py`, `package.json`, etc.)
- Documentation (`docs/`)

### What Stays Local Only (Data - ~4.7 GB)
These are excluded via `.gitignore` and must be shared separately.

**See [DATA_FILES_REFERENCE.md](DATA_FILES_REFERENCE.md) for the complete list with detailed explanations.**

Quick summary:
| Directory | Size | Contents |
|-----------|------|----------|
| `backend/embeddings/` | ~2 GB | Pre-computed semantic embeddings |
| `data/` | ~2.4 GB | Inverted index, lemma tables |
| `cache/` | ~5 MB | Rare words cache |
| `texts/` | ~308 MB | The .tess corpus files |

**Important:** These data files are pre-computed and static. They only change if someone rebuilds the search indexes or adds new texts to the corpus.

---

## The Collaboration Workflow

### Initial Setup (One Time)
1. Connect your Replit project to a GitHub repository (via Git pane in Replit)
2. Push your current code to GitHub
3. Share the data files with students separately (download as .zip from Replit, share via Dropbox/Drive)

### Your Daily Development in Replit
1. Continue working in Replit with AI assistance
2. Changes automatically appear in Replit's Git pane
3. When ready, push changes to GitHub (one click)

### When Students Contribute
1. Students fork your GitHub repo or you add them as collaborators
2. They develop on their machines using the shared data files
3. They submit a **pull request** on GitHub
4. You review and test (see options below)
5. If approved, merge the pull request on GitHub
6. Back in Replit, pull the latest code

---

## How to Review Student Contributions

Since reading code directly may not show you what it does, here are practical review options:

### Option 1: Pull and Test in Replit
- Merge their pull request on GitHub
- Pull the changes into your Replit
- Run the app and test it (or ask AI to help test)
- If something breaks, use **rollback** to restore a previous checkpoint

### Option 2: Students Demo Their Work
- Have students run their version on their own machine or Replit account
- They share a link or screen-share to demonstrate the changes
- You only merge after seeing it work

### Option 3: AI-Assisted Review
- After pulling changes, ask the AI to review what changed
- The AI can explain the code in plain language
- The AI can run the app and take screenshots to show differences

### Option 4: Separate Test Branch
- Create a "test" branch in Replit
- Pull student changes to the test branch first
- Test thoroughly before merging to main
- If it doesn't work, delete the test branch — main code stays safe

**Recommended Approach:** Combine Options 2 and 3. Have students demo first, then use AI to verify after pulling.

---

## Key Safety Features

### Rollback Protection
Replit automatically creates checkpoints during development. If any merge causes problems, you can always restore to a previous state.

### Data File Isolation
Since data files are in `.gitignore`, pulling student code changes will never affect your:
- Embeddings
- Search indexes
- Corpus files
- Cached data

### Sync Rule
Establish that **only you** handle corpus/index changes. Students work on code only. This prevents data divergence.

---

## Summary

GitHub acts as the "central hub" where code meets:
- You **push** FROM Replit TO GitHub
- You **pull** FROM GitHub TO Replit
- Students interact only via GitHub (never touch your Replit directly)
- Data files stay local and unchanged during code syncs
