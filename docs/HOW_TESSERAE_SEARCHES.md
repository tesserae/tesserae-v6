# How Tesserae Searches: A Guide to the V6 Pipeline

*For humanities scholars, collaborators, and anyone who wants to understand what happens between clicking "Search" and seeing results.*

---

## 1. The Texts

Every text in Tesserae is stored as a plain-text file in `.tess` format. Each line pairs a canonical reference tag with the text of that line:

> `<vergil.aeneid.1.1>` Arma virumque cano Troiae qui primus ab oris

The tag identifies the author, work, book, and line number. The text after it is exactly what appears in the standard edition.

The Tesserae corpus contains over 2,100 texts in Latin, Greek, and English, drawn from canonical editions of classical literary works. The Latin collection alone includes 1,429 texts spanning 528,000 lines of poetry and prose, from Ennius to late antiquity. The Greek collection covers 659 texts. A small English collection (14 texts) supports cross-language research.

---

## 2. Preparing Texts for Search

Before any searching happens, Tesserae processes every text into a form that computers can compare systematically. This involves two steps: tokenization and lemmatization.

### Tokenization

Tokenization splits each line into individual words and normalizes spelling conventions that vary across editions but carry no literary significance.

For Latin, this means converting `j` to `i` and `v` to `u` — so *juvenis* becomes *iuuenis* — since the distinction between these letters is a modern editorial convention, not an ancient one. All punctuation is removed and everything is lowercased.

For Greek, the system strips accent marks and breathing marks while preserving the base characters. Accents vary between editions and are often ambiguous in transmission, so removing them prevents false misses. Final sigma is normalized to standard sigma.

After tokenization, the Aeneid's opening line becomes seven separate tokens: *arma*, *uirumque*, *cano*, *troiae*, *qui*, *primus*, *ab*, *oris*.

### Lemmatization

Lemmatization reduces each inflected word form to its dictionary headword. This is essential for a highly inflected language like Latin, where *armis* (ablative plural), *armorum* (genitive plural), and *arma* (nominative plural) are all forms of the same word. Without lemmatization, the system would treat these as unrelated terms and miss obvious connections.

Tesserae uses a two-tier lemmatization system. The primary method draws on lookup tables derived from Universal Dependencies treebanks — curated linguistic databases that map inflected forms to their headwords. The Latin table contains 61,711 mappings; the Greek table approximately 58,000. When a word isn't found in the lookup table, the system falls back to the CLTK (Classical Language Toolkit) lemmatizer, which uses statistical models trained on classical texts.

The system also handles Latin enclitics — suffixes like *-que* ("and"), *-ne* (question marker), and *-ue* ("or") that are written as part of the preceding word. When *uirumque* doesn't appear in the lookup table as a whole, the system strips *-que* and successfully lemmatizes *uirum* to *uir* ("man").

### A Concrete Example

Here is what happens to a single line as it passes through preparation:

| Stage | Content |
|-------|---------|
| **Raw text** | Arma virumque cano, Troiae qui primus ab oris |
| **Tokenized** | arma uirumque cano troiae qui primus ab oris |
| **Lemmatized** | arma uir cano troia qui primus ab os |

The lemmatized form is what most search channels work with. The word *virumque* has become two pieces of information: the lemma *uir* and the enclitic *-que*. The proper noun *Troiae* (genitive of *Troia*) has been reduced to its base form. Even *oris* ("shores," from *os/ora*) is resolved to its headword.

### The Unit of Comparison

Each line of poetry is the basic searchable unit. When the system compares Lucan's *Bellum Civile* Book 1 against Vergil's *Aeneid*, it examines every possible pairing of a Lucan line with an Aeneid line — hundreds of thousands of comparisons, performed in seconds thanks to pre-computed indexes.

But poets don't always confine their allusions to a single line. A sentence often spans two or more lines (enjambment), splitting the allusive vocabulary across a line break. To catch these cases, the system also creates **sliding windows**: each consecutive pair of lines (line 1 + line 2, line 2 + line 3, and so on) is combined into a single two-line unit with the tokens and lemmas of both lines merged. From 695 lines of Lucan Book 1, this produces 694 additional two-line windows, each of which is searched on the same terms as a single line.

---

## 3. Pre-computed Resources

Several large resources are built once and reused across all searches. These represent months of computational work that would be impractical to repeat for every query.

**The inverted index** is the backbone of fast searching. For every lemma in every text, it records which lines contain that lemma and where. When you search for lines sharing the lemma *arma*, the system doesn't scan through half a million lines of Latin — it looks up *arma* in the index and instantly retrieves every line where it appears. The full Latin index is approximately 2.4 gigabytes.

**Semantic embeddings** capture the meaning of each line as a mathematical fingerprint. A neural language model called SPhilBERTa — trained specifically on Latin and Greek texts — reads each line and encodes it as a sequence of 768 numbers. Lines that express similar ideas receive similar fingerprints, even when they share no vocabulary at all. These embeddings are pre-computed for the entire Latin corpus and stored for instant retrieval (approximately 2 gigabytes).

**Syntax parses** record the grammatical structure of each line — which word is the subject, which is the verb, which nouns are in genitive chains, and so on. A state-of-the-art Latin parser called LatinPipe has analyzed 542,000 lines of Latin poetry, producing dependency trees that let the system compare sentence structures rather than just words. These parses are stored in a database (approximately 1.6 gigabytes).

**The synonym database** contains 23,833 curated Latin word pairs drawn from the Tesserae V3 project — pairs like *gladius/ensis* ("sword"), *mare/pontus* ("sea"), and *mens/animus* ("mind/spirit") that any Latinist would recognize as synonyms. When a later poet substitutes a synonym for a word in his model, this database allows the system to detect the connection.

**Metrical scansion** records the pattern of long and short syllables for 146,000 lines of Latin hexameter poetry. While metrical similarity alone is not a reliable indicator of allusion (roughly a quarter of hexameter line-pairs score above 0.70 by chance), metrical information serves as a useful supplementary signal in the scoring process.

---

## 4. What Happens When You Search

When a scholar selects a source text (say, Lucan's *Bellum Civile* Book 1) and a target text (Vergil's *Aeneid*) and clicks "Search," the system performs five operations:

1. **Load and prepare** both texts — tokens and lemmas are ready from the pre-processing stage.
2. **Run nine independent search channels**, each looking for a different kind of similarity between line pairs.
3. **Combine** the results from all nine channels into a single list (fusion).
4. **Score and rank** the combined results so that the most likely genuine parallels appear first.
5. **Present** the ranked list to the scholar, with matched words highlighted and channel information displayed.

The entire process — comparing 695 source lines against 9,896 target lines across nine channels — typically completes in under a minute.

---

## 5. The Nine Search Channels

The core innovation of Tesserae V6 is that it doesn't rely on a single method for detecting parallels. Instead, nine independent channels each look for a different kind of textual similarity. Think of them as nine different experts examining the same pair of passages, each with a different specialty.

### Shared Vocabulary (Lemma, 2-word threshold)

This is the classic Tesserae approach, inherited from the original system: find line pairs that share two or more content-word lemmas. If Lucan and Vergil both use forms of *arma* and *uir* in their respective lines, the lemma channel flags the pair.

This channel is the workhorse of the system. It catches the most common type of allusion — direct verbal echo — and has been the basis of Tesserae since its first version. However, requiring two shared words means it misses allusions built around a single distinctive term, and it cannot detect echoes that use different vocabulary entirely.

### Single Shared Word (Lemma, 1-word threshold)

The same method as above, but requiring only one shared lemma instead of two. This catches allusions built around a single pivotal word. The most famous example: Lucan's *Bella... canimus* ("Wars... we sing," *Bellum Civile* 1.2) echoing Vergil's *Arma... cano* ("Arms... I sing," *Aeneid* 1.1), linked by the single shared lemma *cano* ("to sing"). Over half of the parallels missed by two-word matching share exactly one rare content word.

Because single-word matches are more numerous and less precise, this channel receives a lower weight in the final scoring.

### Exact Wording

This channel looks for lines sharing two or more identical surface forms — the actual word as written, not reduced to a lemma. It catches cases of verbatim quotation or near-verbatim borrowing, where the later poet reproduces not just the same word but the same inflected form.

### Semantic Similarity (AI Embeddings)

This channel uses neural language processing to detect conceptually similar lines even when they share no vocabulary at all. The SPhilBERTa model, trained on a large corpus of Latin and Greek, reads each line and computes a mathematical representation of its meaning. Lines expressing similar ideas — a city under siege, a hero's grief, a storm at sea — receive similar representations.

For example, Lucan 1.491 (describing panic and flight from a city) and Vergil, *Aeneid* 2.796 (gathering crowds in an urban crisis) share no lemmas whatsoever, but the embedding model detects their thematic kinship with a similarity score of 0.787.

This channel opens a window onto allusions that are purely conceptual — the kind a literary scholar recognizes instantly but that no word-matching system can detect.

### Synonym Substitution (Dictionary)

Ancient poets often practiced *uariatio* — deliberately substituting a synonym for a word in their model to demonstrate creative transformation. Lucan might write *mentes* where Vergil wrote *animos*, or *pontus* where the original had *mare*.

This channel draws on 23,833 curated synonym pairs to detect these substitutions. When two lines share two or more pairs of recognized synonyms, the channel flags the connection.

### Sound Patterns

Some allusions work through phonetic echo — the later poet recreates not the words but the sounds of the original passage. This channel measures the similarity of sound patterns between lines by comparing sequences of three consecutive characters (trigrams). A line heavy with *tr-*, *-rum*, *-arm-* sounds will score highly against another line with similar phonetic texture.

This is one of the highest-precision channels: when it fires, the result is often a genuine parallel. But it only catches a small fraction of the total.

### Fuzzy Word Matching (Edit Distance)

Sometimes a poet echoes not the same word but a morphologically related one — *ferrea* ("of iron," adjective) echoing *ferratos* ("iron-clad," participle), or *belligeri* ("war-bearing") recalling *belli* ("of war"). These pairs share a root but have different dictionary headwords, so lemma matching misses them entirely.

This channel computes character-level similarity between words, measuring how many insertions, deletions, or substitutions would be needed to transform one into the other. Words that are at least 60% similar are counted as fuzzy matches.

### Sentence Structure (Syntax)

Two passages may echo each other not through shared vocabulary but through parallel grammatical construction — both using genitive-noun chains, both placing a verb between two accusative objects, both building a list of ablative absolutes. The syntax channel compares the grammatical dependency patterns of lines, as analyzed by the LatinPipe parser, to detect these structural parallels.

For example, Lucan 1.588 (listing methods of divination) and Vergil, *Aeneid* 3.361 (listing omens) share a distinctive genitive-noun chain structure. Neither lexical matching nor sound similarity detects this connection, but the syntax channel recognizes the parallel construction.

A second path within the syntax channel — **structural fingerprint matching** — goes further: it matches lines with identical dependency head patterns even when they share no vocabulary at all. This catches the most challenging type of allusion: structural imitation with complete lexical substitution. For example, Vergil's *corrupitque lacus, infecit pabula tabo* ("it tainted the pools, infected the pastures with corruption") and Lucretius's *vastavitque vias, exhausit civibus urbem* ("it devastated the streets, drained the city of citizens") share zero words but have identical grammatical structure. The structural fingerprint detects this; a follow-up semantic similarity check then confirms the thematic connection, and fusion combines both signals.

### Rare Vocabulary

Some allusions are signaled by the shared use of an uncommon word — a term that appears in fewer than 100 texts across the entire corpus. When two lines share such a rare lemma, the connection is unlikely to be coincidental. The word *quercus* ("oak"), for instance, is distinctive enough that finding it in both Lucan 1.136 and Vergil, *Aeneid* 9.681 is meaningful evidence of a deliberate echo.

Because proper nouns (personal names, place names) are often rare in the corpus but may not signal genuine allusion, the rare word search offers an option to exclude them. The system identifies proper nouns using both a capitalization-based heuristic and a curated gazetteer of over 1,500 Greek and Latin names compiled from Wikidata mythological entities, the Pleiades gazetteer of ancient places, and manual curation of major epic figures and Olympian deities.

---

## 6. Combining the Channels (Fusion)

Each channel produces its own list of candidate parallels with its own scores. The fusion step combines these nine lists into a single ranked result through three layers of scoring.

### Weighted score fusion

The system uses **weighted score fusion**: each channel's score is multiplied by a weight reflecting how precise that channel has proven to be, and the weighted scores are added together. Channels that produce fewer but more reliable results receive higher weights. Sound similarity (weight 4.0) and edit distance (weight 2.0), for example, receive strong weights because when they detect a match, it is very likely to be a genuine parallel. The single-word lemma channel, which casts a wider net, receives a lower weight (0.3).

### Convergence bonus

On top of the weighted sum, the system adds a **convergence bonus** that rewards pairs found independently by multiple channels. If six out of nine channels all flag the same pair of lines, that agreement is strong evidence of a real connection — stronger than any single channel's score alone.

The convergence bonus is modulated by word rarity: it is weighted by the minimum word IDF (inverse document frequency) in the pair, squared. This means that a pair whose weakest word has IDF 0.3 (a common word) gets only 9% of the full convergence bonus, while a pair where all words have IDF above 1.0 gets the full bonus. This prevents common words from accumulating undeserved convergence credit simply because they appear in enough texts for multiple channels to detect them.

### Rarity scoring

The fused score is then scaled by a **rarity multiplier** based on the geometric mean corpus IDF of the matched words. Common-word pairs receive a steep penalty (the multiplier is squared, so a pair with multiplier 0.3 is reduced to 9% of its base score), while rare-word pairs are preserved at full strength or receive a modest boost. This graduated curve ensures that results are ranked not just by how many channels agree but by how meaningful the shared vocabulary is.

### Function-word handling

A critical refinement is the use of a **curated function-word stoplist** (91 Latin words, 202 Greek, 220 English; the English list is the Snowball stopword list plus the same words in their Early Modern forms, sources in docs/DECISIONS.md) to distinguish function words from content words in the scoring layer. Pure frequency cannot make this distinction: the word *tum* ("then") and the word *pectore* ("in the breast") both appear in many texts, but only the first is a function word. The stoplist provides the precision that frequency alone cannot.

Three cases are handled:

- **All function words** (e.g., sharing only *tum* + *inde*): heavy penalty and convergence zeroed — this is grammatical co-occurrence, not allusion.
- **Mixed** (e.g., *nec* + *priorem*): the match is treated as effectively a single-content-word match, since the function word contributes no allusion signal.
- **All content words** (e.g., *pectore* + *curas*): no function-word penalty — only the graduated IDF curve applies.

Importantly, individual channels run *without* stoplist filtering, so they cast the widest possible net. The stoplist is applied only in the scoring layer, where it shapes the ranking without reducing recall.

### The result

The result is a single ranked list in which the most likely genuine parallels rise to the top. A pair sharing rare content words and confirmed by six channels will dramatically outrank a pair sharing common function words found by the same number of channels — which is exactly the behavior a scholar would want.

---

## 7. Catching Allusions Across Line Breaks

A persistent challenge for any line-based system is enjambment: a poet's sentence often spans two or more verse lines, and the allusive vocabulary may be split across the break. Vergil might place *arma* at the end of one line and *uirum* at the beginning of the next. A system that examines only individual lines would see two weak signals instead of one strong one.

Tesserae addresses this with **two-line sliding windows**. Each consecutive pair of lines is merged into a single unit and searched through the lexical channels (lemma, single-lemma, rare word) and the dictionary channel, using the same scoring as single lines. The window spanning lines 5 and 6 combines the tokens and lemmas of both, so any allusive vocabulary split across the break is reunited. Sub-lexical and semantic channels are excluded from the window pass because they compare individual token pairs already exhaustively enumerated in the line pass — expanding the unit does not introduce new comparisons.

The results from line-mode and window-mode are then merged carefully. Line-mode results take priority, and a window result is included only if it covers at least one source-target line pair not already present. This ensures that the sliding window adds recall (finding more parallels) without diluting precision (the quality of the top-ranked results).

Across five evaluation benchmarks, the sliding window raises overall recall from 85% to 93%, recovering dozens of enjambed allusions that line-only search misses.

---

## 8. Scoring and Ranking

Within each channel, individual results are scored using a formula that rewards rare, distinctive vocabulary and penalizes common words.

**Inverse document frequency (IDF)** is the key principle: a word that appears in many texts across the corpus contributes less to the score than a word that appears in few. Sharing the word *et* ("and") between two lines is nearly meaningless — it appears everywhere. Sharing *quercus* ("oak") is noteworthy. The IDF formula quantifies this intuition, assigning each matched lemma a weight proportional to how unusual it is.

**Distance** also matters: matched words that appear close together within their respective lines score higher than matched words at opposite ends. If both *arma* and *uir* appear in the first three words of each line, that tight clustering strengthens the signal.

**Curated stoplists** provide a layer of precision that pure frequency cannot. IDF alone treats all common words the same — but the word *tum* ("then") and the word *pectore* ("in the breast") have similar corpus frequencies while carrying very different allusion potential. The system uses a curated list of 91 Latin function words (pronouns, conjunctions, prepositions, auxiliaries), plus corresponding lists for Greek (202 words) and English (220 words: the Snowball stopword list plus the same words in their Early Modern forms; sources in docs/DECISIONS.md), to cleanly identify function words in the fusion scoring layer. Matches built entirely on function words are heavily penalized; matches where a function word co-occurs with a content word are scored on the content word alone. Critically, the stoplist is applied only during scoring, not during channel matching — so no potential match is missed, only downranked.

The practical result: on the Valerius Flaccus benchmark, 9 of the top 10 results are genuine commentary-attested parallels, and on the Lucan benchmark, 5 of the top 10 are genuine — a level of precision that makes browsing from the top of the list a productive scholarly activity.

---

## 9. What You See

The search results appear as a ranked list of parallel passages, sorted from most confident to least.

Each result displays the source passage and the target passage side by side, with matching words highlighted. The overall score reflects the weighted fusion across all channels, and the display indicates which channels found the pair — allowing the scholar to see at a glance whether a parallel rests on shared vocabulary, phonetic echo, semantic similarity, or some combination.

The scholar can browse the list from top to bottom, examining the highest-confidence results first, or filter by individual channels to explore specific types of similarity. Two modes are available:

- **Ranked fusion** (the default) presents a carefully ordered list optimized for browsing. The top results are overwhelmingly genuine parallels, and quality degrades gradually as you move down the list.
- **Maximum-recall mode** uses sentence-level units instead of lines, sacrificing unified ranking for the broadest possible coverage. This mode finds up to 98% of known parallels and is intended for exhaustive research where missing a connection is costlier than reviewing more results.

---

## 10. How Well It Works

The system has been evaluated against five benchmark datasets drawn from published commentaries — collections of parallels that scholars have identified through traditional close reading. These benchmarks cover 862 parallel passages across five text pairs, ranging from Lucan's relationship with Vergil to Statius's debts to Ovid.

**Tesserae V6 finds 783 of these 862 parallels — a recall rate of 90.8%.** Two benchmarks reach 100% and 92% respectively. On the Valerius Flaccus benchmark, 9 of the first 10 results are attested in the scholarly commentary.

To put this in perspective: the original Tesserae V3 system, using lemma matching alone, found approximately 27% of the same parallels. The improvement comes not from any single technique but from the combination of nine complementary channels, each catching allusions that the others miss:

| System | Recall | Method |
|--------|--------|--------|
| Tesserae V3 (2012) | ~27% | Lemma matching only |
| V6, lemma only | 35% | Improved lemma tables |
| V6, 9-channel fusion | 83% | Nine channels combined |
| V6, fusion + sliding window | **91%** | Adding two-line windows |

The approximately 9% of parallels that remain unfound are predominantly thematic or conceptual — passages connected by shared ideas rather than shared language, sound, or structure. Detecting these represents the frontier of computational intertext study, likely requiring advances in AI reading comprehension beyond current technology.

What the system *does* find is the vast majority of the verbal, phonetic, structural, and semantic connections that scholars have catalogued over centuries of commentary tradition — and it finds them in seconds rather than years, across any pair of texts in a 2,100-work corpus.
