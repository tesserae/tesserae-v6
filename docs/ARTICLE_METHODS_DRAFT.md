# Tesserae V6: AI-Assisted Development of a Multi-Feature Intertextual Analysis Platform

## Abstract

This article describes the development methodology and technical architecture of Tesserae V6, a web-based platform for identifying intertextual parallels in classical Latin, Greek, and English literature. Developed through an extended collaboration between a digital humanities researcher and an AI assistant (Claude/Anthropic), the project demonstrates both the possibilities and challenges of AI-assisted software development in specialized academic domains. The platform advances beyond purely lexical matching to incorporate metrical, phonetic, and semantic features, enabling discovery of allusions that might otherwise escape detection. We present a case study demonstrating how multi-feature analysis reveals a previously unrecognized echo between Vergil's *Aeneid* and Lucan's *Bellum Civile*.

## 1. Introduction

Intertextual analysis—the identification and interpretation of references between texts—has been central to classical scholarship since antiquity. The Tesserae Project, founded by Neil Coffee at the University at Buffalo, pioneered computational approaches to this task, enabling researchers to search millions of potential parallels across a corpus of over 2,100 texts. However, traditional computational methods have relied primarily on lexical matching: finding shared words (typically in lemmatized form) between passages.

This limitation has long been recognized. Many of the most sophisticated literary allusions operate through non-lexical channels: a poet might echo the rhythm of a predecessor's line, deploy similar sound patterns, or invoke conceptual similarities that transcend vocabulary. Tesserae V6 represents an attempt to incorporate these additional dimensions into computational intertextual analysis.

This article focuses not only on the resulting platform but on the development methodology itself. The entire codebase was developed through conversation between a humanities scholar (the project PI) and an AI coding assistant, with no traditional programming by the researcher. This mode of development raises important questions about the future of digital humanities tool-building, the nature of technical expertise, and the potential for AI to democratize access to sophisticated computational methods.

## 2. Development Methodology: AI-Assisted Coding in Digital Humanities

### 2.1 The Collaborative Model

Tesserae V6 was developed over eight days (January 18–26, 2026) through an intensive iterative conversational process using Replit Agent. The PI, possessing deep domain expertise in classical intertextuality but limited programming experience, directed development by:

- Articulating feature requirements in natural language
- Evaluating outputs against scholarly standards
- Identifying edge cases and failure modes
- Providing domain knowledge about Latin and Greek linguistics

The AI assistant (Claude, developed by Anthropic) contributed:

- Implementation of features in Python (Flask backend) and React (frontend)
- Architectural decisions about database design and search optimization
- Integration of NLP libraries (CLTK, NLTK, sentence-transformers)
- Debugging and performance optimization

### 2.2 Challenges and "Blindspots"

This mode of development revealed characteristic failure patterns that differ from traditional software development:

**Context Window Limitations**: AI assistants operate within a limited "context window"—the amount of information they can hold in memory during a conversation. In a complex codebase, the assistant might make changes to one component while forgetting relevant constraints in another. The resulting bugs could be subtle and difficult to diagnose, as they stemmed not from logical errors but from incomplete awareness of the system state.

**Domain Knowledge Gaps**: While the AI assistant could implement sophisticated algorithms, it lacked intuitive understanding of classical scholarship. For instance, early versions treated Latin orthographic variants (v/u, i/j) as distinct characters, failing to recognize that "vada" and "uada" represent the same word. Such issues required the PI to recognize the symptom and articulate the underlying linguistic principle.

**Framework Migrations**: When the frontend was migrated from vanilla JavaScript to React, API connections that had functioned correctly became silently broken. The AI assistant, working within a single conversation session, could not always retain full awareness of which components had been updated and which retained legacy code patterns.

### 2.3 Strategies for Effective AI Collaboration

Several practices emerged as essential for productive development:

1. **Comprehensive Documentation**: The `replit.md` file serves as persistent memory across conversation sessions, recording architectural decisions, known issues, and user preferences.

2. **Regression Testing**: Reference searches (e.g., ensuring that "arma virum" returns expected matches from Ovid and Quintilian) prevent regressions during refactoring.

3. **Incremental Development**: Rather than specifying complete feature sets upfront, the most productive approach involved implementing minimal versions, testing them, and iterating based on observed behavior.

4. **Explicit Domain Knowledge Transfer**: When the PI recognized domain-specific issues (like v/u normalization), documenting these as explicit rules in the codebase proved more reliable than expecting the AI to internalize the principle.

## 3. Platform Architecture

### 3.1 Technical Stack

- **Backend**: Python 3.11 with Flask, PostgreSQL database
- **Frontend**: React with Vite build system, Tailwind CSS
- **Text Processing**: CLTK (Classical Language Toolkit) for Latin/Greek lemmatization, NLTK for English
- **Semantic Similarity**: sentence-transformers with SPhilBERTa (Latin-Greek cross-lingual) and MiniLM (English)
- **Deployment**: Replit Reserved VM (production), with documentation for university server deployment

### 3.2 Search Index Architecture

The platform maintains a pre-built inverted index mapping lemmas to their occurrences across the corpus:

- **Latin**: ~528,000 lines indexed
- **Greek**: ~201,000 lines indexed  
- **English**: ~62,000 lines indexed

This architecture enables sub-second search across the entire corpus, compared to minutes or hours for naive sequential search.

### 3.3 Feature Types

**Lexical Features**:
- Lemma matching (reducing inflected forms to dictionary headwords)
- Exact token matching
- Edit distance (fuzzy matching for variant spellings)

**Phonetic Features**:
- Sound-based matching using phonetic encoding
- Useful for identifying alliterative or assonant echoes

**Metrical Features**:
- Pre-computed scansions from the Musisque Deoque (MQDQ) database
- Pattern matching for dactylic hexameter (the meter of epic poetry)
- Identification of lines sharing identical metrical patterns

**Semantic Features** (available in full-featured deployment):
- Embedding-based similarity using transformer models
- Cross-lingual matching between Latin and Greek
- Identification of conceptually similar passages beyond shared vocabulary

*Note: Semantic features require sentence-transformers, which is disabled in the constrained Replit deployment but can be enabled on university servers with greater resources.*

## 4. Case Study: Multi-Feature Analysis Reveals Lucan's Echo of Vergil

### 4.1 The Parallel

The power of multi-feature analysis becomes apparent in cases where lexical evidence alone is ambiguous but additional features converge to suggest intentional allusion. Consider the following parallel, identified through Tesserae V6 and saved to the intertext repository.

This parallel was surfaced through a lemma-based search of Vergil's *Aeneid* against Lucan's *Bellum Civile*, with results ranked by the V3 scoring algorithm (combining IDF weighting with distance penalties). While its modest Tesserae score (1.0) reflects the limited vocabulary overlap, the platform's integrated metrical display revealed the striking rhythmic identity that elevates this match from coincidence to compelling allusion:

**Source: Vergil, *Aeneid* 1.2**
> *Italiam, fato profugus, Laviniaque venit*  
> "To Italy, an exile by fate, he came to Lavinian shores"

**Target: Lucan, *Bellum Civile* 2.701**
> *Italiam. Vix fata sinunt: nam murmure vasto*  
> "Italy. The fates scarcely permit: for with a vast murmur"

### 4.2 Lexical Analysis

The lexical overlap is modest:
- **Italiam/Italiam**: The proper noun "Italy" appears in the same case (accusative) at the same metrical position (line opening)
- **fato/fata**: The noun "fatum" (fate) appears in different cases (ablative singular vs. nominative plural)

By purely lexical measures, this parallel might rank below many others with more extensive vocabulary overlap. A search returning hundreds of results might bury this match among more superficially obvious candidates.

### 4.3 Metrical Analysis

When we examine the metrical structure, however, a striking pattern emerges. Both lines scan identically:

| Foot | 1 | 2 | 3 | 4 | 5 | 6 |
|------|---|---|---|---|---|---|
| Pattern | D | S | D | S | D | X |
| Vergil | –∪∪ | –– | –∪∪ | –– | –∪∪ | –× |
| Lucan | –∪∪ | –– | –∪∪ | –– | –∪∪ | –× |

The scansion pattern **DSDS** (Dactyl-Spondee-Dactyl-Spondee) with the invariant fifth-foot dactyl is identical in both lines:

`–∪∪–––∪∪–––∪∪–×`

In dactylic hexameter, poets have significant flexibility in choosing between dactyls (–∪∪) and spondees (––) for the first four feet. The probability of two lines sharing the same pattern by chance is not negligible for any single pair, but when combined with lexical overlap, thematic relevance, and the known literary relationship between Lucan and Vergil, the convergence becomes significant.

### 4.4 Interpretive Significance

Lucan's *Bellum Civile* is, among other things, a systematic anti-*Aeneid*. Where Vergil's epic celebrates the founding of Rome through divine providence and heroic endurance, Lucan depicts the Republic's self-destruction through civil war. The opening of the *Aeneid* establishes "fate" (fatum) as the governing principle of Aeneas's journey to Italy. Lucan's echo inverts this: the fates (*fata*, plural—perhaps fragmented, indeterminate) "scarcely permit" (*vix sinunt*) rather than ordaining.

The metrical identity reinforces this reading. By reproducing Vergil's rhythm exactly while inverting his meaning, Lucan creates what might be called a "metrical palimpsest"—the new text written over, but not quite erasing, the old. A reader attuned to Vergilian rhythm would feel the echo before consciously identifying the verbal parallels.

### 4.5 Implications for Computational Intertextuality

This case demonstrates why multi-feature analysis matters. A purely lexical search might rank this parallel low due to its modest vocabulary overlap. A purely metrical search would identify many false positives—lines that share rhythm accidentally. But the convergence of multiple features:

- Shared vocabulary (*Italiam*, *fatum/fata*)
- Identical metrical pattern (DSDS)
- Thematically charged terms (fate, Italy)
- Known literary relationship (Lucan as Vergilian interlocutor)

...creates a stronger cumulative case than any single feature could provide. Tesserae V6's architecture makes it possible to weight these features and surface parallels that might otherwise require serendipitous close reading to discover.

## 5. Feature Examples and Search Modes

Beyond the core phrase-matching functionality inherited from earlier Tesserae versions, V6 introduces several new search modes and scoring enhancements designed to surface different types of intertextual relationships.

### 5.1 Corpus-Wide Line Search

Traditional Tesserae searches compare two specific texts (source and target), returning parallel phrases ranked by shared vocabulary. While powerful, this approach requires researchers to have prior hypotheses about which texts might be related.

The new **Line Search** feature inverts this model: given a single line or phrase, the system searches the entire corpus for potential parallels. This enables exploratory research where the scope of an author's reading or influence is unknown.

**Implementation**: Line search leverages the pre-built inverted index to achieve sub-second response times across 800,000+ indexed lines. For each query line, the system:

1. Extracts and lemmatizes content words
2. Retrieves all corpus lines containing matching lemmas via index lookup
3. Scores matches using the V3 algorithm
4. Returns ranked results with match highlighting

**Example**: [PLACEHOLDER: Add example of a line search query and notable results, demonstrating discovery of an unexpected parallel]

### 5.2 Cross-Lingual Search

A distinctive feature of classical intertextuality is the dialogue between Greek and Latin literature. Roman poets engaged deeply with Greek predecessors—Vergil with Homer, Horace with Pindar, Seneca with Euripides—yet purely lexical matching cannot bridge the language barrier.

Tesserae V6 revives and extends **cross-lingual search** capabilities using semantic embeddings from the SPhilBERTa model, trained specifically on classical languages. This approach:

1. Encodes passages as dense vectors in a shared semantic space
2. Identifies Greek-Latin pairs with high cosine similarity
3. Enables discovery of conceptual parallels that share no vocabulary

**Example**: [PLACEHOLDER: Add example of Greek-Latin parallel discovered through semantic matching, showing how the system identifies conceptual correspondence across languages]

*Note: Cross-lingual semantic search requires sentence-transformers and is available in full-featured deployments. The constrained Replit deployment pre-computes embeddings but does not support real-time semantic queries.*

### 5.3 Rare Word Pairs Search

Common words (like *sum*, *qui*, *in*) appear frequently enough that their co-occurrence provides weak evidence for allusion. Conversely, when two texts share an unusual word combination, the probability of coincidence decreases substantially.

The **Rare Word Pairs** search identifies passages sharing bigrams (two-word combinations) that are statistically uncommon across the corpus. This feature required building a comprehensive bigram frequency index:

- **Latin**: ~4.2 million unique bigrams indexed
- **Greek**: ~2.3 million unique bigrams indexed
- **English**: ~213,000 unique bigrams indexed

**Scoring**: Pairs are ranked by inverse corpus frequency—the rarer the shared bigram, the higher the score. A configurable threshold filters out common combinations.

**Example**: [PLACEHOLDER: Add example showing a rare word pair match, demonstrating how uncommon vocabulary combinations signal deliberate allusion]

### 5.4 Scoring Boosts and Feature Weights

The base V3 scoring algorithm can be augmented with optional **boosts** that reward specific features. These allow researchers to tune searches toward particular types of intertextual relationships:

**Bigram Frequency Boost**: Increases scores for matches containing rare word pairs. This surfaces parallels where the shared vocabulary, though perhaps limited, consists of unusual combinations unlikely to occur by chance.

**Sound Similarity Boost**: Rewards phonetic correspondence between matched passages. Useful for identifying alliterative or assonant echoes where poets replicate sound patterns rather than exact words.

**Metrical Similarity Boost**: Increases scores when matched lines share identical or similar metrical patterns. As demonstrated in the Vergil-Lucan case study (Section 4), rhythmic identity can transform a modest lexical match into compelling evidence of allusion.

**Feature Weight Configuration**: [PLACEHOLDER: Add details on how users can configure feature weights through the interface, with examples of weight combinations suited to different research questions]

### 5.5 Additional Search Modes

**String Search**: Pattern-based search supporting wildcards and boolean operators. Useful for finding specific phrases, morphological patterns, or textual variants across the corpus.

**Rare Words Explorer**: Identifies hapax legomena (words appearing only once) and other low-frequency vocabulary. Displays sortable lists with dictionary definitions and corpus distribution, exportable to CSV for further analysis.

**Hapax Search**: Specifically targets shared rare words between texts—vocabulary that appears infrequently in the corpus but is shared between source and target, suggesting possible direct engagement.

## 6. Validation and Benchmark Testing

### 6.1 The Challenge of Ground Truth

Evaluating intertextual detection systems poses methodological challenges. Unlike tasks with objective correct answers (e.g., named entity recognition), intertextual parallels exist on a spectrum from certain quotation to possible echo to coincidental similarity. Scholars may reasonably disagree about whether a given parallel reflects authorial intention.

### 6.2 Benchmark Development

To enable systematic evaluation, we are developing benchmark sets consisting of:

1. **Confirmed Parallels**: Intertexts identified and discussed in scholarly literature, representing consensus cases of allusion. These serve as positive examples the system should reliably surface.

2. **Rejected Candidates**: Superficially similar passages that scholars have argued do *not* represent meaningful intertextuality. These test the system's ability to avoid false positives.

3. **Disputed Cases**: Parallels where scholarly opinion is divided. These probe the boundaries of computational detection and may reveal which features correlate with human judgments of significance.

### 6.3 Feature Combination Testing

A key research question is how different feature combinations affect precision and recall:

- Does adding metrical similarity to lexical matching reduce false positives without sacrificing true parallels?
- Which feature weights best approximate expert scholarly judgment?
- Do certain feature combinations perform better for specific author pairs or literary periods?

Systematic testing against benchmark sets will enable evidence-based recommendations for feature configuration, moving beyond intuition toward empirically grounded best practices.

### 6.4 Planned Benchmark Sets

[PLACEHOLDER: List specific benchmark sets under development, e.g.:]

- Vergil-Lucan parallels from [scholarly source]
- Homer-Vergil parallels from [scholarly source]
- Seneca-Euripides parallels from [scholarly source]
- [Additional benchmark sets]

## 7. Deployment Architecture

### 5.1 Replit Production Environment

The platform is deployed on Replit's Reserved VM infrastructure (1 vCPU, 4GB RAM) at https://tesserae-v-6.replit.app. This deployment required several optimizations:

**Lazy Loading**: Heavy NLP models load after server startup rather than during import, avoiding startup timeouts.

**CPU-Only PyTorch**: Reduced from 7.6GB (GPU version) to ~1.5GB to fit deployment limits.

**Pre-computed Resources**: Lemma lookup tables, metrical scansions, and semantic embeddings are pre-computed rather than generated on demand.

### 5.2 Scalable Deployment

For institutional deployment with greater resources, the platform can restore full features:

- sentence-transformers for semantic search
- CLTK for enhanced lemmatization and metrical scanning
- Additional computational resources for real-time embedding generation

Documentation in `docs/DEPLOYMENT_GUIDE.md` provides step-by-step instructions for both constrained (Replit) and full-featured (university server) deployments.

## 8. Future Directions

### 8.1 Additional Feature Dimensions

Planned enhancements include:

- **Syntactic matching**: Using Universal Dependencies treebanks to identify parallel grammatical structures
- **Named entity analysis**: Tracking shared references to persons, places, and mythological figures
- **Weighted feature scoring**: User-configurable weights for different feature types based on research questions

### 8.2 Corpus Expansion

The current corpus of ~2,100 texts focuses on canonical Latin, Greek, and English literature. Future expansion may include:

- Medieval Latin texts
- Patristic Greek
- Renaissance neo-Latin
- Modern reception texts

### 8.3 Collaborative Scholarship

The intertext repository feature allows researchers to save, annotate, and share discovered parallels. Integration with ORCID identifiers enables attribution, potentially creating a crowdsourced database of validated intertextual relationships.

## 9. Conclusion

Tesserae V6 demonstrates both the capabilities and limitations of AI-assisted development in digital humanities. The collaboration between domain expert and AI coder produced a sophisticated platform that would have been beyond either party's individual capacity—the PI lacking programming skills, the AI lacking deep understanding of classical intertextuality. At the same time, characteristic failure modes (context window limitations, framework migration issues, domain knowledge gaps) required new practices for documentation, testing, and knowledge transfer.

The platform itself advances computational intertextuality by incorporating multiple feature dimensions. As the case study demonstrates, parallels that appear modest by purely lexical measures may reveal themselves as significant when metrical, phonetic, or semantic evidence converges. This multi-feature approach better reflects how literary allusion actually works: poets echo their predecessors through rhythm, sound, and concept, not merely vocabulary.

The methodology and platform described here may serve as a model for future AI-assisted development in specialized academic domains, where deep domain expertise must be combined with technical implementation capacity that researchers may not personally possess.

---

## Appendix A: Parallel Details from Repository

**Intertext ID**: 3  
**Submitted**: 2026-01-25  
**Status**: Pending review

| Field | Source | Target |
|-------|--------|--------|
| Author | Vergil | Lucan |
| Work | Aeneid | Bellum Civile |
| Reference | 1.2 | 2.701 |
| Text | Italiam, fato profugus, Laviniaque venit | Italiam. Vix fata sinunt: nam murmure vasto |
| Language | Latin | Latin |
| Matched Lemmas | fatum, Italia | fatum, Italia |
| Metrical Pattern | DSDS | DSDS |
| Scansion | –∪∪–––∪∪–––∪∪–× | –∪∪–––∪∪–––∪∪–× |
| Tesserae Score | 1.0 | — |

---

## Appendix B: Technical Specifications

### B.1 Search Algorithm

The V3-style scoring algorithm combines:
- Inverse Document Frequency (IDF) weighting for matched lemmas
- Distance penalty for words separated within phrases
- Optional bigram frequency boost for rare word pairs

### B.2 Metrical Pattern Notation

| Symbol | Meaning |
|--------|---------|
| D | Dactyl (–∪∪): one long syllable followed by two short |
| S | Spondee (––): two long syllables |
| – | Long syllable |
| ∪ | Short syllable |
| × | Anceps (final syllable, either long or short) |

### B.3 Data Sources

- **Corpus texts**: Tesserae Project legacy corpus, supplemented with new ingestions
- **Lemmatization**: CLTK Latin/Greek models, NLTK for English, UD treebank lookup tables
- **Metrical scansions**: Musisque Deoque (MQDQ) / Pede Certo database
- **Semantic embeddings**: SPhilBERTa (Latin-Greek), all-MiniLM-L6-v2 (English)
