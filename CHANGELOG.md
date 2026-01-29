# Tesserae V6 Changelog

## Published (January 26, 2026)

Initial public release of Tesserae V6 at https://tesserae-v-6.replit.app

### Features
- Phrase search with V3-style scoring (IDF + distance penalties)
- Corpus-wide line search across 800,000+ indexed lines
- Rare word pairs search with bigram frequency analysis
- Rare words explorer with dictionary definitions
- Cross-lingual search (Greek-Latin) using SPhilBERTa embeddings
- Intertext repository for saving and sharing discovered parallels
- User authentication via Replit OpenID Connect with ORCID linking
- Metrical scansion display from MQDQ/Pede Certo data
- Text viewer with highlighted matches
- CSV export for search results
- Saved searches (localStorage)
- Shareable search URLs

### Corpus
- 1,444+ Latin texts
- 650+ Greek texts
- 14+ English texts

---

## Pending

Changes made after the January 26, 2026 release, awaiting next deployment:

### Fixes
- Rare Words Explorer: Fixed asterisk display issue in lemma column
- Rare Words Explorer: Added author and work columns (previously empty)
- Rare Words Explorer: Added clickable links to text viewer for each location
- Corpus-wide line search: Fixed highlighting to show all matched word forms (not just exact lemma matches)
- Rare Words Explorer (Greek): Added diacritics lookup for Greek lemmas using corpus text forms
- Repository: Fixed word highlighting using platform-standard u/v normalization (consistent with matcher.py)
- Rare Words Explorer: Fixed "First Work" column to show properly capitalized work title (client-side formatting)

### Enhancements
- Repository: Added submitter attribution showing name AND ORCID when both available
- About page: Added automatic "Last Updated" date (reads from git)
- Created CHANGELOG.md for version tracking
- Enhanced article methods draft with feature examples and benchmark testing sections
- Repository: Simplified status system (flagged/normal instead of pending/confirmed)
- Repository: Added hierarchical "By Work" browse view (Language→Author→Work)
- Repository: Added flag toggle button for logged-in users
- Repository: Added 500-character limit on contributor notes
- Rare Words Explorer: Mobile-responsive layout with compact headers

### Documentation
- docs/ARTICLE_METHODS_DRAFT.md: Comprehensive methods article featuring Vergil-Lucan parallel case study

---

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 6.0 | January 26, 2026 | Initial public release |
