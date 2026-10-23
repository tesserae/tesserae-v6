# Decisions

Method and scoring decisions that change what the site returns, with the
measurement behind each and where to find the data. One entry per decision,
newest first. Working notes and evaluation folders are kept outside this
repository; this file is the record a later reader can find. Operational
history (index builds, cache rebuilds, corpus changes) is in
`DATA_OPERATIONS.md`; per-release changes are in `../CHANGELOG.md`.


## 2026-10-23: machine translation only on request, one passage at a time, labeled, and measured first

A visitor asked at the talk of 2026-10-23 why the site does not supply machine translations for every work without a public-domain or openly licensed human translation (Latin 444 of 1,837 works have one, Greek 457 of 1,335, Persian 3 of 28, Urdu 0 of 18). Decision: no whole-work machine translations in the Translation tab. Pre-modern poetry and elliptical prose are where the free model fails, and a wrong rendering shown like a human translation discredits the human ones. Instead, a Reader button that translates one passage on request with the free campus model, shown in a distinct style with the label "machine translation, unreviewed", cached, never offered where a human translation exists, and excluded from data releases, following the 2026-10-07 rule for commentary notes. Before it is built, the model is measured against held human translations by language and by poetry or prose, and Help states the measured result. If it is bad for a language, Help says so rather than the button hiding it.

## 2026-10-23: the Shahnameh gets its stories and Warner's public-domain translation

A visitor at the talk said a free English Shahnameh exists online. The complete public-domain translation is A. G. and E. Warner (nine volumes, 1905 to 1925, prose); Zimmern (1883) and Atkinson (1832) are abridged retellings that cannot be aligned, and Davis (2006) is in copyright wherever it appears. Decision: re-import the Shahnameh with its story divisions (the current file is one run of 99,218 hemistichs), then align Warner story by story with the proportional prose aligner, credited on every passage, public domain first as the standing translation policy says.

## 2026-10-21: an event passage's participant name is set aside when a model reads it as a different person at every place it occurs

Decided by the project lead, 2026-10-21, after the Battle of Actium listed Marcus Agrippa for Suetonius's "Agrippam nepotem" (Agrippa Postumus) and Tacitus's "Haterium Agrippam". A rule on neighboring words (nepos, rex, filius and the like) was measured first and rejected: of 75 participant names beside such a word across all events, nearly all were right ("Sennacherib rex Assyriorum"). The free gateway model reads up to three lines holding each participant's name in a passage and answers YES, NO or UNSURE, and a name is set aside only when every line is NO, so a passage that names both Agrippas keeps the admiral. The card shows what was set aside and the model's reason.

## 2026-10-20: an event's place is shown under the name an English-language classical scholar would use

Decided by the project lead, 2026-10-20, after a rule that ranked Pleiades names by attested period gave Eusebeia for Caesarea, Agrigento for Agrigentum and Nequinum for Narnia. The candidates are the geographic Pleiades names of the place in Latin, English, Ancient Greek or no stated language that are written in Latin letters, each listed with its attested periods and with no requirement that a period overlaps the event. The free BullsAI gateway model is asked once per event, with the event, its year, the modern place name and the candidates, which one an English-language classical scholar would use for the place in that year, and answers with one candidate or NONE, which leaves the column empty. A short table of hand overrides, each with its reason in `scripts/events/choose_place_names.py`, is applied after the model for places where the data are wrong, and the project lead grades a sample of 60 events before any install. After the lead found 8 of 60 sampled headings wrong, most of them Greek transliterations where English writes the Latin form (Kaphyai for Caphyae), the event's English title decides the spelling when it differs from the chosen name only by transliteration and is the more Latinized of the two, and Delos, Shechem and the Malian Gulf were added to the English forms.

## 2026-10-20: Attic inscriptions are linked to places, peoples and gods by Attic rules, and not to persons

Decided by the project lead, 2026-10-20. The generic document matcher read about half of its rows for the Attic Inscriptions wrongly (Apollonios as the place Apollonia, demotics as persons, the archon as Diotima). The Attic matcher reads a demotic as its deme, a god's name only from a table of dedication forms, an archon date as the year's archon, a month as a month, and a father's name as unlinked, and it links no person, because nearly every name is a private citizen and no rule can tell which individual of the store it is. On 100 rows drawn at random (seed 20) 95 were right, 3 wrong and 2 unclear when graded by the delegate, against the bar of 90.

## 2026-10-20: Attic Inscriptions Online added to the inscriptions collection, shown by edition number

Attic Inscriptions Online (AIO) was added with the permission of its chief editor and its technical consultant, who confirmed that its Greek texts are its own editions and not taken from PHI, so the PHI terms do not apply to them. Each inscription is shown under the edition number AIO's own page gives (IG II2 18), never the AIO number, as the editor asked, and where AIO's heading is its own number or its UK-collections series the first Inscriptiones Graecae or SEG reference on the page is used. For the translations that have no Greek of AIO's, the Greek text of the Berlin Inscriptiones Graecae digital edition (Creative Commons Attribution 4.0, checked in each file) is paired with AIO's translation, and the credit line names both.

## 2026-10-20: a place's page lists the lines that name it only by an adjective

The Latin corpus never names some places by their own name (Livy writes agrum Rusellanum and Rusellani, never Rusellae), and the store keeps such adjectives as separate corpus-name entities apart from the Pleiades place, as the decision of 2026-10-19 on Rome and the Romans requires. The project lead decided that the adjectives stay their own corpus names and that the place's page lists them and their lines under the heading "Named by its adjective", with nothing merged in the store. The link table leaves out Gordianus (the emperor, not Gordion) and Phradates (a Persian name, not Phra), and for Tusculanum it leaves out the 10 rows (9 lines) where the form stands within two words before disputatio, because Cicero's Tusculanae disputationes is a book title and not the place.

## 2026-10-20: the Events article ratings are made with Claude

The Events page rates each linked journal article YES, PARTLY or NO for its event. The project lead decided on 2026-10-20 to make those ratings with Claude Sonnet through the paid Anthropic API, after Claude caught articles rated YES that cite a different passage, which neither two stricter wordings nor the larger free gateway model did. The no-recurring-costs rule holds because the ratings are made offline when the article lists are relinked, never while a visitor waits, and a relink adds only a handful of new links. The full run on 2026-10-20 cost about $36. The same day the project lead added that every paid run needs his approval first, so the script's default is the free gateway model and a Claude run must name the approval it rests on.

## 2026-10-19: the core bundle returns with whole-corpus files rebuilt without the restricted works

The core bundle of 14 October was withdrawn because it held the Sahidica New Testament, and leaving the works' own files out would not have been enough, because the Coptic word index, the bigram table, the lemma frequencies and the list of translation pairs hold their lines and counts inside them. The project lead decided on 2026-10-19 that each such file is replaced in the bundle by a filtered copy, and that the builder refuses to run if a whole-language file of a language with restricted works is taken as it is. The Sahidic Old Testament (`sahidic.*`) is not on the registry and stays in, as do the other 153 Coptic texts. The rebuilt bundle is dated 19 October, and the measurements are in `DATA_OPERATIONS.md`.
## 2026-10-19: ten more data sets offered for download, each with its license and its exclusions

The project lead approved offering every data set that the audit of 2026-10-19 recommended (the Urdu index, the People & Places store, the events store, coins, museum objects, dictionaries, the Latin lemma tables, citation indexes without sentences, text descriptions and a filtered window-text archive). The delegate that built the archives set the exclusions below, and the project lead can widen or narrow any of them. Each archive carries a LICENSE.txt naming its license, sources and required credit, and a README.txt. The license position of each, in one line:

- Urdu index. CC BY-SA 4.0 (Urdu Wikisource transcriptions of public-domain poets). The four Iqbal collections are left out because their source dataset has no license file.
- People & Places store. CC BY-SA 4.0 (the share-alike of EDH governs the whole), with Pleiades (CC BY 3.0) and Wikidata (CC0) credited. The live store held windows of Coptic, Hebrew, Persian and Urdu works as well, among them 752 windows of the Sahidica New Testament. The public copy keeps Latin, Greek and English windows only, which removes 62,291 windows, 116,714 mention rows and the 2,986 entities that were mentioned only there.
- Events store. CC BY-SA 4.0 (Wikidata CC0, Wikipedia summaries CC BY-SA 4.0, EDH CC BY-SA 4.0, EDR and I.Sicily CC BY 4.0, papyri.info CC BY 3.0). The tables `judgements` and `requests` are model working logs and are left out.
- Coins. ODbL 1.0 for the eight nomisma catalogs (94,263 types) and CC BY-NC-SA 3.0, non-commercial, for the 11,913 Corpus Nummorum types in a separate file.
- Museum objects. CC0 for Cleveland, Chicago records and the Smithsonian, CC BY 4.0 for Chicago descriptions. Image addresses stay, image files are not offered.
- Dictionaries. CC BY 4.0 for the Tesserae V3 and V6 files and the review pairs, CC BY-SA for the files drawn from Perseus and the Coptic loanword sources, stated file by file. The Coptic WordNet file and every Hebrew file are left out (the Hebrew files derive from CATSS or BHSA).
- Latin lemma tables. CC BY-NC-SA 4.0, non-commercial, because the Perseus and PROIEL treebanks that feed the table carry that license and the table does not record which treebank gave each form.
- Citation indexes. Bibliographic facts and citations to the corpus, offered under CC BY 4.0. The `sentence` column, which holds publisher text, is emptied in every row.
- Text descriptions. CC BY 4.0, written by language models. The Arabic entries, the Sahidica entries and four Urdu Iqbal entries are left out.
- Window texts. The license of each work, and non-commercial as a whole because the file holds the Hebrew Bible. The file is rebuilt without the 25 Sahidica works (1,800 windows), the Arabic works, the Persian works and eleven Iqbal collections. This closes the item that has been open since 2026-10-11.

Two things are not offered. Arabic stays out in every form, because it is held back from the site and its sources have no recorded terms. The sentences of journal articles stay out, because the Early Journal Content terms and the Project MUSE library agreement cover processing and do not cover redistribution.
## 2026-10-19: the gutter and the connection map use a work's prose windows when it has no fine windows

The Reader's connection gutter and the connection map were built from fine-scale windows only. Since 2026-10-11 a long prose work is cut into paragraph-sized windows, and a work imported after that date has no described fine windows, so it had an empty gutter and no entry in the map. The coverage check after the De legibus install found this on 2026-10-19, and a count over the live index gave 37 such works (De legibus, 22 parts of Cassius Dio, 7 of Diodorus, Appian's Foreign Wars 1, the preface of Augustine's De trinitate and others). The project lead decided that both fall back to the prose windows where a work has no fine windows, and that a work with both scales keeps its fine windows, so nothing changes for the works already in the map. The gutter marks of a prose-only work therefore sit beside paragraph-sized spans, the shape the Reader already shows for its windows. The alternative, describing and indexing the fine windows of those works as well, was not taken, because the prose cutter was adopted precisely so that long prose is not read in line-sized pieces.

## 2026-10-19: every page of People, Places & Things is listed in both views

The menu had listed only the pages whose collections were on, so the Literature view showed People & Places alone with a note that inscriptions, coins and objects appear when their collections are switched on. The project lead asked why the selection should be smaller under Literature when the menu is there anyway ("Why not put everything in the Literature one as well?"). From 2026-10-19 the menu lists all five pages in every view and every profile. The collection switches keep their other effects, what a search covers and which Reader tabs show. The one gate left on the menu is the server switch for the documents collection, which hides Inscriptions & Papyri when no documents index is installed. The client-side trial flag for the documents pages no longer gates the menu.
## 2026-10-19: Help is organized around how a visitor meets the site

The project lead approved on 2026-10-19 the reorganization proposed by that day's audit of the Help pages. The side list has six groups. Start here holds the opening section, the two views, the Collections and Beta marks section, and the measured performance. Searching the literature holds the phrase search sections (how it works, match types, settings, stoplists, reading the results) with Search One Text, Theme Search and Cross-Language Search. Reading holds the Reader and Tessa. People, Places & Things holds the five pages of that menu. Languages holds the language sections. Reference & tools holds the remaining reference sections. Getting Started and The Types of Search are merged into Start here, which is now the section Help opens on, and Understanding Results and Reading the results are merged into one section. Upload Your Text, which was 295 lines mostly of formatter form, has its own page at /upload-help, and Help keeps a two-sentence stub under the old id. The three ids that no longer exist (getting-started, search-modes, reading-results) are kept as aliases that open the section each merged into, so every earlier link and Help button still works.

## 2026-10-19: which pages keep a Beta mark

A Beta mark on a page in the top row means the page is new and still changing, so a scholar should not yet cite from it. The project lead reviewed the five marks on 2026-10-19. Coins and Objects lose theirs. Both pages present the coin types (OCRE and CRRO) and the museum objects (the museums' own catalog descriptions) as their sources publish them, nothing on them is the site's own inference, and together they have had five small changes since they appeared. Search One Text keeps its mark as the most changed page on the site (45 change-log entries since 2026-10-12). Inscriptions & Papyri keeps it until the Latin documents index, built on 2026-10-08 before the Latin lemma corrections, is rebuilt. (Added the same evening: that rebuild had already been installed at 00:20 on 2026-10-19, so the mark came off that night.) Events keeps it because the document and scholarship tightenings of 2026-10-18 and the relevance verdicts of 2026-10-19 have not yet been read on the page.

## 2026-10-19: the pages about what the texts refer to sit under one menu, and a returning visitor opens where they left off

The project lead decided on 2026-10-19 that the five pages about what the texts refer to (People & Places, Events, Inscriptions & Papyri, Coins, Objects) are grouped under one menu in the top row labeled "People, Places & Things". The label is his wording, chosen over "Index" and "The Ancient World", and over "named entities", which he rejected as jargon. The literary pages (Search One Text, Intertextual Search, Read, Theme Search, Browse Corpus) stay as direct tabs, because a menu puts a page one click deeper. The menu shows the same label in every profile, even when People & Places is its only member. A returning visitor opens the site where they left off. The last page and address are kept in the browser only and never sent to the server, and only a bare visit to the site address restores them.

## 2026-10-19: People & Places goes live for everyone on the repaired store

The project lead decided on 2026-10-19 that People & Places goes live for everyone once the repaired entity store is installed, and the `?entities=1` trial gate comes off. The repair carves names that two people or places share into separate entries, then merges back the carves that split one referent in two, by a stem rule (18 merges) and a model question (51 merges). The lead read the 69 merges and kept 55. Figures from the stage 4 report: the 180 fixed pairs hold at 90 of 101 kept pairs right, the stage 1d fresh 40 hold at 33 of 40 strict and 38 of 40 lenient, the new list mentions are right in 25 of 37, and the share of splits read as wrong fell from 11 of 47 to 3 of 30 on fresh samples. Rome and the Romans stay two entries (the decision below). A name shared by two people or places can still be grouped wrongly, and the Help section says so and points to the Suggest a change button. The connector tools stay off until `TESSERAE_ENTITY_TOOLS=1`.

## 2026-10-19: People & Places keeps Rome and the Romans as two entries

The repaired entity store carves the Greek Ῥωμαῖοι and the Latin Romani into a Romans entry (a people, 14,584 lines) beside Rome (a place, 4,771 lines). The project lead decided on 2026-10-19 that they stay separate, since one is a people and one a place, and a query for Rome returns both. The merge pass of 2026-10-19 (pass 4d) leaves that carve alone.

## 2026-10-19: the Sahidica New Testament leaves the public Coptic index download

The Sahidica files (J. Warren Wells's edition, 27 works in the live Coptic index) carry a license for academic use only and no redistribution. They stay searchable on the site. The project lead decided on 2026-10-19 that the downloadable Coptic index archive is rebuilt without them, and that the downloads page says so and points readers to Coptic Scriptorium for the text.

## 2026-10-19: the judged Greek-Latin harvest loads through the review table under one source name

Decided by the project lead. Set A, the 13,831 Greek-Latin pairs that both gateway models (Qwen3.8-27B and gpt-oss-120b) accepted out of 22,144 judged, is loaded into the live dictionary through the `dictionary_review` table with status `accepted` and the source name `harvest_2026-10-19_set_a`. The app already reads accepted rows of that table at start, so no code in the search path changes, and `scripts/dictionary/load_review_entries.py --unload harvest_2026-10-19_set_a --apply` removes the whole set in one step. Pairs the project lead excludes after a hand audit of about 80 rows are left out through an exclusion file. The 5,876 pairs on which the models disagreed stay out until the project lead's verdict on a 200-row sample.

Measurement. The Knauer benchmark is no longer a test of the dictionary, because 500 candidates were harvested from its misses (a control run scored 170 against 171 at baseline). The independent test is the Juhnke set, which scored 43.1 percent at baseline and 44.6 percent with set A, against 16.3 percent for chance. Figures are from the judging report and the Knauer re-measure report of 2026-10-18, kept outside this repository.

## 2026-10-18: a strong mark follows the order of the list

Theme Search and Search One Text order their results by the reader model (the trained second judge, `services/reader_server.py`, since 2026-09-20), and mark a result strong from the index score against the work's confidence band (2026-10-12). The two signals disagreed: the Hamlet soliloquy stood at place six with a strong mark below five unmarked results. Decided (the project lead asked why a strong result stood below unmarked ones, 2026-10-18): the band still decides how many results are strong, and the marks go to the head of the reader's order, so a reader sees the badges where the list is strongest. A strong mark is therefore a statement about the list as ordered, not about one passage's index score. Code `backend/reader_rerank.apply`, tests in `tests/test_reader_rerank.py`.

## 2026-10-18: the Latin lemma table takes a corrections file and a fill from the corpus parse

The live Latin lemmatizer is the lookup table `data/lemma_tables/latin_lemmas.json` alone (111,739 forms, one lemma per form). The production interpreter has no CLTK fallback, so a form the table lacks keeps its own spelling as its lemma. An audit of 2026-10-18 counted 345,693 distinct forms in the Latin index that the table lacks, carrying 1,737,977 tokens (7.91 percent of Latin tokens). The enclitic rule already lemmatizes 241,481 of those tokens, which leaves 6.8 percent of Latin tokens with their own spelling as lemma. The audit also named four faults in the table itself. `facies` maps to the verb `facio` on 14 treebank readings against 11 for the noun, where the parse of the whole corpus reads the noun 1,127 times and the verb 722. `modo` maps to `modus` and is a true homograph with the adverb. `actia` (with `actiaque`, through the enclitic rule) and `distrahor` are absent. Two entries are plain errors. `c`, the abbreviation (6,590 tokens), maps to `que`, and `actius` maps to `ago`. The table is a patchwork of four sources with no recorded counts, so it cannot be regenerated and a change has to be an overlay.

The decision has two parts. The first part is that `data/lemma_tables/latin_corrections.json` is read after the table by one loader, `backend/lemma_tables.py`, which the lemmatizer, the index builder, the hapax and fusion paths, the lemma expander, the prose describer and the cache manifest all call, so every reader sees one table. The manifest also hashes the corrections file, so a cache built without it reports stale. The file holds 76,391 forms. Five are hand corrections (`c`, `actius`, `facies`, `actia`, `distrahor`). 2,774 are assimilated-prefix spellings (`inpendere` beside `impendere` is the pattern) whose other spelling the table knows, each mapped to the lemma the table gives that spelling. 73,612 are forms absent from the table whose LatinPipe lemma for the corpus is a table lemma. `data/lemma_tables/latin_corrections_provenance.csv` gives the source and the evidence of every form, so each row can be rebuilt.

The quality rule for the fill keeps a form when the parser lemma differs from the form and either the form occurs once in the parse or the lemma holds at least 80 percent of the form's parser readings. Of 77,215 candidate forms (496,796 tokens) the rule keeps 74,031 (459,917 tokens). Exclusions then remove five forms the audit's reading marked wrong, 132 forms whose parser lemma is on the Latin stoplist and which are not inflections of that word (OCR damage and run-together words), four forms found wrong on a second seeded reading, and 14 forms of the three parser lemmas behind those errors. A last reading by the maintainer, after the pull request review pointed at `acceperimus` mapped to `acco`, dropped 263 more forms (856 tokens): every filled form whose first two letters differ from its lemma's, except 72 read as right (`caetera`, `dandus`, `eatur`, `sies`, `optulerunt`, the assimilated spellings the parse resolved to the standard lemma), and every form under a parser lemma that is not a Latin word (`acco`, `icio`, `aeo`, `assuo`, `iuo`, `uero` and the one- and two-letter fragments). Two readings of 200 forms each checked the result. The audit's reading found 193 right, 6 wrong and 1 unjudged. The second reading, of the forms that survived the rule, found 196 right and 4 wrong. Each is one reader's judgment and neither is a measured truth, and about 400 of the 74,000 forms were read.

Two things stay out. A second lemma per form for homographs such as `modo` and `bonum` (the existing `variant_lemmas` slot) is held for a later trial under a stricter rule. Second lemmas for the 4,267 forms with a minority parser reading would give 3.2 percent more pairs of lines sharing two lemmas in a random sample, mostly through common words (`tantus`, `modo`, `multus`, `solus`), and some are parser artifacts. The second is refused. Parser lemmas the table does not know (119,833 forms, 468,929 tokens) stay out. The parser agrees with itself on 90.0 percent of the readings of those forms, against 96.7 percent for the forms of the fill, and many of the lemmas are invented singulars (`foederum`, `discriminum`, `munium`) or errors (`interfo`, `praecorus`, `decosceo`).

The change was measured in staging against the production files before any swap, on the 76,654-form file before the maintainer's last reading (the 263 forms dropped afterwards carry 856 of the 501,995 changed tokens, 0.17 percent). 236,324 of 967,935 cache lines and 501,995 of 22,128,881 tokens (2.27 percent) get another lemma, and the distinct lemmas of the Latin index fall from 327,498 to 248,013. The five Latin benchmarks find 752 of 862 gold entries, against 747. Lucan 1 against the Aeneid is unchanged at 176 of 213. Achilleid against the Thebaid keeps its 47 of 52 but loses 5.8 points of recall at rank 1,000 (40.4 to 34.6). Traced: the three entries (Achilleid 1.79 against Thebaid 3.178, 1.81 against 5.179 and 9.254) stood at ranks 976, 977 and 979 and stand at 1,009, 1,010 and 1,026 with the same channels, the same matched words and scores changed in the third decimal, because the list grew by 382 pairs from the filled forms and some of them score higher. Nothing is lost at rank 5,000. The reference searches for "arma virum" return the same results (372 lemma, 31 exact). The three pairs the audit asked about (Actia and Actiaque, `facies` and `faciem`, `distractus` and `distrahor`) go from no shared lemma to one, so only the single-lemma channel can return them and the default two-lemma channel still cannot. Ten random lines with a filled form gained matches that share a real second word in 59 of 60 cases read, and one line lost 368 false matches that came from `facies` read as `facio`. The cost of that choice is that `facies` as the future of `facio` is now read as the noun everywhere. Nothing is live until the data stores are rebuilt and swapped on production. The measurement folder is kept outside this repository.

Decided by the project lead on 2026-10-18 on the lead's recommendation.

## 2026-10-17: the Greek-Latin pivot dictionary through LSJ and Lewis and Short is parked

A second Greek-Latin dictionary, 26,859 pairs built in May 2026 by pivoting LSJ glosses against Lewis and Short glosses, has lived only in the development checkout and never served the site. Measured on 2026-10-16 on one configuration, with and without it: recall of Knauer's Aeneid 1 parallels at 10, 50 and 100 moved from 23.8, 41.5 and 51.2 percent to 24.3, 43.0 and 52.7 (six more of 412 gold lines at 50), recall on the 2,397 Juhnke line entries moved under a point (59.6 to 60.4 at 50), precision at 50 against the Knauer gold from 0.950 to 0.983 percent, and the share of dictionary matches resting on common words from 44.3 to 41.7 percent. A model judge read a random 200 pairs of the file and called 120 wrong, 72 right and 8 partial. The file cannot be regenerated exactly, because the stoplist used in May was not recorded; the rewritten filter (`evaluation/scripts/finalize_lsj_pivot.py`, #981) reproduces 122,714 of its 122,782 candidate pairs and adds 2,710. Decision, on the owner's word of 2026-10-17: the file is parked. It is removed from the development checkout so that development and production score alike, the finalizer stays in the repository as the record of the method, and every benchmark quotes the production dictionary's figures. If it is revived, the route is the finalizer plus a frequency floor on the Latin side plus a sample read by a classicist, never the May file.

## 2026-10-16: the Hebrew-to-Greek route through the Septuagint is the default, chosen per search, with a server switch (record of the 2026-08-27 and 2026-09-30 decisions)

A Hebrew query against a Greek text has two routes. The direct route compares Hebrew and Greek lines through the Hebrew-Greek dictionary and the translated-run check. The Septuagint route searches the Greek target against the Greek Bible, which the monolingual Greek search does well, and maps each Septuagint verse back to its Hebrew verse through a routing table and a verse map. The table routes a book only where the correspondence is trustworthy, encodes the Psalms' verse offset, and refuses Jeremiah, the merged Esdras and Ecclesiastes. Every routed result keeps the Septuagint verse visible beside the Hebrew it answers for. Measured on the 22 formula-marked citations of Isaiah in Romans, Isaiah's 1,290 verses against Romans' 432, the direct route found 0 at 10, 0 at 100, 1 at 1,000 and 4 at 5,000, the direct route with the translated-run check 1, 4, 7 and 7, and the Septuagint route through the live site 9, 15, 20 and 22 (the build record's own end-to-end row, 8 at 10 and 15 at 100). The route went live on 2026-08-27. On 2026-09-30, at a Hebrew reader's request, the route became a choice on every Hebrew-Greek search. The default is the Septuagint route. A reader can ask for the direct route, or for both, in which case each result is labeled with the route that found it. The choice sits in the cross-language controls, the connector parameter and the help page. A server setting turns the routed search off for the whole site, so that a wrong verse map can be withdrawn without a deploy, and the direct route then answers alone. The 2026-10-01 Greek rebuild (the Septuagint lemma table and the two text corrections) changed the Greek side after the figures above were taken, and the rerun is pending in the private record.

## 2026-10-16: the Greek New Testament is carried under Creative Commons Attribution 4.0

The SBL Greek New Testament (ed. Michael W. Holmes) entered the corpus on 2026-08-21 under the terms of its original end user agreement, which allowed free redistribution with attribution and forbade a Greek-English diglot without a separate license. The publishers released version 1.1 of the public text on 19 December 2022 under Creative Commons Attribution 4.0, and the license page at sblgnt.com now carries that license. Checked 2026-10-16 against the public repository and the license page. The site's credit and the notice beside the text files (`texts/grc/SBLGNT_LICENSE.txt`) now name CC BY 4.0 and keep the attribution statement the publishers ask for. The change matters for the Reader, which shows the public-domain World English Bible beside the Greek text for all 27 books since 2026-08-28. Under the earlier agreement that display sat close to the diglot restriction. Under CC BY 4.0 it is permitted. The Hebrew-to-Greek articles cite the New Testament as the far side of the Septuagint pivot, and this entry is the license record they refer to.

## 2026-10-16: the Juhnke cross-language gold keeps three of his four grades and caps line entries at ten lines

Juhnke's indexes of Homeric parallels in the Thebaid, the Achilleid and the Punica grade each entry on a four-step scale. A passage in square brackets without cf. is one he judges most probably or certainly not a correspondence, so those entries leave the gold and are kept in a separate file for the record. The three other grades stay, with the grade as a column so recall is always reported per grade. The line benchmark holds entries whose Latin and Homeric ranges are each ten lines or fewer. Every Latin line of a range is queried, and the entry counts as found when any of its lines brings up any line of the Homeric range, which is how a reader checks a short parallel. Entries with a longer range on either side are scene-level correspondences and form a separate set for the passage tools. Ranking only the first line of a range had let long ranges score far above chance for no merit of the search.

## 2026-10-16: a year after a name is not a locus, and a blank line ends a locus

The citation recognizer reads "Quint. 1989, 37" as book 1989, line 37 and "Livy iii. 33. 1.", a blank line, then a footnote "3" as one locus 3.33.1.3. Two rules now apply to every work. A first level that is a four-digit year from 1500 to 2030, joined to the next level by a comma, is not a locus. A blank line between two levels ends the locus. Together they removed 35 of 2,082 citations on a 2,000-article sample, nearly all glued footnote numbers (I read the first ten, and one of them, "Ath. 134, blank line, D", may have been a real Stephanus reference). A bare author name (Livy, Thucydides) followed by one word that is shaped like a Roman numeral ("Livy did", "Thucydides, I am") is not a citation unless the numeral is Arabic or has two or more capital letters. A work listed whole and in parts now resolves to the whole work when every tied candidate is that work or one of its parts. "Liv." and "Plin. Nat." could never resolve before. Bare "Plin." stays unresolved because Pliny the Elder and the Younger both match.

## 2026-10-15: Rare Words leaves the corpus-occurrence list out unless asked
- Scope: `backend/blueprints/hapax.py` (`_compute_rare_words`, `/hapax-search`), `client/src/components/search/RareResultsDisplay.jsx`, `client/src/utils/rareWordsExport.js`.
- Decision. Each Rare Words row carried `all_corpus_locations`, every place the word occurs in the corpus (up to 50 works' lines). It was 96 to 98 percent of each response (up to 303 MB for whole Iliad with Odyssey), and the page, the Claude connector and Tessa never read it. The field is now opt-in: send `include_corpus_locations: true` in the JSON body or query string. The server still computes the list first, because its proper-noun test uses it, and drops it from the rows at the end.
- How to get everything. The Rare Words page has a second download beside Export CSV, "Download everything (CSV)", which repeats the same search with the flag and writes one row per corpus occurrence. Anyone calling the API passes the flag.
- Evidence. On ten recorded pairs (Latin and Greek, parts and whole works) the response with the flag is byte-identical to the previous one, and the default response equals it minus that one field. Sizes fell from 492 KB to 5 KB (Aeneid 1 with Metamorphoses 1) and from 30.9 MB to 0.97 MB (whole Aeneid with Metamorphoses). The golden check against a fresh live recording differs only in `rare_words`, by the missing field.
- Not changed: which words are returned, their order, counts, `corpus_count`, and the other fields.

## 2026-10-14: Line Search and Wildcard search skip work that cannot change the answer, and tied Wildcard rows keep folder order
- Scope: `backend/wildcard_search.py`, `backend/blueprints/line_search.py` (the scan and the closeness count), `backend/inverted_index.py` (`lookup_lemmas`), `backend/univerbation.py` (`match_line`), `backend/metadata_cache.py` (new), `backend/utils.py` (the reading of a text's kind from its first lines).
- Decision. The first full day of request timings put Line Search second by total wait (379 requests, median 2.3 s, 90th percentile 10.7 s, slowest 85 s) and the 90th percentile of Wildcard search at 41 s. Profiled stage by stage, 80 percent of Line Search's time was in finding candidates, half of it in whole-corpus scans for exact and regular-expression searches and half in lemma searches on common words. A Wildcard search spent its time folding and testing every line of the language and looking up the title of every text. Every change leaves the answer alone. A file is folded once and only the lines holding a match of a term the query requires are tested, line by line, as before. A match that crosses a line break marks every line it touches. Stored positions are read only for lines with enough of the query's lemmas. The smallest gap between two position lists comes from the merged order. Metadata is remembered together with the modification stamps of the text and of the two metadata files, so a replaced text or an edited file is read again. Wildcard rows are built after the sort and only for the rows returned.
- One rule changes. Wildcard rows with an equal sort key (year, author, reference) came back in the order the eight scan threads finished, which differed between rows of one answer and between runs. The files are now scanned one after another, so tied rows come back in the folder's order. The recorded check compares a Wildcard answer with the order inside runs of equal keys ignored (`tie order`) and counts a run cut by the result cap as `tie cutoff` when it has the same key and size. Every other field must be equal. Of 60 recorded answers, 34 differ in tie order only, 6 in the cut run only, and 20 are identical.
- Evidence. The 258 recorded Line Search requests are identical on the branch (258 of 258). The golden check against the 12 October recording is identical except for the languages list, whose English cross-language hold depends on a data folder the preview does not have. The reference search for "arma virum" returns Vergil, Ovid, Quintilian and Seneca as required. New tests hold each shortcut to the plain way on input built to be awkward. Timings are in the CHANGELOG entry.
- Not changed: scoring, filtering, ordering by era, year and author, result caps and the corpus. Left: Greek exact-phrase search puts the whole text in NFC form (10 s), regular-expression search tests every line (7 s), and the documentary collection's search in `documents.py` was outside this work.

## 2026-10-14: Theme Search keeps work it has already done, and nothing it keeps can change an answer
- Scope: `backend/reader_rerank.py`, `backend/passage_index.py` (`embed_query`, `_lexical_boost`, `find_by_text`), `backend/window_texts.py`.
- Decision. A first Theme Search spends 6.2 s of about 7.5 s in the reader's computation, so the only saving that leaves every answer unchanged is not repeating work. The reader's score is kept per (query text, window id), the encoder's vector per exact input text, the word index's rows per match string and the file's size and time, each per web worker, with limits on count and age (6 h, 1 h). A score, a vector and a row list are functions of the query and the stored window: the reader is a fixed model reading fixed text, the encoder is deterministic, the word index is read-only. A cache drops its entries when the texts file, the word index file, the reader address or the model name changes. A failed reader or encoder call is never stored. When some windows of a query are cached the reader is asked only for the rest, so a score may differ from a whole-call score in the seventh decimal (padding changes the order of arithmetic); on the 134 recorded responses, rounded to four places, nothing differed.
- Not changed: the reader's model, inputs and K (300), which are quality. Sorting passages by length with a batch of 8 in the reader is available behind environment settings, off, with the measurement (6.2 s to 4.7 s; order identical on 10 of 10 searches; int8 and bf16 were not faster or changed the order and are not offered).

## 2026-10-13: a text held twice under two names keeps the copy with the named edition, and a fragment file inside a longer one goes
- Scope: the corpus and every store built from it (indexes, passage windows, registries). Found by `scripts/corpus/scan_opening_lines.py` (#904), which compares the opening lines and four-word sequences of whole-file texts.
- Decision (the owner, 2026-10-13 22:05, on the two cases put to him): `ennodius.epigrammata` (931 lines, The Latin Library, no edition stated) shares its opening and 96 to 97 percent of its four-word sequences with `magnus_felix_ennodius.carmina_2` (932 lines, CSEL 6, Hartel 1882, through Open Greek and Latin); the named edition is kept and the other retired. `aretaeus.signorum_acutorum_morbum` (18 lines) is wholly contained in `aretaeus.curatione_acutorum_morbum` (84 lines) and is retired as a fragment of it. The rule for the next such pair: keep the copy with the named, dated edition (or the better-formed references when both are named), retire the other with an archive and a README, as on 2026-09-10 and 2026-09-19.
- Also decided in the same run, as rules for the tools: a `.tess` already renamed by a pull is not a collision for `rename_work.py`; an index rename moves only line references that carry the old work id (a file whose references are abbreviations keeps them); `rename_work_in_passage_index.py --leaf` renames one whole work id (the Libanius part files); a set of descriptions under a few thousand is encoded with the site's own encoder (`encode_with_embed_service.py`), the GPU route staying for larger runs.
- Record: `DATA_OPERATIONS.md`, 2026-10-13 "Small corpus leftovers: production run"; archive `~/tesserae-backups/retired_duplicates_2026-10-13/`.

## 2026-10-13: Tessa's facts say whether a pair's shared words are common or rare, from the index's document frequency
- Scope: the block of computed facts Tessa narrates on a results page (`backend/assistant/findings.py`, `format_for_narration`).
- Decision. Each listed pair carries its shared words labeled rare (in under 2 percent of the language's texts), uncommon (under 15 percent) or common, with the counts, and the number of works where the pairing recurs when the search provides it. The labels come from the index's `lemma_doc_freq` table, not from the IDF or frequency in a result row, because the row's figures count occurrences in the two texts compared and say nothing about the corpus (the reason #586 replaced the first version). When the page names no language, it is taken from the index that holds most of the shared lemmas.
- Evidence. The recorded check of the assistant's preparation step (211 questions, two routing modes) is identical before and after; new tests cover a rare word, a common word, the recurrence count present and absent, and the route.

## 2026-10-13: a coverage gap is a comparison with comparable works, never an absence alone
- Scope: the Daylight prototype (topics treated for one work and not for comparable works), measured on the JSTOR Early Journal Content articles (1827 to 1922).
- Decision. A topic is called a gap for a work only when its share of that work's articles falls below the share among comparable works, on counts divided by each work's total articles, for works with at least 20 articles. Comparable means the same language, the same genre (or the same era and metre), and a profile correlation of at least 0.3 after subtracting the average work's profile. An absence on its own is never reported as a gap, and every statement of a gap names the holdings it was measured on.
- Evidence. Uncentred profile correlations had a median of 0.80 between any two works, because textual criticism and book reviews dominate everywhere, so they could not tell neighbours from strangers. Centred on the average work, the median is 0.29, and 135 of 169 works with 20 or more articles keep at least one neighbour at 0.3. Gap score is (expected minus observed articles) over the square root of the expected articles, shown only where at least 3 were expected.
- Where the data is. Tables and the vocabulary are staged outside the repository (coverage, normalised coverage, neighbours, gaps).

## 2026-10-13: English has two sets of line embeddings, and the English cross-language pairs are tuned on a Milton probe set
- Scope: `backend/embeddings/en` (MiniLM, 384 dimensions) and `backend/embeddings/en_cross` (SPhilBERTa, 768), `backend/semantic_similarity.py`, `backend/blueprints/search.py` (`ENGLISH_CROSS_SETTINGS`), `evaluation/benchmarks/milton_classical_probe.json`.
- Decision, two sets. English-English search keeps the MiniLM files, so nothing changes for it (the same pair of English texts returns identical rows before and after, checked on Adonais and Lycidas). The cross-language semantic channel and its recovery step read English from `en_cross`, in the SPhilBERTa space that Latin and Greek already share. `model_name_for('en')` returns MiniLM, which is what the English files hold, and `cross_model_name_for` returns SPhilBERTa for Latin, Greek and English. The admin builders use those two functions, so a builder cannot choose a different model from the search. The two English pairs are held while `en_cross` holds no `.npy` file and lift themselves when it does.
- Why not one set. A single SPhilBERTa set would have changed English-English search: its cosines sit in a narrow high band (median 0.58 to 0.77 on three English pairs, against 0.52) and the monolingual channel's fixed floor of 0.6 would stop selecting. That choice is separate and was not made.
- The probe set. 24 widely cited borrowings of Paradise Lost from Vergil, Homer and Ovid, as references only, taken from the commentary of the Longman Annotated English Poets edition and the standard studies of Milton's use of Vergil and Homer. Every reference was read against our files. All 24 were kept. Two were fixed (item 10 starts at Paradise Lost 1.619, item 22 gains 9.13 to 19) and one is marked loose (item 9, where the silence is in the Greek only). Metric: the source (Latin or Greek) book is the source and the Paradise Lost book the target, the rank of the first result whose two lines fall inside the item's ranges (one line of slack), from the first 2000 rows. 16 items have a Latin source and 13 a Greek one.
- Before (the plain settings: two-lemma gate excludes, raw cosine). Latin-English: 1 of 16 items returned at all, recall at 10, 50, 100 of 0, 0, 1. Greek-English: 1 of 13, recall 1, 1, 1. The gate removes every pair without two dictionary hits, which an English translation of a Latin or Greek line rarely has.
- What was tried, one value at a time from the plain settings (recall at 50 Latin / Greek, items returned Latin / Greek, median rank of the returned items). Nothing moved with the gate on, except the gate itself.

| Lever | Value | Recall at 50 | Returned | Median rank |
|---|---|---|---|---|
| plain settings | | 0 / 1 | 1 / 1 | 69 / 5 |
| lemma gate | penalty | 0 / 1 | 12 / 7 | 203 / 161 |
| lemma gate | off | 0 / 1 | 12 / 7 | 204 / 147 |
| semantic_top_n | 50, 100 | 0 / 1 | 1 / 1 | 69 / 5 |
| semantic max_results | 5000, 20000 | 0 / 1 | 1 / 1 | 69 / 5 |
| recovery threshold | 0.2, 0.3, 0.5 | 0 / 1 | 1 / 1 | 69 / 4 to 5 |
| semantic weight | 0.6, 2, 3 | 0 / 1 | 1 / 1 | 69 / 5 |
| dictionary weight | 1, 3 | 0 / 1 | 1 / 1 | 69 / 5 |
| translated-run weight | 0, 6 | 0 / 1 | 1 / 1 | 69 / 2 to 5 |
| early-modern spelling folded | on | 1 / 1 | 2 / 1 | 40 / 5 |
| hubness correction (CSLS, k 10) | on | 0 / 1 | 1 / 1 | 68 / 4 |

- Combinations, built on the gate change. Gate off or penalty with pure cosine ranking (dictionary weight 0) is worse (recall at 100 of 0 or 1 of 16, median rank 414 to 730). Raising the semantic weight to 2, 3 or 5 returns the same items but lowers their ranks (median 223 to 444 against 158). Lowering the dictionary weight does the same. A bonus for mutual nearest neighbours (two lines that are each other's nearest three) did not help (recall at 100 of 3 and 2, median rank 298 to 415, worse at larger values) and was removed. The adopted combination: gate penalty, early-modern spellings folded, hubness correction with 10 neighbours, every weight and cap unchanged. Around it, top_n 50, recovery 0.3 or 0.5, run weight 0 or 6, penalty factor 0.3 or 0.7, hubness 5 or 20 change nothing or one item.
- After (adopted settings). Latin-English: 12 of 16 items returned, recall at 10, 50, 100 of 1, 1, 3, median rank of the returned items 158. Greek-English: 8 of 13 returned, recall 1, 1, 3, median rank 166. Counting missing items as beyond the list, the median rank is 245 (Latin) and 904 (Greek) out of 2000 rows. The ceiling is the encoder: for the best line pair of each item the hubness-corrected cosine ranks it in the top hundred of about 600,000 pairs in only 4 of 30 searches, and in the top 2000 in 16.
- The standard rows read plausibly at the top. Aeneid 1 against Paradise Lost 1 ranks first "exciderant animo: manet alta mente repostum" with "Can perish: for the mind and spirit remains" and has "claudentur Belli portae, Furor impius intus" with "Rais'd impious War in Heav'n". The Iliad 1 list is weaker: swords drawn, the Muse's song and the sea appear, and several rows owe their place to two dictionary words.
- What was not changed. Greek-Latin, Hebrew, Coptic and Persian-Urdu pairs read the plain values (their recorded rows are identical to the previous code's). The English dictionaries (4,552 Latin-English and 4,971 Greek-English entries) were not enlarged. Folding spellings recovers only elisions and plurals.
- Open. A fuller English dictionary, a lemmatizer fit for early-modern spelling (it turns "Bees" into "be"), and a better encoder for the cross-language step are the levers left. All are larger than this change.

## 2026-10-12: written paragraphs keep quoted words in their original script, and the transliteration is made by a table
- Scope: the Search One Text summary and Scholarship paragraph (and the
  Scholarship list in Theme Search).
- Decision. The model quotes Greek, Latin and Hebrew words in their own
  letters and is checked for it. The transliteration shown after each Greek
  or Hebrew word is made by a fixed letter table in the code (classical
  scholarly style for Greek, SBL general-purpose style for Hebrew), never by
  the model, so none can be invented. Beta code is not shown on the page. It
  is provided as a function for export controls.
- Evidence. On Herodotus 1.32.5 the paragraph read "*euzen*" for the Greek
  words of the note by How and Wells. The model had transliterated the Greek
  and wrapped it in asterisks. A reader cannot check "euzen" against the note.
- The check. After the model answers, the server looks for asterisk spans and
  for any word of the text that is the table's transliteration of a Greek or
  Hebrew word or phrase in the notes (words of three letters or fewer are
  skipped, since "to" and "he" are also English). It asks once more with the
  fault named, and strips asterisks if the second answer is still wrong. The
  answer's `script_problems` list shows how often that happens on the live
  site.
- The table lives in two languages (Python and JavaScript) and both are tested
  against one file of cases, so they cannot drift.

## 2026-10-12: Cleaning the code's shape without changing what it does
- Scope: every change meant to reorganise code (splitting the large Flask
  module into an app factory and blueprints, tests for the scoring core,
  splitting Line Search into steps, the two oversized site components) and
  not to alter an answer.
- The rule. Nothing may break, change, or go backwards because of the
  cleaning. A structural change therefore ships only with all of these:
  1. the golden check (`scripts/review/golden_api.py`) reports every request
     `same` against a recording from before the change, on a preview of the
     branch, and again on the live site after the deploy;
  2. the reference searches (`tests/search_reference_tests.md`) and the Theme
     Search probe sets (`evaluation/probe_sets/`) give the same answers;
  3. the linters pass (ruff and ESLint, pinned to the code of 2026-10-12, so
     they fail only on a new fault).
  A request whose answer is meant to change is re-recorded in the same pull
  request, and the CHANGELOG entry says which and why.
- A superseded script is moved to `scripts/superseded/` with its replacement
  named in its header, because an old build script left beside its successor
  and writing the same output file overwrites the better data without any
  error. A script that overwrites data defaults to a dry run, takes a stamped
  backup before writing, and writes to a temporary path and renames it over
  the original (`scripts/corpus/corpus_safety.py`).
- A formatter (black, prettier) is not used. It would rewrite nearly every
  file, which hides the real changes of a pull request and defeats the rule.
- The weekly reading of the code by reviewers is not scheduled. The
  development period is intensive and finite, so a read is run on demand,
  after a large change.
- Why a recorded check and not tests alone. The unit tests do not exercise the
  search over the real index. The recording does, through the same routes the
  site uses, so a refactor that shifts a score, an order or a field shows as a
  difference at once. Requests that give different answers on two runs
  (timings, cache flags) are normalised away; requests that call a language
  model or a live outside service are left out.
- First structural job under the rule: the Flask module became an application
  factory with its routes in blueprints (see the CHANGELOG entry of the same
  date). It shipped with the golden check `same` on every request a preview
  can answer, a URL map identical in paths, methods and registration order
  (in both the production mode and the development mode with the /api prefix),
  the body of every moved function identical by syntax tree, the same test
  results as main, and an import time within ten percent. The URL map and the
  function bodies are checked by two scripts kept in `scripts/review/`, so
  the next structural job can run the same proofs.
- Second job under the rule, tests only: characterization tests for the
  feature extractor, distance filter, syntax parser, metrical scanner,
  wildcard search, database helpers and the untested parts of the matcher.
  Each expected value was taken from the code as it stands and read for
  plausibility; none was corrected. The three Latin spelling folds named
  `normalize_latin` (the matcher's and the distance filter's are now one
  function; the wildcard search's keeps case and folds a final -om to -um)
  are pinned as they are in `tests/test_normalize_latin_three_ways.py`.
  Whether to unify them is a separate decision.
- Third structural job under the rule: `line_search()` became a sequence of
  named steps (see the CHANGELOG entry of 2026-10-13). A recording of 258
  Line Search requests made on a preview of main (none of them differs between
  two runs of the same server) gives the same answer on a preview of the
  branch for every one. The standard recording of 68 requests is the same too.
  The body of each of the 22 other functions and classes in the module is
  identical by syntax tree. The 56 Line Search tests and the reference
  searches pass. Ten timed requests (one word, a pair, twelve words, an exact
  scan, documents, both collections, Hebrew without points, the Persian Reader
  path, a count, a 500-row answer) have medians within 2.5 percent of main's
  over five runs each. The steps stay in the blueprint module because tests
  replace names in it, and only the reading of the parameters moved to its
  own module.
- Fourth structural job under the rule: `fuse_results()` became a sequence of
  named steps (see the CHANGELOG entry of 2026-10-13). The function is not
  reached by the API check alone (its two fusion requests are compared
  loosely), so a direct recording was made from the function itself: nine real
  searches (three Latin pairs, two Greek, one Coptic, one Persian, the first
  Latin pair again on the meter baseline and again without the passage-context
  pass) with every row of the 97 fusion calls they make, 5,123,959 rows. The
  new code gives every row identical, both by rerunning the searches and by
  replaying the recorded inputs through the function alone. The standard
  recording of 68 requests is the same, with both previews started with the
  same hash seed so the fusion requests are compared exactly. The body of each
  of the 52 other functions and classes in the module is identical by syntax
  tree. The tests give the same ten known failures as main. The loop over the
  pairs is moved as one block of 210 identical lines with no function call
  added inside it. Its constants arrive as local variables read once before
  it, as the code did. The Latin and Greek first pairs run through the
  function alone in the same time (medians 5.67 and 4.81 seconds against 5.69
  and 4.80 over five runs). One fact the recording had to allow for: the
  document frequencies are cached in the process, and which lemmas were looked
  up first changes the value cached for others (the u/v variants and the
  headword adjustment), so the same pair can score slightly differently after
  other searches in the same process. A recording therefore starts each search
  from empty caches. The behaviour is unchanged by this job and is recorded
  here for the next one.
- Fifth structural job under the rule: `_direct_crosslingual_core()` became a
  sequence of named steps (see the CHANGELOG entry of 2026-10-13). The proof
  is a recording made inside the function, because the standard recording
  holds one cross-language request and compares it loosely: ten searches (nine
  pairs and settings, plus the error the live Latin-English search raises)
  give the same rows, field for field and score for score, on the branch as
  on main, and two runs on main agree with each other. The standard recording
  of 68 requests is the same on a preview, the reference searches pass, the
  five cross-language test files pass, and the full suite fails only the
  tests that fail on main. The body of each of the 45 other functions and
  classes in the module is identical by syntax tree. The Greek-Latin and
  Latin-English calls, five runs each, have medians within 5 percent of
  main's. The fusion loop stays one block, moved whole, with no new call
  inside it.
- Sixth structural job under the rule: the streaming fusion search
  (`search_fusion_stream()` and its nested generator) became a sequence of
  named steps (see the CHANGELOG entry of 2026-10-13). The standard recording
  does not hold this route, so a recording of the stream itself was made.
  It posts fifteen requests to a preview of main (460 events in all) and reads each stream to
  the end, with the times removed and the paged result's identifier replaced
  by its presence. Two runs on main agree with each other. The branch gives
  every event of every request identical, score for score, in order. The
  requests cover the cached and the full path of the same pair, the formula
  filter at both settings, line and window modes, channels switched off,
  custom weights, the meter, a Coptic pair, a Persian pair, a paged answer
  and both error cases. A recording starts each request from the cache as the
  script found it. The standard recording of 68 requests is the same, with
  both previews started with the same hash seed. The body of each of the 34
  other functions and classes in the module is identical by syntax tree. The
  tests give the same eight known failures as main. The reference searches
  pass. Over five runs each, the uncached search took 16.06 seconds against
  16.09 on main, and the cached answer 27.4 milliseconds against 26.8, with
  the first event at 3.0 against 2.9 milliseconds (a difference of 0.6
  milliseconds on a request whose spread is 11). The loop over the search's
  events stays one block, moved whole. The generator creates the search
  slot and hands it to the steps that need it, so the release in its
  `finally` still sees it.
- Seventh structural job under the rule: `iter_fusion_search()`, the generator
  every fusion search runs, became a short body that calls named steps (see
  the CHANGELOG entry of 2026-10-13). The recorder that stores every row of
  every `fuse_results` call now also stores every event the generator yields
  (type and payload, elapsed times zeroed, heartbeats counted and not
  compared, since their number depends on timing). It covers eleven searches:
  Latin, Greek, Coptic and Persian pairs, the frequency basis set to meter,
  context confirmation off, three channels enabled, and custom channel
  weights, which this generator reads. Two runs on main agree with each other
  (11 searches, 3.16 million rows, 362 events). The branch gives every row and
  every event identical. The fifteen-request stream recording of the sixth
  job is the same, the standard 68-request recording taken from main's
  preview is the same on the branch's, the reference searches pass, the body
  of each of the 69 other functions and classes in the module is identical by
  syntax tree, and the tests fail only where main's do. The two loops over
  the channels stay whole blocks with no new call inside them. The
  replay of the largest fusion calls takes within 3 percent of main's time.
- Eighth structural job under the rule: the assistant's `_prepare()` in
  `backend/assistant/agent.py`, which runs the searches and builds the fact
  block for Tessa, became a short body that calls named steps (see the
  CHANGELOG entry of 2026-10-13). The model enters it through the routing
  judgment and the chooser, and every search goes through one transport
  function, so the recorder holds those two still with answers captured
  once from the real gateway and the real site (143 model answers, 31 distinct
  search responses, the two comparison routes answered by a fixed rule). It
  runs 211 questions with model routing on and off, 422 runs: 126 from the
  assistant test files, 40 from the graded question set, and 45 of our own
  with a short conversation where the path needs one, covering a guide
  question, a "yes" after an offer, follow-ups with a pronoun, holdings for
  one language, two languages named, comparison requests, translations of
  one work, themed, reading and nonsense questions. Three runs on main agree
  with each other once the recorder fixes the string-hash seed, because a
  set of work names is sorted by length and ties came out in hash order. The
  branch gives the same returned dictionary, progress messages and ordered
  outside calls in all 422 runs, and a deliberately altered label in three
  places made 20 runs differ. Every comment moved with its code, and a
  line-by-line comparison finds no removed line that is not present again,
  apart from the dedenting of comments and the one initialization that
  became a field default. The 19 assistant test files give 199 passed and 1
  skipped on both, the body of each of the other 48 functions and classes
  in the module is identical by syntax tree, and the full suite fails only
  where main does. The 422 runs take 20.6 seconds on the branch against 20.7
  on main (median of four).
- Rule for a bad number in a request. A parameter that must be a number and
  is not gets a 400 with a plain JSON message (`{"error": "limit must be a
  whole number"}`), through one helper, `int_param` (and `float_param`) in
  `backend/request_params.py`, never a 500 that prints Python's own error. A
  value that is absent or empty keeps its default, so every valid request
  gives the answer it gave before. Routes that already tolerated a bad value
  by falling back to a default, or that already returned their own 400, were
  left as they were.
- Rule for calls from the browser. Every call from the pages goes through the
  helper in `client/src/utils/api.js`, which checks the status, reads the
  text first, and reports a failure with the server's own `error` message
  when the body has one, else the status and a short preview of the body
  (not "Unexpected token '<'"). Pages that show the server's `error` field
  themselves receive that body as before. The admin tabs, the assistant and
  the calls that already check the status with their own message are
  moved when next touched, not in one sweep.
- Eighth and ninth structural jobs under the rule, the two largest front-end
  files (see the CHANGELOG entries of 2026-10-13). The front end gets its own
  recorded check: `client/src/test/renderRecording.test.jsx` and
  `renderRecording.appflow.test.jsx` render the result list in each of its
  modes (sorted by score and by locus, paged, chart open, corpus panel open,
  each language, streaming, loading, error and empty), the App on every
  address the router knows, and the App's search, Search Corpus and Save
  Parallel flows, with fetch answering from fixed fixtures, and snapshot the
  HTML. The snapshots were recorded on main before any file was split, and a
  split passes only if every one is identical, apart from the markup of the
  one chart that was redrawn on purpose. The check records what the code does
  today, not what it should do (it records, for example, that saving a fusion
  result from the Save Parallel dialog fails because the card's channels are
  a list and the dialog expects text).
- One way to highlight matched words. The CSV export, the result card and the
  corpus panel's instance lines each had their own function for marking
  matched words. They differ in what counts as a match, which punctuation is
  cut and which letters are folded, so the module `client/src/utils/highlight.js`
  keeps three entry points over shared pieces (the edge-punctuation strip, the
  Hebrew point strip, the word splitter), and 60 inputs recorded from the three
  old functions (`client/src/utils/__fixtures__/highlight_cases.json`) must
  come out character for character the same.
- One chart library for the public pages. The corpus panel's timeline, drawn
  by hand in D3, is redrawn as a horizontal bar chart in Chart.js, the library
  every other public chart uses. D3 stays only for the network graph and the
  admin map, which are genuine uses of it.
- The App's own pieces follow the same rule as the result list: the code is
  moved, each piece is a hook or a component with its state, and the 94
  recorded renderings must stay identical. Recharts is left for the admin
  Analytics tab until that tab's four charts have a render test.
- The corpus panel's timeline keeps its hand-drawn D3 form, in a component of
  its own. #899 redrew it as a Chart.js bar chart so that the public pages
  would use one chart library, but the bar chart lost the date axis and the
  one-dot-per-occurrence marks, so time clusters and gaps were no longer
  visible. The rule for the cleaning is that nothing a visitor sees goes
  backwards, and it outranks the one-library aim; the original drawing was
  restored the same evening. D3 therefore stays for the timeline, the network
  graph and the admin map.


## 2026-10-12: the band inside one work is refitted on eleven works, and its lowest level is a caution, not a verdict
- Scope: Search One Text (`/ask-a-work`) and any Theme Search restricted to
  one work. The corpus-wide band has its own entry below.
- The problem. The owner found three right answers labelled "a nearest
  neighbor, not a finding": Browning's sonnet 43 for "the poet counts the
  ways she loves", Ferdowsi for "Rostam fights the White Div", and Annals
  4.1 for "the rise of Sejanus". The band of 2026-10-11 read the spread of
  the work's own scores, fitted on 45 questions over three long works.
- Measurement. The same 45 plus 80 new queries over eight more works chosen
  for their lengths (Browning's Sonnets 143 windows, Sappho 320, Catullus
  953, Hafez 2,218, Ovid's Metamorphoses 2,782, the Odyssey 2,800, Livy
  4,729, Ferdowsi 23,150): five subjects each work treats, five it does not
  (three modern, two from another genre) and two nonsense strings. One
  subject was dropped on reading because its answers were wrong (Rostam and
  Sohrab). Nineteen measures of the score distribution were swept for a
  one-threshold rule, with the threshold also fitted on ten works and tested
  on the eleventh.

  | Measure | Accuracy, 140 queries | Leaving one work out |
  |---|---|---|
  | Spread of the work's scores (the 2026-10-11 rule) | 0.766 (0.738 at its shipped value) | 0.702 |
  | Best passage's lift over the median | 0.809 | 0.752 |
  | Mean lift of the top ten | 0.787 | 0.752 |
  | Coherence of the top twenty | 0.766 | 0.716 |
  | Lift divided by the spread, the interquartile range or the median deviation | 0.70 to 0.76 | 0.68 to 0.75 |
  | Best passage's lift OR coherence (the new rule) | 0.836 | 0.821 |

  The spread fails on long works, where a subject's few windows barely
  widen the distribution (0.42 on Ferdowsi, 0.50 on Ovid), and on short
  ones, where it is noisy (0.58 on Browning). Dividing a lift by the spread
  is worse still, because the spread rises with the very tail being
  measured.
- Decision. The band reads the best passage's lift over the work's median
  (moderate from 0.048, strong from 0.055, above every absent or nonsense
  subject measured, 0.0546) or the coherence of the top twenty (moderate
  from 0.925). No rule reached nine in ten across these works, so the band
  is an estimate: its lowest level is labelled "Closest passages", says
  that no passage stands far above the rest of the work so the order is
  less certain, claims nothing about absence, and the list is shown under
  every level. The per-passage strong mark (three standard deviations above
  the work's median, not under the lowest level) is unchanged. Of the three
  cases, Browning and Ferdowsi now read moderate and Sejanus reads lowest
  with its list shown and no claim of absence.
- Data: the measurement folder of 2026-10-12 (within-work refit) in the
  private backups, with the measurement and sweep scripts; the first fit's
  folder beside the pilot of 2026-10-11.

## 2026-10-12: the lowest band is "Closest passages", and its floor is refitted to the enlarged index
- Scope: Theme Search over the whole corpus (`/theme-search`), every
  language. The band within one work (Ask a Work) uses its own rule and is
  unchanged.
- The problem. The owner ran "a debate in the assembly over how the city
  should be governed", read a good list (Aristotle's Constitution of the
  Athenians, Dionysius of Halicarnassus) under the label "Low confidence",
  and said that the label was deflating. Two things were wrong. The label
  claimed a difference the evidence does not show: on 2026-10-11 the lists
  under this band on sixty historical subjects were as relevant as the
  lists under the moderate band (0.75 against 0.73, share of the top ten
  graded relevant). And the floor between this band and the moderate band
  had been fitted on 2026-10-08 against an index of 530,917 windows; the
  prose-windows run of 2026-10-11 took the index to 693,611, so every
  result opened with a paragraph saying the thresholds were provisional.
- Measurement. The 178-query probe set of 2026-10-08 (115 subjects the
  corpus holds, 63 it does not, across eight language settings), the
  original 57-query set, and the sixty historical subjects of 2026-10-11
  (graded lists), all run against the live index. The sweep of the floor:

  | Floor | 178-query set | 57-query set | Of 60 historical subjects, marked lowest (relevant lists among them) |
  |---|---|---|---|
  | 0.0738 (2026-10-08 value) | 74.7% | 66.7% | 18 (15) |
  | 0.065 | 81.5% | 80.7% | 6 (6) |
  | 0.060 | 86.0% | 77.2% | 2 (2) |
  | 0.055 | about 80% | 63.2% | 0 |

  At this index the two populations overlap. Subjects the corpus does not
  hold reach 0.0767 ("soldiers fire machine guns from trenches") and
  0.0800 ("a steam engine", 57-query set), while held subjects run down to
  0.0551 ("a revolt of slaves", seven of its top ten about the subject).
  No value separates them, so the 2026-10-08 design, which placed the floor
  above every absent subject, now costs 64 of 115 held subjects. A rule
  using coherence as well was swept and bought nothing (held subjects
  0.927, absent 0.907, too close).
- Decision. The floor moves to 0.060, the best value on the larger set and
  on the two sets together (197 of 235). The cost is named: absent subjects
  from the modern world or other cultures (a locomotive, a satellite, a
  telephone, a sextant) read moderate rather than lowest. So the moderate
  note no longer says the corpus holds the subject, only that the top
  passages stand out from the rest, though not by a wide margin. The
  strong threshold is unchanged at 0.1006, still above every absent
  subject measured.
- The label. The lowest band is "Closest passages", and its sentence says
  that no passage stands far above the rest of the corpus on this subject,
  so the order is less certain than usual. The list is shown, as since
  2026-10-11. The "provisional" paragraph is no longer printed on the page.
  It is kept in the answer as `confidence.calibration` for anyone checking
  the fit, and the fitted size is now 693,611, so it is empty today and
  will fill again only if the index drifts more than fifteen percent.
- Data: measurements and sweep in the private working folder of
  2026-10-12 (confidence refit); the probe sets in
  `evaluation/probe_sets/`; the script
  `evaluation/scripts/calibrate_confidence.py`.

## 2026-10-11: a low confidence band shows the list, and only a degenerate band hides it
- Scope: Theme Search over the whole corpus (`/theme-search`), every language
  and every kind of text. Ask a Work and the search within one work use a
  different rule (the spread of the work's own scores) and are unchanged.
- The problem. The owner searched "establishment of democracy" and was told
  the corpus did not appear to contain passages of this kind, with the list
  held behind a link. The hidden list was good: Thucydides 8.63 on the
  oligarchy at Samos, Polybius 6.4 and 6.9 on the cycle of constitutions,
  Diodorus 12.11 on the democracy at Sybaris, Xenophon's Hellenica. The band
  rests on head lift, the mean of the top ten scores above the corpus median,
  fitted on 57 queries that mixed real literary scenes with nonsense and
  absent subjects. A real subject spread across many passages does not lift
  its top ten far above the median, and a short phrase rarely does.
- Measurement. Sixty historical queries (thirty subjects in a short form and
  a sentence form) and the fifteen Ask a Work pilot questions, run corpus-wide,
  the top ten of each graded 0, 1 or 2 by the gateway model from the
  passage descriptions. A list counts as relevant when half or more of its
  top ten are graded 1 or 2.

  | Set | Marked low | Of those, relevant list | Shown | Of those, not relevant |
  |---|---|---|---|---|
  | 60 historical queries | 31 | 27 | 29 | 4 |
  | the 30 short forms | 24 | 24 | 6 | 0 |
  | the 30 sentence forms | 7 | 3 | 23 | 4 |
  | 15 pilot questions | 13 | 11 | 2 | 0 |

  Mean share of relevant passages in the top ten was 0.75 under a low band
  and 0.73 under a moderate one, so on real subjects the band carried no
  information. Short forms did better than sentences (0.82 against 0.50 in
  the low band), the opposite of what the banner's advice to write a full
  sentence assumed. Head lift and coherence were at chance as separators of
  good lists from poor ones (area under the curve 0.52). The degeneracy test
  (coherence at or above 0.995) never fired in this set, since no real
  subject reaches it.
- Decision. The list is shown whatever the band. A low band carries a
  one-line caution that the ranking is less certain than usual, without the
  claim that the corpus lacks the subject. Only a degenerate band, where
  nothing in the corpus resembles the query, holds the list behind a link and
  makes that claim, and only there is the short-query hint given. The
  per-passage weak-neighbor tag is left off under a low band, where every row
  would carry it. The response adds `confidence.degenerate`.
- What is not changed. The thresholds and the bands themselves, which still
  tell a real subject from nonsense. This measurement had no nonsense or
  absent-subject queries, so the band's value against those stands as fitted.
- Data: the queries, judgements and report are kept outside the repository.

## 2026-10-11: long prose works get paragraph-sized passage windows, and short sections are merged to the same size
- Scope: the content index behind Similar Passages, Theme Search, Ask a
  Work and the Reader's gutter, for prose works whose units (chapters,
  sections) are long. Pull requests #814 (first run) and #821 (merging and
  the full run). Poetry and short-unit prose are untouched.
- The problem in plain terms. The index is made of passage windows:
  stretches of text that each get a one-sentence description and a vector,
  and a search compares a question with those. For poetry a window is a run
  of twelve lines, a few hundred characters, about one scene or speech. For
  prose the same rule took twelve "lines" of the file, and in a prose file a
  "line" is a whole chapter or section. In Tacitus's Annals one window ran
  from 7,500 to 15,000 characters, a dozen scenes under one description. A
  question about one of those scenes matched the window only weakly, because
  its description and its vector were a blend of everything in the chapter.
  In the Ask a Work pilot the five Annals questions ranked below the
  Aeneid's (0.40 against 0.62 of the first ten directly about the subject),
  and the judge named the chapter-sized windows as the cause.
- Measurement. An audit of 3,470 works found 1,511 whose median window is
  over 3,000 characters, all but one of them prose (39,512 windows). Cutting
  them all into windows of about 1,200 characters was estimated at 274,684
  windows. The 3,000-character line for "long" is a judgement, chosen where
  a window stops being one episode.
- Decision 1, the prose scale (first run, live 2026-10-11 12:50). Long
  prose chapters are cut at sentence boundaries into windows of about 1,200
  characters, a paragraph, each with its own description and vector. The
  chapter reference is kept, with a part number. The length is a chosen
  round figure, long enough for one episode or one step of an argument and
  short enough for a single sentence to describe. First run: the Annals (746
  windows, median 874 characters), Thucydides (3,577) and the ten works with
  the longest median windows (2,115), 6,438 in all. Check after the install,
  one reader grading the descriptions against the pilot's standard: for the
  question on the death of Germanicus the directly relevant passages in the
  first ten rose from 3 to 6, and for the mutinies of the legions from 3
  to 6.
- Decision 2, what happens to the old chapter windows. They stay in the
  index, because the Reader's position marks and the coarse-grained map
  still use them. But a work that has prose windows no longer offers its
  chapter windows in rankings, neighbour lists or the names list, so a
  chapter is not offered twice, once whole and once in parts.
- Decision 3, merging short sections (the full run, staged 2026-10-11,
  install recorded in `DATA_OPERATIONS.md`). The first run never joined
  neighbouring units, so Thucydides, whose sections run 300 to 500
  characters, got one window per section: 3,577 windows too short for a
  description to say much. For the full run, consecutive short sections of
  one book are joined until the window reaches about 1,200 characters, and
  the reference runs from the first section to the last. A section longer
  than that is still cut into parts as in the first run, and a window never
  crosses from one book into the next. Thucydides comes to 1,159 windows in
  place of 3,577, and the remaining 991 long-prose works to 153,405 windows.
- Measured after the full run was installed (2026-10-11 23:49). The fifteen
  pilot questions were re-run live and the 175 passages in the new top
  twenties that had no grade were judged with the pilot's second-judge
  prompt (first judge's grades kept where they existed).

  | | Directly relevant in top ten | Relevant at all in top ten | A direct hit in the top five |
  |---|---|---|---|
  | Before (pilot) | 0.44 | 0.75 | 14 of 15 |
  | After | 0.59 | 0.80 | 15 of 15 |
  | Annals before / after | 0.40 / 0.70 | 0.68 / 0.88 | 5 / 5 |
  | Thucydides before / after | 0.30 / 0.46 | 0.64 / 0.58 | 4 / 5 |
  | Aeneid (unchanged by the run) | 0.62 / 0.60 | 0.94 / 0.94 | 5 / 5 |

  Ranking quality by nDCG at ten fell from 0.75 to 0.71 overall, mostly in
  Thucydides (0.73 to 0.60), where the merged windows are coarser than the
  single sections for two questions about one speaker's view (Pericles, and
  justice against self-interest). The figures are not on identical ideals,
  since the new grades enlarged the ideal ranking. Kept as installed.
- A smaller merge target, tested and not adopted (2026-10-12). Thucydides
  books 1 and 2 were re-cut at 600 and 800 characters and the five pilot
  questions ranked offline against the installed 1,200, every passage graded
  by the same judge: 600 beat 1,200 on every measure (directly relevant in
  the top ten 0.64 against 0.50, nDCG 0.92 against 0.84), 800 did not. The
  same comparison on Herodotus (books 1 to 3) and Diodorus (books 11 to 14),
  eight new questions, did not confirm it: 600 tied on Herodotus and lost on
  Diodorus for precision (0.26 against 0.31 overall), winning only on
  ranking order (0.85 against 0.83) and on a direct hit in the top five
  (8 of 8 against 6 of 8). One win, one tie and one loss on five to eight
  questions a work is not grounds to re-cut 284 works, nor to give one work
  a different cut from the rest. The target stays at 1,200.
- Open. The describing model writes Thucydides' speeches without the
  speaker's name, so a search for a person in Thucydides falls back to the
  text itself.

## 2026-10-11: Ask a Work pilot graded by a second, independent judge
- Scope: the figures quoted for Ask a Work (`/ask-a-work`) and for its
  confidence band and strong marks.
- Why. Every figure rested on one judge, a Sonnet model reading each
  passage's description, opening and translation. A second model from a
  different family (Qwen 3.8 27B, on the university gateway) re-graded the
  same 293 passages from the same material, with the same instructions, at
  temperature 0.
- Result. The two judges agree exactly on 69% of passages (kappa 0.54,
  quadratic 0.71) and agree on whether a passage is relevant at all on 81%.
  The second judge is stricter about passages that merely touch a subject:
  37 of the first judge's "touches it" grades become "not about it". The
  strong marks' precision for relevant passages is 0.905 under the first
  judge, 0.873 under the second, 0.857 where both agree.
- Decision. The band and the strong marks stand. The site and Help report
  the figures as a range across two judges, and the softer figure is the one
  to quote for passages that only touch a subject.

## 2026-10-11: a confidence band for a search within one work, from the spread of that work's scores, provisional
- Scope: Theme Search restricted to one work, and Ask a Work.
- Why. The corpus-wide confidence rating was fitted on scores over the whole
  index and does not carry into one work, so a restricted search had no
  rating (decision of 2026-10-09). A question that a work does not address
  at all looked the same as one it answers.
- Measurement. 45 queries over the Aeneid, Thucydides 1 to 2 and Annals 1
  to 6: the pilot's 15 real questions, 15 subjects absent from the work, 15
  nonsense strings. The spread (standard deviation) of the work's window
  scores separates real from absent best, with accuracy 0.889 and
  leave-one-work-out 0.867. Head lift, top-hit lift and coherence do as well in sample, but
  their thresholds do not carry from one work to another.
- Decision. Three bands from the spread: low below 0.0099, strong from
  0.0125 (above the largest spread any absent subject produced), moderate
  between. A passage is marked strong when its score stands 3 spreads above
  the work's median and the band is not low: 63 of 293 judged passages
  marked, precision 0.905 for relevant passages (first judge). Both are
  labelled provisional, because they were fitted and tested on the same 45
  queries over three works. On the Ask a Work page a low band does not hide
  the list, because one real question in five came out low.

## 2026-10-11: Ask a Work keeps the reader re-rank
- Scope: Ask a Work and Theme Search restricted to one work.
- Why. The reader model re-orders the top results by reading them, which
  costs two to three seconds against under one second without it. Within one
  work the gain was untested.
- Measurement. The fifteen pilot questions re-run with and without the
  reader, scored against the pilot's judgements. With it, 0.44 of the first
  ten passages are directly about the subject and 0.75 are relevant at all.
  Without it the figures are 0.41 and 0.59.
- Decision. Kept on. The time is spent on a better first page.


## 2026-10-09: Theme Search restricted to an author or work lists up to 10 passages per work, none capped for a single work, with no confidence rating
- Scope: `/api/passages/theme-search` with `author=` or `works=`, and the
  "Search within" picker on the Theme Search page.
- Decision: a restricted search is a flat list of passages. The corpus-wide
  rule of one head per work and three rows each (`PASSAGES_PER_WORK`) is
  dropped, because it exists to stop one huge work owning a page of the
  whole corpus. Several chosen works share the page at up to 10 passages
  each (`RESTRICTED_PER_WORK`). A single chosen work has no cap, because a
  cap would end paging at the cap. Confidence (head lift, coherence) is not
  rated for a restricted search, the response says so in its `note`, and no
  result is marked strong.
- Measurement: five queries in each of Vergil and Livy (Latin) and Homer and
  Thucydides (Greek), asking for 25 passages under per-work caps 3, 10, 25
  and unlimited, on the production index read-only (means over the five
  queries). Livy and Thucydides are one work each in the index.

  | Author | Cap | Passages returned (of 25) | Distinct works in top 25 | Distinct books in top 10 | Most from one book in top 10 |
  |---|---|---|---|---|---|
  | Vergil | 3 | 8 | 2.8 | 5.4 | 2.4 |
  | Vergil | 10 | 23.2 | 2.8 | 3.6 | 6.4 |
  | Vergil | unlimited | 25 | 1.4 | 3.6 | 6.4 |
  | Livy | 3 | 3 | 1 | 2.8 | 1.2 |
  | Livy | 10 | 10 | 1 | 8.2 | 2.2 |
  | Livy | unlimited | 25 | 1 | 8.2 | 2.2 |
  | Homer | 3 | 9 | 3 | 7.4 | 2 |
  | Homer | 10 | 25 | 3 | 6.4 | 3.4 |
  | Homer | unlimited | 25 | 2.2 | 6.4 | 3.4 |
  | Thucydides | 3 | 3 | 1 | 2 | 2 |
  | Thucydides | 10 | 10 | 1 | 4.8 | 4.4 |
  | Thucydides | unlimited | 25 | 1 | 4.8 | 4.4 |

- Reading: cap 3 is unusable inside an author, since a single work returns
  3 passages in all and Vergil returns 8 of 25. Cap 10 and unlimited give the
  same top ten everywhere (a cap of 10 cannot change ten rows). They differ
  deeper: with the Aeneid dominant, an unlimited list is 1.4 works out of
  3 across 25 rows, while cap 10 keeps the Georgics and Eclogues in view
  (2.8 works). The cap does not govern flooding by one book. The share of the
  top ten taken by one book is the same at 10 and unlimited (Thucydides 4.4
  of 10 from one book, Vergil 6.4), so that is a property of the ranking and
  of the query, and the picker's Work step is the remedy.
- A single work is uncapped because with cap 10, Livy ended at 10 passages and
  Show more had nothing further to fetch.
- Confidence: the head-lift and coherence thresholds were fitted on 57
  queries over the whole index. Inside one or a few works the median and the
  spread both change, so the thresholds are not comparable, and no
  restricted-query fit has been made. The figures are withheld, and the page
  and the connector say so. A rating that has not been validated is not
  shown.

## 2026-10-09: licensed scholarship is indexed for retrieval and shown as citation, excerpt and link, never summarised
- Scope: every source of secondary literature the site holds under a
  licence or a permission (journal articles, monographs, commentaries
  from publishers, libraries and aggregators, called licensors
  throughout). The Scholarship tab, Theme Search over scholarship (a
  measured prototype, see below) and the assistant all follow it.
- The rule: the full text is indexed on our own server for retrieval
  only, as embeddings and a keyword index, and is never served in bulk.
  What a reader sees for a passage is a citation (author, title, journal
  or publisher, year, page, a link to the licensor's own page) ordered by
  how closely each item bears on the passage, with at most a short
  excerpt of the sentence that made the match. No description, abstract
  or summary of an article is written or generated by the site. The
  assistant answers questions about scholarship by quoting a sentence
  with its citation and does not paraphrase an argument. Text is deleted
  at the end of the project where a licensor asks (one publisher's term,
  October 2026). Each source can be set to show no excerpt at all.
- Why: a sentence-long excerpt with a link sends a reader to the article,
  which is what the licensor's own search already does; a summary lets a
  reader cite an article without reading it, and would be the derivative
  work a licensor could object to. The site's own passage descriptions are
  prose about public-domain primary texts and are not the model here.
- Measurement behind the retrieval side (2026-10-09, 15 queries, one
  judge, 82,814 windows of 393 commentaries and 33,386 journal sentences):
  P@10 meaning-based 0.57, keyword 0.57, reciprocal-rank hybrid 0.57;
  nDCG@10 0.59, 0.52, 0.64; queries with a fully relevant hit in the top
  ten 11, 12, 13 of 15. The hybrid is the design when licensed article
  text arrives. The quarter-sample run earlier the same day gave 0.37 and
  0.43 for the two base systems, so the full index matters.
- Decided by the project lead on 2026-10-09 on the recommendation above.
- Applied 2026-10-16 to Project MUSE journals (agreement with the library covers text processing): their citations are kept in a separate database, read as a second index beside the one from before 1923, and shown as the article's citation, one sentence of at most 400 characters centered on the citation, and a DOI link. No full text and no abstract are shown. Rows whose locus is a year or that absorbed a footnote number are dropped at build time, so a reader is not sent to an article by a false citation.

## 2026-10-11: the public data bundle's terms: non-commercial as a whole, commentaries sorted by licence, three vernacular texts in
- Scope: the downloadable data bundle and the install recipe (pull request #739).
- Decisions, taken by the owner on 2026-10-11 after the four questions the draft raised.
  1. The Koine Greek and Hebrew lemma tables stay in, so the bundle is offered for non-commercial use as a whole. The cost is that a commercial user cannot take the bundle as it stands, which is a small price for an academic tool. The alternative, a second bundle without them, was not worth the complication.
  2. Texts from the Latin Library and Forum Romanum stay in. They have no stated licence, and the bundle treats them as the site's own per-language downloads already do.
  3. Commentaries are sorted by their own licence lines instead of being left out wholesale: public-domain and Creative Commons files travel, including non-commercial ones under the bundle's terms, and files with no licence or a no-republication notice stay out.
  4. Dante's Commedia, the Chanson de Roland and the Nibelungenlied go in. All three come from public-domain sources: Project Gutenberg's Commedia (#1000), the French Wikisource transcription of Bédier's edition (Bédier died 1938), and Bartsch's 1887 edition of the Nibelungenlied scanned on the Internet Archive (Bartsch died 1888).
- Still out: Persian, Urdu and Arabic in every form, the citation index built from journal text, the trained reader, the syntax databases, cached answers from scholarly services, and translations whose licence fails the rule.
- Built: core bundle 3.3 GB archived, 18.6 GB unpacked; full bundle 8.6 GB archived, 29.2 GB unpacked; every manifest hash verified after unpacking.


## 2026-10-09: Inscriptions & Papyri as its own main-menu page
- Scope: a new route, `/inscriptions-papyri`, with its own component under
  `client/src/components/documents/`. It combines the documents-collection
  search (filters, restoration/formula options, ranking, totals, paging,
  the century/region chart) with the browse-by-facet view (kind, then
  region, then century, with a findspot level added for papyri, see the
  entry below) on one page. Before this, the documents collection was
  reachable only as a secondary option inside Lines search and a section
  of Browse Corpus. The search logic is factored out of `LineSearch.jsx`
  into shared code under `client/src/components/documents/`, so the new
  page and Lines search's own "Documents"/"Both" option (kept as a
  secondary route, not removed) share one implementation.
- Placement: shown in the main navigation beside Theme Search, only when
  the documents trial is active (server `TESSERAE_DOCUMENTS=1` and the
  client's `documents_trial` session flag, set by `?documents=1`, the
  same gate the Lines-search documents option and Browse Corpus's
  Documents section already use). The page itself redirects to the main
  search when the flag is not set, so the route is never a back door to a
  trial feature for a visitor who never opted in. It is reviewed, like
  the rest of the documents trial, before being offered to every visitor.
- The documents collection (inscriptions and papyri) is a different kind
  of material from the literary corpus Lines search is built around: no
  author/work/line-range browsing, credit/license per result, restoration
  markup, its own facet tree. Inside Lines search it
  read as a secondary, easy-to-miss option on a page named for something
  else. A named page in the main menu makes it a first-class part of the
  site for a reader who came specifically for the epigraphic or
  papyrological material, with the existing Lines-search route left in
  place, not duplicated or removed.

## 2026-10-09: papyri grouped by nome, with the findspot nested under it
- Scope: `backend/documents_browse.py`'s Browse Corpus facet tree grouped
  papyri by a single flat `region` field derived from HGV's free-text
  findspot column. A document naming only a town (e.g. "Oxyrhynchos") and
  one naming only its administrative nome (e.g. "Oxyrhynchites") landed in
  two unrelated top-level buckets, checked against metadata.db 2026-10-09:
  4,440 and 1,637 documents, split, with no link between them, the same
  pattern for Thebes/Peri Thebas, Hermopolis/Hermopolites, Elephantine/
  Katarraktes Mikros. HGV records the nome as its own structured field in
  the source XML (`<placeName subtype="nome">`, separate from the town's
  own `placeName`), but the metadata extraction
  (`scripts/documents/epidoc_convert.py`) never read it.
- Fix: parsed the raw HGV_meta_EpiDoc XML corpus directly (68,022 files,
  dev workspace, not production) for every (town, nome) pair HGV's own
  structured field records anywhere in the corpus. 573 towns had at least
  one such pair, resolved by majority vote where a town's nome varies
  across documents (39 towns, almost always one dominant nome). Written to
  `data/documents/papyri_nome_map.json`, a small, whitelisted reference
  file alongside `eagle_labels.csv` and `german_label_translations.json`,
  not the full HGV corpus. `normalize_papyri_region` now returns
  `(nome, findspot)`. The nome comes from a document's own parenthetical
  when it has one, else from the map for the town it names, else
  "Unknown nome" when neither resolves (a town outside the nome system
  entirely, or no place recorded at all). The facet tree gained a
  `findspot` level between region (nome) and century. The browse UI labels
  the first level "Nome" for papyri, with a new "Findspot" facet under it.
  Full before/after top-20 counts are in this PR's description and
  `CHANGELOG.md`.

## 2026-10-09: century facet's earliest buckets, source errors excluded
- Scope: checked every document behind the century facet's earliest
  buckets ("31st century BC", "16th century BC", "13th century BC")
  against the real stored date fields. All 8 are source-data errors, not
  early material. One is an EDR epitaph (CIL 09, 03008, an ordinary
  1st-century cinerary urn with `date_not_before` stuck at -3030). The
  other 7 are `O.Trim. 3` ostraca from a documented 3rd/4th-century-AD
  excavation series where 1,043 of the other 1,050 entries carry sane
  Roman/Late Antique dates and these 7 alone carry a Bronze Age
  `date_not_before`. Checked and left alone: the genuinely early
  7th/8th-century-BC EDH/EDR entries, archaic Italic and Sicilian-Greek
  epigraphy (Gabii, Praeneste, Veii, Selinus, Satricum), which are real,
  narrowly-dated finds, not errors.
- Fix: `century_bucket` (`backend/documents_browse.py`) now gives a
  document with a `date_not_before` earlier than 1000 BC
  (`_IMPOSSIBLE_DATE_FLOOR`) its own "Date uncertain" bucket, outside the
  century facet. No
  Latin or Greek alphabetic inscription, and no Greek/Demotic/Coptic
  documentary papyrus in this corpus, is genuine before that floor, and
  it sits safely below the real 7th/8th-century-BC material, which keeps
  its own bucket. The document's own displayed date (`date_label`) is
  unchanged. Only the century facet bucket moves, so a document's page
  still shows what the source actually recorded.

## 2026-10-08: documentary reuse table, formula exclusion threshold and tiers
- Scope: a cross-collection table per language (`cache/reuse_pairs/<lang>_documents.db`,
  `scripts/reuse/build_documents_reuse_table.py`) pairing each literary
  line against the documents collection, with the SAME word-triple
  containment logic and thresholds as the literary table
  (`scripts/reuse/build_reuse_table.py`): `min_shared=2`/`min_jaccard=0.15`,
  `min_shared_override=4`/`min_containment=0.5`, and the rare-single-ngram
  rule (`rare_max_df=20`/`rare_min_containment=0.06`). Kept identical
  rather than re-tuned for documents, since the question the thresholds
  answer (is a shared trigram shape strong enough evidence of reuse) does
  not change with what the other side of the pair is; `shared==1` is the
  tier 'possible', everything else kept is 'strict' -- read-time only, no
  stored tier column, the same derivation `backend/reuse_table.line()`
  already uses.
- Formula exclusion threshold: the literary table excludes a pair whose
  shared n-grams are all built from commonplace LEMMAS (a corpus-wide
  lemma-frequency ratio). Documents have no equivalent "commonplace lemma"
  signal worth computing fresh -- `backend/app.py`'s stage 3b-3 decision
  above already measured and shipped exactly this question for the
  documents collection itself ("is a shared word a boilerplate formula or
  a genuine parallel, by how many documents use it") and found a three-
  order-of-magnitude gap between the smallest formula (3,535 documents)
  and the largest genuine parallel (19): `DOCUMENTS_FORMULA_DEFAULT_N=100`.
  Reused verbatim as `DOCUMENT_FORMULA_MAX_DOCS` here rather than
  re-measured, plus `data/documents/formula_words_<lang>.txt` (the hand-
  reviewed funerary/honorific/legal/dating word lists already shipped for
  the documents-collection search's "hide stock formulas" control). A
  shared n-gram is formula-only when every one of its three words is
  either on that list or a lemma used by more than 100 individual
  documents (computed once per build from the documents index's own
  `postings` table, grouping by the ref's owning doc_id the same way
  `backend.documents.doc_for` does -- NOT from the documents index's
  existing `lemma_doc_freq` table, which counts frequency across the 160
  bucket FILES, not the ~179K individual documents, and so cannot answer
  "how many documents" at all). A pair whose shared n-grams are ALL
  formula-only is dropped entirely, and the rare-single-ngram rule's one
  contributing n-gram is checked the same way, mirroring the literary
  table's `drop_all_commonplace`/`commonplace_hashes` gate.
- Measured against the dev checkout's own Latin data: 605,758 of 632,199
  candidate cross-collection pairs (96%) were dropped as all-formula,
  leaving 5,414 kept pairs, only 280 of them strict (shared>=2) -- most
  genuine literary-to-document reuse this table finds is a single rare
  shared phrase (the 'possible' tier), not a verbatim shared line, which
  is itself the expected shape: a document line is usually a few words
  long, so a literal shared LINE the way two literary works share one is
  the exception (the Pompeii "arma virumque cano" graffito, jaccard 1.0),
  not the rule.
- Known gap, not fixed here: matching is ORDER-SENSITIVE (contiguous or
  one-gap-skip trigrams), inherited unchanged from the literary table. The
  Pompeii "fullers' parody" of Aen. 1.1 ("Fullones ululamque cano, non
  arma virumque", word order reversed) shares the same three content
  words with Vergil's line but no trigram in common, so it is NOT found by
  this table. Recorded here rather than silently claimed as a working
  sample; the two genuine "arma virumque cano" graffiti this table does
  find (CIL IV-shape, verbatim and near-verbatim) are documented in
  `docs/DATA_OPERATIONS.md`.
- Gutter display: a document hit is shown as a SEPARATE count ("quoted in
  N inscriptions or papyri"), not merged into the existing "quoted in N
  works" number. Chosen over merging because the existing number has
  already shipped with a fixed meaning (works, not documents); silently
  changing what it counts would be a bigger change than the Reuse tab
  addition itself, and a document is a different kind of witness from a
  literary work (no author, no title, a different citation shape) that
  reads oddly folded into the same integer.

## 2026-10-08: a shared title needs its own author's name nearby, not just the bare title

**Question.** The Scholarship tab for Apollonius Rhodius, Argonautica 1.5-17
listed "Valerio Flaco (2016). Argonáuticas" and a Smallwood note on
"Valerius Flaccus' Argonautica 1.5-21." Apollonius Rhodius and Valerius
Flaccus both wrote a work called Argonautica, and the backend accepted a
bare match on that title for either author's passage.

**Check.** The corpus holds 145 titles used by more than one author
(`backend.scholarship._load_shared_titles`, built from the corpus file
list), including Argonautica (Apollonius Rhodius, Valerius Flaccus),
Metamorphoses (Ovid, Apuleius) and dozens more. The live production route
was queried read-only for Apollonius Rhodius, Argonautica 1.5-17 and
Valerius Flaccus, Argonautica 1.1-21 on 2026-10-08. The Google Books
channel, which has no author check of its own, returned the same eight
books for the Apollonius page. Three were actually about Apollonius
Rhodius (Morrison, Berkowitz, Augoustakis, each citing "A.R." or "A. R."
next to the locus). Five were about Valerius Flaccus instead: two editions
titled "Valerius Flaccus' Argonautica, Book 1," the Spanish
"Argonáuticas," and the Stover and Tanner books, all four of the last
group citing the Smallwood 1962 note on "Valerius Flaccus' Argonautica
1.5-21."

**Decision.** For a shared title, require the target author's own name or
citation abbreviation near the match, and reject a match naming a
competing author of the same title instead, drawing the abbreviations from
`data/citations/abbreviations.json` (production, read-only). Most dev and
test machines do not have that file, and the check does nothing without
it. Rerunning the lookup against that same production data for Apollonius
Rhodius, Argonautica 1.5-17 now keeps the three Apollonius Rhodius books
and drops all five Valerius Flaccus ones. The same check on Valerius
Flaccus, Argonautica 1.1-21 keeps the three Valerius Flaccus books (the two
editions and the Spanish translation) and drops the three Apollonius
Rhodius ones. Stover's and Tanner's books are dropped from both pages.
Their matched snippet quotes only the Smallwood note and never names
either poet, so nothing in it says whose Argonautica they cite.

A corpus filing quirk very nearly doubled as a second, false "Aeneid"
author. `maffeo_veggio.aeneid.tess` duplicates his own Supplementum under
the stray title "Aeneid" and is not a real second Aeneid. The abbreviation
table marks it `unmatched` (no author_names, no work_titles), and the
guard drops any title-group member the table marks that way before
deciding whether a title is really shared, so an ordinary Vergil citation
still needs no "Vergil" nearby.

## 2026-10-08: the Documents browse scheme (kind, region, century)

**Question.** The documentary corpus (inscriptions from EDH, EDR, and
I.Sicily, papyri and ostraca from HGV via papyri.info) has no browse view
of its own. The only way to explore it is the Line Search documents
trial's free-text filters. What grouping lets a reader explore it without
already knowing a search term?

**Decision.** A three-level facet tree with counts at every level. Kind
(Inscriptions, Papyri and ostraca) comes first, then region, then
century, each level narrowing the one before it. Flat filters (text type,
material, object, language) apply within the current selection at any
level. Sources (EDH, EDR, I.Sicily, papyri.info) appear as a credit on
each document, not as a browse level, because EDH and EDR both cover the
same inscriptions and a source-first tree would double several regions.

**Region.** Inscriptions use the source's own `region` field, already a
Roman province, or for Italy an Augustan region. EDH and EDR label the
same Italian region differently. EDR writes the fuller "Latium et
Campania cum insulis (Regio I)". EDH writes a shorter form and marks an
uncertain region with a trailing "?". These variants are merged to one
canonical label per region, with the original value kept on the document
record. I.Sicily carries no `region` column at all and is assigned
"Sicilia" directly, since every one of its inscriptions is Sicilian by
construction of the source. A few labels name two provinces at once
("Tuscia et Umbria", "Macedonia, Epirus", "Sicilia, Melita"). These stay
their own bucket, since the document genuinely spans both and a merge
into either side would misstate where it is from.

Papyri have no region column. HGV's `ancient_place` field is German-
labeled, with 2,055 distinct values, and is parsed to find a region. A
parenthetical qualifier that looks like an Egyptian nome ("Karanis
(Arsinoites)") becomes the region. A qualifier that is a country,
province, or disambiguator instead ("Masada (Palästina)", "Theben (?)")
is dropped, and the site name in front of it is used on its own. "X oder
Y" ("X or Y", an uncertain alternate reading) takes the first option. A
small alias table anglicizes the most frequent bare German names (Theben
to Thebes, Oxyrhynchos to Oxyrhynchus, unbekannt to "Unknown findspot").
The top 80 raw values cover 85.7% of all papyri. The long tail passes
through with only the general cleanup, not a specific alias, so some rare
findspots keep a German or otherwise unanglicized label.

**Century.** Computed from `date_not_before`, falling back to
`date_not_after` when that bound is missing, with BC/AD assigned by the
usual astronomical-year convention. A document whose two bounds fall in
different centuries is filed under the earliest one, and its own date
label, shown next to it in the leaf list, names the full span, so a
reader is never misled into thinking it is confined to the bucket it sits
under. A document with neither bound is its own "Undated" bucket, apart
from every century.

**Where.** `backend/documents_browse.py` holds the normalization and the
in-memory facet cache, built once over `metadata.db`. The route is
`GET /api/documents/browse`, behind `TESSERAE_DOCUMENTS=1`. The UI is
`client/src/components/corpus/DocumentsBrowser.jsx`, a new tab inside
`CorpusBrowser.jsx`, behind the client's own documents trial.

## 2026-10-08: document results are ranked, a 500-row cap is gone, and German label words are translated

**Question.** A documents-collection search (the `?documents=1` trial)
returned hits in storage order with no total above 500, and the EDH source
database's own German placeholder and connector words ("unbekannt", "bei")
reached the page untranslated. What should rank the list, what should the
total mean once the 500-row cap is gone, and which values actually need
translating?

**Ranking.** No score exists anywhere on this path (see the 2026-10-08
entry below on stage 3b-3 and the 2026-08-25 fusion entries for where
scoring does live, neither of which this touches). The default sort
('relevance') is a four-part ordinal rank, not a score: an exact adjacent
phrase before one whose matched words are scattered on the line, a match
on surviving text before one resting on an editorially restored word,
fewer restorations elsewhere on the same line, then earliest date. Every
part is read from data the documents index already returns for a lemma
match (the per-lemma token positions `find_co_occurring_lemmas` returns,
and the restored-word sidecar), not from a second fetch of the line's own
text. 'Oldest first', 'Newest first', and 'Region' are the three
alternatives offered on the sort control.

**Totals and paging.** The true total is counted the same way the
existing stock-formula count already works. Both read the documents
index's own postings, through `find_co_occurring_lemmas` and `doc_for`,
never a corpus scan and never an estimate. Measured against the
production `la_documents_index.db`/metadata.db, "dis manibus"
(co-occurring on 35,231 documents) now returns 35,231 as its own total,
counted and ranked in about 1.1 to 1.2 seconds warm end to end
(candidates 0.3 to 0.7s, `doc_for` 0.12s, a chunked bulk metadata fetch
0.4 to 0.6s, the restored-word sidecar lookup, once loaded, 0.05s),
comfortably inside the "about 2 seconds warm" target. The expensive step
for any one request, a line-text fetch per matched document, now runs
only for the 50 rows of the page actually requested, grouped by bucket
file. The one-time cold cost of loading a bucket file's restored-word
sidecar (about 1.9 seconds the first time any request touches it, 26 MB
of JSON Lines across 109 Latin bucket files) is paid once per process,
which is why the 2-second figure above is stated as a warm one.

**German label translation.** Every distinct value of metadata.db's
region/ancient_place/modern_place/material_label/object_type_label/
text_type_label fields was scanned for German words (2026-10-08, against
the production metadata.db, 249,610,240 bytes). Counts are document ROWS
containing the word, not distinct values (a word like "bei" recurs inside
thousands of different place strings):

| German word | English | Rows |
|---|---|---|
| bei | near | 14,106 |
| unbekannt | unknown | 11,210 |
| Ägypten | Egypt | 3,022 |
| oder | or | 1,453 |
| aus | from | 627 |
| Oberägypten | Upper Egypt | 531 |
| bzw. | or | 269 |
| und | and | 33 |
| von | of | 29 |
| östlich | east | 14 |
| oase | oasis | 5 |
| szienit | syenite | 5 |
| südlich | south | 4 |
| bezirk | district | 4 |
| gau | district | 3 |
| nördlich | north | 2 |
| unterägypten | Lower Egypt | 2 |
| sekundär | secondary | 1 |
| verwendet | used | 1 |
| nicht | not | 1 |
| wohl | probably | 1 |

A real place spelled in German (Köln, Mainz, Wien, and every other German
city EDH names in its own working language) is NOT in this table and is
never touched. That is the place's own name, the same reason "Roma" is
never translated to "Rome" anywhere else on the site. Only connector,
placeholder, and descriptive-geography words are translated. The table is
committed at `data/documents/german_label_translations.json` and applied
word by word, case-preserved, on the way out (`backend.documents.
translate_label`). The value stored in metadata.db is never rewritten.

A place value recognized as a "not known" placeholder (German
"unbekannt", English "unknown"/"unknown location", or the Latin
"ignoratur" several principal editions still carry) is left off the
result row entirely (`backend.documents.is_unknown_place`). The word
"unknown" printed alone told a reader nothing, so the row carries no
place value for that hit. The Latin and English markers are the same
placeholder problem under a different word, so the hiding rule covers
all three together.

**Decision.** Rank by the four-part relevance order above by default,
offer the three named alternatives, report the exact total from postings
with no cap, page 50 rows at a time server side, and translate the words
in the table above for display while leaving metadata.db untouched.


## 2026-10-08: editors' prose inside a poetry text is removed, the poet's own prose is kept

**Question.** Some Persian and Urdu files, built from complete-works
collections, contain long prose. Which of it belongs in the corpus?

**Check.** Every Persian and Urdu file was scanned for lines over 40 words
and each range was read. Khayyam's Diwan held a signed 1934 introduction by
a modern editor (142 lines, with page references and footnotes), and
Ghalib's Wikisource Diwan held two variant-reading footnotes. The long
prose in Attar (Tazkirat al-Awliya), Saadi (the Gulistan), Naser Khosrow
(the Safarnama) and Sanai is the poets' own.

**Decision.** Remove text written by modern editors, keep prose written by
the author, and keep the remaining lines' references unchanged so the gap
shows where material was taken out. Removal runs through
`scripts/corpus/drop_lines_from_work.py`, which keeps every store in step.

## 2026-10-08: Ghalib's Translation tab shows a Pritchett link, not copied English

**Decision.** For Ghalib (`ghalib.diwan_wikisource`), the Reader's
Translation tab shows a link to Frances W. Pritchett's "A Desertful of
Roses" verse page. Ghalib has no aligned English translation. The link
travels on a new `external_links` field on `/api/translation`. The field
is additive. A
work can carry this field, an aligned translation, both, or neither.
`backend/translation_links.py` loads
`data/translations/links/ur__ghalib_pritchett_links.json`, built by
`scripts/build_ghalib_pritchett_links.py`.

**Why.** Pritchett's site states no licence for her translations or
commentary. They cannot be copied into the site the way the public-domain
and non-commercial-licensed translations in `data/translations/` are.
Linking to her own page for the matching verse is permitted and sends the
reader to her full commentary.

**How the link table was built.** Only `ghalib.diwan_wikisource` (272
ghazals, Wikisource's numbering) ships in `texts/ur/`. A second edition,
numbered exactly as Pritchett's site numbers it, was retired from the
served corpus earlier, so a Ghalib passage could not appear three times
over in Theme Search, Similar Passages, and cross-language results. It
survives only outside the repository, as a cross-reference for this
alignment. The two editions' ghazal numbers do not correspond, so matching
goes by text, not number, at two levels. Each ghazal's opening verse first
pairs up the ghazals. Verse by verse inside each matched pair comes next,
against the retired edition's own text, never assumed from a shared verse
count. That file is not uniformly one line per half-line. Some ghazals
split each verse into two lines, others join both halves into one, and
Pritchett appends unpublished manuscript-variant verses after the regular
numbering for some ghazals. The real, ordered verse-label list for each of
her 234 ghazals, confirmed against her site and including the
"x"-numbered variants, came from her own per-ghazal index pages, fetched
once each (one request at a time, a plain User-Agent, no site refusal
encountered) and cached.

**Result.** 2,514 of 3,345 Wikisource verses (75%) resolved to a Pritchett
verse URL. The ghazal-pairing step reproduced, with no mismatches, all 67
pairs already recorded in `data/poetics/ghalib_pritchett_to_wikisource_ghazal_map.json`
from earlier work. Several verse-level matches were also checked against
her live pages by eye (her own worked example {98,4} and the opening verse
{1,1}) and read correctly. 18 of 234 Pritchett ghazals could not be split
into verses unambiguously from the retired copy's line count against the
real verse count. Most are short by exactly one verse, missing from that
one-time copy. Two carry a stray extra line. These 18 are left unmapped,
reported, and not guessed at. Ghazals she does not cover at all are also
unmapped and expected, since she covers a selection of the diwan, along
with a handful of tied, equally good verse matches.

## 2026-10-08: Theme Search confidence: HEAD_WEAK refit for Latin, Greek, and English

**Decision.** `HEAD_WEAK`, the floor above which a Theme Search result
counts as a match at all, moved from 0.0750 to 0.0738. `HEAD_STRONG`
(0.1006) and the coherence degeneracy threshold (0.995) are unchanged.
`FITTED_AT_WINDOWS`, the index size the live bands are fitted to, is now
530,917 (the production size measured for this refit), replacing the
603,594 recorded for the superseded combined-score design.

**Why.** The pervasive-theme fix above (same day, logged just below)
promotes a single-language search when that language's own median score
sits far above the whole corpus's, but it only ever promotes; it cannot
help a specific, non-pervasive scene whose language-median is not
elevated. On the 139-query set behind that fix, Latin and Greek stayed at
64.7% and English at 47.1%, and every remaining miss was a false `low` on
a result confirmed on topic by reading its description, because none of
those languages' queries are pervasive by this corpus's own statistics
(Latin's and Greek's measured excess over the whole-corpus median tops
out at 0.0046 and 0.0076 against the 0.005 promotion floor, mostly
negative; English peaks at -0.0003). The underlying number the fix would
need to move, `head_lift`, had never itself been refit against the
current, roughly 531,000-window index; it was last fitted 2026-08-25 on
57 queries at 603,594 windows.

The labeled set was extended first, keeping every existing query, to
carry 30 queries each for Latin, Greek, and English (was 17), split
across pervasive themes, specific scenes, and absent subjects, each
checked against its own top results' descriptions read against the
production index: `evaluation/probe_sets/theme_confidence_2026-10-08.json`,
now 178 queries. The original 57-query
`evaluation/probe_sets/combined_confidence.json` (one word to a full
sentence, unfiltered) was kept untouched as a regression check.

`evaluation/scripts/calibrate_confidence.py` swept `HEAD_WEAK` from
0.0400 to 0.0800 against both sets at once, read-only against the
production index. `HEAD_STRONG` does not affect this metric: it only
separates `moderate` from `strong`, never `low` from the rest, so sweeping
it was not useful once that was confirmed. The absolute floor any global
value must clear is set by the single highest-scoring ABSENT query across
both sets and every language at once, because `head_lift` is computed
from the whole corpus for a given query text regardless of which language
the search is narrowed to (see the PERVASIVE THEMES design, logged
below): "a surgeon administers ether before an operation" (unfiltered),
head_lift 0.073282. The only flat, zero-false-positive plateau the sweep
found sits immediately above that, `(0.073282, 0.074292]`, bounded above
by the lowest of three Latin queries that would otherwise tip back to
`low`. 0.0738 sits in the middle of it.

| probe set | queries | old (0.0750) | new (0.0738) |
|---|---|---|---|
| Latin | 30 | 56.7% | 66.7% |
| Greek | 30 | 63.3% | 63.3% |
| English | 30 | 43.3% | 46.7% |
| Persian | 18 | 94.4% | 94.4% |
| Urdu | 18 | 88.9% | 88.9% |
| Hebrew | 17 | 100.0% | 100.0% |
| Coptic | 17 | 94.1% | 94.1% |
| unfiltered | 18 | 83.3% | 83.3% |
| extended set, all languages | 178 | 73.0% | 75.3% |
| original 57-query set (regression check) | 57 | 66.7% | 68.4% |

(Persian, Urdu, Hebrew, Coptic, and unfiltered figures are the already-
shipped pervasive-promoted accuracy; the three later refits, Latin,
Greek, English, use it too, since nothing about this change touches that
mechanism.) Latin gained three queries ("a banquet with speeches, music,
and entertainment," "an old nurse recognizes her former charge by a
scar," "a lover complains of a mistress's cruelty," head_lift 0.074292 to
0.074544) and English gained one ("a garden described in loving detail,"
0.074782). Nothing fell on either probe set: the change can only move a
query out of `low`, never into it, and the ceiling it respects is the
highest-scoring absent query across both sets at once, so a regression on
either set was not possible by construction. Zero absent queries were
promoted to `moderate` or `strong` anywhere in either set, at either
value.

Greek did not move. Its present, non-pervasive queries' `head_lift` jumps
directly from 0.0675 to 0.0762 in this probe set, straddling the entire
plateau, and its own highest-scoring absent query ("a satellite orbits
the earth," 0.070457) sits inside that gap, so no value between 0.0705
and 0.0762 helps Greek without first crossing that query into a false
positive, and no value below 0.0705 is reachable at all without crossing
the global 0.073282 ceiling first. This is a property of this embedding
and this probe set, not of Greek as a language: a probe that happened to
include a Greek scene scoring between 0.0705 and 0.0762 would be rescued
the same way Latin's and English's were.

**Single global value, not per-language bands.** Per-language `HEAD_WEAK`
values were measured against each language's own floor (lowest present,
non-short-query `head_lift`) and ceiling (highest absent `head_lift`) and
rejected: Latin's and Greek's ceilings (both 0.070457, "a satellite
orbits the earth") and English's (0.072210, "a political election
campaign with televised debates") are each already inside the single
global plateau or no lower than the point the global value already
reaches, so a language-specific override would have bought nothing beyond
what 0.0738 already gives Latin and English, and nothing at all for
Greek, at the cost of three numbers to maintain instead of one. The
single global value was kept.

Refit the same way after a corpus-wide re-describe or a size change past
`FITTED_TOLERANCE` (15%), with `evaluation/scripts/calibrate_confidence.py`
against the 178-query set (extend it further first if a new error class
shows up) and the 57-query regression set together, and update
`FITTED_AT_WINDOWS` alongside the two constants.

## 2026-10-08: Theme Search confidence: a single-language search promotes, never recomputes

**Decision.** A Theme Search narrowed to one language now gets a third
confidence outcome, `pervasive`, alongside the two the band already
reported (`low`, nothing resembles the query; `strong`/`moderate`, a
specific match): when the searched language's own median score for the
query sits well above the whole corpus's median for the same query
(`PERVASIVE_EXCESS_BASELINE`, 0.005, measured below) and the existing,
whole-corpus rule would otherwise have called the result `low` or
`moderate`, the match is instead reported as a theme that runs through
much of that language's own literature, rather than conflated with an
absent subject. `head_lift` and `coherence` themselves stay the
whole-corpus measure for every search, including a single-language one;
only this one promotion check is language-specific, and it can only ever
raise a result from `low`/`moderate` to `pervasive`, never lower one. A
query of three words or fewer that does not reach a clear match now also
carries a line saying a full sentence is answered better than a short
phrase, since the index holds sentence-length descriptions and scores a
bare word or two worse by design.

**Why.** A Persian search for "passionate love" returned Rumi, Rudaki, and
Anvari addressing the beloved, on topic by any reading of the results, and
reported "the corpus does not appear to contain passages of this kind,"
because the whole confidence block (baseline, head_lift, coherence) was
computed from the entire, seven-language corpus regardless of the
language filter: confirmed by requesting the identical query text under
every single-language filter and the unfiltered default, which returned
byte-identical confidence numbers every time, since the language filter
reached the results list but never the statistics.

Measured against a labeled set of 139 queries (18-20 per language across
Persian, Urdu, Latin, Greek, English, Hebrew, and Coptic, plus an
unfiltered group), split across pervasive themes (love in Persian and Urdu
lyric, praise of God in Hebrew scripture, war in Latin and Greek epic),
specific scenes (a lover waiting at the beloved's door, a demon tempting a
monk, a messenger breaking news of disaster), and absent subjects
(airplanes, a stock market crash, a smartphone), each checked against the
description of its top results, then run read-only against the real,
roughly 531,000-window production index (`evaluation/scripts/
calibrate_confidence.py`, saved as `evaluation/probe_sets/
theme_confidence_2026-10-08.json`), not a dev copy:

| language | queries | existing rule | this fix | labelled pervasive |
|---|---|---|---|---|
| Coptic | 17 | 52.9% | 94.1% | 10 |
| English | 17 | 47.1% | 47.1% | 0 |
| Persian | 18 | 61.1% | 94.4% | 9 |
| Greek | 17 | 64.7% | 64.7% | 1 |
| Hebrew | 17 | 52.9% | 100.0% | 9 |
| Latin | 17 | 64.7% | 64.7% | 0 |
| Urdu | 18 | 72.2% | 88.9% | 7 |
| unfiltered | 18 | 83.3% | 83.3% | 0 |
| **all** | **139** | **62.6%** | **79.9%** | **36** |

Every remaining error is a false `low` on a result confirmed on topic by
reading its description; no absent query was ever promoted (zero false
positives in this set). English and Latin did not move: no query tried
against them this time sat far enough above the whole corpus's median to
cross the threshold, not because the mechanism excludes them. Greek
promoted once, from an already-correct `moderate`, so its accuracy did
not move either.

**The first design tried was wrong, and this same measurement caught it
before it shipped.** Recomputing `head_lift` AND `coherence` from the
searched language's own rows, rather than only comparing its median to the
whole corpus's, was tried first: it helped Persian, Urdu, Hebrew, and
Coptic the same way, but made Latin, Greek, and English WORSE than the
existing, unfixed rule (Latin 64.7% to 52.9%, Greek 64.7% to 52.9%,
English 47.1% to 41.2%). One language's own windows cluster more tightly
in this embedding than the whole, heterogeneous seven-language corpus
does, so `head_lift` measured within a single language reads lower across
the board, for present subjects and absent ones alike, not only for a
genuinely pervasive theme; the absolute thresholds the existing rule uses
were fitted on the cross-lingual measure and do not transfer to a
same-language one. The promote-only design above cannot regress a
language's accuracy below what the existing rule already gets it, by
construction, which is why it shipped instead.

`PERVASIVE_EXCESS_BASELINE` (0.005) is the widest flat plateau in a sweep
from 0.0 to 0.015 against the measurement above (accuracy 79.1%-80.6%
across that plateau; the highest single point, 80.6% at 0.0035, was not
taken, as a narrower spike one query wide); no absent query in the set
crossed 0.0031, so nothing in the plateau risked a false positive against
it. It is a property of the current index and this probe set; refit it
the same way after a corpus-wide re-describe or a substantial size change,
with `evaluation/scripts/calibrate_confidence.py --sweep` against this
same probe set or a larger one built the same way.

## 2026-10-08: requests workflow, GitHub issues as the single store
- Scholars never need a GitHub account. GitHub issues are nonetheless the
  single store of every request (feature, language, text, bug, result
  problem, correction, suggestion), and the public Requests page
  (`/requests`, backed by `GET /api/requests`) is a read-only mirror of
  that store, not a second database. This keeps one source of truth for
  what has been asked for and what happened to it, recorded once, where
  the team already works.
- Every request type now files a GitHub issue when filing is configured
  (previously the AI-assistant connector's `text` and `other` types did
  not). Every entry point and every type now uses one label scheme,
  `request` plus `request:<type>` (the connector's earlier filings carried
  `from-ai-protocol` plus a bare type label). The Requests page reads every
  request back with one query (`labels=request`) regardless of where it
  came from.
- The public listing never returns an issue's full body, only the short
  line after an explicit "Summary:" marker if the filer's submission
  produced one, or the title alone. Contact info was already excluded
  from the issue body itself. This is a second, independent boundary
  against a long or incidentally identifying free-text context ever
  reaching the public page.
- No email sending was added for the three new entry points, matching the
  existing connector path: the private notification email only fires when
  SMTP is already configured, and otherwise the submission still lands in
  the `feedback` table.

## 2026-10-08: restoration exclusion, stock-formula filter, document view (stage 3b-3)
- `hide_formulas` default threshold: measured directly against the real
  dev documents indexes (`la_documents_index.db`/`grc_documents_index.db`),
  counting DISTINCT documents sharing the matched lemma set via the same
  postings lookup `formula_count` uses (`backend.documents.
  find_co_occurring_lemmas` + `doc_for`): "dis manibus" 35,231 documents,
  "bene merenti" 11,903, "votum solvit libens merito" 3,990, "hic situs
  est" 3,535 (all genuine formulas) against "arma virumque" 19 and "arma
  virumque cano" 8 (genuine parallels, not formulas). The gap between the
  smallest formula (3,535) and the largest genuine parallel (19) spans
  three orders of magnitude, so 100 (`DOCUMENTS_FORMULA_DEFAULT_N` in
  `backend/app.py`) separates them with wide margin on both sides.
- `formula_count`/`hide_formulas` apply only to the LEMMA search path.
  'exact' search gets a best-effort version via matched token positions
  located after the fact (`_find_exact_phrase_positions`) when the
  resulting `matched_lemmas` is non-empty; 'regex' never populates
  `matched_lemmas` at all (true in the literary branch too), so it has no
  well-defined lemma pair to count and `formula_count` stays `None` for
  those hits. `hide_formulas` never drops a hit whose `formula_count` is
  `None`: an unmeasured count is not evidence of a formula, and silently
  changing regex/exact document-hit behavior whenever this filter is on
  would be a bigger change than the spec asked for. Recorded as a
  deviation rather than building a full-corpus phrase-document scan into
  the request path to cover the other two search types.
- The soft-penalty word lists (`data/documents/formula_words_la.txt`/
  `_grc.txt`, spec item 6) are STILL not applied as a down-rank. Checked
  directly, again: `/api/line-search` computes no per-result score or
  rank for document hits (they are appended in candidate-discovery order,
  filtered/deduped, never sorted by any merit measure) — the identical
  absence stage 3b-2 already found for formula words generally. Left for
  whichever later phase gives document hits a score at all, rather than
  inventing one now to have something to attach a penalty to.
- `matched_restored`/`partly_restored` are computed from the matched
  tokens' own index POSITIONS, not from re-splitting the matched word
  strings: the lemma FAST PATH already enumerates positions while
  building `matched_words`, so this is a byproduct of that loop, not an
  extra pass. For 'exact', positions come from a new best-effort phrase
  locator (`_find_exact_phrase_positions`) that mirrors
  `exact_phrase_pattern`'s own asymmetric word-boundary rule (no trailing
  boundary on the last word, so a Latin enclitic still matches). For
  'regex', no position concept exists at all (the literary branch has
  none either), so both flags are always `False` there — treated as "not
  restored," the same safe default an exact hit the locator could not
  place also gets, rather than guessing.
- `exclude_restored` and `hide_formulas` apply identically under
  `collection=documents` and `collection=both` (the same
  `_search_documents_collection` call both paths share); the literary
  side of `collection=both` is untouched by either parameter, matching
  stage 3b-2's own "two insertion points only" rule.

## 2026-10-08: documents in the corpus-wide phrase search (stage 3b-2)
- Restored-word marking uses a light dotted underline, not scholarly
  square brackets. The matched-word highlight already uses `<mark>`
  (amber background); the corpus's own angle-bracket convention is
  reserved for editorial brackets carried IN the source text itself
  (`decodeEntities` in `LineSearch.jsx`). An underline composes cleanly
  with both without visual collision.
- Formula words (`data/documents/formula_words_la.txt`/`_grc.txt`) are NOT
  applied as a penalty this phase. The spec asked for them to be applied
  "the same way function words are penalized in line search, if line
  search has such a penalty" — checked directly, and it does not: `/api/
  line-search` filters/excludes stopwords but computes no per-result
  score for either the literary or the new documents path, so there is no
  existing penalty mechanism to extend. Left for a later phase rather than
  inventing a new scoring step not asked for.
- `collection='both'` does NOT fold the documents count into the existing
  `total`/`distinct_loci` fields. Those keys have always meant "how many
  places in the corpus" for literature alone; changing their meaning under
  one particular parameter value would silently hand a different number
  to a caller (the MCP connector, a saved script) that already reads
  `total` and has not been told to expect two collections. The documents
  count is reported separately (`documents_total`,
  `documents_by_source_region`).
- A document hit's matched-lemma rarity, if anything scored by it, belongs
  to the documents index's OWN `lemma_doc_freq` table (the reason stage
  3b-1 built a separate index at all: computing rarity over literature and
  documents together would shift literary word rarity). Since neither
  collection's line-search path computes a score, this has nowhere to bite
  yet; `rare_focus_filter` (which DOES read the literary table) is applied
  only to literary rows, never to document rows, so it is ready the day a
  documents-side rarity measure is added without silently using the wrong
  table in the meantime.
- Latin's u/v, i/j spelling-variant expansion (`backend/inverted_index.py`
  `lookup_lemmas`) now fires for documents too, keyed on the real language
  code ('la') rather than a pseudo-language — a byproduct of giving that
  function a connection-override parameter, not a deliberate quality
  change, but worth recording since the stage 3b-1 dev tool
  (`query_documents_index.py`) explicitly flagged the ABSENCE of this
  expansion as a known limitation of its own pseudo-language reuse trick.

## 2026-10-08: what the Scholarship tab draws on, and on what terms
- Sources:
  - open scholarly metadata (OpenAlex, Crossref, and Unpaywall for legal
    open-access copies);
  - open full text through CORE;
  - book pages through Google Books, with a HathiTrust search link;
  - an offline citation index built from public-domain early journal
    literature;
  - commentaries held on the site.
- Subscription articles are linked by DOI and through the reader's own
  library link, never copied.
- Commentaries are installed only when their licence permits reuse (public
  domain, or an open licence such as CC BY-SA, credited on the sources
  list). Texts whose licence is unknown or restrictive are left out.
- No paid service sits in the request path. The external services used are
  free, with keys held in the server environment only.
- Machine translation of a commentary note is made on request by the local
  model, marked as unreviewed, cached, and offered only for notes the site
  holds.
- The tab and the connector tools stay behind their switches until they
  have been tried and the Help text written.

## 2026-10-07: how names are found for "same people and places" in each language

The Similar Passages group "Same people and places" links passages in other
works that name the same rare people or places. It needs to know which words
are names, and the method differs by script.

- Latin, Greek and English: capital letters. A word counts as a name when it
  is capitalised mid-line in at least 85 percent of its uses (judged on the
  stem, five letters after transliteration) or in 90 percent of the uses of
  its exact form. Unchanged from the first version.
- Hebrew: the ETCBC/BHSA morphology already in data/lemma_tables/hebrew_pos.json
  marks proper nouns (part of speech nmpr). Its 2,164 name forms are matched on
  the consonantal form the Hebrew index uses. Known weakness: consonantal
  homographs, such as a form that is both "her judges" and the name
  Shephatiah.
- Coptic: the Coptic Scriptorium part-of-speech tags already in the Coptic
  syntax database. A form counts when it is tagged PROPN in at least 85 percent
  of at least two tagged uses, which gives 1,742 forms. Occasional common nouns are
  mistagged.
- Persian and Urdu: neither script has capitals, so the part-of-speech tags that
  the Stanza tagger wrote into the lemma caches when the texts were imported
  are used, with the same purity rule (PROPN in at least 85 percent of at least
  three uses). A short hand list is added: the Qur'anic prophets, the lovers of
  Persian and Urdu romance (Majnun, Layla, Shirin, Farhad, Zuleikha, Khizr) and,
  for Urdu, the figures of Karbala. Urdu then removes a hand stoplist of stock
  ghazal images the tagger reads as names (wine, ruby, dew, narcissus and
  others), and the word husn, which is "beauty" in nearly every ghazal and the
  name Hasan only in the marsiyas. This gives 362 Persian and 557 Urdu name forms.
- Arabic: not done while Arabic is held. The tagger found no names in the
  Arabic corpus, so it will need a hand list.

Rarity is counted within each script group (Latin, Greek and English together,
Hebrew, Coptic, and Persian and Urdu together, which share name spellings), so
adding the new languages did not change Latin, Greek or English results: their
rows are identical to the previous index. Names now mark 5,240 of 5,372 Hebrew
passage windows, 7,523 of 13,200 Coptic, about 81,800 of 220,011 Persian and
about 10,600 of 14,759 Urdu. Checked by eye on fifteen random windows per
language and on known cases (a Genesis passage naming Abraham links to 1
Chronicles 1, Exodus 6, Psalm 105 and Joshua 24, a Hafez passage naming
Joseph links through Zuleikha to Saeb and Sanai).

## 2026-10-07: Persian and Urdu are served on the main site; Arabic stays held

Persian and Urdu joined the main site's languages after two rounds of
review by a reader of both. In the second round, ninety ranked pairs were
graded, thirty per sheet, ten each from the top, middle and margin of the
ranking. Persian, Hafez against Iqbal: 30 Good. Urdu, Ghalib against Iqbal:
22 Good, 6 Plausible, 1 Wrong, 1 blank. Persian against Urdu, Hafez against
Ghalib: 20 Good, 9 Plausible, 1 blank. That is one Wrong in 89 graded pairs.
Counted as distinct judgments, since one refrain-and-rhyme poem pair
filled several rows, the ninety rows are 8 poem pairs and 46 word-level
pairs. Every Plausible verdict named a set phrase or compound, not a
retrieval error. Neither the corpus frequency of the phrase nor a language
model could separate those from the Good pairs, so set phrases are shown
with a count of the works sharing the wording and are not penalised (entry
of 2026-10-06). The reader graded only six Arabic pairs and declined to
judge further, so Arabic's passage windows stay held from Theme Search and
Similar Passages and its tab stays off until another reader grades it.

## 2026-10-07: Similar Passages adds per-language sections, the same for every language

The Similar list ranks every language together by content, so the corpora
with the most passages fill it. An Urdu passage from Mir returned 28 Persian
matches and 2 Urdu ones, because the index holds about 220,000 Persian
windows and 15,000 Urdu. Rather than a rule for Persian and Urdu alone, every
selection now also gets, for each served language with fewer than five
results in the list, that language's five best matches above the ranking's
similarity floor, shown as one collapsed row of language buttons ordered by
best match. A Persian passage from Hafez then offers Urdu (Ghalib, Dagh)
first, and a Latin passage from Curtius offers Persian (Ferdowsi, Nizami),
Greek and Hebrew. The main list and its order are unchanged. The sections
reuse the scores already computed, about a third of a second for all
languages together.

## 2026-10-07: refrain and rhyme are matched across Persian and Urdu, identical forms only

The Persian against Urdu search had two channels, shared words and meaning,
so an Urdu ghazal written in a Persian ghazal's form was found only through
its words. It now has a third: two poems whose refrain and rhyme are the
same in the shared letter forms (backend/perso_arabic.cross_form), scored
like the single-language form channel (unique on both sides 1.0, discounted
by how many poems carry the form in the two texts and in the two corpora,
and by a meter mismatch where both poems are labelled), with weight 5.0
against dictionary 2.0 and meaning 1.2. Measured on the corpus tables: 19 of
2,633 Urdu poems share refrain and rhyme with a Persian poem. Two of the
first results were homographs of function words (Urdu hua "became" and
Persian hava "air"), so a refrain made only of words on either language's
stoplist is excluded. Across all 504 Persian and Urdu text pairs ten poem
pairs remain, among them Hafez's "dost" ghazal and Ghalib's ghazal 64,
Saeb's "ahista ahista" line and Wali's ghazal 31, and Saadi and Dagh on
"pargar-e dil" and "parvardigar-e dil". A translated refrain (Persian ast,
Urdu hai) with the same rhyme would match 198 Urdu poems, too many to be
evidence without the meter, which the Urdu texts do not carry, so it is not
matched.

## 2026-10-07: a possible echo must overlap its passage by at least 0.002

The Reuse tab's "possible echoes" are pairs kept by one shared rare
word-triple. In long prose units that rule admits almost anything: for
Argonautica 1.2 the list held paragraphs of Galen, Aretaeus, Plutarch and
Aelius Aristides of up to 1,139 words, each sharing "kata stoma kai" and
nothing visible besides. Possible echoes are now shown, and counted in the
Reader's gutter, only when the pair's word-triple Jaccard is at least 0.002.
Measured on the built tables: this removes 72,441 of 254,117 Latin possible
echoes (28%), 21,610 of 86,932 Greek (25%) and 180 of 113,707 English, whose
lines are short. Strict pairs (two or more shared triples) are unchanged. The
filter is applied when the table is read, so no rebuild is needed and the
value can be moved.

## 2026-10-07: Similar Passages shows "same people and places" above "same kind of scene"

Similar Passages ranked windows by content alone, and the descriptions name
no one by design ("a commander", "a city"), so a passage's direct parallels
could rank below generic scenes of the same kind: for Curtius 3.1 (Alexander
at Celaenae) Arrian's account of the same event (1.28-29) was not in the top
100. The Similar tab now shows first the windows of other works that share
rare proper names with the selection, ranked by content similarity plus the
names' rarity (log of windows over windows containing the name, above a
threshold), commentaries on a work set aside, and then the content-ranked
list without those windows. A word counts as a name in a language when it is
capitalised mid-line in nearly all its uses there, judged per language and on
whole word forms as well as stems. Tested on twelve passages in three rounds:
the first group found Arrian 1.28 and Livy 38.13 for Curtius 3.1, Suetonius
and Claudian for the Rubicon, Apuleius 6.19 for the Golden Bough, Eobanus'
Latin version of Iliad 22 for Hector's death. Weak where a passage's only
names are very famous (Hector, Hannibal): that group starts collapsed.
Trialled behind a switch, then made the default.

## 2026-10-06: Persian and Urdu refrain-and-rhyme matches, one per poem pair; set phrases shown, not penalised

From the first expert review (Walt Hakala, 90 graded pairs: one Wrong, nine
Plausible for set phrases, 72 Good). The refrain-and-rhyme channel emitted
every line pair of two poems sharing a refrain, so a ranking of 200 held a
handful of poem pairs repeated; it now emits one result per poem pair, and a
shared refrain and rhyme is discounted by how many poems in the whole corpus
carry it (factor sqrt(2/n)). Retest: every pair graded Good still found, the
Wrong pair out of the top 200. Set phrases were not penalised: neither corpus
frequency (Good pairs share phrases found in 10-12 of 28 Persian works,
Plausible ones in 1-2) nor a language-model judgement separated the expert's
Good from his Plausible pairs, so a discount would demote good results as
readily as weak ones. The count of works sharing a result's wording is shown
instead, with the existing control to hide common phrases. Arabic is held out
of results until a reader grades it.

## 2026-10-06: a Reader selection is matched to its passage window by every reference coordinate

The match compared only the last two numbers of a reference and searched every
book of a work, so in works cited book.chapter.section a selection could get
another book's window (Curtius 3.1.1 matched 10.1.1). It now compares every
coordinate, within the book being read; on 600 random windows used as
selections, 599 resolve to their own book and one to the identical window of
its book file.

## 2026-10-03: the passage descriptions are the GLM 5.3 Flash set

Every passage window's description was rewritten from the window's own
text by GLM 5.3 Flash, chosen on 2026-09-30 by a blind pairwise
judgement on 100 windows a pair: it beat the August descriptions 96 to 4
and Qwen 3.8 93 to 7 with no invented proper name in 300. Retrieval on
the sixteen-query benchmark, every top-ten pair judged by the judge fixed
on 2026-09-15 against 97 hand grades, moved from 0.381 to 0.403 precision
at ten (nine queries up, five down, two level), as expected: retrieval
compares vectors that keep a description's topic and lose its detail, so
the rewrite's gain is in the text shown beside each result. The
descriptions went live on 2026-10-03 (docs/DATA_OPERATIONS.md). Windows
are still cut by line count; in the Latin poem collections 8,862 of
18,139 straddle two poems (Martial 91 percent), kept for now and to be
cut at poem boundaries at the next index rebuild.

## 2026-10-01 Classical forms get a third lemma table, behind the treebank and the Koine tables

**Question.** Even with the treebank table and the new Koine table, a share
of Greek tokens still carry no real lemma, mostly in classical authors the
treebank table under-covers. How large is that share, and can a lookup
table close it without the CLTK backoff that invents stems.

**Measurement.** Forms in neither table were 4.3% of the Iliad, 10.7% of
the Republic, 10.6% of Thucydides, 15.1% across Plutarch, 2.3% of the
Septuagint, and 14.4% of the whole Greek index (2.04 million of 14.19
million tokens, each work counted once). A table built from the GLAUx
treebank corpus, 936 treebanks of ancient Greek spanning classical through
late antique texts, resolves 90.2% of them, all of the Iliad, 99.4% of
Thucydides, 91.5% of Plutarch, and only 16.2% of the Septuagint, since
GLAUx's texts are classical Greek, a different register from the
Septuagint's Koine. 200,583 tokens are still left, most of them crasis
forms such as τἀληθῆ (τὸ plus ἀληθῆ), which a lemma lookup table cannot
split, or technical terms the corpus does not cover.

**Decision.** The classical table is a third table in the chain, loaded
after the treebank table and the Koine table and filling only what both
still lack. The treebank table and the Koine table keep the last word on
every form either already has, so no existing lemma changes. The 6,136
forms where GLAUx disagrees with an existing table are kept in a file for
review and not applied.

**Rejected.** Installing the CLTK backoff lemmatizer on production for the
remaining classical gap. It invents a stem for any form it cannot otherwise
lemmatize, and the Greek rebuild this morning removed exactly those
invented stems from the index once a real table covered the forms behind
them.

**Left open.** The 6,136 conflicts, to be read by eye. The crasis forms,
which call for a word splitter that a flat lookup table does not provide.
A spelling map between
sources that write one verb two ways (γίνομαι in the Koine morphology and
this table, γίγνομαι in the treebank table), which keeps related forms
apart until it exists. Side finding from this measurement: 29 works,
among them the Iliad, the Odyssey, the Republic, Thucydides and Herodotus,
sit in the Greek index both whole and as parts, counted once per work
throughout.

## 2026-10-01 The Hebrew-Latin bridge is filtered by attestation and a judged remainder (HE.5)

**Question.** `hebrew_latin.csv` reached Latin through Greek, Hebrew to Greek
by the CATSS alignment and Greek to Latin by the dictionaries, so Greek
polysemy let wrong pairs through. Gold reached argentum through a Greek
word glossed both ways, and six reached quattuor. Of the 29,901 bridged pairs,
how many are real equivalents, and how to find them without reading all.

**Measurement.** The Vulgate is a translation of the Hebrew, so a pair that
occurs in the same aligned verse is attested. Across 35 books with matching
Vulgate files (20,128 aligned verses, Psalms left out for its numbering),
6,719 pairs are attested at least once. The other 23,182 went to two
model judges, each given the pair with the Hebrew word's BHSA glosses: a
first pass (Qwen 3.8 on the gateway and Qwen3-8B on the BullsAI GPU) and
a second pass over the whole pool by Qwen 3.8 27B on the BullsAI GPU
(23,182 pairs in ten minutes). The first pass judged 5,435 equivalents at
high confidence, the second 6,483, and 4,595 pairs got a high-confidence
yes from both. 4,293 pairs carried CATSS's medial-letter
spelling of a final letter (אדונ), which the first attestation and the
first judging never matched. Both were redone with the spelling converted,
and the judge's yes rate on them rose from 9% to the general 26%.
Of the pairs both judges accepted, 1,531 have a Hebrew side that is no
BHSA lemma (inflected forms the bridge inherited) and are left out. Sample
reading of the pairs only one judge accepted found proper names against
common nouns (Dan against iudex) on one side and overconfident "standard
Vulgate translation" claims (טוב "good" against bellus) on the other, so
agreement is required. The pairs both accepted read as right in a sample
of forty. Of the dropped, nearly all were wrong.

**Decision.** The shipped dictionary keeps the attested pairs and the
lemma-keyed pairs both judges accepted, 9,783 in all. The 20,118 dropped
are listed with their reasons in `data/proposals/hebrew_latin_dropped_2026-10-01.csv`,
the reason naming the judge that rejected a pair the other had accepted.

**Rejected.** Keeping the whole bridge for recall. Two thirds of it was
noise, and noise in a dictionary channel costs precision on every
cross-language search. Rebuilding the bridge from scratch. The attested
core is the same thing, found cheaper.

**Third build, the same evening.** Attestation by shared verse alone kept
frequent companions: gold reached argentum (98 shared verses) and three
reached quinquaginta. The attestation was recomputed with each word's
verse frequency, over 36 books once Psalms was added through Jerome's
psalter from the Hebrew (`jerome.vulgate.part.21a`, Vulgate numbering
mapped psalm by psalm, the merged and split psalms 9 to 10, 114 to 116
and 147 left out), 22,548 aligned verses. A pair's lift is its shared
verses over the number chance would give. Of 6,882 attested pairs, 1,393
co-occur at chance level (lift under 2, or a single verse with lift under
5) and are out. The 27B judge then read every attested pair: 1,991 it
rejected at high confidence are out, companions among them (gold with
argentum at lift 35, three with triginta), at the cost of a few true pairs
it misreads (קדם "ancient times" against antiquus). A rescue for
rejected pairs whose Latin word had no stronger Hebrew partner was tried
and dropped, because the rescued pairs were mostly collocations (Ashkelon
against Gaza). A single shared verse counts only when the judge confirms
it (573 kept, 573 not). The dictionary now holds 5,922 pairs: 2,925
attested and 2,997 judged. Each dropped pair's reason is in the dropped
list.

**Left open.** The judge's false rejections among attested pairs, for the
Hebrew specialist to read, the judges' loose positives, and a direct Hebrew-Latin lexicon source if one with an open
licence appears.

## 2026-10-01 Koine forms get a second lemma table, and the treebank table keeps the last word

**Question.** The Greek lemma table comes from Ancient Greek treebanks and
has little Koine in it. On the Septuagint the lemmatizer falls to the CLTK
backoff, which invents stems (υμνειτοσ for ὑμνεῖτε, λημψοσ for λήμψομαι),
or leaves the surface form. Measured on the production index, 71,572 of
589,484 Septuagint tokens (12.1%) carried a lemma that is no known lemma,
40,733 of them the surface form itself. Dictionary candidates drawn from
the Septuagint inherited the invented stems.

**Measurement.** Of the unresolved tokens, 5,837 were tokenizer artifacts
(the ano teleia and the spacing breathing kept on the word, fixed
separately). A table built from the Rahlfs Septuagint morphology (31,069
forms the treebank table lacks) resolves 53,164 of the remaining 66,035
(80.5%). What is left is inflected proper names for the most part. On the
Greek New Testament the treebank table already covers all but 0.35% of
tokens. 1,336 forms are in both tables with different lemmas: some are
Koine readings that are better (ἄγε as the imperative of ἄγω, not a lemma
of its own), and some are homograph ambiguities (ἀγών "contest" against
the participle of ἄγω) that a lookup table cannot settle either way.

**Decision.** The Koine table is loaded after the treebank table and fills
only the forms it lacks. The treebank table wins on every shared form, so
no lemma in a classical text changes, and the conflicts are kept in a file for
review and not applied. The source carries a Creative Commons
Attribution-NonCommercial-ShareAlike licence, the same family of terms as
the Hebrew morphology, and the attribution file names the repository and
the CCAT analysis it derives from.

**Left open.** The 1,336 conflicts, to be read by eye. The proper names
still unresolved, which would need a names table. Lemma spellings that
differ between the two sources for one verb (γίνομαι in the Koine
morphology, γίγνομαι in the treebanks), which keep a Septuagint form and a
classical form of the same verb apart until a spelling map joins them. The
full Greek rebuild that applies this table and the tokenizer fix to the
index.

## 2026-10-01 Hebrew-Greek dictionary candidates pass through a model judge and a reader, never straight in (#519)

**Question.** The 1,787 Hebrew-Greek pairs proposed from verse alignment
(co-occurrence at least 10, lift at least 5) are mostly neighbours, not
translations: Pharaoh beside Egypt, flock beside shepherd, king beside
book. The first pass had taken 26 by hand. How to get the rest of the real
equivalents out without reading 1,787 rows.

**Measurement.** A triangulation through Latin (the Greek word's Latin
translations meeting the Hebrew word's) passed 32 and was wrong on about
a third of them, and in doing so exposed errors in the Hebrew-Latin bridge
(gold reaching argentum, six reaching quattuor), which is now its own
item. A model judge (Qwen 3.8 on the gateway, no reasoning, each pair with
the Hebrew word's BHSA glosses) answered yes to 216 of 1,787 at high
confidence. Of those, 88 had a Greek side that is no lemma at all (υιρι,
ελαλησ, γαη): the candidate generator's Greek lemmatizer leaves many
Septuagint forms unlemmatized. The 128 left were read one by one: 97 are
translation equivalents in some sense of the Hebrew word, 31 are not
(metonymies such as אכל with ἄρτος, neighbours such as בקר with πρόβατον
and אהל with μαρτύριον, and plain judge errors such as אתה with εἰ).

**Decision.** Candidates reach the dictionary only after the judge, the
artifact filter and a reading. The 74 pairs not already present are added
with a dated comment line naming the method. The 88 artifact rows are not
added even where the sense is right, because a dictionary of real lemmas is
what the file is, and the index tokens behind those forms are a
lemmatization problem to fix at its source.

**Left open.** The Greek lemmatizer's coverage of Septuagint forms, which
both pollutes candidates and leaves those tokens reachable only by their
surface form. The Hebrew-Latin bridge audit (HE.5 on the private list).

## 2026-10-01 Hebrew homographs are separate lemmas, read from the vowel points (#483)

**Question.** The Hebrew lemma table was keyed by consonants and kept the
first lemma BHSA listed for a spelling, so words that share their letters
collapsed into one lemma. Issue #483 named the cost. Stopping אל for
the preposition also stopped אל "God", and מלך "he reigned" was tagged as
the noun "king". Three ways were open. Leave ambiguous words off the stoplist
and accept the noise, keep one lemma per spelling but mark homographs in
the table without a way to choose between them, or read the vowel points,
which the text has and the lemmatizer discarded.

**Measurement.** On BHSA's 420,102 word occurrences, 3,430 consonantal
spellings cover more than one lexeme and 21,687 occurrences (5.2%) take the
wrong lemma under the majority reading. Keyed by pointed form, 1,408 keys
remain ambiguous and 4,804 occurrences (1.1%) take the wrong reading. A
pointed table built from BHSA finds 99.3% of the 328,822 words in texts/he
once the two editions' conventions are folded into the key: holam written
before or on the waw, dagesh present or absent, holam haser for waw and
qamats qatan as their plain marks.

On the held-out doublet 2 Samuel 22 = Psalm 18 (51 verse pairs, current
code on both sides, the old and the new Hebrew index) the default search
finds 10, 35, 40, 47, 48 and 49 of them in the top 10, 50, 100, 500, 1,000
and 5,000, against 10, 36, 43, 47, 47 and 49 before. Forty pairs moved,
twenty-four down and sixteen up, most by a few places. The one large mover
is 22.27 = 18.27 (13th to 71st): its shared words were ברר, עקש and עם, and
עם "with" is now the stopped preposition עם² while the old lemma, which also
meant "people", had passed as a content word. Two pairs gained correct
lemmas the old table could not give (22.30 = 18.30: "I run", אָרֻץ, had been
read as "land", and the prefix in בְכָה as "weep"). The doublet is a
near-verbatim parallel and does not measure what the change is for, which
is correct lemmas for one word in twenty, correct tags, a stoplist that
stops function readings only, and fewer pairs built on a shared spelling
with different meanings. The lemma-only configuration of the benchmark
cannot be read across this change. In its merged line-and-window mode
three gold pairs that the lemma matcher does produce (checked directly)
fall out of the result list, and in line mode they are present at ranks
76, 85 and 102.

**Decision.** Pointed lookup first, consonantal fallback. A lemma is the
consonantal spelling. When a spelling covers several lexemes the most
frequent keeps the bare spelling and the others carry a superscript numeral
in order of BHSA frequency (אל, אל², אל³, and עם "people", עם² "with"). The
numeral is part of the lemma everywhere lemmas are stored or compared, and
is stripped only where a lookup is keyed by consonants (the cross-language
dictionaries). The bare spelling goes to the most frequent reading rather
than to a fixed part of speech, because an unpointed query (a reader
typing אל) should find the reading it most often means, and the stoplist
names the rest by number. The stoplist stops function readings only.

**Rejected.** Marking homographs with BHSA's own symbols (אל=, אל/) was
rejected: the slash and bracket mark part of speech, not identity, and the
symbols would reach the display. A fixed part-of-speech order for the bare
form was rejected for the reason above. Rebuilding the dictionaries by
homograph was deferred: they are keyed by consonants from CATSS and the
aligned verses, and the stripped lookup loses nothing they had.

**Left open.** Unpointed queries take the majority reading, so a line search
for אל does not also find אל³. A query-time expansion to the whole homograph
group is the follow-up. Latin and Greek have the same collapse in a smaller
way (the lemma tables keep one lemma per form) and could use the same
mechanism with a different disambiguating signal.

## 2026-09-30 Theme Comparison, two works read against each other by content

**Question.** Theme Search reads the whole corpus against a description a
reader writes. Asked what two named books share in content, the site had
no answer, and the assistant said so. Can the same vectors compare two
works directly?

**Check.** Every passage window of one work scored against every window of
the other on the Similar Passages vectors, in blocks, each window of the
first work keeping its three best partners, pairs deduplicated on the
unordered pair. A whole work stored as book files gathers its books, and a
named book keeps to its own windows. On the live index, Aeneid 1 against
Lucan 1 puts Jupiter's prophecy (1.289) beside Lucan's prophecies (1.661,
1.31) and the storm beside the panicked exodus. The whole Aeneid against
the whole Bellum Civile puts storms with storms, a leader rallying troops
with the same, battle chaos with battle chaos, in a tenth of a second
once the index is loaded. Metamorphoses 1 against Hesiod's Theogony,
across languages, puts the cosmogonies together.

**Decision.** Shipped as Theme Comparison, with a "Compare two works" mode on
the Theme Search page, the route /api/passages/compare, the connector tool
theme_compare, and a path in the assistant that runs it for a question
about what two texts share in content and reads the best pairs from the
descriptions alone. Confidence reads the pair's own score matrix, the
median as baseline and the mean of the top ten above it as head lift,
with the Theme Search lift thresholds. This is a convention carried over,
not a fit, until a graded sheet of pairs exists. Pairs beyond forty
million cells are refused with advice to compare books.

## 2026-09-30 The assistant runs the comparison she is asked for (#533)

**Question.** Asked to compare two texts, the assistant said the corpus
held both and offered a control that opened the search. That was right
for a model that took twenty seconds to write a sentence and a search
that can take minutes. Is it still right with the model on the gateway?

**Check.** A cached pair's first page comes back from the fusion route at
once, and the results prompt reads twenty-five parallels in two to four
seconds with every guard reporting clean (the Statius against Aeneid
reading in the 2026-09-30 prompt entry). An uncached pair starts its run
on the first request and most finish within a minute or two.

**Decision.** For two texts in one language she fetches the first page,
waits up to a hundred seconds with a word to the reader while the run
starts, reads the page with the results prompt and its guards, and still
offers the control that opens the full list. Whole authors and
cross-language pairs hand over as before. The site's copy about her
says search, read, interpret, since that is now what she does.

## 2026-09-30 The assistant's accuracy is checked and recorded, not sampled (#532)

**Question.** The guards check citations, quotations and figures against
the material the assistant was given. Once she may add general knowledge
as background, a wrong century or a misattributed work carries none of
those and passes. What checks that?

**Check.** A second pass with the same model and the same material, asked
only for specific claims (a date, century or reign, an attribution, a
title, a work's contents) the material does not support, with a revision
that removes or softens the specific. Tried on a live answer about
Dracontius it removed "priest, active in the sixth century" and left "a
late antique Latin poet" and the judgement that he imitated Vergil, which
is the intended line: specifics are checked, judgements are hers. A first
version flagged the period word and the judgement too and gutted a fair
answer, so a filter now keeps a finding only when the sentence carries a
date-like token or the claim names a title, attribution or contents. The
pass takes about two and a half seconds after the answer.

**Decision.** Every answer runs through the check, and every exchange is
kept on the server with no identifier for a weekly sample reading. A
graded question set for the live site follows separately. The check is
a net, not a proof: a correct date it happens not to flag is a correct
date, and a wrong one it misses is what the weekly reading is for.

## 2026-09-30 The assistant is asked to judge, not only to report (#531)

**Question.** The assistant's prompts were written for a model with about
three billion parameters active, and confined it to naming searches and
putting computed facts into prose. With a 27-billion-parameter model
answering, can it be asked to weigh the parallels it is shown without
losing the one property that matters, that it never supplies a citation,
a quotation or a figure of its own?

**Check.** Old prompt against new on the same gateway model: three real
result sets (Lucan 1 against Aeneid 1, Thebaid 1 against Aeneid 1,
Metamorphoses 1 against De rerum natura 1), the default reading and three
questions each, plus eight guide questions. The guards stripped no
reference on either side and found every quotation in the passages
given. Number flags fell from twelve to seven, most of them the words
"twenty-five" for a 25 in the facts, which the guard now reads as one
number. Shown ten passages of up to 400 characters instead of five of
180, the new prompt found and explained the Thebaid 1.473 "meminisse
iuvet" against Aeneid 1.203 "meminisse iuvabit" echo, which the old one
never saw. Asked about a lesser-known author, the model invented a title
twice. Handing it the corpus's list of that author's works, with the
site's blurbs where they exist, stopped the invented titles. It did not
stop a wrong date offered from general knowledge.

**Decision.** The new prompts ship. Background about authors is marked as
background and draws on the site's own blurbs, which exist today only for
texts imported since late August. Writing blurbs for the rest of the
corpus is the follow-up, recorded separately when done.

## 2026-09-30 The assistant's model moves to the university's AI platform (#528)

**Question.** The assistant's model (Qwen3-30B-A3B under llama-server on
the web server's CPU) holds about 25 GB of memory, takes 15 to 20 seconds
to a finished paragraph, and forces every other heavy job on the machine
to run one at a time. The university's own AI platform serves larger open
models over an OpenAI-compatible gateway at no cost to the project. Is an
answer from there as good, and how fast?

**Check.** Ten of the assistant's typical questions (eight on using the
site, two reading a fixed set of search results) were put through her own
prompts to four gateway models. Qwen 3.8 27B with thinking off answered in
1.1 to 2.0 seconds and kept every rule. It named the right tool, declined
the request for scholarship with the right reason, said when the help
material it was given did not cover a question, and read the results
without invention. GPT-OSS 120B was fuller but explained a score from its
own knowledge, which the prompt forbids, and once returned nothing when
its reasoning consumed the token cap. GLM 5.3 Flash reasons before it
speaks and produced no visible text within the cap. Gemma 4 E4B misstated
what the help covered. A like-for-like run against the local model
follows the same day.

**Decision.** The client is made configurable for a keyed gateway with the
local server as the unchanged default. Production moves to Qwen 3.8 with
thinking off on the campus gateway, and the local model server is stopped,
returning its memory to the machine. Questions stay on campus. The Help
page says so.

## 2026-09-28 Hebrew stoplist: עם and שם come off, אל, את and על stay (#483 §2)

**Question.** Hebrew lemmas are consonantal, so one stoplist entry stops
every word with those consonants. Five entries collapse a function word
with a content word. Which should stay stopped until lemmas can tell them
apart?

**Measurement.** Every word in BHSA (ETCBC/bhsa via Text-Fabric), grouped
by the consonants of its lexeme, Hebrew and Aramaic together:

| Entry | Function readings | Content readings | Content share |
|---|---|---|---|
| עם | "with" 1,071 | "people" 1,881 | 64% |
| שם | "there" 834 | "name" 876, Shem 17 | 52% |
| אל | "to" 5,517, "not" 730, "these" 10, "where" 1 | "God" (El) 235, "power" 5, "nothingness" 1 | 3.7% |
| את | object marker 10,987, "with" 878, "you" 57 | "ploughshare" 5, "sign" 3 | 0.1% |
| על | "upon" 5,870 | "yoke" 40, "height" 9 | 0.8% |

**Decision.** Remove עם and שם: stopping them discarded more content
words than function words. Keep את and על, which are almost wholly
function words. Keep אל for now: its content reading is El (the usual word
for God, אלהים, is a separate lemma and is not stopped), and unstopping it
would admit some 6,250 occurrences of "to" and "not" to recover 235. The
list is now 52 entries.

**Revisit** when lemmas are looked up by pointed form (#483 §2–3, fix C),
which would separate אֵל from אֶל and עַם from עִם so each function reading
can be stopped alone.

**Effect.** The stoplist is applied at search time, so no index rebuild is
needed, but cached Hebrew results must be cleared: the cache key does not
include the stoplist. The classic lemma matcher's automatic mode also adds
a frequency cutoff (the Zipf elbow over the two texts), which can still
stop עם or שם in a long pair; that mechanism is unchanged.

## 2026-09-28 Hebrew stoplist: entries that can never match are removed (#483 §1)

**Observation.** The Hebrew stoplist (`backend/hebrew/stopwords.py`) is
compared against lemmas, but ten of its 64 distinct entries were prefixed
surface forms or forms the BHSA table never gives as a lemma, so they
stopped nothing: ויהי (becomes היה), והנה (הנה), לפני (פנה), אחרי (אחר),
כאשר (אשר), ההוא (הוא), ההיא (היא), האם (אם), אתם (את), אתן (נתן). Three
entries were also listed twice (את, אל, אין).

**Decision.** Remove the ten and the duplicates; the list is now 54
entries (52 after the entry above). Their lemmas were not added in their place. Six (הנה, אחר, אשר,
הוא, היא, את) are already on the list; the other four (היה "be", פנה
"face", אם "if"/"mother", נתן "give") are content words or homographs of
one, and the standing rule keeps content words off stoplists.

**Effect.** None on results: the removed entries never matched a lemma.
The homograph entries (אל, עם, את, על, שם) and the pointed-form lookup
that would separate them are §2–3 of #483 and still open.

**Left open.** The list as a whole is due for review: which Hebrew words
belong on it, including whether any of the four content-word lemmas above
should be, is not settled by this change. The interrogative entry אנה is
kept as it stands although BHSA gives its lemma as אן; אן is not added
until that review.

## 2026-09-27 Persian and Urdu stay in the all-languages Theme Search default

**Question.** Whether the Persian (218,589 windows) and Urdu passage
windows should be left out of Theme Search's default all-languages page,
since Persian alone is more than a third of the index and its two largest
works held most of a page before the per-work composition rule.

**Decision.** They stay in. The page is composed one window per work and
then by language round-robin (see the composition entries), so a large
language no longer crowds the page, and a scholar reading across
literatures should see what the corpus holds without opting in. Anyone
who wants one literature has the language filter.

## 2026-09-27 A work stored as a whole file and as book files keeps only the books' windows

**Observation.** 137 works are stored both ways, and the passage index held
each of them twice: 113,850 whole-file windows beside 112,185 book-file
windows, a third of the 620,773-window index. The same lines were described
and embedded twice under two names. A Similar Passages list could show one
passage twice, the result ranking carried a collapse step to hide that, and
the connections map and every count by work counted these works double.

**Decision.** The book files are the canonical copies (the decision of
2026-09-21, from which the whole files were regenerated), so their windows
stay and the whole file's are dropped. The Reader's whole-work view draws
its gutter marks from the books' windows through the existing whole-work
fallback in `connection_density`, and a selection in that view maps to a
book window the same way. The references are the same line references, so
the marks fall on the same lines.

**Exception.** Eight works have a book file with no windows of its own: a
two-line poem of Catullus, a preface, a set of fragments, fifteen files of
one to five lines in all. The whole file's windows are the only ones
covering those lines, so those eight keep both copies until the fifteen
files have windows. The tool refuses them unless told otherwise.

**Tool.** `scripts/corpus/drop_whole_file_windows.py`, dry run by default.
It backs up the four index files, drops ids, embedding rows, descriptions
and window-text rows in step with count checks, leaves the works' line rows
alone, and reports what it kept and why. Tests in
`tests/test_drop_whole_file_windows.py`. The dry run against the live
index names 129 works and 110,631 windows. The operation and the cache
rebuilds it forces (word index, passage density, connections map) are
recorded in DATA_OPERATIONS.md when run.

## 2026-09-27 Coptic: U+03E2 to U+03EF is the normal form of the seven Coptic-only letters

**Question.** Unicode has the Greek-derived Coptic letters at U+2C80 to
U+2CB1 and the seven Coptic-only letters (ϣ ϥ ϧ ϩ ϫ ϭ ϯ) at U+03E2 to
U+03EF. Which code points should stored Coptic forms use?

**Observation.** The normaliser moved the seven to U+2CB2 to U+2CBF in the
belief that these were the same letters in the Coptic block. Unicode names
them Dialect-P alef, Old Coptic ain, cryptogrammic eie, Dialect-P kapa,
Dialect-P ni, cryptogrammic ni and Old Coptic oou. Because query and text
were moved alike, no search was affected, but every stored form was wrong,
11,722 of 29,323 index lemmas among them, and anyone reading the
dictionaries outside Tesserae received the wrong letters. Twelve texts use
U+2CBB and two neighbours as editorial marks, which the tokenizer counted
as letters, so a mark glued to a word changed the word.

**Decision.** The seven letters stay at U+03E2 to U+03EF, their only code
points. U+2CB2 to U+2CBF are stripped by the normaliser as marks. There is
one normaliser, in `backend/coptic/processor.py`, and the interface and the
build scripts use it rather than copies. Traditional Coptic alphabetical
order, the seven letters last, is kept in the Rare Words Explorer by its
sort key, not by the stored form.

**Consequences.** Every stored Coptic form changes, so the dictionaries and
stoplist are corrected in the same change (`scripts/corpus/restore_coptic_letters.py`,
a one-to-one reversal) and the lemma caches, the Coptic index and the rare
words cache are rebuilt at deploy, recorded in DATA_OPERATIONS.md. Tests:
`tests/test_coptic_letters.py`.

## 2026-09-27 A third shared word raises the score: the sum, not the mean

**Question.** The lemma score sums the rarity (IDF) of the words two lines
share and divides by a corpus term. The code also divided by the number of
shared words, which made the sum a mean. Should it?

**Observation.** Under the mean an extra shared word raised the score only
when it was rarer than the words already counted. Aeneid 1 against Lucan 1
on 2026-09-22, 150 two-word results averaged 0.746 and the two three-word
results scored 0.538 and 0.468 (issue #465). This contradicts Coffee et al.
(2012), which the scorer cites, and the scorer's own docstring at the time.

**Measurement, 2026-09-27.** Lucan book 1 against the whole Aeneid on a test
checkout of main with the divisor switchable, data from production, results
cache bypassed.

Lemma search, at least two shared words, no ceiling: 2,088 results and 50
of the 213 attested parallels under either rule, order only differing.

| | mean | sum |
|---|---|---|
| attested in the top 10 | 6 | 6 |
| attested in the top 50 | 14 | 14 |
| attested in the top half | 40 | 43 |
| mean rank of an attested parallel | 541.5 | 473.1 |
| median rank | 396 | 344 |
| mean score, two shared words (2,058) | 0.704 | 1.409 |
| mean score, three shared words (29) | 0.534 | 1.601 |
| the one four-word result | 0.494 | 1.975 |

Fusion search, every channel, about 204,000 results, 75 s a run:

| | mean | sum |
|---|---|---|
| P@10 | 50% | 60% |
| P@50 | 26% | 28% |
| P@100 | 18% | 17% |
| R@500 | 20.2% | 20.2% |
| R@1000 | 25.8% | 25.8% |
| R@5000 | 41.8% | 41.3% |

**Decision.** The sum. The divisor is the corpus term alone
(`backend/scorer.py`). Both searches improve or hold, and the code again
does what its description and the published method say. Scores roughly
double for two-word matches. Nothing downstream depended on the old scale
in any way the fusion benchmark could see.

**Consequences.** Every lemma and fusion score changes. The results cache
is keyed on the search settings, which the rule is not, so at the rarity
deploy of 2026-09-22 cached searches kept answering under the old rule
until the files were deleted by hand. The rule's name
(`SCORING_RULE` in `backend/score_bounds.py`) is now part of every cache
key, so a changed rule orphans the old entries by itself and no clear can
be forgotten. `tests/test_scorer_rules.py` pins the rules the scorer
promises, including this one and the key. Data: `research/threads/465_measurement/` (kept outside the
repository).

## 2026-09-25 Hebrew: the Stanza fallback is off, and the index is built the way the server runs

**Question.** Words the BHSA lookup table does not have can be handed to
Stanza, an optional analyser, for a guessed dictionary form. Should the
fallback be on?

**Observation.** Stanza is listed in requirements.txt but was never
installed in the production environment, and because the fallback is
optional nothing reported it. The Hebrew index, built where Stanza was
installed, carried its guesses. Live queries did not. Measured on
2026-09-25 by building the index both ways from the same texts: 200 of
305,550 tokens (0.065 percent) take a different lemma with Stanza than
without. Every one is a word the table lacks, mostly rare names and
unusual forms. Installing Stanza on production would load a language model
in each of three web workers, the pattern the query encoder was moved out
of the web app to avoid.

**Decision.** Off unless `TESSERAE_HEBREW_STANZA=1` is set, on the server
and at build time alike (`backend/hebrew/processor.py`). The production
index was rebuilt without it the same day and swapped in, so the index and
the live server now agree on every word. A fraction of a percent of Hebrew
words keep their surface form instead of a guessed lemma.

**Effect.** Jerusalem, the case that started the Hebrew work, is unchanged:
625 postings on one lemma. Tests: `tests/test_hebrew_processor.py`, the
default-off case and the switch.

## 2026-09-25 Part-of-speech classes come from one table per tag scheme, and an untagged word abstains

**Question.** The part-of-speech boost compares the class of a shared word
in the source with its class in the target. Which class does each stored
tag belong to, and what does a word nobody tagged contribute?

**Observation.** Sampling 25 lemma-cache files per language on 2026-09-25
found three tag schemes in use. Hebrew stores Universal Dependencies tags
throughout. English stores Penn Treebank tags in 3 of 14 files and `UNK`
elsewhere, 85 percent of its tokens. Greek stores the nine-position Perseus
treebank code for 42 percent of its tokens and `Unk` for the rest. Latin
stores `UNK` for 82 percent of its tokens and the Perseus code in 4 of 25
files. The normaliser told these apart by prefix. `PROPN` begins with `PR`
and was classed as a pronoun (issue #487). Of the Perseus code only the `N`
and `V` positions were recognised, so seven other word classes became
OTHER, which matches itself. `UNK` also became OTHER, so two untagged words
counted as agreeing.

**Decision.** Each scheme is matched exactly against its own table in
`backend/feature_extractor.py`. Proper nouns and numerals class with nouns.
Auxiliaries and participles class with verbs. The article classes with
determiners. Particles, interjections, exclamations and punctuation are
OTHER. A tag from no scheme, a blank Perseus position, or `UNK` is UNKNOWN,
and a pair with an unknown on either side is left out of both the numerator
and the denominator, so an untagged word neither helps nor hurts. If every
shared word is untagged the boost is 0.

**Effect.** None on live results, because the boost is not in
`enabled_features` in production or in the defaults. Where it is switched
on, a Hebrew name now agrees with a noun rather than a pronoun, and a Greek
adjective no longer agrees with a preposition. The 20 cases in
`tests/test_pos_normalisation.py` are drawn from the stored tags.

**Open.** Whether the boost should be on at all, given how little of Latin
and English is tagged, is not decided here.

## 2026-09-22 A parallel's score is no longer capped at 1.0

**Question.** `backend/scorer.py` ended with `min(score, 1.0)`, so every
result that computed above 1.0 was flattened to exactly 1.0 and results the
scoring had already separated became indistinguishable.

**Measurement.** Lucan book 1 against all twelve books of the Aeneid, lemma
search, `min_matches=2`, run against production. 1,923 results, 47 of them
among the 213 commentator-attested parallels in
`evaluation/benchmarks/lucan_vergil_lexical_benchmark.json`.

| | |
|---|---|
| Results at the ceiling | 317 of 1,923 (16%) |
| Attested parallels inside that block | 20 of 47 |
| Block size within one search | 19 to 35 results, arbitrary order |

Letting the scores through ranks 5 of those 20 first in their block and 13
in the top half. Counting ties at their average rank, attested parallels in
the top ten of a search rise from 5 to 13, and the mean rank of an attested
parallel improves from 54.7 to 52.6.

**Choice.** The ceiling is off by default, in one place
(`backend/score_bounds.py`), read by the scorer, the feature extractor and
the cache key. A caller may still pass `unbounded_scoring: False`.

**Scope.** Smaller than it sounds. `backend/fusion.py` already set
`unbounded_scoring: True` on every channel, and the interface defaults to
fusion, so the search most people run was never capped and already returns
scores up to about 1.43. Only a single-channel search was affected, which is
what a reader gets after changing the match type away from fusion. The
ceiling was an inconsistency between two code paths rather than a decision
anyone made.

**Consequence.** Results cached before this change were scored under the
ceiling. They are keyed on the setting, so they are not found again rather
than served.

**Also corrected.** The scorer's header claimed that more matching words
raise the score. The divisor carries the match count, so they do not. It now
describes the code and points at issue #465 for whether the code is right.

Adopted on the measurement above.

## 2026-09-22 "Rare" is a share of the corpus, not a fixed number of works

**Question.** The rare-vocabulary channel admitted a word as rare when it
appeared in 100 works or fewer, a work being a text with its parts
collapsed. The number was the same for every language.

**Measurement.** Work counts from each language's own index, 2026-09-22.

| language | works | old cut-off | as a share | new cut-off |
|---|---|---|---|---|
| Latin | 744 | 100 | 13% | 89 |
| Greek | 853 | 100 | 12% | 102 |
| Coptic | 180 | 25 | 14% | 22 |
| English | 42 | 100 | 238% | 5 |
| Hebrew | 39 | 100 | 256% | 5 |

100 was chosen against Latin. In English it admitted everything: the
commonest English word appears in all 42 English works, so no word could
fail the test and the channel stopped discriminating. `backend/fusion.py`
already carried the consequence in a comment: 431,000 window matches for
*Paradise Lost* Book 1 against *Hyperion* and 12 GB of memory, which is why
the channel was capped in September. The cap treated the symptom.

**Choice.** 12% of the works in that language's corpus
(`hapax.RARE_WORD_SHARE`), at least 2, falling back to 100 when the corpus
size cannot be read. One share reproduces all three cut-offs that had been
set by hand, including Coptic's 25, which existed because sub-word
tokenisation inflates its document counts. That is what makes it the rule
underneath them rather than a fourth special case. A caller may still pass
`rare_word_max_occurrences` to override it for a single search.

**Not affected.** The sliding scale that scores every result, which is a
continuous inverse document frequency with no cut-off anywhere. The gate
belongs to one channel. The two also count different things: the scale
counts how many times a word occurs, the gate counts in how many works it
appears. Both are now described in `HOW_TESSERAE_SEARCHES.md` under "How
rarity is measured".

**Open, noticed while checking this.** `frequency_source` decides what the
sliding scale counts against. The main search sends `corpus`; the default in
the scoring code is `texts`, meaning only the two texts being compared.
Anything calling the scorer without the setting therefore judges rarity
locally rather than against the corpus. Not investigated yet.

Adopted on the measurement above.

## 2026-09-20 Translations: public domain first, then open non-commercial with attribution (Silius books 9 to 17)

**Decision.**
The Reader's aligned translations come, in this order of preference, from
(1) public-domain texts, (2) translations whose author grants free
non-commercial reproduction, storage, transmission and display, credited
by name on the Reader and in the sources registry, and never included in
the site's own CC-licensed data releases. Silius Italicus, Punica books
9 to 17, is the first case of (2): A. S. Kline's translation
(poetryintranslation.com), whose licence note permits exactly those uses
for non-commercial purposes and asks for attribution. Books 1 to 8 keep
J. D. Duff's Loeb translation (1927, public domain); Duff's second volume
(1934) enters the US public domain on 2030-01-01 and can replace Kline
then if the site prefers a uniform translator.

**Why.** The site is a free scholarly service with no commercial use, so
Kline's terms fit. The alternatives were measured first. Thomas Ross's
1661 verse translation, the only complete public-domain English Punica,
exists as a CC0 EEBO-TCP transcription (A60230: 19,149 verse lines, about
400 small illegible gaps) and could be aligned by book and by proper
names, but it is a 17th-century paraphrase without line numbers, which a
reader of the Latin cannot follow line for line. Kline's section headings
("Book IX:1-38") carry exact Latin line ranges, so his units align to the
Latin at section level with no guessing.

**Rules that follow.**
- Each aligned translation records its source per unit (`unit_sources`)
  so a work with two translators credits the right one on every passage.
- The data releases under Downloads exclude non-PD translations; the
  Reader displays them with the translator's name and a link to the
  source page.
- A future public-domain replacement (Duff vol. II in 2030) is a swap of
  the same units, recorded in `DATA_OPERATIONS.md`.

## 2026-09-20 Theme Search: the reader re-scores all 300 composed rows

**Decision.** The page is
composed as about 100 works with three windows each, in order of each
work's best score with languages interleaved; the reader then re-scores
rows and the page shows the first 25. It used to re-score the first 100
rows. It now re-scores the whole composed list (READER_HEADS = 100 works,
DEFAULT_K = 300 rows; THEME_READER_K still overrides).

**Why.** With the lexical boost in place, measured on the real code path
over the 16-query benchmark: first-ten precision 0.444 at 300 rows against
0.453 at 100 (neutral within noise for sixteen queries; 0.350 against
0.375 on the four held-out topoi). What changes is reach: a work whose
rows sit past the first hundred can now be lifted by the reader. The
Odyssey's recognitions on "a wife or child recognizes someone long thought
dead or lost" sat at rows 146 to 148 of the composed list, unseen; with
all rows re-scored the Odyssey lands at row 15 of the page. Cost: about
9 s a query against 4 s (the reader service accepts up to 400 passages).

## 2026-09-20 Theme Search: a lexical channel over the descriptions, adopted

**Decision.** Theme Search
scores each passage window by the cosine between the query's embedding and
the window's description embedding, plus LEXICAL_BETA (0.02) times a BM25
word-match score over the description text (gist, themes, action steps,
participants, setting), normalised to [0, 1] over the top 3,000 word
matches and zero elsewhere. The confidence band is still computed from the
embedding alone. The composition (one window per work, languages
interleaved, three windows per work) and the reader over the first hundred
rows are unchanged.

**Why.** Four tests on 2026-09-20 with the calibrated Opus judge on the
16-query benchmark (harnesses in evaluation/theme_benchmark/composition_test/,
private):

| change | all 16 | 12 development | 4 held out |
|---|---|---|---|
| shipped page | 0.434 | 0.471 | 0.325 |
| reader over a deeper per-work pool | 0.419 | 0.425 | 0.400 |
| work score by mass of close windows | 0.391 | 0.425 | 0.287 |
| mass relative to work size (blend) | 0.434 | 0.462 | 0.350 |
| lexical channel, rank fusion (harness) | 0.475 | 0.483 | 0.450 |
| lexical channel, light boost (harness) | 0.506 | 0.533 | 0.425 |
| **light boost on the real code path (adopted)** | **0.453** | **0.479** | **0.375** |
| the same with the reader over all 300 composed rows | 0.444 | 0.475 | 0.350 |

**A correction found while re-measuring.** The first four rows come from
an offline harness whose page composition lacked the site's collapse of
overlapping windows, so a passage indexed twice (whole-file and book-file
copies, 130 works) could occupy two of the ten slots and be counted twice.
The real code path collapses them, and its figures are the honest ones:
a gain of 0.019 over the sixteen queries and 0.050 on the four held-out
topoi, positive on both, smaller than the harness suggested. The earlier
negative results (deeper pool, mass, density) were measured with the same
inflation and would only look worse without it.

The case that started it: "a wife or child recognizes someone long
thought dead or lost" returned no Odyssey, although the index describes
Odyssey 23.199 as "a woman recognizes Odysseus through a unique sign". The
encoder ranks the Odyssey 63rd by work for that wording; with the boost it
is 50th on the real path, and its rows sit at 146 to 148 of the 300
composed rows, past the 100 the reader re-scores. With the reader over all
300 rows the Odyssey lands at row 15 of the page. Whether to deepen the
reader (about 9 s a query instead of 4 s; precision neutral) is a separate
decision. Judgements: 236 new Opus verdicts across the tests (about 380k
input tokens).

**Operations.** `scripts/build_desc_fts.py` writes
`data/passage_index/desc_fts.sqlite` (about three minutes) and must be run
after every change to descriptions.jsonl; the app compares the index's
description count with the passage index's and refuses a stale one.

## 2026-09-20 Fusion channels: function words are not matching features, and candidate lists are bounded

**Problem.** One fusion search of Paradise Lost (10,565 lines) against
Hyperion held a web worker at 25.6 GB for over 19 minutes on 2026-09-19,
and the quotation-weight sweep was killed twice at the window stage on
whole-file prose sources. Cause, found 2026-09-20: the lemma, lemma_min1
and exact channels ran the matcher with `stoplist_size: -1`, which meant an
EMPTY stopword set, so "the", "and", "his", "with" (English) and "qui",
"sum", "hic", "non" (Latin) were matching features. Every pair of two-line
windows sharing one of them became a candidate held in memory, and the
list grew with source units times target units. The `lemma` and `exact`
channels also had no result cap, so every candidate was scored in full.

Candidate pairs at the window stage, counted from the lemma caches
(`count_pairs.py`, session scripts 2026-09-20):

| pair | one shared word, as it was | one shared word, function words excluded | two shared words, as it was | two, excluded |
|---|---|---|---|---|
| Paradise Lost x Hyperion | 5,287,486 | 330,358 | 1,380,119 | 7,186 |
| Aeneid x Lucan 1 | 1,142,943 | 584,430 | 115,664 | 28,236 |
| Aeneid x Achilleid | 1,763,321 | 823,283 | 156,892 | 32,655 |
| Aeneid x Metamorphoses | 22,308,739 | 9,145,844 | 2,535,778 | 393,788 |
| Iliad x Odyssey | 61,407,496 | 24,240,161 | 11,133,128 | 1,908,090 |

**Decision (five changes, one PR).**
1. The three channels pass `exclude_function_words` with their
   `stoplist_size: -1`, so the language's curated function-word list
   applies in the matcher, as it already did for Coptic. A user's own -1 in
   the classic search keeps its documented meaning (no stoplist at all). Common content words stay matchable and are
   down-weighted by rarity in scoring (the 2026-09-19 rule, now true of the
   channels as well as the scoring layer).
2. The matcher keeps a bounded candidate list (`candidate_cap`, four times
   the channel's result cap) ranked by the same quick IDF score the channel
   runner's pre-filter used, so memory is proportional to the cap, not to
   the text sizes. The kept set is the one the pre-filter kept.
3. `lemma` and `exact` get the 50,000 result cap every other channel has.
   On the two poetry benchmark pairs it does not bind (28k to 33k two-word
   window pairs); it binds on prose sources against the Aeneid (a 287-line
   Quintilian book produced 783,588 uncapped window results) and on very
   long pairs such as Aeneid x Metamorphoses (394k), where the pairs
   dropped are the lowest by quick IDF beyond the top 200,000.
4. The `dictionary` channel is bounded the same way (cap 50,000,
   candidates 200,000). With `include_lemma_matches` it re-finds every
   pair sharing two content lemmas plus the synonym pairs and had no cap:
   up to 360,126 window results per prose source against the Aeneid, and
   the first after-fix benchmark run was killed at its 12 GB cap in this
   channel's window step for Seneca's Letters, after the lemma channels
   had passed the same step in under a minute at 3 GB.

5. The `rare_word` channel is bounded the same way (cap 50,000). It had no
   cap, and in English "rare" means df <= 100 of only 42 works, so every
   shared lemma counts as rare there: Paradise Lost Book 1 against Hyperion
   produced 431,131 window matches, and the whole poem was killed at a
   12 GB cap in this channel after the other four were bounded. The English
   rarity threshold itself (100 works out of 42) is a separate decision,
   taken on 2026-09-22 and recorded above.

**Not a fusion defect.** salutati.de_laboribus_herculis.tess has 97 units
of median 1,232 words (one .tess line per chapter), so every channel
works on chapter-sized units and the pair against the Aeneid runs for
hours. That is a text-segmentation defect of the file; it is skipped in
the measurement and listed as a corpus follow-up.

**Measurement (2026-09-20, `evaluation/fusion_memory_test/`).** The
quotation-weight harness run twice at the production weight on identical
texts and caches, once with the code at main ("before") and once with this
branch ("after"): 32 verbatim prose quotations of Vergil in Gellius,
Macrobius, Quintilian and Servius; the Lucan 1 and Achilleid benchmarks
against the Aeneid; Odyssey 6 against Argonautica 3.

| gold set | pairs | before: found in top 10 / 50 / 100 | after: 10 / 50 / 100 | channel seconds before -> after |
|---|---|---|---|---|
| prose quotations of Vergil | 32 | 19 / 26 / 28 | 17 / 26 / 28 | 3,260 -> 2,300 |
| Lucan 1 + Achilleid against the Aeneid | 266 | 6 / 14 / 20 | 6 / 14 / 20 | 240 -> 205 |
| Odyssey 6 against Argonautica 3 | 16 | 1 / 1 / 1 | 1 / 2 / 2 | 40 -> 33 |

Peak memory of the whole run: 11.3 GB before, 4.7 GB after (the before
run sat just under its 12 GB cap on the benchmark pairs alone). Poetry
recall is identical pair for pair. In the prose set two quotations moved
from the top ten to the top fifty (Macrobius 4 against the Eclogues,
Servius against the Eclogues), Macrobius 5 against the Aeneid lost one at
50 and one at 100, Macrobius 3 gained one at 50 and Macrobius 6 one at
100; the whole-list counts at 50 and 100 are unchanged. Six more gold
quotations, in Seneca's Letters and De beneficiis as whole files, could
not be run before (the window step blew a 12 GB cap) and now score 4 of 6
in the top ten and 6 of 6 in the top fifty, the Letters against the
Aeneid in 20 minutes at a 4.4 GB peak. English (production's texts and caches, no gold set, the pair that held
a web worker at 25.6 GB for 19 minutes on 2026-09-19):

| pair | before: channel seconds, process peak | after: seconds, peak |
|---|---|---|
| Paradise Lost Book 1 (798 lines) x Hyperion (885) | 126.5 s, 4.38 GB | 33.5 s, 2.19 GB |
| whole Paradise Lost (10,565 lines) x Hyperion | killed at 12 GB before the fix (25.6 GB observed in production) | 102.5 s, 2.83 GB |

Channel counts for Book 1: lemma line pairs 13,101 before (function words)
against 54 after; rare_word window matches 431,131 against 50,000. The
whole poem's top ten after the fix leads with "intestine broil" (Paradise
Lost 2.1001, Hyperion 2.192).

**Why a few prose ranks moved (traced on Macrobius 4 against the
Eclogues with full fused lists).** The gold quotations' own scores are
identical before and after. What changed is competitors: fifteen pairs in
the top 200 rose (1.20 to 1.43, 0.68 to 1.16), all of them adjacent-line
window matches of genuine Vergil quotations. The scoring layer has a
"mixed" penalty: when any matched word is a function word, the pair is
scored like a single-word match with its convergence bonus removed, even
if it shares two or more content words as well. Now that function words
are never among the matched words of the lemma, exact and dictionary
channels, that penalty stops firing for such pairs, and multi-content-word
matches that also shared "et", "qui" or "non" score as content-only
matches. That is the scorer's own stated intent ("function words add zero
allusion signal") applied consistently. It moves genuine quotation
neighbours up beside the gold lines, so per-pair gold ranks slip a few
places among tied pairs, while whole-list recall at 50 and 100 is
unchanged and poetry recall is unchanged pair for pair.

**Deferred.** A request-size guard in `/api/search` (refuse or
queue pairs whose estimated candidate count is too large, with a plain
message) and a memory cap on the web workers (root). Both are visible
behaviour changes.

## 2026-09-20 Theme Search: sample searches are measured winners; a deeper per-work re-ranking pool was tested and not adopted

**Sample searches (PR #419).** The five suggestions on the Theme Search page
for the Latin, Greek and English site are queries that rated "strong" on
production on 2026-09-20 and whose first works are the expected ones: a
guest welcomed with food, wine and a bath; a mother lamenting her dead son;
a warrior arming piece by piece; funeral games (the theme the 16-query
benchmark scores best, first-ten precision 1.00); a storm at sea. The
former chip "a wife or child recognizes someone long thought dead or lost"
rated moderate and did not return the Odyssey's recognitions.

**Why the Odyssey misses that query.** The passage index describes the
scenes accurately (23.199 "a woman recognizes Odysseus through a unique
sign", 19.466 "recognized by his nurse", 16.181 "reveals his identity to
Telemachus"), but the description encoder ranks the Odyssey 63rd among
works for that wording across all languages (25th within Greek), and the
head of the page is one window per work chosen by cosine. Theme Search has
no word-matching bonus: the score is the cosine between the query's
embedding and each description's embedding. The distilled cross-encoder
that reorders the top hundred then places the Odyssey's cosine-best window
(23.232, the reunion and the delayed dawn) low. Wordings that name the
scene's own features find it at once ("a man is recognized by an old scar":
Odyssey at ranks 2, 4 and 5).

**Deeper per-work pool for the re-ranker: tested, not adopted.** On the 16
benchmark queries, judged with the calibrated Opus judge (80 new pairs):
shipped page 0.434 first-ten precision; reader sees all 300 composed rows
0.447; 40 works with 8 windows each 0.419; the same grouped by work 0.388.
Within noise or worse, and none reaches a work the encoder ranks 63rd.
Harness: evaluation/theme_benchmark/composition_test/run_deep_per_work.py.
Ideas still open: a work-level score that pools a work's several close
windows instead of taking its single best, and a lexical channel over the
descriptions fused with the cosine ranking.

## 2026-09-19 Standing rule: stoplists are function words only

**Decision.** A stoplist holds function words (articles,
pronouns, prepositions, conjunctions, auxiliaries, particles) and nothing
else. A common content word such as "summer", "day", "old" or "began" is
down-weighted by its corpus frequency in scoring, never removed from
matching or from the shared-word count. Applies to every language and to
every place a stoplist is used: the search channels, the fusion scoring
layer's function-word penalty, and the Quotation table builder's
commonplace test.

**Consequence found the same day.** The curated English list in
`backend/matcher.py` (`DEFAULT_ENGLISH_STOP_WORDS_LIST`, 202 entries)
mixes function words with common verbs ("know", "take", "make", "go",
"see", "come", "think", "look", "want", "give", "use", "find", "tell",
"ask", "work", "seem", "feel", "try", "leave", "call"). The fusion scoring
layer penalizes those as function words. Adopted 2026-09-19. The list, 275 words (220 plain words plus 50 Snowball contractions and five apostrophe forms, since the tokenizer keeps contractions whole), is the Snowball English
stopword list (Porter's Snowball project, `snowball.tartarus.org/algorithms/
english/stop.txt`, 174 entries, 124 once contractions are set aside), a
published function-word list widely reused (NLTK, Lucene, R), PLUS the
early modern inflections of the same function words that the current list
already carries (thou, thee, thy, thine, ye; art, wast, wert; hath, hast,
hadst; doth, dost, didst; shalt, wilt, canst, mayst, mightst, shouldst,
wouldst, couldst; 'tis, 'twas, 'twere, 'twill, 'twould; ere, oft, unto,
whilst, hither, thither, whence, thence, wherefore, whereon, wherein,
whereof, hereby, herein, therein, thereof; nay, yea, prithee, forsooth,
verily, methinks, lo, behold, alas, ah, oh, o), which follow the pronoun
and auxiliary paradigms of Early Modern English as set out in Charles
Barber, Early Modern English (Edinburgh, 1997) and the Cambridge History of
the English Language, vol. III. Net change against the current 202-word
list: add the 27 Snowball words it lacks (above, again, against, below,
between, cannot, did, does, doing, down, during, further, herself, himself,
itself, myself, off, once, only, ought, ourselves, over, themselves,
through, under, yourself, yourselves); remove the 7 content verbs (get, go,
know, make, say, see, take). No published list combines both parts; the
Voyant/Taporware list, the only common one with early modern forms, has
571 entries including content words (make, take, see, find, thing) and only
three archaic forms (thou, thee, thy). The Latin (102) and Greek (167)
lists to be audited by the same rule.

## 2026-09-19 Quotation channel weight 10 for Latin and Greek (PR #411)

**Decision.** `CHANNEL_WEIGHTS['quotation']` goes from 0 to 10, so the
Latin and Greek fusion profile (`latin_epic`) scores runs of three or more
identical words. The English profile pins it at 0 until measured. Approved
on 2026-09-19.

**Measurement.** A gold set of 42 verbatim prose quotations of Vergil was
built from the corpus's own texts (Gellius, Macrobius, Quintilian, Seneca,
Servius, Salutati; six or more identical words), and the fused ranking was
recomputed at weights 0, 2, 5, 10 and 35 with every other weight unchanged,
against that set and against the two poetry benchmarks the Latin weights
were tuned on (Lucan 1 and the Achilleid against the Aeneid, 266 gold
pairs). Three whole-file prose sources (Salutati, Seneca's Letters and De
beneficiis, 10 gold pairs) could not be run; 32 gold pairs were scored.

| weight | prose quotations found in top 10 / 50 / 100 (of 32) | poetry top 10 / 100 (of 266) |
|---|---|---|
| 0 (before) | 8 / 14 / 14 | 8 / 22 |
| 2 | 11 / 15 / 20 | 8 / 22 |
| 5 | 13 / 21 / 23 | 8 / 22 |
| 10 (chosen) | 19 / 26 / 28 | 8 / 21 |
| 35 (Coptic value) | 24 / 30 / 32 | 5 / 22 |

Greek (Odyssey 6 against Argonautica 3, 16 gold pairs): unchanged at every
weight; the channel finds no identical three-word runs in Homeric echoes.

**Why 10.** It more than doubles first-ten recall of prose quotations for
one Lucan pair lost at rank 100 and none in the top ten. 35 finds every
quotation but pushes three poetry pairs out of the top ten, so it suits a
quotation-first profile, not the default.

**Caveat.** Fusion results are cached per text pair; a Latin or Greek pair
already cached keeps its old ranking until recomputed.

## 2026-09-19 Quotation table builder rules (PRs #404 to #409)

The corpus-wide Quotation table behind the Reader's quotation markers
(`scripts/reuse/build_reuse_table.py`) was rebuilt for Latin, Greek and
English under rules settled by measurement on Latin against the live table
(54,880 strict pairs):

1. Part files of one work count as one work, so a poem's repeated formulas
   across its own books are not "quotation by another work".
2. An n-gram made only of commonplace words (corpus-frequency threshold, or
   the language's function-word list) still counts toward the pair's shared
   total; a pair is dropped only when EVERY shared n-gram is such, and only
   for English (`--drop-all-commonplace auto`). Two stricter variants were
   measured and rejected: counting such n-grams for nothing cost 5,445
   strict Latin pairs, mostly the Fathers quoting the Vulgate; dropping
   all-commonplace pairs in Latin too cost 1,863, including short scripture
   quotations made entirely of common words (John 10.30 in Hilary). The
   English case that started this ("What shall I do?" in Hamlet, matched to
   eight Bible verses) is a function-word run with no content word.
3. Work ids stored as escaped bytes in older Greek lemma caches are decoded
   back to their Greek file names.

Final Latin table: 54,571 strict pairs, the only losses the 309 part-file
pairs of one work. Details and Done lines: `DATA_OPERATIONS.md`,
2026-09-19.

## 2026-09-19 Reader connection gutter: chunked density (PR #403)

The gutter's density computation scored all of a work's passage windows
against the corpus in one block, 2.5 MB per window (5 GB for the Punica,
11.6 GB for the Vulgate). It now scores 256 windows at a time with
byte-identical output (checked on the whole Aeneid). A batch script
precomputes the cache for every work.

## 2026-09-19 English search: why common words rank high (open)

**Observation.** On the default English pair (Paradise Lost 1 against
Hyperion) the fusion search ranks "began, read", "fled, over" and "summer,
day" beside genuine borrowings like "dire event" and "Saturn old".

**Diagnosis.** Two causes, neither a missing stoplist (the scoring layer
already penalizes function words from the curated English list):

1. Rarity is measured per work, and English has 42 works once part files
   are collapsed, so the scale from "common" to "rare" is compressed.
2. English lemmatization is inconsistent across the lemma cache: "began"
   is a lemma of its own in 2 works and "begin" in 28; "fled" 2 against
   "flee" 24; "stood" 2 against "stand" 30; "went" 2 against "go" 34. The
   unlemmatized forms sit almost entirely in Paradise Lost (whole file and
   its twelve part files) and Wordsworth's Prelude, whose lemma caches were
   built with a different lemmatizer setup from the rest of the English
   corpus. In a Milton search, Milton's own past tenses therefore look as
   rare as proper names, and the rarity boost rewards them.

**Check.** The current English lemmatizer, run on Milton's own lines,
returns "begin, flee, stand, sit" for "began, fled, stood, sat", so the
old caches predate it rather than reflect it.

**Action (same night).** Rebuild the whole English lemma cache with the
current lemmatizer, rebuild the English index and its rarity table, rebuild
the English Quotation table, clear the cached search results for English,
Latin and Greek (the Latin and Greek ones also carry the old quotation
weight), and re-warm the default pairs. Recorded in DATA_OPERATIONS.md.
Rarity by lines rather than works stays deferred until an English gold set
exists to measure it against.

## 2026-10-12: file operations are made independent of the web server's locale in code

The web process runs with an ASCII file-system encoding, which Python fixes when it starts, and the server setting that would change it is not to be requested again. Thirty-six Greek texts have Greek letters in their names, so every file call on a text, translation or embedding name goes through `backend/fspaths.py`, which passes UTF-8 bytes to the operating system and returns names decoded as UTF-8. The proof is a two-locale comparison: the same requests (`scripts/review/greek_names_requests.json` and the standard list) sent to a server started in the ASCII state and one started in UTF-8 must give the same answers. Names that an operation only ever sees in ASCII (hashed cache names, index files) were left as they were.


## 2026-10-13: the two Latin spelling folds stay as they are

- Scope: `normalize_latin` in the matcher and the distance filter (one shared function: lower case, v to u, j to i) and in the wildcard search (case kept, v to u, j to i, a final -om folded to -um).
- Decision. Both are kept, pinned by tests (`tests/test_normalize_latin_three_ways.py`). They are not unified.
- Why. The lemma tables hold keys in the older spelling, such as "diuom", so adding the -om rule to the matcher's fold would miss them; removing it from the search box would change what a wildcard search for "servom" finds. Neither change has a user report behind it. If one arrives, the fold that caused the miss is revisited with a recording, as the structural jobs are.

## 2026-10-13: the fallback Latin scanner uses a vowel-length table, not the scanner's guessing modes

- Scope: Latin verse outside the MQDQ table (the table covers 103 works; everything else goes to the copied CLTK scanner).
- Decision. The line is macronized from a fixed table before scanning. The scanner's own guessing modes (dactyl smoothing, the optional i-to-j transform) are left off, and the CLTK macronizer's part-of-speech tagger is not used.
- Evidence (400 lines each of the Aeneid, the Metamorphoses and the Pharsalia, against MQDQ; "correct" means valid and the same pattern, "wrong" means valid and a different pattern):

| Mode | Correct | Wrong |
|---|---|---|
| plain scanner (before) | 32 to 36 percent | 6.5 to 7.2 percent |
| dactyl smoothing | 61 to 66 | 23 to 25 |
| optional transform | 25 to 26 | 19 to 22 |
| CLTK macronizer with tagger, then plain | 47 to 58 | 5.2 to 7.2 |
| macron table, first form, then plain (chosen) | 46 to 48 | 3.5 to 4.2 |

- Why this choice. The meter score is a boost on candidate parallels, so a wrong scansion is worse than none. The guessing modes roughly double the correct lines but quadruple the wrong ones. The tagger gains a few more correct lines than the table on two works but needs the full CLTK stack, which the live site does not carry, and is twenty times slower. The table costs 0.2 seconds per 400 lines and gives fewer wrong scansions than the plain scanner.

## 2026-10-13: dead code is removed, not kept in the tree

`backend/composite_scorer.py` had no importer (checked across backend, scripts and evaluation by the second structural job). It is removed; git history keeps it. The rule from here: a module that nothing imports is removed in its own small change, with the commit named in the CHANGELOG, rather than left for a reader to wonder about.

- Wildcard queries with several operators follow the ordinary precedence, tightest first: NOT, then proximity (~), then AND, then OR, each left to right. Proximity takes two terms, so a NOT inside a proximity operand covers the pair.
- A stoplist built from fewer distinct words than the elbow minimum keeps at most half the vocabulary, the commonest words, and none that occurs in a single unit.

## 2026-10-13: record request timings before any speed work

A day of timings from the live site comes before work on speed, so the effort goes where visitors wait and not where we guess. `backend/request_timing.py` records, for each API request, the time, method, path, status, milliseconds, response size and worker process, in one file per day under the folder named by `TESSERAE_TIMING_DIR` (nothing is recorded when it is unset). It does not record the query string, the request body or the answer, so no text a visitor searched for is stored. The report script collapses ids in paths into one route and ranks routes by total time spent, which is what a visitor waits on across a day.

## 2026-10-13: a lemma's document frequency is a function of the lemma alone

The cache of corpus document frequencies gave a lemma a value that depended on lookup order. The first-seen u/v variant in a batch was queried and its value copied to its partner, and a headword's cached entry was either its raw count or one already raised by its own headword, depending on whether it had arrived as a lemma first. One row measured 2.815 against 3.118 for that reason. The decision is two caches, written once and never revised. Raw is the index's answer for the lemma (for Latin, the larger of the lemma and its i/j partner form, each queried alone, with u/v partners kept in separate calls because the index function sums both spellings and lets partners in one call overwrite each other). Final is the larger of the lemma's raw value and its headword's raw value, one headword step only. The meter and text-pair lookups follow the same rule.

Measured on the nine recorded fusion searches replayed with identical inputs (5,123,959 rows), 10 rows changed, all one pair of lines in two searches (Aeneid 1.98 with Metamorphoses 1.552, fused score 0.7223 to 0.8893). The cause is the chain dextra to dextera to dexter. The old value for dextra was 383 when dextera had been looked up earlier and raised, and 260 otherwise. It is now always 260. Nine searches run twice in one process without clearing the caches give identical rows, the property wanted. Timing of the largest fusion call is unchanged within noise.

## 2026-10-15: two small memos in the Rare Words search, both of pure functions

Rare Words checks the lines of a word's occurrences to decide whether the word is a proper noun and what form to show. Two functions in `backend/blueprints/hapax.py` did the same work for every token of every line: `word_matches_lemma` cleaned and folded the lemma again, and normalized the Greek token again, on each call. They now read two `functools.lru_cache` tables: the folded form of a lemma (8,192 entries) and the diacritic-free form of a Greek string (65,536 entries). Each holds short strings, about 10 MB per web worker at most. Both are functions of their arguments alone (no file, index or setting is read), so a stored value cannot go stale and the answer cannot change. The citation, locus and author/work strings of a result row are computed once per file or reference inside one request (a dict that lives for that request only). Measured on ten recorded pairs, the responses are identical byte for byte before and after, and the median warm time fell from 17.2 s to 1.5 s.

## 2026-10-15: the Place filter matches a whole place name, with the editorial marks allowed after it

The filter text is matched case-insensitively as a prefix of a document's ancient or modern place, and the prefix must end the value or be followed by a comma, a question mark or an opening bracket. A comma alone, the rule first proposed, would have left out the 1 document marked "Rusellae?" and every papyrus whose place carries a nome in brackets ("Karanis (Arsinoites)"), so a search for Karanis would have found none of its 2,000 papyri. The same marks are removed from the names in the Place list, which merges "Rusellae", "Rusellae, bei" and "Rusellae?" into one entry of 155.

## 2026-10-15: passage references are shown as the short locus from the server, never the file's tag

The corpus files tag lines with abbreviations ("thuc. pele. 2.57.1"), and the passage index handed them to pages as `ref_start` and `ref_end`, so each page that printed them showed the tag. The server now adds `locus`, `locus_start`, `locus_end` and `citation` to every passage-index result (one helper, `_short_locus_fields` in `backend/passage_index.py`, built on `format_short_locus` and `build_citation`), pages print `locus` with the tag as hover text, and `client/src/test/noRawRefs.test.js` fails when a component prints a raw `ref_start`, `ref_end` or `ref`.

## 2026-10-16: large pairwise comparisons run in parts under a bounded memory and are never refused

A fusion search of the whole Thebaid (9,731 lines) against the whole Aeneid (9,896 lines) held 38 GB in one web worker, because each channel keeps its candidates for every source line against every target line. The decision is that such a comparison is never refused. Above 4,000,000 source-by-target line pairs the source is cut into consecutive blocks, each block runs the whole pipeline against the whole target, and the rows are merged once. Blocks overlap by one line so the window across a block edge is kept. The passage-context confirmation (top 3,000 rows), the removal of overlapping windows and the merge of the line and window levels run once over the merged rows. Each block keeps at most the best 20,000 rows (or four times the requested maximum) per level. One large comparison runs at a time in a process; a second one waits and the page says so.

A pair's channel score used the word frequencies of the units handed to the scorer, so a block of the source gave different scores from the whole (on a 53-by-40 line test, 588 of 623 rows differed). The scorer and the channel runner's quick-IDF filter now take the two whole texts' units for their counts when running in parts, and nothing changes when they are not given.

Measured on the Thebaid book 1 against the Aeneid book 1 (720 by 756 lines, 200-line blocks): with and without parts, the rows, scores and total are identical, and in the same order once equal scores are put in one fixed order (score, then source line, then target line), which the parts path always uses. Without that order the two lists differ only where scores tie exactly (176 rows of 5,000 swap for an equal-score neighbor; equal-score overlapping windows are kept on one side only). The meaning is that scores are identical up to ties. Whole Thebaid against whole Aeneid, in parts, under a 10 GB cap and without the semantic channel (the encoder is not loaded in the measuring environment): 1,000-line blocks were killed at the cap in the third block; 500-line blocks (20 parts) finished with a peak of 7.4 GB (7.6 GB resident for the Python process, passage index included) in 26 minutes 42 seconds, 3,578,124 candidate rows, best score 60.6161.

A comparison that takes half an hour is announced before it starts, with an estimate, and not only reported while it runs. `GET /api/fusion-estimate` reads the two texts' line counts and returns the pair count, whether the search will run in parts, the number of parts and the estimated seconds. The estimate is `FUSION_SECONDS_PER_MILLION_PAIRS` = 17 seconds per million line pairs, with a floor of 60 seconds. The constant comes from the 2026-10-16 measurement (26 minutes 42 seconds for about 96.3 million pairs) with the semantic channel off, so a search with it on takes longer than the estimate says. When the search will run in parts, the page shows a panel with the number of pairs and the minutes, and two choices: run the full comparison, or choose books. Comparing selected books stays under the 4,000,000-pair threshold and finishes in a minute or two. While the search runs, the progress line gives the part and the minutes left, taken from the time the finished parts took (from the estimate until the first part finishes).

## 2026-10-16: every scholarship result links to one page naming the sources, their terms and the method

A reader who sees a scholarship result should be able to find out what was counted and how it was chosen. The decision is one public page, "Scholarship: sources and methods" at `/scholarship-sources`, and a small "About these sources" link at the head of every place scholarship is shown (the Reader's Scholarship tab, Search One Text, the Theme Search scholarship list, the Events Scholarship tab, the Documents Scholarship block and the Help section), each opening the page at the section that applies. The page is built from the live data, not typed by hand: the journal tables are counted from the two citation databases, the commentaries come from the held files, and the dates are the files' modification times, so the page cannot drift from what the site holds. The terms of each source (public domain and quoted by the sentence for the journals before 1923, licensed and shown as one sentence for Project MUSE) and the text of the methods are fixed in the backend, so the page and the API agree. The figures in the methods are those of the measured rows in the search scope table.

## 2026-10-18: the Greek-Latin evaluation scorer counts distinct words and gives a lone pair no rarity lift

The evaluation scorer (the Greek-Latin path chosen with `crosslingual_scorer=evaluation`, and the benchmark scripts) now counts the dictionary matches of a pair as distinct words, the smaller of the number of distinct Greek and distinct Latin lemmas among the matched pairs, and a pair that rests on one distinct word with no syntax match keeps its rarity multiplier at 1.0 (rule `v2`). No pair is cut. The settings remain `crosslingual_dict_count` (`words`, now the default, or `pairs`) and `crosslingual_lone_pair` (`keep`, still the default, `rare` or `drop`), and `XL_DICT_COUNT`, `XL_LONE_PAIR` and `XL_RARITY_VARIANT` in the benchmark scripts. Before this date the benchmark scripts defaulted to `pairs` and `baseline` while the site's evaluation path already used `v2`, so the two disagreed. A cached evaluation-scorer result carried no count and was computed under `pairs`, so the cache key and the poll job key now always name the count.

Counting distinct words leaves recall unchanged within one pair. On the 412 Knauer pairs the pairs count with the baseline rule found 95, 170, 210 and 264 at ranks 10, 50, 100 and 200, and the words count with v2 found 98, 169, 210 and 264. On the 2,397 Juhnke all-lines rows it was 772, 1,424, 1,698 and 1,995 against 771, 1,424, 1,698 and 1,995 at the same ranks. For Aeneid 1 against Iliad 1 and the other Iliad books, the share of the top fifty rows that rest on one distinct word fell from 51 to 31 percent (613 of 1,200 rows to 374), and Knauer precision at 50 moved from 18 to 16 hits in 1,200 rows, within noise.

The hard cut at the same-language rarity threshold (a word at or under 12 percent of works) was rejected. Of Knauer's 124 gold pairs that rest on one word only 3 clear it, and recall at 50 falls from 41 to 24 percent on Knauer and from 59 to 48 percent on Juhnke. The soft rule keeps Knauer and Juhnke within noise, clears lone-pair rows from the top sixty unlisted Thebaid pairs (56 of 60), and moves the listed gold least. The median rank of the 425 high-confidence listed pairs went from 90,636 to 142,155 under it, against 227,108 and 401,155 under the two alternatives (rarity-cap study, 2026-10-17).

The live scorer is different. It already counts distinct words and has the two-lemma gate, and it is not changed. Whether the live scorer should take the same rule is recorded separately. Decided by the project lead on 2026-10-18.

## 2026-10-18: the Mentions index keeps the oblique-case lemma extension off

The extension (`case_form_extension` in `backend/entity_lemma.py`, `--case-forms` in `scripts/entity_stage3b.py`) adds the table lemma of the oblique case forms of an entity's stems. It adds 1,811 (entity, lemma) pairs and about 9,500 mention lines (136,454 to 145,990, 7 percent), but it lowers precision on the 180 fixed graded pairs from 88.5 to 84.5 percent against the 88.2 percent floor, and a fresh draw of 40 new mentions came out 28 right against a floor of 32. After a stem gate and a model confirmation question, the pairs that remain wrong are other people who share the name's stem (Alcimena for Alcimenes, Harpalos, Britomartis, Pallantion, Melissos), and the model confirms them as names. The live store is therefore the one built without the extension, equal to stage 3a on every graded pair. The extension stays available through the flag for a later pass that handles names which share a stem. Decided by the project lead on 2026-10-18.

## 2026-10-19: documents rank stock-formula hits last, and hide_formulas drops them before their lookups

The formula word lists (`data/documents/formula_words_la.txt`, `_grc.txt`) were not applied because document hits had no rank. Stage 4 gave them one (the default `relevance` sort), so the lists now enter it as a soft penalty: a hit whose matched lemmas all belong to the lemmas of the list's words sorts behind every hit that matched something else, and keeps its place among its own kind. The lists hold surface forms, so each word is lemmatized once and the hit's lemmas are tested against that set. The oldest, newest and region sorts are unchanged. On the Latin sentence "vixit annis plus minus pius in suis dis manibus sacrum bene merenti fecit" all twenty first hits were formula-only before and none are now. On a Greek dating-formula sentence ten of the first twenty change places.

The slow part of a hide_formulas query was not the formula count (cached per matched set, under 50 ms) but the per-hit metadata, restored-word and ranking lookups paid for hits that are then dropped. With no other filter and no restored-word exclusion the count decides a hit's fate alone, so the hits above the threshold are now counted and removed before those lookups run (from 2,000 candidates up). Results and `formulas_hidden_count` are identical on fourteen queries. The remaining time is the index lookup itself.

`data/documents/formula_words_cop.txt` is added for Coptic. There is no Coptic documents index, so it holds function words (the corpus's 300 most frequent lemmas that are in `backend/coptic/stopwords.py`) and no search reads it yet.

## 2026-10-21: Tessa runs Search One Text, People & Places and Events, routed by narrow patterns in code

Three more of the site's pages are searches Tessa runs herself (`backend/assistant/three_searches.py`). Which question reaches which is decided from the reader's words, in code, and not by the model, for the reason the other fast paths are: a routing judgment that is a list of phrases fails visibly and can be tested, and the model-routing switch (`TESSERAE_MODEL_ROUTING`) is off. Search One Text takes a question that names exactly one work (an author with one work counts as that work, an author with several does not, and a book number becomes the `books` argument) and asks what it says about a subject. People & Places takes a capitalized name with a verb of naming ("where is Sarpedon mentioned", "which works name Perusia", "how often does Tibullus mention Delia"), and a lower-case name only when the entry list holds exactly that name. Events takes an event noun with a name ("the siege of Perusia"), and a bare place ("which texts describe Thermopylae") only when the Events page has an event of that name. A quoted phrase, a comparison, a question about the site and a theme question with no work named keep their old routes. Measured over the 100 site questions of 2026-10-21 (`research/assistant/site_questions_60.json` and `site_questions_40b.json`), the routing function gives the same result for all 100 before and after. When more than one entry or event carries the name, or none does, or Search One Text reports nothing resembling the subject, the answer is written in code and no model is called. Where the model writes, it is given a computed fact block, the references of the passages returned and the page's own match band, and the existing guards (citations only from the facts, numbers only from the facts, quoted text only from the facts) cover it. The Events name search was widened to the ancient name of the place, because "Perusia" found nothing while the event is stored with the place "Perugia" and the ancient name "Perusia".

## 2026-10-21: Tessa runs the Inscriptions & Papyri, Coins and Objects searches, and puts English into the documents' own words

The three collection pages are searches Tessa runs herself (`backend/assistant/collections_searches.py`), routed in code like the first three. The signal is a collection word (inscriptions, papyri, coins, a coin denomination, museum objects) together with something to look for. A question about a page or the data ("how do I", "do you have", "come from", a yes-or-no question opening with does or can), a comparison, a question naming two collections, and a question that names one work for Search One Text keep their old routes. Measured over the 100 site questions of 2026-10-21 and the 24 probe questions of the previous change, the new routing function takes none of them. The documents are searched by their own Latin or Greek words and the page cannot search English, so a subject typed in English ("grain") is put into dictionary forms by the gateway model with a one-line instruction and searched in those (sitos), unless the reader marked a phrase ("the phrase dis manibus") or typed Greek. The answer states the words searched beside the words asked, and the control opens the page with the searched words, so the reader sees what was run and can correct it. A reply in the wrong script, or more than three words, is discarded and the words are searched as typed. The findspot is read from the page's own list (`/documents/places`) by its stem, and the commonest spelling that begins with it is taken, unless the exact spelling holds a fifth as many documents as that one. The list holds a stray "Oxyrhynchus" with one document beside "Oxyrhynchos" with 4,400. Coins take a mint through the page's Mint filter when the page lists it and as a word otherwise, and a denomination through the Denomination filter, since "denarii" matches no coin text. Coins and Objects are searched by the words of the question, singular where the question has a plural common noun, because the page matches the start of a word ("mirrors" found 4 objects, "mirror" 7). Five examples are listed with the page's total. The Coins and Objects pages now read the search from the address, which they ignored, so the control is a filled-in search.
