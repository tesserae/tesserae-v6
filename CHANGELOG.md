# Tesserae V6 Changelog

Newest first. Every pull request adds a line here; production data
operations that are not code (index rebuilds, cache rebuilds, corpus
repairs) are listed under "Data operations" with the script that did them,
so the state of the live site can be reconstructed from this file and
docs/DATA_OPERATIONS.md. Method and scoring decisions, with the measurement
behind each, are in docs/DECISIONS.md.

## 2026-10-10

### The Reader's About this text panel and the coin page, in plain words
The About this text panel is one column: the work's name as a heading, one quiet line of date, era, kind and length (each with a plain tooltip), the description at reading width, and the sources as a small footnote ("Text from ... through Perseus. Translation by ...") ending in Full credits. The print edition is decoded for display, and 37 records in `backend/text_sources.json` that held `&amp;` now hold `&`. The coin type page opens with a plain description built from the fields ("Silver denarius of Augustus, minted at Rome, 27 to 25 BCE"), the catalogue's own name for the type under it, Front and Back columns each with Shows and Inscription, Issued by and Portrait in words, and one link, "See coin images at Corpus Nummorum", where there were two. The identifier box is gone and the id sits on the credit line. The list cards use the same headings and a short "See images" link. Help explains obverse, reverse and legend.
### A scope box on every search page
Each search page opens with one grey line, "What this search does", with a Details link. Opened, it gives the search's scope, the texts and collections it covers with live counts, its limits and its measured performance, and links to the search's Help section. It appears on the five Search modes (Phrases, Line, Strings, Rare Pairs, Rare Words), Cross-Language, Theme Search, Inscriptions & Papyri, Events, Coins and Objects, and remembers whether it was open. The facts live in `client/src/data/searchScope.js`, and the Help table "How well does it work?" now renders from the same data, so a figure is written once. A new route, `/api/scope` (site-only in the connector manifest), answers the counts: works per served language, documents, passage windows, events, coins and objects, cached for ten minutes.
### Start here: smaller, feature names first
The Start here panel took the top of the Search page with six boxes. It is now one short card with the feature's name and a half-line of what it does ("Line Search: every line in the corpus where a phrase or a pair of words occurs"), three to a row, with Skip beside the question. The Collections button in the menu bar is now shown to every visitor, so the inscriptions, papyri, events, coins and objects the panel names can be switched on from the top of the page; the default profile is still Literary.
### Research moves under About
The Research entry leaves the main menu (most visitors will not look at the project's studies regularly). The page stays at /research and is reached from a Research block on the About page, beside Text Credits.
### Coins: a Latin passage's related imagery comes from the Roman catalogues
With the seven Greek catalogues installed, the Reader's Coins tab ranked every description for every passage, and on the ten Latin test passages the Greek types took 27 of the 50 top-five places with about three real matches (Persian kings for Actium, Dionysus heads for the Ara Pacis), so the measured hit rate fell from 0.34 to about 0.26. A Latin passage now ranks the two Roman catalogues only, which restores the measured lists; a Greek passage searches all nine. The operations record marks the Greek coins and Objects installs as run and drops a duplicated entry left by a merge.

### Start here: the collections answer switches every collection on
The sixth answer on the Start here panel ("Search inscriptions, papyri, events and coins") opened the Historical profile, which has no coins or objects. It now opens the Everything profile, so every collection it names is on.

### Greek coin types in the Coins collection (in testing, off by default)
The Coins page now lists 106,176 Greek and Roman coin types. They are the 58,715 Roman types and 47,461 Greek types from seven catalogues published through nomisma.org (IRIS 13,399, Corpus Nummorum 11,913, Seleucid Coins Online 8,694, PELLA 7,228, Ptolemaic Coins Online 3,650, BIGR 2,107, Levantine Coinages Online 470), under the Open Database Licence except Corpus Nummorum (Creative Commons non-commercial, share-alike). The Source filter shows each under a short label and each card carries its own credit line. The converter takes any number of `--dataset CODE=PATH` arguments and a new `scripts/coins/fetch_nomisma.py` downloads a catalogue's type records. A Greek legend can be typed without accents or with either sigma, and Latin look-alike capitals inside Greek words (a Latin B and A in a Seleucid legend) are read as Greek. The Help section, the Coins page text, the collection blurb and Tessa's description of the site say "Greek and Roman". `embed_descriptions.py` gains `--rows-out`, which lists each distinct description with the types that carry it (46,244, of which 19,783 are new). Seven credits records were added. The data file is rebuilt and installed by the steps in docs/DATA_OPERATIONS.md.
### Tessa's holdings sentence is built per request, and the coins data is installed
Tessa named only Latin, Greek and English for most of the day. Her prompt module built the holdings sentence when it was imported, before the language plugins register, and the ten-minute cache kept that version because the web workers recycle before it expires. The sentence is now built when she answers and a version naming no optional language is never cached. The records of the coins installs (database and description vectors, both run) are updated.
### Objects: museum catalogue descriptions as a collection (in testing, off by default)
A new Objects collection holds 1,361 Greek, Roman and Etruscan objects with the museum's own catalogue description: 305 from the Cleveland Museum of Art (CC0), 395 from the Art Institute of Chicago (records CC0, descriptions CC BY 4.0) and 661 from the Smithsonian (CC0, the National Museum of Natural History's Greek vases and Roman lamps). An object is kept when its record has a description or note of at least 40 characters. Coins are left out, because they have their own collection. The Objects page (`/objects`, `/objects/<id>`) searches titles, descriptions, labels and inscriptions and filters by museum, object type, culture, material and date. Each card carries the credit line and licence and links to the museum's own record, and shows the museum's image only where it is free to reuse. Theme Search gets an Objects choice beside Coins, ranking the description vectors on their own, never mixed into the passage list. Objects is switched on by the Archaeological and Everything profiles. The data and vectors are built offline (`scripts/objects/`) and are not in git. Not installed on the live site until the steps in docs/DATA_OPERATIONS.md are run.

### Coins tab in the Reader and a Coins choice in Theme Search (in testing, off by default)
With the Coins collection on, the Reader gains a Coins tab. "Named on coins" lists people named on a coin type (as authority or obverse portrait) and in the selected Latin lines, labelled as a name link and not an echo, each linking to the coin list for that person. "Related imagery" lists the five coin descriptions nearest the gist of the covering passage window, found through the query encoder service with a cosine against 26,461 description vectors, each with a confidence level and the measured hit rate of about one in three (17 of 50 on ten test passages). Theme Search gains a Coins choice that searches the coin descriptions on their own and shows a separate list. New routes `/api/coins/for-passage` and `/api/coins/theme` and a `person` filter on `/api/coins` (all site-only in the connector manifest), `scripts/coins/pack_descriptions.py` and `scripts/coins/measure_for_passage.py`, and the hand-written Latin name table `backend/coins_authority_names.json`. The vectors are installed by the steps in docs/DATA_OPERATIONS.md.
### Line Search: "whole phrase" means the phrase as typed
The first form of the closeness tag counted only the query's content words, and the lemma search drops common words such as "sit" and "tibi", so for "sit tibi terra levis" it marked 23 of 36 lines as the whole phrase, Caesar's "levibus cratibus terraque" among them, and put Martial's "Sit tibi terra leuis" twelfth. A line is now a quotation only when it also carries the query's own words in surface form, common ones included, with at most one inflected or missing. The tags say "key words" when common words were dropped ("key words together", "key words apart", "1 of 2 key words"), and the Closest match order ranks by quotation, then by how many of the typed words a line carries, then by the width of the window holding them, then by date.
### Search: a work against itself shows where it repeats itself
Comparing a work with itself on the Search page returned every line paired with its own twin. When source and target are the same work in the same unit, a line is no longer paired with itself and each pair of lines appears once, the earlier line as the source, so the list shows the phrases the work repeats.

### Start here: a front door on the Search page
The Search page asks a first-time visitor what they are trying to do and opens the right search; a header link brings the question back; Tessa answers 'where do I start' with the same six choices.
### Events: the best-attested events first, empty ones hidden
The Events list opened on the earliest events in the database, several of them with no passage and no document attached. It now opens on the events with the most attached passages and nearby documents (an Order control offers the chronological order), leaves out the events with neither until a box is ticked, says how many it left out, and shows the count of each type in the Type menu. Four Wikidata items with no label beyond their identifier are no longer listed.
### Tessa describes what the server holds from its own state
Asked what the site holds, Tessa named five languages from a fixed sentence in her prompt, written before Persian, Urdu, the inscriptions and papyri, the scholarship and the events were added. The sentence is now built when she answers, from the same checks the site makes: the language flags and text folders behind the language tabs, the documents indexes, the scholarship data and the events database, with the coins collection named once its database exists. A test holds the helper to the languages route so the two cannot drift apart.
### Line Search: lines that quote the phrase come first
A search for several words ("sit tibi terra levis") listed its literary hits by era, so lines sharing one word of the phrase stood above lines quoting it. Each literary hit now carries how many of the query's content words it shares and whether it has them all within a short window (a near quotation). A query of two or more words opens on a "Closest match" order (quotations first, then lines sharing more words, then the older text) with a tag beside each line ("whole phrase", "3 of 4 words"); By Era and A-Z remain. On the Inscriptions & Papyri page the "Both" search now shows the documents first and the literary companions after them, ranked the same way and folded to five until opened.
### Coins collection with a Coins page and search (in testing, off by default)
A Coins page lists 58,715 Roman coin types (56,113 from OCRE, 2,602 from CRRO, nomisma.org, ODbL), searchable over legends and descriptions and filterable by authority, mint, denomination, material, source and date, with a detail view for each type and a link to the type's own page for specimens and photographs. The new `scripts/coins/build_coins_db.py` writes the SQLite file (FTS5 index) that the new `/api/coins`, `/api/coins/facets` and `/api/coins/<id>` routes read. The converter now also records each type's obverse portrait and region. Coins is a collection switch, on in the Archaeological and Everything profiles, and the menu entry and page follow it. Help gains "Coins (in testing)". Tests cover the loader and API on a 12-type fixture, the page, the menu gate and manifest parity. The data file is built and installed by the steps in docs/DATA_OPERATIONS.md.

### Usage summary: referrers from real browsers only, rotated logs read, one bot list
A referring site now counts only when the referred address also loaded the application that month, which removes forged referrers sent by scanners. The script reads rotated copies of the access log (plain or compressed) before the current file, and takes its bot list from the module the page-view route uses.

### Reader: the key folds away, and the inscriptions box opens the Reuse tab on the inscriptions
The key to the marks in the text (gutter colours and the quotation boxes) took three rows at the top of the Reader. It is now one slim row with the two colours and a Key button that opens the rest, remembered in the browser. Clicking the amber box on a line (quoted in that many inscriptions or papyri) opens the Reuse tab with the inscriptions and papyri first and the literary quotations below under their own heading, where before the literary quotations came first.

### Tessa leaves beta
The "beta" tag on the assistant's header is gone. A live check of twenty-one questions covering what the Help page promises (holdings by language and author, where a phrase occurs, comparisons within and across languages, how the site works, follow-up questions) was answered correctly throughout after the fixes of 10 October. The translations fact she reads now names the translation's language, so she no longer calls an English translation a Latin version.
### The site records each visit's pages in its own database, and the admin panel shows the paths

Each page a browser opens during a visit is now recorded in a new `page_views` table in the site's own database, with the visit's random token, the page, the language, the outside referrer host, and the city and country the address suggests. The city and country are looked up once per visit, in the same way the search log does it. The admin Analytics tab has a new section, "Paths through the site", and the About page now says what the site records.

### Tessa's collapsed button reads "Tessa"
The closed assistant was a red circle with a bare T at the bottom right of the page, which told a first-time visitor nothing. It is now a pill of the same height that reads "Tessa".
### Latin verse scansion on every server: the CLTK scanners carried in the backend
The hexameter, pentameter and hendecasyllable scanners from the Classical Language Toolkit (MIT licence, eleven pure-Python modules) now live in backend/prosody_lat and are used when the CLTK distribution itself is not installed. The production server had no CLTK (its dependencies run to several gigabytes), so every verse outside the precomputed MQDQ table went unscanned. Verified in the production environment: Catullus 1.1 scans as a valid hendecasyllable.
### Admin panel: visitors and feature use from the web server log
The Analytics tab now has a section headed "Visitors (from the web server log)" with the addresses that loaded the application each month, the addresses that made a request, request totals, feature use by month, and the main referring sites. The existing tab reads only the search log table, which misses everyone who browses without searching. A script, `scripts/usage/build_usage_stats.py`, reads the access log once and writes a small JSON summary that a new route, `GET /api/admin/usage`, serves to administrators. Robots and the server's own addresses are removed. The summary is built by hand until the nightly timer is installed.

### Metre scanner: a missing scanner is reported once, not once per verse
On the production server the optional CLTK prosody modules are not installed, so every verse offered to the hendecasyllable scanner raised an error that was written to the web server's error log, thousands of lines per search, 22 GB by October. The scanner now returns no scansion for a metre it cannot scan and writes one warning per process.
### Tessa: two-title comparisons, Greek-Latin pairs, the Scholarship tab, translations of a work, and a quieter number check

A question that names two titles, such as Thebaid 1 and Aeneid 1, now resolves to those two works instead of one author's Silvae. A Greek-Latin pair, or any pair the Cross-Language tab serves, now runs the cross-language comparison the way a same-language pair runs, and when it does not finish she names the pair and links the Cross-Language tab with both texts chosen. Her Help excerpt now carries the Scholarship tab, the Collections button, Inscriptions and Papyri, and Events, and a question about the translations of a named work is answered from the site's record of aligned translations. The number check reads 1,326 as one number and no longer flags number words that count a listing.

### Tessa lists a language's holdings when asked what the corpus holds in Persian, Urdu, Greek or Coptic

A question about Persian works made Tessa look "Persian" up as a work name and name a Greek play. A question about holdings in one language is now answered from that language's listing with the authors and titles, and Arabic is reported as not served.

### Site subtitle becomes "Literary and Historical Discovery"
The header line under the title, and the two citation forms on the About page, read "Literary and Historical Discovery" in place of "Intertextual and Literary Discovery", since the site now serves inscriptions, papyri and events beside the literary texts. Chosen by the project lead on 2026-10-10.

### Sources and credits: coverage of the journal index, Wikidata for the Events page, photographs as links
The record for JSTOR Early Journal Content now says what the offline index covers (24 journals, 1827 to 1922, 29,055 articles read, 5,193 citing 437 held works, plus 956 sentences citing 742 inscriptions and papyri) and no longer calls it a live service. New records: Wikidata (CC0) for the Events page, and the photographs of inscriptions and papyri, which are links to the holding institutions and never copied. The Help page's Scholarship, Events and Inscriptions sections carry the same facts, and a document's Scholarship section says where its sentences come from. The table of literary texts drops four stale "World English Bible" rows (the files hold the King James text) and gains the King James New Testament. Data operation: seven Studies in Philology articles re-dated from 1992 to 1922 in the citation index.

## 2026-10-09

### Roman coins prototype: converter for OCRE and CRRO type records (draft, nothing loaded into the site)
- `scripts/coins/convert_ocre.py` turns the 58,715 OCRE and CRRO coin types
  (nomisma.org export, ODbL) into the documents collection's intermediate
  JSONL, one document per type, with kind `coin`, legends as the indexed
  text, the obverse and reverse descriptions kept separate, mint with a
  Pleiades id, dates, authority, denomination and material. Two further
  scripts embed the descriptions and query them with literary passages.
  `data/sources_credits.json` gains records for OCRE and CRRO.

### Inscription and papyrus pages gain a Scholarship section of journal sentences that cite the document
- `scripts/documents/build_document_citation_index.py` runs the document-citation recogniser over the Early Journal Content full text and the commentary notes, links each reference to documents through their stored edition references, and writes `data/citation_index/document_citations.db` (one row per citing sentence and document). `GET /api/documents/<id>/scholarship` returns citation, one excerpt and a link (JSTOR stable address, or the commentary file), newest first, with a count. `/document` shows a Scholarship section under the text when there is at least one hit. The route is site-only (not a connector tool). Without the index file the section does not appear.
### Theme Search: optional "in this author or work" restriction
- `/api/passages/theme-search` takes `author=` (one author id, all that author's works with passage windows in the chosen languages) and `works=` (comma-separated work ids). An unknown author or work answers 200 with an empty result and a `note`. A restricted search returns a flat list of passages, up to 10 per work when several works are involved and no cap for a single work, and states that confidence is not rated, because the confidence figures were fitted to corpus-wide queries. The Theme Search page has a "Search within" picker (Author, then Work) that is closed by default, shows the restriction in the results header, and carries it in the address. The `theme_search` connector tool accepts the same two parameters. Measurement and cap choice are in docs/DECISIONS.md.
### Tessa: the cross-language pair list matches the search again
- The search has offered Persian with Urdu, Arabic with Persian and Arabic with Urdu since 5 September, and the assistant's own list of pairs had not been told, so its test against the search's list failed. The three pairs are added; Persian with Urdu is marked as reachable from the Cross-Language tab, the two Arabic pairs as supported while the Arabic texts are held back.
### Reader: the selection popup sits under the selected line on every path; legend names the inscriptions marks
- The popup used to sit at the top of the pane, over the opening lines, when the selection came from a click on a quotation mark or from a URL, because those paths set no anchor; the line is now measured from the page. With the documents trial on, the legend gains the two amber inscriptions marks (quoted in that many inscriptions or papyri; possible echo), which had no entry and could be read as the grey "possible echo" mark.
### Inscription and papyrus pages: image links named by institution, dead hosts hidden, moved addresses rewritten
- The Images list on `/document` shows "Photo F034014 at Epigraphic Database Heidelberg" style labels (address in the href and title) and omits links to hosts that no longer serve them, with a note giving the count. Labels and the dead-host list are in `client/src/components/documents/imageHosts.json`. `scripts/documents/image_url_rules.py` holds the rewrite rules (old Heidelberg photo host, old CIL photo files) and the extractor applies them; `scripts/documents/fix_image_urls.py --dry-run|--apply --db PATH` fixes an existing metadata.db (backup first).
### Reader: the inscriptions mark no longer overlaps the line
- With the documents trial on, a line can carry both the "quoted in N works" mark and the amber inscriptions mark, and the mark column fitted one: the second sat over the text (Aeneid 1.1). The column is wider whenever the trial is on, so every line keeps the same left edge. The mark's tooltip says "papyri", not "papyruses".
### Documentary reuse: phrases common across the literature discounted, word order no longer required
- `scripts/reuse/build_documents_reuse_table.py` gains `--max-literary-works N` (a single-phrase pair is dropped when its phrase occurs in more than N distinct literary works; pairs sharing two or more phrases are kept whatever the phrase's currency), an order-free rule (three content lemmas within six tokens in any order, so the Pompeian fullers' parody of Aeneid 1.1 is found), a candidates cache for threshold sweeps in seconds, and per-work pairs per thousand lines in the stats file. Installed at N=10 (see DATA_OPERATIONS). `backend/reuse_documents.py` admits order-free pairs (their jaccard is 0 by construction) when the table carries a `rule` column, so the Reuse tab shows them as "possible".
### Events page (in testing): a focus view for a battle, siege or treaty
- New `/events` list and `/events/<id>` focus view with Passages, Inscriptions & Papyri, Scholarship and Map tabs, read-only `GET /api/events` and `/api/events/<id>` over an offline dossier SQLite (`TESSERAE_EVENTS_DB`, default `data/events/event_dossiers.sqlite`, built by `scripts/events/load_dossiers_sqlite.py`). Shown when Collections has Inscriptions, Papyri or Scholarship on (`PAGE_NEEDS.events`). The Reader shows a link back to the event when opened from it. Help gains a paragraph.
### Scholarship tab: an expired CORE key no longer switches CORE off
- On a 401 or 403 the full-text search retries CORE once without the key, paced to CORE's keyless limit across workers, and says the key needs renewing while results keep coming. A 429 waits and retries once. `scripts/ops/check_scholarship_keys.py` and timer templates in `scripts/ops/systemd/` check both keys weekly.
### Xenophon, Hellenica and Cassius Dio, Roman History 36 to 55, added with English translations
- `xenophon.hellenica` (1,146 lines, seven books) and `cassius_dio.roman_history`
  (4,403 lines, books 36 to 55), each as a whole-work file plus one file per
  book (29 `.tess` files), from the Perseus canonical-greekLit TEI
  (tlg0032.tlg001 and tlg0385.tlg001, CC BY-SA 4.0), converted by the new
  `scripts/corpus/perseus_greek_history_to_tess.py`. Dio's tables of contents
  at the head of books 37 to 55 are chapter 0, and eleven words broken across
  a printed page are rejoined. Perseus's Greek for Dio begins at 36.18 and
  stops at 55.9.4.
- Translations: Brownson's Loeb (1918 to 1921) for the Hellenica, from the
  Perseus TEI, exact by book.chapter.section, 1,146 of 1,146 lines
  (`scripts/translations/align_hellenica.py`), and Cary's Loeb (1914 to 1927)
  for Dio from LacusCurtius, exact by chapter and section, 4,384 of 4,403
  lines, the other 19 being the tables of contents
  (`scripts/translations/align_dio.py`).
- Descriptions, provenance rows and a Dio date entry added. Production
  steps are in docs/DATA_OPERATIONS.md under the 2026-10-09 entry for these
  two works. Nothing has been run on production.
### Collections control replaces the trial switches
- A "Collections" button in the main menu turns literature, inscriptions,
  papyri, scholarship (and later coins and objects) on and off and sets four
  profiles (Literary, Historical, Archaeological, Everything). The choice is
  saved in the browser; Literary is the default and matches the site as it
  was. The Reader's Scholarship tab, the Reuse tab's inscriptions and
  papyri group, the Inscriptions & Papyri page and menu entry, and the
  Browse Corpus documents view follow it. `?documents=1` and
  `?scholarship=1` still work. See docs/COLLECTIONS.md.

### Scholarship tab: Semantic Scholar snippets read in their real shape, one source's failure no longer takes the tab down
- The snippet endpoint returns authors as name strings and carries no
  year, venue or identifiers, with the DOI only inside the open-access
  disclaimer. The reader expected dicts and raised, and the whole
  `/api/scholarship` route answered 500 while a key was set. It now accepts
  both shapes, reads the DOI from the disclaimer, spaces requests at one a
  second with one retry after a 429, and any unexpected answer from one
  full-text source is logged and skipped with a warning in the response.
### Documentary reuse build reads one literary cache at a time
- `scripts/reuse/build_documents_reuse_table.py` loaded every literary lemma
  cache at once, and the Greek build stalled at its 12 GB memory cap. It now
  lists the corpus files first and loads one cache at a time. The Latin
  table it builds is identical to the live one (6,769 pairs), with peak
  memory 1.9 GB.
- The build now also drops pairs that share fewer than two distinct content
  lemmas (lemmas not on the new `data/documents/function_words_la.txt` and
  `function_words_grc.txt`, taken from CLTK's stopword lists) or whose longest
  contiguous run of shared lemmas is shorter than two. A hand check had found
  87% of Greek and 70% of Latin pairs were coincidences sharing only function
  words. Numerals count as non-content (Latin and Greek cardinals, ordinals and
  distributives on the lists, Roman numerals and Greek alphabetic numerals
  recognised in code). Pair counts: Greek 11,124 to 1,509, Latin 6,769 to
  3,412. Options
  `--min-content-lemmas`, `--min-run` and `--no-quality-filter`. The pairs
  table gains a `content_shared` column, which the Reader route ignores
  because it selects columns by name.
### Sources and credits for every collection
- New "Sources and credits" section at the top of the Text Credits page, grouped by collection (literary texts, translations, inscriptions and papyri, scholarship, places and identifiers), built from `data/sources_credits.json` through `/api/sources-credits`. It names each source with its licence, version and retrieval date, including the four document sources (EDH, papyri.info, I.Sicily, EDR), the commentary collections, the scholarship search services, Pleiades and Trismegistos. The Help paragraph on inscriptions and papyri now names the licences. Every future import adds one record to the file (rule in docs/DATA_OPERATIONS.md).

### Scholarship tab: offered by the language of the work, not of the commentary
- `/api/scholarship/sources` listed the languages commentaries are written
  in (mostly English), so the Reader hid the tab on Greek works annotated in
  English. It now lists the languages of the works commented on, with
  scripture commentaries counting for every language that holds a Bible
  version. On current data: Latin, Greek, Hebrew, English and Coptic.

### Inscriptions & Papyri: a page of its own, papyri grouped by nome, impossible dates excluded from the century facet (#724)
- New route `/inscriptions-papyri`, shown in the main navigation beside
  Theme Search only when the documents trial is active (server
  `TESSERAE_DOCUMENTS=1` and the client's `documents_trial` session flag,
  set by `?documents=1`). The page redirects to the main search when the
  flag is not set. It combines the documents-collection search (filters,
  restoration/formula options, ranking, totals, paging, the century/region
  chart) with the browse-by-facet view on one page. The search logic moved
  out of `LineSearch.jsx` into shared code under
  `client/src/components/documents/` so Lines search's own "Documents"/
  "Both" option (kept as a secondary route) and the new page share one
  implementation. Help & Support gained a short section on the page and
  its sources.
- Browse Corpus's Documents section now groups papyri by nome (the
  Egyptian administrative district, e.g. "Arsinoites"), with the town or
  village a document names (the findspot, e.g. "Karanis") nested under it.
  The old flat region level put a document naming only a town and one
  naming only its nome in two unrelated top-level buckets (checked
  2026-10-09: Oxyrhynchos the town and Oxyrhynchites the nome, 4,440 and
  1,637 documents, now one "Oxyrhynchites" group of 6,081). The nome comes
  from HGV's own structured field where the raw papyri.info corpus records
  it (`data/documents/papyri_nome_map.json`), with a fallback to the
  document's own text when that names the nome directly. See
  `docs/DECISIONS.md` for the full before/after top-20 counts.
- The century facet's earliest buckets ("31st century BC", "16th century
  BC", "13th century BC") are gone. All 8 documents behind them were
  source-data errors, not genuine early material: one EDR epitaph and 7
  `O.Trim.` ostraca from an otherwise correctly Roman/Late-Antique-dated
  series. A `date_not_before` earlier than 1000 BC now files under a new
  "Date uncertain" bucket. Genuinely early 7th/8th-century-BC inscriptions
  keep their own bucket. See
  `docs/DECISIONS.md`.

### Diodorus Siculus (books 1 to 5, 18 to 20), Procopius' Wars, Zosimus and four Plutarch Lives added with English translations
- `diodorus_siculus.bibliotheca_historica` (4,166 lines, books 1 to 5 and
  18 to 20), `procopius.wars` (7,240 lines, eight books), `zosimus.historia_nova`
  (1,071 lines, six books), each as a whole-work file plus one file per book,
  and `plutarch.lysander` (155), `plutarch.dion` (388), `plutarch.eumenes` (98)
  and `plutarch.demosthenes` (130) as one file each: 29 `.tess` files. The
  Greek is the Perseus canonical-greekLit TEI for Diodorus (tlg0060.tlg001
  grc5 and grc6, the Teubner texts), Procopius (tlg4029.tlg001, Dewing's Loeb
  Greek) and Plutarch (tlg0007, Perrin's Loeb Greek), and First1KGreek for
  Zosimus (tlg4084.tlg001, Mendelssohn's Teubner of 1887). All are CC BY-SA
  4.0. Diodorus books 11 to 17 are left out. `scripts/corpus/perseus_greek_history_to_tess.py`
  gained `--no-book` for the Plutarch Lives, drops an English source label
  (the "Unknown" Perseus puts after two quoted lines of the Lysander) and
  removes three stray question marks inside Greek words.
- The Zosimus Greek is an OCR of the Teubner scan and has 20 places where a
  letter was lost ("??" in the file). `scripts/corpus/repair_zosimus_procopius_text.py`
  restores 18 words and drops 2 unreadable consular numerals (6.2.1), and
  puts a space back at two places in Procopius where a combining breathing
  joined two words.
- Translations: Oldfather (books 1 to 5) and Geer (books 18 to 20), Loeb, from
  LacusCurtius, exact by book.chapter.section, 4,158 of 4,166 lines
  (`scripts/translations/align_diodorus.py`). Dewing's Loeb of the Wars from
  LacusCurtius, exact, 7,240 of 7,240 (`align_procopius.py`). Perrin's Loeb for
  the four Lives, from the Perseus TEI, exact by chapter.section, 771 of 771
  lines (`align_plutarch.py`). Zosimus from the Green and Chaplin translation
  of 1814 (Internet Archive scan, OCR), which has no chapter numbers, so each
  Greek line is mapped to an English paragraph by dynamic programming and the
  file is marked approximate: 1,071 of 1,071 lines in 314 blocks
  (`align_zosimus.py`).
- Descriptions, provenance rows and dates (Diodorus, Procopius, Zosimus) added.
  Production steps are in docs/DATA_OPERATIONS.md under the 2026-10-09 entry for
  these works. Nothing has been run on production.

## 2026-10-08

### Reader About panel in two columns, Scholarship tab on one line, documents deep link fixed
- The Reader's "About this text" panel is now two columns on wide screens
  (one on phones): the description, and a facts list (author, work, date,
  era, kind, line count, print and digital edition, attached translation,
  with a "Full credits" link), each row left out when there is no data for
  it. `GET /api/text-descriptions` carries the facts additively.
- The results panel's tab row (Similar, Parallels, Translation, Reuse,
  Scholarship) now fits one line at the panel's normal width instead of
  wrapping the fifth tab to a second line; it scrolls horizontally rather
  than wrapping if a narrower width still will not fit them all.
- The Scholarship tab (behind the `?scholarship=1` trial switch) now
  offers itself only for a language the site actually holds secondary
  scholarship for, read from `GET /api/scholarship/sources`' new
  `languages` field instead of a fixed list.
- `/line-search?documents=1` now opens directly in "Input Search Text"
  mode, where the Literature/Documents/Both control lives, instead of
  landing on "Find Text to Search". The `documents=1` and `scholarship=1`
  trial switches are now captured once when the app itself first loads, so
  either holds for the rest of the visit even from a page other than the
  one that reads it.

### Reader "Shared names": a Greek name no longer cut short by a misplaced accent
- `window_texts.db` stores some accents and breathings as combining marks
  separate from the letter they belong to, and sometimes standing BEFORE
  that letter rather than after it. The names-panel tokenizer treated any
  combining mark as the end of a word, so a name cut short at the first
  such mark: "Αναυ" for the river Anauros, "Ηρακλη", "Ποσειδα", "Ελλα",
  "Υψιπυ". `scripts/corpus/build_window_names.py`'s la/grc/en pass now
  normalizes each window to NFC before tokenizing, moving a leading
  combining mark onto the letter it belongs to first so NFC can compose
  the two, and its token regex continues through any combining mark NFC
  had no precomposed form to fold into. A full copy of production's
  `window_texts.db` rebuilt both ways: 61,048 of 74,365 named Greek
  windows changed (15,587 Greek name keys before, 17,712 after), 1,517 of
  130,342 named Latin windows changed (quoted Greek inside a Latin text),
  and English, Hebrew, Coptic, Persian and Urdu were byte-for-byte
  unchanged. The generic mark-repositioning rule was tried over Hebrew,
  Coptic, Persian and Urdu too and reverted: their own tokenizers already
  include each script's combining-mark ranges in the word regex, so none
  of them had this truncation, and the repositioning rule actively broke
  one Hebrew case (the traditional free-standing "Jerusalem" hiriq) by
  moving it across a letter boundary it does not belong on either side
  of. Tests added (`tests/test_build_window_names_marks.py`).

### Reader header and selection bar: a citation for the open work, not a split abbreviation
- The header and selection toolbar read "A, R 1.1" for Apollonius Rhodius's
  Argonautica, because the .tess line tag ("<A.R. 1.1>") uses an
  abbreviation the citation helper's static table does not list, which then
  read the two letters as an author and a work. Both now build the citation
  from the open work's own corpus-list entry (author, title, and a part's
  label where one applies) plus the numeric locus read off the ref, so the
  result no longer depends on whether the tag's own abbreviation is one the
  static tables happen to carry. A survey of `texts/la`, `texts/grc` and
  `texts/en` found 1,116, 868, and 162 files respectively whose leading tag
  abbreviation the static tables do not resolve; this fixes the header and
  selection bar for all of them. Tests added.

### Documentary reuse in the Reuse tab
- When a literary line is quoted or near-quoted in an inscription or
  papyrus, the Reader's Reuse tab now shows those documents in a separate
  group, "In inscriptions and papyri", below the literary groups, and the
  margin gutter carries a separate "quoted in N inscriptions or papyri"
  mark alongside the existing "quoted in N works" one (shown as its own
  badge, not merged into that count, so an already-shipped number keeps
  its meaning).
- New cross-collection table per language, `cache/reuse_pairs/<lang>_documents.db`
  (`scripts/reuse/build_documents_reuse_table.py`), built with the same
  word-triple containment logic and strict/possible tiers as the literary
  table (`scripts/reuse/build_reuse_table.py`), scored between literary
  lines and documentary lines only. A shared n-gram made entirely of
  documentary formula words (`data/documents/formula_words_<lang>.txt`,
  or a lemma used by more than 100 individual documents) is excluded, the
  documentary equivalent of the literary table's commonplace-word
  exclusion; see `docs/DECISIONS.md`.
- `GET /api/reuse/line` and `GET /api/reuse/marks` (`backend/blueprints/reuse.py`,
  `backend/reuse_documents.py`) carry the documentary hits/counts
  additionally, only when `TESSERAE_DOCUMENTS=1`; the existing literary
  response is unchanged otherwise. No new route, so no connector manifest
  change.
- Client: behind the `documents_trial` session flag (`?documents=1`, the
  same flag the documents collection search already uses) -- without it
  the Reader is unchanged. Tests added for the builder, the route, and
  the Reuse tab's new group.
- Validation build against the dev checkout's own data (not yet on
  production): Latin, 453,830 literary lines against 411,466 documentary
  lines, 5,414 pairs kept, peak 11.0 GB, 9m8s; Greek figures and the
  production install steps are in `docs/DATA_OPERATIONS.md`.

### Scholarship tab: titles shared by more than one author, and a shorter footer
- A citation of a bare work title that more than one author in the corpus
  uses, such as Argonautica (Apollonius Rhodius and Valerius Flaccus) or
  Metamorphoses (Ovid and Apuleius), was accepted for either author's
  passage with no check on which one the citing piece actually names. The
  Google Books channel has no author check of its own, so the Apollonius
  Rhodius, Argonautica 1.5-17 tab listed "Valerio Flaco (2016).
  Argonáuticas" and a Smallwood note on "Valerius Flaccus' Argonautica
  1.5-21" for exactly this reason. `backend/scholarship.py` now builds the
  list of shared titles from the corpus file list and, for one of them,
  requires the right author's name or citation abbreviation near the
  match (drawn from `data/citations/abbreviations.json` on production)
  and rejects a match naming a competing author of the same title
  instead, in the Google Books channel and in the OpenAlex, Crossref and
  journal-index channels alike. Without that table (every dev and test
  environment) the check does not run, so an untracked filing quirk in
  the corpus (a stray "Aeneid"-titled duplicate of Maffeo Veggio's own
  Supplementum) cannot force ordinary Vergil citations to name "Vergil"
  outright. Tests added. docs/DECISIONS.md has the before and after
  counts, measured against production's live data.
- The long "Found by title and abstract in OpenAlex and Crossref..." and
  HathiTrust paragraphs under every Scholarship result list are replaced
  by one short line: "Where these results come from" (a new Help section,
  `client/src/components/pages/HelpPage.jsx`, under The Reader) and the
  existing HathiTrust search link on its own. Tests added.

### A Documents section in Browse Corpus, behind the documents trial
- Browse Corpus can now show the documentary corpus (inscriptions, papyri)
  as its own section: kind (Inscriptions, Papyri and ostraca), region
  under each kind (Roman province, or for Italy the Augustan region,
  nome or findspot for papyri), and century under each region, every
  level carrying its own count. Filters for text type, material, object,
  and language narrow the same selection down to a paged list of
  documents that open the existing document Reader view.
- New read-only `GET /api/documents/browse` route, gated behind
  `TESSERAE_DOCUMENTS=1` like the rest of this feature. The switch off
  returns 404, the same as the rest of this feature.
  `backend/documents_browse.py` builds an in-memory, normalized facet
  index over `metadata.db` once per process and rebuilds it only if the
  file changes. Added to `backend/blueprints/mcp_manifest.py` as
  site-only.
- The section itself is behind the client's own documents trial
  (`?documents=1`, remembered for the visit), the same gate
  `LineSearch.jsx` already uses, and lives entirely inside
  `CorpusBrowser.jsx` as a new tab backed by
  `client/src/components/corpus/DocumentsBrowser.jsx`.
- Tests: `tests/test_documents_browse.py` covers region normalization,
  century bucketing, facet counts, paging, and the gate. Vitest covers
  the new tab and a filter.

### Documents results: example searches, relevance ranking, uncapped totals, German labels translated
- The documents trial's results page (behind the existing `?documents=1`
  trial) gets four one-click example searches, verified against the live
  documents indexes: "arma virumque cano" (Vergil's opening plus a Pompeii
  fuller's parody of it, Both), "conticuere omnes" (Aeneid 2.1 scratched
  into Pompeian walls, Both, exact match), "sit tibi terra levis" (an
  epitaph wish with its own literary echoes, Both), and a Greek epitaph
  phrase on the Greek tab (Documents).
- Document results are ranked by relevance by default: an exact adjacent
  phrase before matched words scattered across the line, a match on
  surviving text before one resting on editorially restored text, fewer
  restorations elsewhere on the line, then earliest date. A sort control
  adds Oldest first, Newest first, and Region. Computed server side
  (`backend/app.py`, `backend/documents.py`) from the same index position
  data `find_co_occurring_lemmas` already returns, so ranking tens of
  thousands of matches needs no extra line-text fetch.
- A document hit no longer stops at a fixed 500-row cap. The true total is
  counted from the documents index the same cheap way the existing
  stock-formula count works, the list pages 50 rows at a time server side,
  and a compact chart breaks every match down by century and by region
  (not just the visible page), reusing the Line Search page's existing
  chart styling.
- German placeholder and connector words from EDH/EDCS/Trismegistos
  metadata ("unbekannt", "bei", "oder", and others) are translated to
  English for display. A document's place is left off the card when the
  underlying value is one of these placeholders in German, English, or
  Latin. The raw metadata value is never changed. The mapping table is
  `data/documents/german_label_translations.json`, with the counts
  behind it in `docs/DECISIONS.md`.
- Tests: `tests/test_documents_stage4_polish.py` covers ranking order,
  sort modes, uncapped totals, 50-row paging, the German mapping, and
  place hiding. `client/src/components/search/__tests__/
  LineSearch.documentsPolish.test.jsx` covers the example buttons, the
  sort control, and chart rendering. The existing documents-collection
  parity test and the rest of the vitest suite for the documents trial
  both still pass unchanged.
- The "Filter by Text" section of the Line Search page (author/work/line
  range, which only ever filters the literature half of a search) is
  hidden entirely when Documents alone is selected, and relabeled "Filter
  the literature (optional)" under Both.

### Records: the Rumi translation install and the editorial-prose rule
- `docs/DATA_OPERATIONS.md` records the installation of the Masnavi opening
  translation. `docs/DECISIONS.md` records which prose inside Persian and
  Urdu poetry files is removed and which is kept. No code change.

### Citations name the corpus version for every search
- The Cite popup on the main pair search showed no corpus version, because
  that response carried no stamp. The page now asks a new
  `GET /api/corpus-version?language=` route when a search finishes.
- The stamp itself was stale (Latin read 2026-08-16): it is written only
  by full index rebuilds, and texts added or removed since left it behind.
  `get_corpus_version` now uses the later of the stamp and the index
  file's own date. Tests added.

### Result cards: a "Report a problem" link beside Cite
- Every result card on the main and Cross-Language searches shows a red
  "Report a problem" link with a pencil icon right after Cite, opening the
  same request form with the result's details filled in. The link inside
  the Cite popup stays.

### Suggest a change: visible in the header, and the in-context links marked
- An outlined "Suggest a change" button with a pencil icon sits in the
  header beside Sign In on every page (wider screens; the footer link
  remains for phones). "Suggest a correction" in the Reader's selection bar
  and "Report a problem with this result" in the Cite popup are shown as
  red links with the same icon, where they were plain gray text.

### A per-verse Ghalib link to Frances W. Pritchett's commentary in the Translation tab
- Her site ("A Desertful of Roses") states no licence. Her English cannot
  be copied into the site, so the Translation tab links to her own page for
  the matching verse, named and opening in a new tab. A passage with an
  aligned translation still shows it, with the link added below. Ghalib has
  no aligned translation at all, so for Ghalib the link is the only thing
  the tab shows.
- `scripts/build_ghalib_pritchett_links.py` builds the lookup table
  (`data/translations/links/ur__ghalib_pritchett_links.json`) by aligning
  `ghalib.diwan_wikisource` (272 ghazals, the only Ghalib edition that
  ships in `texts/ur/`) against a retired, Pritchett-numbered edition kept
  outside the repository for exactly this cross-reference. Matching goes by
  text, not by number, at two levels. First each ghazal's opening verse,
  then verse by verse inside each matched pair. 2,514 of 3,345 Wikisource
  verses (75%) now link to a verse page. Most of the rest are ghazals she
  does not cover (expected, since she covers a selection of the diwan).
  18 Pritchett ghazals whose verse count could not be split unambiguously
  from the local copy are left unmapped, reported, and not guessed at.
- `backend/translation_links.py` is the new loader. `backend/translations.py`
  `for_passage()` adds an `external_links` field, additive alongside the
  existing `text`/`available` fields, present (as an empty list when there
  is nothing to show) with or without an aligned translation. The MCP
  connector's `get_passage(translation=true)` carries the same field
  through for parity.

### Compare two works: a heading per side, plain field labels
- Each side of Compare two works is headed "First work" or "Second work",
  and its fields read "Language", "Author" and "Work" (they read "First
  work Work" before). The main search keeps its "Source Author" style
  labels. The side name stays in the screen-reader labels.

### Reader: readable names in the Reuse tab and in Urdu and Persian references
- The Reuse tab names each quoting work and line the way the rest of the
  site does ("Sauda, Kulliyat 6.6", not "Sauda, Kulliyat Wikisource" over a
  raw site ID), and its caption no longer limits it to Latin, Greek and
  English.
- References that open with a section name read as words and keep it:
  "Ghalib, Diwan, ghazal 1.1-7", "Mir, Kulliyat, marsiya 3.2". One
  collection can hold several numbered sections, so the name stays.

### Translation aligner: Rumi's Masnavi opening ("Song of the Reed") from Nicholson's 1925/1926 translation
- `scripts/translations/align_rumi_masnavi_nicholson.py`, built on the shared
  `write_aligned.py` helper. Our corpus holds only the eighteen-line reed-flute
  prologue of Book I (`texts/fa/rumi.masnavi.part.1.tess`), and R. A.
  Nicholson's English translation (public domain, published 1925/1926, more
  than 95 years ago) numbers its couplets continuously from 1, so this is a
  one-to-one, exact-confidence alignment with no offset or proportional
  block. 18/18 refs covered. Its output is staged for installation as
  `data/translations/fa__rumi.masnavi.part.1.json` (not tracked in git).

### Corpus tool fix: drop-lines-from-work rebuilds the lemma cache instead of deleting it
- `scripts/corpus/drop_lines_from_work.py` deleted the one cached lemma
  analysis after rewriting a work's text, on the mistaken assumption that
  the cache filename was a hash of the file's content (it hashes the
  work's path, not its content -- `backend/lemma_cache.py`'s
  `get_cache_path`), so the next request would rebuild it under a new
  name. It does not: the stale file sits at the exact path the correct
  one belongs at, and for a language whose cache build needs a library
  production deliberately does not carry (Urdu's Stanza pipeline), there
  was no next request that could rebuild it there at all -- the rare-
  bigram rebuild for that work failed until the cache was rebuilt by hand
  under the development environment. The tool now rebuilds the one
  work's cache itself, right after the text rewrite, with a backup of the
  old file kept either way. If the language's processor cannot be
  imported in the current environment, nothing is deleted or changed: the
  old cache is left exactly as it was, the exact command to run elsewhere
  is printed, and the tool exits non-zero so this is never silently
  missed. Tests for both paths added to `tests/test_drop_lines_from_work.py`.

### Theme Search: confidence bands refit for Latin, Greek, and English
- `HEAD_WEAK` (the floor for a Theme Search result to count as a match)
  moved from 0.0750 to 0.0738, refit against the production index
  (530,917 windows) and an extended 178-query labeled set (30 queries
  each for Latin, Greek, and English, was 17), with the original 57-query
  set kept as a regression check. Latin rose from 56.7% to 66.7% and
  English from 43.3% to 46.7%; Greek is unchanged (63.3%) because no Greek
  query in this set sits in the safe range. `HEAD_STRONG` and
  `FITTED_AT_WINDOWS` (now 530,917) were also reviewed; only
  `FITTED_AT_WINDOWS` changed. Zero absent queries were promoted on either
  probe set at either value. See `docs/DECISIONS.md`.

### Records: Persian and Urdu data operations of 2026-10-08
- `docs/DATA_OPERATIONS.md` records the Khayyam and Ghalib removals, the
  Similar Passages and Theme Search outage and its repair, the cache and
  table rebuilds, the Asrar-e Khudi translation and the new reuse tables.

### Theme Search: the "runs through the corpus" message no longer repeats itself
- A short query that lands in the pervasive outcome showed the pervasive
  message and the short-query hint, both asking for a description of what
  happens. It now shows the pervasive message alone.

### Theme Search: a third confidence outcome for a theme common in one language
- A Theme Search narrowed to one language (`languages=fa`, etc.) used to
  report the SAME confidence numbers as the unfiltered, whole-corpus
  search for the identical query text, because the language filter never
  reached the statistics, only the results list: a Persian search for
  "passionate love" returned Rumi, Rudaki, and Anvari addressing the
  beloved and still reported "the corpus does not appear to contain
  passages of this kind." A single-language search now additionally
  checks whether that language's own median score for the query sits well
  above the whole corpus's, and promotes a `low`/`moderate` call to a
  third outcome, `pervasive` ("this theme runs through much of the
  Persian corpus..."), when it does; it can only ever promote, never
  demote, so it cannot make any language's accuracy worse than before.
  Measured on a 139-query labeled set, read-only against production:
  62.6% to 79.9% overall, with Coptic, Persian, and Hebrew each gaining
  30-47 points and Latin, Greek, and English unchanged. A query of three
  words or fewer that doesn't score as a clear match now also gets a line
  suggesting a full sentence instead. See docs/DECISIONS.md, 2026-10-08.
  `backend/passage_index.py`, `evaluation/scripts/calibrate_confidence.py`
  (new), tests in `tests/test_theme_confidence_classification.py`.

### Theme Search page: the language-coverage line now names the languages this server actually serves
- The line under the language chips named a fixed four languages (Latin,
  Greek, English, Coptic) regardless of what the server actually
  indexed, so a Hebrew, Persian, or Urdu reader was told their language
  wasn't covered at all even once it was. It now reads the server's own
  `/api/languages` list. `client/src/components/passages/ThemeSearchPage.jsx`.

### Cite popup opens toward the side with room
- On cards whose Cite button sits near the left edge of the page (the
  Cross-Language results), the popup opened off-screen. It now opens to the
  right when there is no room on the left.

### Translation aligner: Iqbal's Asrar-e Khudi from Nicholson's 1920 translation
- `scripts/translations/align_asrar_nicholson.py` plus its shared
  `write_aligned.py` helper, which writes the served (compact) shape
  `backend/translations.py` reads (`units` + `ref_to_unit`) directly, the
  same fields the earlier Latin and Greek aligners record inline. Aligns
  R. A. Nicholson's *The Secrets of the Self* (Project Gutenberg 57317,
  public domain, 1920) to `texts/fa/iqbal.asrar_e_khudi.tess` couplet for
  couplet in 17 of 19 sections (the Prologue needs a hemistich offset for
  our opening epigraph), one section in blocks of two couplets, and
  leaves Nicholson's section XVII untranslated rather than misaligned
  (43 couplets in his English against 61 of ours). 872/872 refs covered;
  its output is already installed on production as
  `data/translations/fa__iqbal.asrar_e_khudi.json` (not tracked in git).
  This PR ports the script itself to `main` for reproducibility.

### Reuse table builder confirmed language-generic; Persian and Urdu built on the dev checkout
- `scripts/reuse/build_reuse_table.py` and `backend/reuse_table.py` named
  no language anywhere in either (both already drive off `--language`
  and `cache/reuse_pairs/<lang>.db`'s existence); `is_available()` for
  Persian and Urdu was simply never tried. Dropped the stale "Latin only"
  docstring claim and added a test exercising the whole stack (the
  builder's own fixture shape, `is_available`, `/api/reuse/line`,
  `/api/reuse/marks`) with Persian script and a language code with no
  entry in the cross-lingual stoplists, so a future change cannot
  silently reintroduce a Latin/Greek/English-only assumption.
- Built on the dev checkout's own corpus (not production): Persian 28
  works, 942,922 lines, 1,663,213 pairs kept, 298s, peak 6.3 GB
  (`cache/reuse_pairs/fa.db`, 238 MB); Urdu 18 works, 58,857 lines, 38,258
  pairs kept, 17s, peak well under 1 GB (`cache/reuse_pairs/ur.db`).
  Neither directory is tracked in git. Production steps for both follow
  the Latin pattern already in `docs/DATA_OPERATIONS.md`.

### Cross-Language results: the same tools as single-language results, plus citation guidance
- The Cross-Language result card gained the same actions the single-language
  card has: Cite (naming both sides, the language pair and the site, with
  the "Report a problem with this result" link that already comes with
  CiteButton), Register (recording both languages, both texts and refs, and
  the channels, no schema change needed since `source_language`/
  `target_language` were already independent columns), and one Search
  Corpus action per side (a cross-language pair's two lines are in two
  different languages, so each side searches only its own language's
  corpus).
- Page-level parity: pagination with a page-size control above the list and
  navigation below it, Export PDF alongside the existing Export CSV, Refresh
  results (clears the cache and reruns), a Share link extended with the
  cross-language parameters (`pair`, `source`, `target`, `min_matches`, on
  top of the existing `lang=cross`) so a shared link reopens the same
  search, Saved Searches under its own storage key (a language pair is not
  a language the single-language list's loader could reopen), Ask Tessa,
  and the highlight legend with its Help link.
- Cite popup (`client/src/components/common/CiteButton.jsx`): one sentence
  above the citation says one citation of the project per publication is
  enough, with a link to the About page's "How to Cite" section (now
  `id="how-to-cite"`, and `AboutPage` takes an `initialAnchor` the same way
  `HelpPage` already does). The same sentence and link are in Help's
  "Reading the results" section.
- Removed the one-line description above the Cross-Language page and the
  em dash in the bigram description (`SearchDescription.jsx`).
- Backend: `backend/assistant/findings.py` `_channels_of` read a
  cross-language result's `channels` (a comma-joined string, not a list)
  with `set()`, which silently returned a set of characters, so Tessa's
  "Ask" on a cross-language result always computed "weak" evidence
  regardless of what the channels actually were. It now parses that string
  form too.

### Corpus tool fix: drop-lines-from-work keeps the passage index in lockstep and no longer over-drops scattered refs
- `scripts/corpus/drop_lines_from_work.py` had two defects found on its
  first production run. (1) Dropping windows removed rows from
  `ids.json` and `descriptions.jsonl` but left `data/passage_index/
  embeddings.npy` untouched, even though the tool's own report claimed
  those rows were dropped; the three fell out of lockstep and the passage
  index refused to load (Similar Passages and Theme Search both down
  until the extra embedding rows were removed by hand). `embeddings.npy`
  is now dropped by the same row positions, backed up first, written
  atomically, and the three stores' row counts are asserted equal before
  any of the four window files is swapped into place and again after,
  aborting and restoring every backup if they ever disagree. (2) Passing
  several scattered refs (e.g. two unrelated footnotes far apart in a
  file) was planning drops for every window between the first and the
  last of them, not just the windows actually touching one; windows are
  now matched against each contiguous run of dropped refs in file order.
  Caught in dry run against a scratch copy of production data before
  anything was applied. Tests added for both:
  `tests/test_drop_lines_from_work.py`.

### Sign-in box: plain wording
- The sign-in box opened by Register is titled "Sign in", and the note for
  accounts created by the site's administrators now reads "If we created
  your account for you, you will be asked to choose a new password after
  you sign in."

### Corpus tool: drop specific lines from a work across every store that names a line by its ref
- `scripts/corpus/drop_lines_from_work.py`, following an audit of Persian
  and Urdu imports that found a signed, dated modern editor's essay
  bundled into a diwan file alongside the poem it prefaces. Dry run by
  default; `--apply` rewrites the `.tess` file (remaining lines keep their
  original ref labels, nothing renumbered), the matching rows of the
  language's inverted index (with `lemma_doc_freq` recomputed under the
  canonical per-work rule), the matching rows of the work's embeddings
  `.npy`/`.meta.json` (dropped by ref, not recomputed: the surviving
  rows' text did not change), and any passage window whose span touches a
  dropped ref, with its description and vector rows. Prints the
  whole-language/whole-corpus follow-up (lemma cache rebuild, bigram
  rebuild, names-index and connections-map rebuild) it does not attempt
  itself. Backups and copy-modify-swap throughout, per
  `scripts/corpus/corpus_safety.py`. Tests only, against a fixture; not
  yet run against production. `tests/test_drop_lines_from_work.py`.

### Result card tidy, second pass: hover popovers, one legend line, Search Corpus highlighting
- `client/src/components/common/InfoBadge.jsx`: no more info icon or help
  cursor on every badge; the badge itself is the trigger. A popover opens
  after about 150ms on hover (no flicker crossing the card), at once on
  keyboard focus or tap, and stays open while the pointer is over the
  badge or the popover; it closes on Escape or a tap outside. Content is
  one short sentence plus a "More" link into Help, with no heading.
- Every badge's explanation on `SearchResults.jsx` and
  `CrossLingualSearch.jsx` is now one sentence; the fuller version moved
  to a new "Reading the results" section in `HelpPage.jsx`, with an id
  anchor per label (score, refrain, rhyme, meter, refrain-lines,
  works-count, form-count, channels, theme) that the "More" links and the
  new legend line both point to.
- The old "Colours" and "Badge colours" legends are replaced with one line
  above the results, naming the highlight colors (when a poetic result is
  on screen) and linking to Help; badge colors themselves are unchanged.
- The result card's second row (how-common badges, evidence badges, and
  the Search Corpus / Register / Cite buttons) no longer wraps the buttons
  to a third row at desktop widths: the buttons sit in their own
  non-wrapping group at the row's right.
- American spelling throughout `client/`: colour, licence, judgement,
  labelled, and neighbour(hood) in user-visible text are now color,
  license, judgment, labeled, and neighbor(hood).
- Cross-Language (Persian -> Urdu and the other script-sharing pairs):
  citations now show "Author, Work reference" on both the source and
  target side (the target-only fix was never actually applied, since the
  state that freezes the chosen texts' names was never set); a refrain-
  and-rhyme result now marks the rhyme word in rose, not just the refrain
  in yellow, reusing the single-language card's own position logic; the
  settings bar's description is the per-pair sentence the page already
  computes (SPhilBERTa only for the classical pairs) instead of one fixed
  sentence for every pair; and badge order is Score, form (refrain,
  rhyme), then evidence (a channel-count-and-names badge first, the
  semantic percentage after it, both in the evidence blue rather than
  semantic's old amber).
- Search Corpus (`CorpusSearchResults.jsx`): a Persian or Urdu line with
  Arabic-script punctuation attached to a word (e.g. a trailing "،") now
  highlights correctly. The highlighter walks the same word-runs the
  Persian/Urdu tokenizers use server-side (`backend/persian/processor.py`,
  `backend/urdu/processor.py`), so a punctuation mark never consumes a
  token position the way a whitespace-only split could. The query header's
  citation now resolves through the corpus text map, the same resolver the
  result cards use, instead of showing a raw internal id.

### Requests workflow: three new entry points, a public Requests page
- A scholar can now ask for something, report a problem with a result, or
  suggest a text correction without ever touching GitHub. One dialog
  (`client/src/components/common/RequestDialog.jsx`) opens from: the Cite
  popup's "Report a problem with this result" (`CiteButton.jsx`, so every
  result card that already shows Cite gets it with no change of its own),
  the Reader's "Suggest a correction" when a line or range is selected
  (`SelectionToolbar.jsx`, pre-filled with the work, refs and selected
  text), and a plain "Suggest a change" link in the footer and on the Help
  page, with just the page URL as context.
- `POST /api/feature-request` now accepts three new types (`result-problem`,
  `text-correction`, `suggestion`) alongside the connector's existing
  feature/language/text/bug/other, and files a GitHub issue for every type,
  labelled `request` plus `request:<type>` (labels are created if the repo
  doesn't have them yet). Contact info stays in the private DB record and
  email only, never the issue. Free text is HTML-stripped before it reaches
  a public issue body.
- `GET /api/requests`: a public, read-only mirror of those GitHub issues
  (`backend/github_requests.py`), grouped open vs. done, status mapped from
  GitHub's own state/state_reason/labels, with the merged pull request link
  when a "done" issue has one. Only a short line after a "Summary:" marker
  in the issue body is ever shown. The rest of the body never leaves the
  server. Cached in process for 10 minutes, mirrored to disk so a restarted
  worker doesn't refetch immediately.
- New page `/requests` ("Requests"), linked from the footer and Help, not
  the main navigation.
- `backend/blueprints/mcp_manifest.py`: noted the extension and the new
  read-only route for the connector-parity tests.

### Cross-Language: Persian to Urdu no longer crashes the page; only served pairs shown
- `CrossLingualSearch.jsx` fetched text lists for a fixed four languages
  (Greek, Latin, English, Hebrew), so choosing Persian -> Urdu found no list
  and the page went blank, and it showed the Arabic pairs although the
  server does not serve Arabic. It now reads the served pairs from
  `/api/languages`, shows only those, loads a list for every language in
  them, and guards the menus against a missing list. Test added (fails on
  the old code).

### Result card: the info mark drawn as an icon, and Iqbal's titles with -e
- The info mark on explained badges is a small drawn icon in place of the
  circled-i character, which showed as an empty box where a font lacks it.
- `backend/utils.py` `DISPLAY_NAMES`: Iqbal's nine Persian and Urdu titles
  join the connective -e to the word before it ("Zabur-e Ajam", not
  "Zabur E Ajam"), in citations and the text lists.

### Result card tidy: badges, explanations, citations
- Every badge on a pair-search result card (and the matching ones on the
  cross-lingual search page) now opens a real popover on hover, keyboard
  focus, or tap -- `client/src/components/common/InfoBadge.jsx` -- instead
  of a native `title` tooltip, which showed nothing for a second or two and
  gave no sign an explanation existed. Each badge carries a small info mark
  so the explanation is visible before anyone hovers.
- Badge colour now marks one of three categories consistently: yellow/
  rose/purple for the poem's form (refrain, rhyme, meter), gray for how
  common the shared wording or form is, blue for the evidence that found
  the match (channels, theme lift). A legend line above the results says
  so. The channel-count badge ("2 channels") is gone; one blue badge names
  the channels ("form + sound"). "Matches:" is omitted when the matched
  words are exactly the refrain words a badge already shows.
- Citations resolve "Author, Work reference" for every language, not only
  Latin, Greek, and English: `client/src/utils/textNames.js` now falls
  back to the corpus list (`/api/texts?language=<lang>`) for Persian, Urdu,
  or any other language without a static abbreviation table, the same
  author/title record the corpus browser and the Reader read from. The raw
  site id stays available as the Cite popup's last line and the refrain-
  lines popover names each work once with its lines collapsed into ranges.

### Documentary texts, stage 3b-3: restored-word exclusion, a stock-formula filter, and a document Reader view
- `/api/line-search` (documents/both): each document hit now carries
  `matched_restored` (every matched token is one the source marked
  restored) and `partly_restored` (some are). New optional
  `exclude_restored=1` drops a hit whose match rests entirely on restored
  text; the response reports `restored_excluded_count`. The card states
  "match on restored text" for a fully-restored hit, and Line Search gets
  a "Leave out matches on restored words" checkbox next to the existing
  documents filters.
- Each document hit also carries `formula_count`: how many documents in
  the SAME documents index share its matched lemma pair or phrase,
  computed from postings the same way line search counts co-occurrence
  candidates (not a corpus scan), cached per query. A lemma search also
  returns a `formula_summary` for the query as a whole. New optional
  `hide_formulas=N` drops a hit whose `formula_count` exceeds N
  (`formulas_hidden_count` reported); Line Search gets a "Hide stock
  formulas" checkbox using a measured default (100 — see
  `docs/DECISIONS.md`). The soft-penalty word lists
  (`data/documents/formula_words_la.txt`/`_grc.txt`) are still not applied
  as a down-rank: document hits carry no score or rank for either
  collection to attach one to, the same finding stage 3b-2 already
  recorded.
- A new route, `GET /api/documents/<doc_id>` (behind `TESSERAE_DOCUMENTS=1`,
  404 otherwise), returns one document's own lines with restored/fragment
  positions, credit, date/place/labels, and the stage 3a display fields
  (museum, inventory, dimensions, translation, apparatus, commentary,
  image links). Listed `site_only` in the connector parity manifest (a
  website trial, not yet exposed to the connector).
- Client: clicking a document hit's citation opens a document view
  (`/document?doc=...`) with the text (restored words marked), the
  credit, date/place (with a Pleiades link), labels, and the display
  fields, apparatus and commentary collapsed; a back link returns to Line
  Search with the originating query, type and language intact. The
  literary Reader is unchanged; this view is reachable only from a
  document hit.

### Records: documents trial opened on the live site
- `docs/DATA_OPERATIONS.md` records the server switch that opens the
  `?documents=1` trial. No code change.

### Documents: a trial behind ?documents=1, and a separate switch for the connector
- The Literature/Documents/Both control on the corpus-wide phrase search
  appears only after a visit with `?documents=1` (remembered for the rest
  of the visit), and only when the server also has documents on, the same
  pattern as the Scholarship tab. The server switch can therefore be on
  without every reader seeing the option.
- The connector's `line_search` forwards `collection` and the documents
  filters only when `TESSERAE_DOCUMENTS_CONNECTOR=1`, so the trial is not
  opened to every connector user. Tests for both.

### Documents: the credit shows each source's deposit licence
- `scripts/documents/extract_metadata.py` takes the licence for every
  document from the source's own deposit record, not from the sentence in
  each file's header. EDR's headers still carry an older "reserved rights"
  template although its 2026 deposit is CC BY 4.0, and EDH's headers give a
  full sentence where a licence name belongs. Test added. The metadata
  database was rebuilt (257,428 documents: EDH CC BY-SA 4.0, EDR CC BY 4.0,
  I.Sicily CC BY 4.0, papyri.info CC BY 3.0).

### Documentary texts, stage 3b-2: documents in the corpus-wide phrase search, behind a switch
- `backend/documents.py`: lazy, read-only access to the stage 3b-1
  documents index(es), stage 3a's metadata database, and the per-bucket
  restored-word sidecars, all path-configurable by env var. `enabled()`
  reads `TESSERAE_DOCUMENTS` fresh on every call, so the switch can be
  flipped on a running process without a restart. Everything else in this
  entry is unreachable unless it is on.
- `backend/inverted_index.py`: `lookup_lemmas`, `find_co_occurring_lemmas`,
  `has_lines_data` and `get_lines_batch` gained an optional `conn=` override
  (default `None`, every existing caller unchanged) so `backend/documents.py`
  reuses this module's own query and Latin u/v, i/j variant-expansion logic
  against a documents-index connection, keyed on the real language code
  rather than a pseudo-language.
- `backend/app.py`: `/api/line-search` gains an optional `collection`
  (`literature` default, `documents`, `both`) and, when documents are
  requested, `date_from`/`date_to`/`region`/`text_type`/`material`/`source`
  filters. With `collection` omitted, or the switch off, the response is
  unchanged byte-for-byte — the literary code path runs exactly as before;
  the documents search is reached only through two new, additive insertion
  points (an early return for `collection=documents`, a pre-return merge for
  `both`). A document hit carries `collection:'documents'`, `doc_id`, a
  credit block (licence, source, principal edition), date range, place,
  region, type/object/material labels, and restored/fragment token
  positions, grouped separately from literary works in
  `documents_by_source_region`. Rarity for a document hit is left to the
  documents index's own `lemma_doc_freq` (not computed here, since line
  search computes no score for either collection); `rare_focus_filter`
  (which DOES read the literary table) is applied only to literary rows.
  Formula words (`data/documents/formula_words_la.txt`/`_grc.txt`) are NOT
  yet applied as a penalty: line search has no per-result scoring step for
  either collection to attach one to, so this is left for a later phase.
- `/api/languages` reports `documents_enabled` (the switch on AND at least
  one language's documents index actually present) so the client can show
  the collection control.
- `backend/blueprints/mcp_http.py`: the `line_search` connector tool gained
  the same `collection`/filter parameters, forwarded as-is; a document
  result in its output carries `doc_id`/`credit`/date/place/labels instead
  of author/work/era/year, and `both` adds `documents_total` alongside the
  literature-only `total`.
- Client: `LineSearch.jsx` (the corpus-wide phrase search) shows a
  Literature/Documents/Both control, and the filters, only when
  `documents_enabled`; a document hit gets its own card (credit line
  linking to the source record, principal edition as the citation, date and
  place, type/object/material labels) in a section separate from literary
  results, so no existing literary rendering path changes. Restored words
  are marked with a light dotted underline (not the scholarly square
  brackets): the matched-word highlight already uses `<mark>`, and the
  corpus's own angle-bracket convention is reserved for editorial brackets
  carried in the source text itself.
- Unit tests for `backend/documents.py` against a tiny fixture index +
  metadata db + sidecar (`tests/test_documents.py`); a golden check that the
  literary response is byte-identical with the switch off and with
  `collection` omitted; `tests/test_mcp_parity.py` still passes unchanged.
- `docs/DATA_OPERATIONS.md`: a "to be applied" entry listing the files
  production needs copied (the two documents indexes, the metadata
  database, the restored-word sidecars) and the env line, for the main
  session to apply.

### Records: the Origo translation applied on the live site
- `docs/DATA_OPERATIONS.md`: the Origo translation entry now records the
  production step, and an older entry describes a log message in place of
  quoting it.

### Documentary texts, stage 3b-1: a separate documents index, built dark (no site change)
- `scripts/documents/write_document_tess.py`: writes the documentary
  corpus into packed `.tess` files, one per source/region/century
  bucket (264 files for Latin+Greek together, not one file per
  document), reusing the existing bucketing and restoration-token
  rules unchanged. Text is the restored reading with the gap
  placeholder dropped (kept only as a count) and a mixed
  gap/real-character token split into its surviving pieces; restored-
  word and fragment positions go to a sidecar JSONL per bucket, never
  into the `.tess` text itself. A document's own merged-corpus id is
  its citation tag, so it joins directly against the metadata
  database from stage 3a.
- `scripts/documents/build_documents_index.py`: builds a SEPARATE
  `<lang>_documents_index.db` per language by reusing the existing
  index-build code unchanged (same schema, same per-lemma document-
  frequency table, now scoped to the documentary corpus alone so it
  never shifts literary word rarity), plus a new `doc_meta` table
  mapping each document to its bucket file and line range. Guards
  refuse to write under `/var/www` or to any literary index filename.
- `scripts/documents/query_documents_index.py`: a dev-only lemma/
  phrase lookup against a documents index, joined against the
  metadata database for licence and source credit.
- `backend/lemma_cache.py`'s `rebuild_lemma_cache()` gained three
  optional, default-preserving parameters: `file_filter` (a subset of
  filenames, for sharding), `fast_greek` (Greek only, the same
  table-only lookup the index build's own fast mode uses, cutting the
  Greek cache rebuild from 63.8s to 0.1s per ~1,500 lines and measured
  at 100% lemma agreement with a fast-mode-built index), and
  `build_phrase_units` (default True; False for documents, after
  measuring `process_file`'s phrase-accumulation at 5.24 GB peak RSS
  on one epigraphic bucket file with a 706-line unterminated run,
  against 1.45 GB for line mode alone on the same file; nothing in
  this stage reads a documents phrase cache entry).
- `scripts/documents/build_lemma_cache_shard.py`: builds one shard of
  a language's lemma cache, files balanced by line count across
  shards (the documentary buckets are heavily skewed), so bucket files
  cache in parallel across `tess-job` scopes.
- A 2-bucket pilot measured real per-line costs first, before deciding
  whether to run a full build; the initial projection (CLTK-bound
  Greek lemma-cache rebuild, ~8.6 hours alone) exceeded the 6-hour
  budget, so the fast-Greek and skip-phrase-units fixes above were
  built and re-measured. Full Latin and Greek documents indexes and
  lemma caches are now built: `la_documents_index.db` (411,466 lines,
  160 texts, 160 cache files) and `grc_documents_index.db` (711,801
  lines, 104 texts, 104 cache files), together well under 20 minutes
  wall time, no concurrency slowdown measured between 4 and 7 parallel
  Latin cache shards on this 32-core machine.
- 54 tests across five new/extended test files, plus the existing
  search reference wiring test, all passing. One pre-existing,
  unrelated test failure on `main` itself (a cross-lingual pair list
  mismatch in the assistant actions module) is untouched by this work.
- No change to any literary index or to the live site. The literary
  index files were checksummed before and after and are unchanged.

### Origo Gentis Romanae: a public-domain English translation added
- `scripts/translations/align_origo.py` aligns the 2004 collaborative
  translation published at tertullian.org (ed. Roger Pearse, public
  domain) to all 126 refs of `pseudo_aurelius_victor.origo_gentis_romanae`
  (coverage 1.0, proper-name check 0.99). Three refs where the corpus's
  Latin Library line carries two of the translation's numbered sections
  are merged, listed by hand in the script. Closes the gap the Aurelius
  Victor addition below left open. The built translation file is data. It
  stays out of git, like every other file under `data/translations/`. The
  data operation is recorded in docs/DATA_OPERATIONS.md.

### Aurelius Victor additions: dates entry and the record of the production steps
- `backend/author_dates.json`: era and date for the two works transmitted
  with Aurelius Victor, so the corpus browser shows them as Late Antique.
- `docs/DATA_OPERATIONS.md`: the planned steps for these works replaced by
  the record of what was run on the live site.

### Documentary texts, stage 3a: per-document metadata layer (no site change)
- `scripts/documents/extract_metadata.py` reads the stage 2 merged
  documentary corpus plus the raw EDH/EDR/I.Sicily/papyri.info EpiDoc
  files, and writes a SQLite database (`documents` + `display` tables,
  schema in the script's own docstring). For every document: licence
  and a link back to the source's own page (EDH's canonical domain and
  EDR's actual query parameter both corrected from what was assumed
  going in), the principal edition citation, EAGLE-vocabulary text
  type/object type/material translated to English, date range, place,
  languages, and a verse flag. The flag is set only for I.Sicily, the
  one source whose format marks a verse line structurally. Confirmed
  by checking directly against the full raw export.
  Separately, museum, inventory, dimensions, letter height,
  layout/hand notes, apparatus, commentary, translation, and image
  links. Every field is optional, and a missing one never drops a
  document. 257,428 documents written, matching the stage 2 merged
  total exactly.
- `data/documents/eagle_labels.csv`: an English label for 290 EAGLE
  Network vocabulary terms used across the corpus, built from EAGLE's
  own SKOS/RDF records where one exists, by hand for the roughly 70
  concepts EAGLE's own vocabulary carries no English label for at all,
  plus 8 corrections where EAGLE's own data mistags a German or
  Hungarian string as English.
- `tests/test_extract_metadata.py`: 31 tests against
  `tests/fixtures/epidoc/`, covering licence/source-link/citation
  extraction per source, the EAGLE term-to-English mapping, I.Sicily's
  translation and image links, that a document with no findable raw
  file still gets a row of its own, and (added after the PR's own
  automated review caught a duplicate-key bug) that
  `eagle_labels.csv` can never hold two rows for the same vocabulary
  term again.
- Follow-up: papyri.info/HGV tag `material` and document type as plain
  text with no EAGLE vocabulary link at all, so the first pass left
  them almost entirely unmapped. Added hand-built English mappings for
  all 75 distinct `material` values (63,856 documents: "Papyrus",
  "Ostrakon", "Pergament"/parchment, "Wachstafel"/wax tablet, and 72
  rarer terms) and the top 40 `text_type` keyword values by count
  ("Quittung"/receipt, "Vertrag"/contract, "Liste"/list, and 37 more),
  reusing the same `material`/`typeins` fallback the other three
  sources' own ref-less free text already used. Papyri's
  `material_label` coverage: 4.0% to 97.9%. `text_type_label`: 0.3% to
  81.8%.


### Records: scholarship sources installed, and the terms they are held on
- `docs/DATA_OPERATIONS.md` records the installation of the commentary
  catalogue, citation index, abbreviation table and service keys on the live
  site. `docs/DECISIONS.md` records what the Scholarship tab draws on and the
  licence rule for commentaries. No code change.

### De Viris Illustribus and Origo Gentis Romanae added to the Aurelius Victor corpus
- Two pseudonymous Latin prose works transmitted with the Aurelius Victor
  corpus, from The Latin Library (edition not stated):
  `pseudo_aurelius_victor.de_viris_illustribus.tess` (86 chapters, 519
  lines) and `pseudo_aurelius_victor.origo_gentis_romanae.tess` (23
  chapters plus an unnumbered preface, 126 lines). Neither work is by
  Aurelius Victor, and the authorship of both remains unknown.
  `scripts/corpus/latinlibrary_to_tess.py` gained two converters,
  `de_viris_illustribus` and `origo_gentis_romanae`, each following its
  source page's own chapter and section numbering (the first page marks
  sections with inline `<FONT size=2>` tags, the second with plain
  digits). Both keep the source transcription's own numbering gaps. The
  converter documents each one. Descriptions added to
  `data/text_descriptions.json`, provenance rows to
  `backend/text_sources.json`, and genre and era rows (Late Antique,
  prose, historiography) to `data/text_genres.csv`, matching the existing
  `aurelius_victor.*` entries. Both files pass
  `scripts/corpus/validate_tess.py`.

### Scholarship: the commentary credits list is cached
- `commentary_sources()` in `backend/scholarship.py` read and parsed every
  commentary file on each call, which takes seconds once the full catalogue
  (about 400 files) is installed. The rows are now kept until a commentary
  file is added, removed or rewritten, using the same change stamp that
  already governs the per-work commentary cache. Output unchanged. Test in
  `tests/test_scholarship.py`.

## 2026-10-07

### Connector: find_scholarship and get_commentary, behind TESSERAE_SCHOLARSHIP_TOOLS=1
- Two new MCP tools in `backend/blueprints/mcp_http.py`: `find_scholarship`
  (articles, chapters and books that cite a passage or a pair of passages,
  via the backend PR's `/api/scholarship`) and `get_commentary` (the
  public-domain commentators' notes at a span, via
  `/api/scholarship/commentary`). Both are defined in `TOOLS` unconditionally,
  so the connector-parity manifest and its tests stay internally consistent
  either way, but are hidden from `tools/list` and refused by `tools/call`
  ("Unknown tool") unless the environment carries
  `TESSERAE_SCHOLARSHIP_TOOLS=1`, checked per request. `backend/blueprints/
  mcp_manifest.py` gained the four `/api/scholarship*` route entries
  (two tool-covered, two site-only: the Sources credits list and the
  on-demand note translation, neither useful to an agent). No other tool's
  behaviour changed. Two new tests cover both flag states directly: both
  tools absent from `tools/list` and refused by `tools/call` with the
  flag unset, both listed and callable with it set to `1`.

### Documentary texts, stage 2: dedup, restoration tokens, formula candidates, lemmatizer gaps, places crosswalk, index layout (no site change)
- `scripts/documents/dedupe_sources.py` merges the 10,238 Trismegistos ids
  shared between EDH and EDR into one record each (recorded per-field rule:
  text by lower supplied share, date by narrower non-null range, findspot by
  a resolved place identifier first, then the longer named place), keeps
  both source ids and a provenance field, attaches EDH's Trismegistos/
  Pleiades place identifiers to every merged record regardless of which
  source's findspot text displays (93.78% of merged records now carry a
  resolved Pleiades id), flags (does not merge) the smaller cross-source
  overlaps with papyri.info and I.Sicily. 257,428 deduplicated records.
- `scripts/documents/restoration_tokens.py` maps character-level restoration
  to word tokens: a gap-only token is dropped (position kept on the next
  token), a token split by a gap becomes two excludable fragments, a token
  is marked restored when a strict majority of its characters were supplied.
  5.4% of all tokens touch a gap boundary; a quarter are whole supplied words.
- `scripts/documents/formula_stoplist.py` lists the top 300 words by document
  frequency per language with Latin/Greek formula and function words marked,
  for review (not finalized, and the candidate list itself is kept out of
  this public repository).
- `scripts/documents/lemmatizer_gaps.py` classifies Roman numerals (I V X L C
  D M letter runs), measures a 43,170-entry name-candidate list's coverage,
  and excludes gap fragments from the unresolved tally; combined unresolved
  share on a 200-docs-per-source rerun drops from 9.22% to 5.43%.
- `scripts/documents/places_crosswalk.py` builds a Trismegistos-place to
  Pleiades crosswalk from EDH's own geography file and the Pleiades dump's
  Trismegistos backlinks (both openly licensed); EDH's Pleiades coverage
  rises from 0.0% to 73.6%. EDR carries no place identifier anywhere in its
  raw export (confirmed over the full 115,591 files), so its coverage stays
  at 0.0%. A 30-case spot check of the 291 entries where EDH's own file and
  the Pleiades dump disagree confirms EDH as the more reliable source (right
  in 11 of 30 against 3 for the other side, the rest ambiguous or
  inconclusive).
- `scripts/documents/index_layout.py` prototypes and counts a `.tess`-format
  file layout (one index line per short document, grouped by source, region,
  and (for any bucket over 10,000 documents) century of date; one file per
  long document, line by line): 39,111 files, 1,222,573 index lines for the
  full corpus, 0 lines failing the `.tess` format regex. Found and fixed at
  the source a converter bug that had left raw newline/tab whitespace inside
  7,751 documents' text (`epidoc_convert.py`'s text/tail handling now
  collapses whitespace; all four converted sources and the merged corpus
  were regenerated).
- Added `ijson` to `requirements.txt` (streaming JSON parsing; a naive
  `json.load` of the Pleiades dump measured 16.3GB peak memory).
- `data/documents/formula_words_la.txt` and `formula_words_grc.txt`: a
  soft-penalty (not a hard stoplist) formula-word list for documentary
  matching, built from the reviewed candidate list plus three Latin words
  added by hand (solvit, fronte, pedes); excludes personal names and
  numerals by design.
- No data from any source is in this repository. Nothing in this change
  touches the live site, the search index, or the database.

### Scholarship: a secondary-scholarship backend, no UI yet
- `backend/scholarship.py` asks the open scholarly metadata services
  (OpenAlex, then Crossref), Unpaywall for a legal open-access copy, and
  Semantic Scholar/CORE full text, for articles, chapters and books that
  cite a passage or a pair of passages, ranked by whether a piece names the
  work and the exact locus; it also reads the site's own public-domain
  commentaries (`data/commentaries/`) and, where one has been built, an
  offline citation index (`data/citation_index/citations.db`, not shipped
  here). `backend/citations/` is a citation-grammar extractor for ancient
  texts ("Aen. 1.1", "Verg. A. I 1"), reimplemented from Matteo Romanello's
  CitationParser rules; it degrades to finding nothing without its
  abbreviation table (`data/citations/abbreviations.json`, GPL-3.0,
  intentionally not committed). `backend/scripture.py` gives scripture one
  citation key across Hebrew, Greek, Coptic and English Bible versions, so
  a commentary on a verse serves every version. New route
  `GET /api/scholarship` (plus `/commentary`, `/sources`, `/translate`),
  registered in `backend/app.py`; no existing route changed. Keys are
  environment variables only (`S2_API_KEY`, `CORE_API_KEY`,
  `TESSERAE_CONTACT_EMAIL`, `GOOGLE_BOOKS_KEY`); nothing hard-coded beyond
  the existing contact default. `/scholarship/translate` only ever
  translates a note the site already holds at the given work and ref
  (checked word for word against what `commentary_at()` returns), never
  arbitrary submitted text. No UI: the Reader tab and the connector tools
  are separate PRs, both behind their own switch.
### Scholarship tab in the Reader, behind ?scholarship=1
- A fifth Reader panel tab, "Scholarship" (commentators, articles and
  books on the selected lines), added to `ResultsPanel.jsx` beside
  Similar, Parallels, Translation and Reuse. Hidden unless the address
  carries `?scholarship=1`, which then remembers the setting in
  `sessionStorage` for the rest of the visit, the same pattern the names
  grouping used behind `?names=1`. With the flag off the panel is byte-for
  -byte the same four tabs as before. `ScholarshipTab.jsx` calls
  `GET /api/scholarship` (added in the backend PR) and needs no other change to the existing
  Similar/Parallels/Translation/Reuse tabs. The cross-link that lets a
  Similar Passages or Verbal Parallels row set a second passage for a
  "scholarship on both" lookup was left out of this change to avoid
  touching those tabs' own rendering; a later change can add it.
- `data/commentaries/`: Servius on the Aeneid, Eclogues and Georgics
  (14,205 notes; Thilo-Hagen text via the Perseus Digital Library's
  open-source TEI, CC BY-SA 3.0 US), credited in
  `data/commentaries/README.md`. A much larger commentary
  catalogue exists (Perseus's other authors, Sefaria, Matthew Henry, several
  scanned English literary editions) but was not brought into the repository;
  the README explains how to add more, since the commentary loader reads
  every file in the directory by its work id regardless of who installed it.

### Documentary texts, stage 1: an EpiDoc converter, no site change
- `scripts/documents/epidoc_convert.py` converts EpiDoc TEI-XML (the Heidelberg
  and Roma epigraphic databases, I.Sicily, papyri.info's DDbDP and HGV
  metadata) into one normalized JSON record per document: id, Trismegistos
  and source-local ids, language(s), date range, findspot with a Pleiades id
  where the source gives one, and a diplomatic/expanded/plain reading per
  line with which characters were supplied by an editor flagged. Handles
  `<choice>` (keeps the regularized reading), `<expan>`/`<abbr>`/`<ex>`,
  `<supplied>`, `<gap>`, and line breaks across a word boundary
  (`<lb break="no">`). Tests in `tests/test_epidoc_convert.py` run against
  17 small real EpiDoc samples in `tests/fixtures/epidoc/` (credited in that
  folder's README). No data from any source is in this repository: raw
  downloads and converted output live outside it, documented in a local
  `SOURCES.md`, per the open licences each source carries (CC BY-SA 4.0,
  CC BY 4.0, CC BY 3.0). Nothing in this change touches the live site, the
  search index, or the database.

### Help: corrections from a claim-by-claim audit
- Sixteen statements corrected against the code and the live site: stoplist
  sizes, the rare-vocabulary threshold (about one in eight works, not a fixed
  100), the quotation channel (every language, not Coptic only), the Max Results
  default (all results, not 5,000), the Latin qualifier on the 92 percent figure
  and its date, one consistent Arabic count (149 texts), Arabic pairs described as
  opening with Arabic, the cross-language setting's real name (Min Matches), four
  Greek-Latin channels not two, the Knauer benchmark (94 percent found somewhere
  in the ranking), and what the AI connector returns (a link, not charts).

### Help: Fusion page names every served language
- The Fusion page's note on examples now lists Hebrew, Persian and Urdu beside
  Greek, English and Coptic, and says correctly which channels Persian and Urdu
  run (nine: eight of the eleven plus refrain and rhyme) and that Greek has syntax
  data for about half its texts.

### Help: section blocks reordered to match the sidebar
- In HelpPage.jsx the content block for each section sat in an order
  unrelated to the sidebar's `sections` array, making the file hard to
  edit (2026-10-07 Help audit, item 7). Blocks moved, nothing else
  changed: reader-visible output is identical. Verified mechanically
  (same ids, each block byte-identical by SHA-256, code outside the
  blocks unchanged, new order equals the sidebar order).

### Help: one colour for the card bars
- The cards in Help carried thirteen different left-bar colours that meant
  nothing to a reader. They now share one light gray bar.

### Help: readable headings, one style per level, tidier contents
- Sidebar group labels are bold and dark with a rule above each group, and the
  entries sit indented under them. The labels had been smaller and lighter than
  the entries. This restores the fix approved on 2026-09-06, which was made on a
  branch that never merged.
- One style per level: every section title (24px bold, ruled), every subsection
  (18px semibold, above the 16px body; five competing styles before), every box
  label (small bold capitals in the box's colour).
- Boxes follow one colour rule: amber for cautions, blue for worked examples,
  gray for reference. Ten boxes in other colours were brought into it.
- Titles match the sidebar ("The Types of Search", "Repository", "Languages
  overview"). The cross-language card in The Types of Search links to the full
  page instead of repeating it. Understanding Results explains the "in N works"
  badge, the Formulas setting and the refrain and rhyme colours.

### Names rarity per script; how names are found, documented
- "Same people and places" counts a name's rarity within its script group, so
  extending the names index to Hebrew, Coptic, Persian and Urdu leaves Latin,
  Greek and English results unchanged. The builder writes one total per group
  and the reader uses the selected passage's.
- docs/DECISIONS.md and Help describe how names are found in each language.

### Sources page credits every Persian and Urdu text
- `backend/text_sources.json` had no entries for any of the 28 Persian or
  18 Urdu texts, so the Sources page credited nothing for either language.
  Added one entry per work (28 + 18): the Chronological Persian Poetry
  Dataset (CC BY-SA 4.0, built on Ganjoor) for 21 Persian works, the Iqbal
  Demystified Dataset for 11 Iqbal works across both languages (no LICENSE
  file, served as is per the 2026-09-03 decision), and Urdu Wikisource
  (CC BY-SA 4.0) for the other 14 Urdu works, Ghalib and Mir among them.
  Every source URL checked (`curl -sI`) before adding it.
- `scripts/corpus/verify_text_coverage.py -l fa --all` and `-l ur --all` now
  report `sources ok` for all 46 texts.

### "Same people and places" extended to Hebrew, Coptic, Persian and Urdu
- `scripts/corpus/build_window_names.py` (behind Similar Passages' "Same
  people and places" group) now marks names in four more languages, each
  from its own existing source rather than a new tagger run: Hebrew from the
  BHSA `nmpr` table already in `data/lemma_tables/hebrew_pos.json`; Coptic
  from `data/inverted_index/syntax_coptic.db`'s hand-curated UD tags, kept
  where a form is tagged PROPN at least 85% of the time and seen twice;
  Persian and Urdu from the Stanza tags already cached per line in
  `cache/lemmas/{fa,ur}/`, same 85%/3-occurrence purity rule, unioned with a
  short hand-built lexicon (Quranic/biblical figures, Persian and Urdu
  ghazal's stock beloved names, Karbala names for Urdu) and, for Urdu only,
  minus a hand stoplist of stock ghazal nature-images (wine, a ruby, dew, a
  leaf, a tulip, stars, eyelashes...) that the tagger treats almost as
  consistently as a real name. Latin, Greek and English are unchanged,
  confirmed byte-for-byte identical against the live index. Arabic stays
  held (Stanza finds no proper nouns at all in its 132-line corpus).
- Unit tests in `tests/test_build_window_names_other_scripts.py` cover the
  new per-language logic with toy fixtures, including an end-to-end
  `main()` run and the Urdu stoplist/lexicon precedence.

### Similarity Map includes Persian and Urdu
- `scripts/build_connections_map.py` and the map page's language list now include
  Persian and Urdu, served since today; the map is rebuilt on production with them.

### Quotation rows show their words; Tessa out of the way; safer passage rename
- Quotation-only results now list the words of the quoted run. They had no
  matched words once the scorer's markers were dropped, so the corpus chart
  called "jan-e man o jan-e shoma" (Hafez, quoted by Iqbal) a one-word parallel.
- The corpus chart's word filter keeps words with combining marks or the
  zero-width joiner, which Persian and Urdu words carry.
- Closed, Tessa is a small round button, and its x tucks it into a slim tab on
  the right edge, remembered in the browser. The two-line pill covered the
  corner of every page.
- `scripts/corpus/rename_work_in_passage_index.py` updates window_texts.db on a
  copy and swaps it in, since the live file is held open by the web workers.

### Persian and Urdu: refrain and rhyme across the pair; stoplists listed
- The Persian against Urdu search matches two poems that share refrain and
  rhyme in the shared letter forms (`backend/poetics.find_cross_form_matches`),
  as the single-language search does, excluding refrains of function words.
  Ten poem pairs across the two corpora, among them Hafez and Ghalib on "dost".
  Result cards show the refrain (docs/DECISIONS.md).
- The Persian and Urdu function-word stoplists, already used in matching, are
  listed on the Help page's Stoplists section.
- Similar Passages: an "In other languages" row under the list, one button per
  language with few results in it, opening that language's five best matches,
  for every language alike (docs/DECISIONS.md).

### Iqbal's diwan renamed into his other Persian works
- The Persian divan filed separately as `iqbal_lahori.diwan` (Ganjoor's Iqbal
  collection) is renamed `iqbal.diwan`, joining the seven other Persian-titled
  works already filed under `iqbal`. The two filings split one poet's charts
  and lists in two; the rename merges them under one author key.
  `backend/author_dates.json`, `client/src/utils/eras.js`,
  `data/poetics/form_signatures_fa.json`, `data/text_descriptions.json` and
  `data/text_genres.csv` updated; `data/poetics/ganjoor_iqbal_lahori.diwan.json`
  moved to `ganjoor_iqbal.diwan.json` with its ref ids rewritten. A new
  production script, `scripts/corpus/rename_work.py`, does the equivalent
  rename everywhere a work's name is held outside git (the `.tess` file and
  its line tags, the inverted index, the lemma cache, the passage index, the
  embeddings): dry run by default, `--apply` to act, every file backed up
  first. Production run (the `.tess`, the index, the caches) is a follow-up
  data operation, not part of this pull request.

### Help brought up to date; connector names Persian and Urdu
- Help: Persian and Urdu in the language lists; Arabic shown as indexed but not
  yet open, with its page left out of the menu until the site serves it; the
  Cross-Language page covers all seven open pairs; the Urdu page describes the
  eighteen texts now held; corpus, passage and parse counts match the live site
  (one figure per fact); the Reader section describes the two Similar Passages
  groups, opening a result at its passage with a way back, and the possible-echo
  rule; the English corpus is described correctly (the King James Bible, not a
  modern translation); the AI setup text lists eleven signals and the Persian
  and Urdu codes.
- Connector: tool descriptions name Persian (fa), Urdu (ur) and the fa-ur pair,
  and Theme Search is described as covering every served language.

### Corpus chart counts every work, not the first 500 lines
- Line search now returns `by_work_all`, the number of co-occurring lines in
  every work (a work held whole and in books counted once), taken from the
  index lines it already gathers, and `lines_all`, their total.
- The search results' "Across the corpus" chart (timeline, era, work) draws
  from those counts. It had drawn from the first 500 lines in index order, so
  for a common pair such as the Persian refrain "man ast" (4,759 lines in 25
  works) it showed two or three poets and left out Hafez and Iqbal, the poets
  being compared. Clicking an author whose lines were not among the 500 loaded
  fetches that author's own lines, and the caption gives the true total.

### The site remembers your language
- The search page and the Reader open in the language chosen last, kept in the
  browser's own storage (no account, nothing sent to the server). "Open in" at
  the end of the language tabs fixes a start language instead, for a reader who
  visits other languages but always starts in one. A link that names a language
  or a work still opens there. Help describes it under Languages.

### Reuse tab: Greek highlights, fewer empty "possible echoes"; Persian corpus chart
- Greek reuse lines now highlight their shared words. The Greek text stores
  accents as separate marks after their letters, and the word-edge test treated
  a mark as a non-letter, so a word ending in one never matched.
- A possible echo (one shared rare word-triple) needs a word-triple overlap of
  at least 0.002 with the other passage to be listed or counted in the gutter.
  This drops matches buried in long prose paragraphs, such as Argonautica 1.2
  beside a paragraph of Galen on the stomach (docs/DECISIONS.md).
- The search results' "Across the corpus" chart opens on the first parallel
  with two or more shared words, and the menu marks one-word rows. Persian and
  Urdu lists lead with one-word refrain matches, so the chart had opened empty.
- The Reuse tab and Help no longer say Latin only.

### Test fix: corpus picker race test reads the hook's author field
- `useCorpus.race.test.jsx` read `authors[0].name`, the API's field, where the
  hook hands out `author`; it failed on main for that reason alone. The hook is
  unchanged.

### Reader: a Similar or Verbal Parallels result opens at its passage, with a way back
- Opening a result in another work used to land at that work's first line and
  leave no way back but the browser. It now opens at the passage, selected, under
  a banner naming the passage left ("Opened from Quintus Curtius, Histories
  3.20") with a "back to" link that returns to that passage. The browser's
  Back button also returns to the line left instead of the top of the work.
- The arrival selection applies once, so drawing more lines while scrolling no
  longer reselects it over a line the reader has since clicked.

### Text removal finds every lemma cache file
- `scripts/corpus/remove_restricted_text.py` matched only `<work>.json` in the
  lemma cache and missed the content-hashed `<work>-<hash>.json` the cache also
  writes, for a work without book files. Found on its first run against real
  data, the duplicate Augustine fragment, where the hashed copy was removed by
  hand. A licence ending requires every copy deleted, so the finder now strips
  the hash before matching; the test covers both names.

### Duplicate Augustine fragment retired
- `texts/la/unknown.corpus_scriptorum_ecclesiasticorum_latin.tess`, a
  20-line excerpt listed as "Unknown", is chapters 32 to 46 of Augustine's
  De natura et gratia from the CSEL edition (volume 60), a work the corpus
  already holds whole. Its file, genre row, description, provenance and
  credit entries are removed; the index, passage windows, vectors and lemma
  cache are cleared on production (docs/DATA_OPERATIONS.md, 2026-10-07).

### Reader type
- The Reader's Gentium is served from the site itself (SIL's Gentium Book
  7.000, compressed to WOFF2 with its data unchanged, licence in
  `client/public/fonts/gentium-book/OFL.txt`). Google's copy lacked the
  free-standing combining accents the corpus stores, so grave accents drew
  detached from their vowels; the diagnosis is John James's (#624). Each
  style is about 360 KB, fetched only by pages that use it and shown with
  `font-display: swap`, so text appears at once in the fallback.

### Coverage gaps closed
- A work can carry its own date in `backend/author_dates.json`
  (`author.work`), which wins over its author's; dates added for 30
  anonymous Latin works (Carolingian poems, pilgrim itineraries) and two
  anonymous Greek geographies, which the browser showed as undated.
- Six Latin works gain genre rows; the Paschasius Radbertus book file
  had old-style line endings (carriage returns only) and is converted.
- The Sources page lists the eleven works whose source is not yet traced,
  marked "Source to be confirmed".
- The coverage checker no longer expects texts under ten lines in the
  connection map.
### Similar Passages: two groups by default
- The Reader's Similar tab now opens with "Same people and places" above
  "Same kind of scene" for every reader (trialled behind ?names=1 earlier
  today; ?names=0 shows the single list for comparison). The name index's
  builder is `scripts/corpus/build_window_names.py`, run after any change to
  the passage index.

### Similar Passages: same people and places (trial, behind a switch)
- With `?names=1` on a Reader address, the Similar tab shows two groups:
  passages in other works that share rare proper names with the selection
  (ranked by scene similarity and the names' rarity, each card naming the
  shared names, commentaries on a work set aside), then the usual
  same-kind-of-scene results without those passages. `/passages/similar`
  gains a `same_names` field when asked with `same_names=1`; without it the
  response is unchanged. Reads `data/passage_index/window_names.db`.

### Rare word-pair tables
- The rebuild counts bigrams as it reads them instead of holding every
  occurrence in one list, which grew past the 12 GB cap for Greek; with the
  lemma cache unused the English table comes out identical. It now reads
  each text's units from the lemma cache, the units the search itself uses,
  falling back to processing the file: ten times faster, and the English
  table differs from a fresh processing run by 0.3 percent of occurrences.

## 2026-10-06

- Vegio's Supplementum (`maffeo_veggio.supplementum`): line numbers made
  sequential within each book. The file carried numbers with their trailing
  zero lost (1.10 written 1.1, 1.100 written 1.10), so 16 references repeated.

### Corpus
- The text filed as Polignac, "Imitatio", is Maffeo Vegio's Aeneid
  supplement (book 13, opening "Turnus ut extremo devictus Marte profudit"),
  a second edition beside `maffeo_veggio.aeneid`. Renamed to
  `maffeo_veggio.supplementum` with line tags `vegg. supp.`; credits, genre
  and description follow. The index, passage windows and vectors are moved
  by the data operation recorded in docs/DATA_OPERATIONS.md.

### Sources page
- 297 works that had no entry on the Sources page are credited (166 Greek,
  99 Latin, 32 English), each with its digital source and, where known, the
  print edition, traced from the import records; credited to "Tesserae
  Project". Nine works remain untraced.

### Text descriptions
- About-this-text descriptions for Erchempert's verse martyrology,
  Callimachus' Iambi and Philo's Allegories of the Laws, the three works the
  coverage checker found without one.
### Corpus browser
- Dates and eras for authors the browser showed as undated: pseudo-Caesar,
  Censorinus, Germanicus, Grattius, Obsequens, Solinus, Vegetius, Francis
  Glass and the Confucius Sinarum Philosophus; the Septuagint books (filed
  under the key "septuagint") now show the Hellenistic date their entry
  already carried.

### Menus
- Every menu that lists names (Reader author, work and book; Search work and
  text; Line Search author and work; Cross-language work and section) opens
  as a full list on click and also narrows as you type: names starting with
  the typed letters first, then names containing them, ignoring case and
  accents (shared `SearchableSelect` component; phones keep the native menu).

### Reader: Similar Passages for a selection
- A Reader selection is matched to the passage window that covers it by
  every reference coordinate, within the book being read. It compared only
  the last two numbers and searched every book, so in works cited
  book.chapter.section (Curtius, Livy, Ammianus and others) a selection
  could get another book's window: Curtius 3.1.1-4 showed Similar Passages
  for 10.1.1-12. The same match feeds the fusion search's context channel
  and the connector's theme_pair_lift.

### Theme Search
- 19,978 more Persian, Urdu and Arabic passage windows in the index (Urdu
  coverage grows from 2,150 windows to 14,759); Arabic is held out of results
  (data operation recorded in docs/DATA_OPERATIONS.md).
- Arabic passage windows are held out of Theme Search and Similar Passages
  until a reader has graded Arabic (`held_languages()` in
  backend/passage_index.py; TESSERAE_HELD_LANGUAGES overrides; a server that
  serves Arabic through TESSERAE_LANGUAGES, the preview, still shows them).
  The windows stay indexed, so opening Arabic needs no rebuild.

### Semantic channel
- Semantic vectors now exist for every Latin, Greek and English work, so the
  semantic channel runs in every comparison. Before, 443 Latin works, 284 Greek
  and all 41 English had none and the channel silently returned nothing for them;
  31 older vector files with the wrong number of rows were re-encoded and
  replaced (data operation recorded in docs/DATA_OPERATIONS.md).

### Persian and Urdu search (from the first expert review)
- The refrain-and-rhyme channel returns one result per pair of poems, the
  opening-line pair, with the poems' other refrain lines listed on the
  result card. Before, every line pair of the two poems was a separate
  result, so a ranking of 200 held a handful of poem pairs repeated.
- A shared refrain and rhyme is weighed by how many poems in the whole
  corpus of the language carry it (scripts/build_form_signatures.py writes
  data/poetics/form_signatures_<lang>.json; the result card shows "form in
  N poems"). Before, rarity was measured only within the two texts.
- Cross-language results carry the formula count (how many works share the
  result's wording), looked up in each side's own language tables, so the
  "in N works" badge and the hide control work for Persian against Urdu.
### Translations
- Quintus Curtius, History of Alexander (books 3-10): J. C. Rolfe's 1946 Loeb
  translation, public domain in the United States, aligned section by section
  (96.5% of sections exact, four chapters whole) for the Reader and the
  translation shown beside search results (`scripts/translations/align_curtius.py`;
  the data operation is recorded in docs/DATA_OPERATIONS.md).

### Search and interface (collaborators' changes)
- The main search results can be sent a page at a time: with a page_size the
  search stores its full ranked list for six hours and returns the first page
  with a result id, and further pages, sorting, filtering and the export are
  served from that stored list without searching again. Without page_size the
  response is as before, so the connector and scripts are unchanged (#614).
- Pagination behaves the same way across the search results and the data
  views (#615, rebased onto main after #614).
- The admin request listing is paginated, filtered and sorted on the server,
  with every filter and sort value checked against a fixed list (#610).

- Each fused search result carries channel_token_attrs: for every channel
  that matched the pair, the word positions it matched on each side, so a
  display can mark lexical, sound and other matches differently without
  searching again. Results computed before this change and served from the
  results cache carry the field empty until the search is run again (#618,
  a collaborator's change).

### Connector
- The installed (stdio) connector gains the seven tools the web connector
  already had: compare_texts, theme_search, get_passage, similar_passages,
  theme_compare, theme_pair_lift and describe_text (#619).

## 2026-10-05

### Admin and corpus
- The admin user listing fetches every user's roles in one query where it
  made one query per user (#609, a collaborator's change).
- The Text Credits page's parsed metadata is cached between requests and
  reread only when the file's modification time or size changes (#612, a
  collaborator's change).

### Data operations
- 2026-10-05 06:18 to 06:20 EDT: the Persian, Urdu and Arabic texts, inverted
  indexes, lemma caches, bigram and frequency tables and line embeddings
  copied into production from the development checkout, unserved: the
  languages endpoint is unchanged until TESSERAE_LANGUAGES names them.
  Record in docs/DATA_OPERATIONS.md.


## 2026-10-04

### Languages
- The search engine's hook points for Persian, Urdu and Arabic, ported from
  the development branch onto the current code: the per-language stoplist
  dispatch in the matcher, the sound channel's gate and cap for Arabic
  script, the form channel (refrain and rhyme for ghazals, default weight 0,
  enabled by the persian_ghazal profile), the Arabic root rarity in the
  scorer, the per-search e5 floor in the semantic channel, the cross-script
  dictionary channel and inflected-form line search, the rare-words list
  rules, the hemistich marks in the text processor, and the passage index
  and Theme Search paths for the three languages. The three languages
  register, and join the corpus list, only when TESSERAE_LANGUAGES names
  them, so production carries the code and serves nothing new. Tests: the
  six ported suites pass, two assumptions in them updated to main's current
  constants (the quotation weight, twelve channels).

### Interface
- The pages know Persian, Urdu and Arabic: tabs in Browse Corpus and the
  Rare Words Explorer, era lists for the three, right-to-left text and the
  Arabic-script folding used to highlight matches, the refrain, rhyme and
  meter badges on a result pair, inflected-form hints in Line Search, the
  Arabic-script font in PDF exports, dictionary links for the three, and
  Downloads entries. Only the demo branch's language-related changes were
  taken; main's own citations, help text, sample searches and era table
  stand. Nothing shows until a server serves one of the languages.

### Search
- The results page no longer downloads every parallel to show one page of
  them. A parallel search now asks for its page size; the server still runs
  the whole search exactly as before, keeps the finished list on disk for
  six hours (`tmp/search_results/`, at most 1 GB, oldest removed first) and
  sends the first page with an id. Later pages, the Sort menu and the chart's
  bar filter are requests to `GET /api/search-results/<id>`, which filters
  and sorts the whole list before cutting the page. The chart counts come
  from the server, CSV/PDF export fetches the full list when clicked, and the
  "Across the corpus" picker lists the parallels on the current page. On a
  1,456-row lemma search the final response fell from 3.8 MB to 0.1 MB.
  Search time is unchanged. Requests without `page_size` (connector, agents,
  scripts) get the same full response as before.

### Tessa
- "Are you still working?", "is it done?" and the like, asked after a
  comparison that outlasted her wait, are now answered about that
  comparison: the two texts come from the reader's earlier turn (with any
  shared book number), the finished run is read from the cache at once,
  and an unfinished one is reported as still running. Before, a question
  that named no text got a stock answer about the tool.

### Corpus
- `texts/grc/aelius_herodianus.on_enclitics.tess` carried CTS-URN line tags
  on all 26 lines, the same fault #578 fixed in 21 Septuagint files. The
  tags are now the plain form every other Greek file uses, with the line
  text unchanged. The stored references derived from the file are rebuilt
  in a data operation after this merges.
- Lemma tables, poetics data and a font added for Arabic, Persian and Urdu:
  three surface-lemma tables, ten poetics data files, and the Arabic-script
  font `NotoNaskhArabic-Variable.ttf`, all new files. Metadata entries for
  the 194 works in these languages were added to `data/text_descriptions.json`,
  `data/text_genres.csv` and `backend/author_dates.json`, leaving every
  existing entry in those files unchanged. The text files themselves are not
  in the repository. Nothing is served yet: no language handler is
  registered for `ar`, `fa` or `ur`, so none of the three appears in the
  corpus list, Browse Corpus, Theme Search or downloads.
- The per-language modules for Arabic, Persian and Urdu (tokenizers,
  normalizers, stoplists, the shared Perso-Arabic comparison form and the
  poetics/form-matching module) are now in the repository as new files
  under `backend/arabic/`, `backend/persian/`, `backend/urdu/`,
  `backend/perso_arabic.py`, `backend/poetics.py`,
  `backend/served_languages.py` and `backend/surface_lemmas.py`, each with
  its own `register()` function in the same pattern as Hebrew and Coptic.
  Registered by nothing: no file on main calls `register()` for these three
  languages, so they serve nothing yet and the corpus list, Browse Corpus,
  Theme Search and downloads are unchanged. The hook points that will call
  them, add the `form` fusion channel and apply the curated stoplists are a
  later pull request.

### Data operations
- 2026-10-04 12:45 to 12:51 EDT: the Herodian On Enclitics line tags
  followed into the Greek index (one file replaced, `lemma_doc_freq`
  rebuilt, backup kept), the passage index and the map caches; no URN
  reference remains anywhere. Record in docs/DATA_OPERATIONS.md.
- 2026-10-04 08:12 to 08:18 EDT: 175 more passage windows received their
  new description and vector in the live index (510,759 of 510,839 now
  carry the re-described text, 80 keep the August text); word index
  rebuilt. Record in docs/DATA_OPERATIONS.md.

## 2026-10-03

### Blurbs
- 1,559 of the 1,649 work descriptions rewritten for readability: three to
  nine sentences of at most 40 words, no list over four items, no Latin or
  Greek quoted except a title, each Latin or Greek title glossed in English
  at its first mention (199 glosses, every one checked, 8 corrected or
  removed), and the sentence explaining a title or a work's background
  restored where the complete-text rewrite had dropped it. Across the
  changed descriptions the longest sentence fell from a median of 55 words
  to 27. 90 descriptions keep their text; two more were edited by hand.

### Search
- The semantic channel computes similarity in blocks of 512 source rows
  against pre-normalised vectors, never the whole matrix. A pair of 9,502
  by 157,780 lines (two Persian diwans, all results) built a 6 GB table
  twice over and was killed at a 20 GB memory cap three times in an hour on
  the demo server; the same code ran on the live site. The pairs returned
  are the same as before, in the same order (test).

### Jobs
- A GPU job on the campus cluster can return its result file: `PUT
  /api/jobs/upload/<job>/<name>` with the job's token in `X-Job-Token`
  stores the body under `data/job_uploads/<job>/` and answers with the size
  and SHA-256. The token is a file the maintainer writes before submitting
  the job (`scripts/jobs/new_upload_token.py`), compared in constant time;
  names are plain tokens, the body streams to disk, and one upload is
  capped at 512 MB so a large result goes in parts. Until now the cluster
  could fetch our inputs but return only log lines.

### Tessa
- Two more reading rules: "suggests", "suggesting", "reinforcing the idea"
  and "supports a reading" count as hedges like "likely" and "may", and
  authors are spelled as the site spells them (Vergil, never Virgil).
- "compare Aeneid 1 and Silius Italicus Punica 1" now compares the two first
  books. The author's name resolved first, to the whole Punica, and the
  two-text limit stopped the reading before "Punica 1" could narrow it, so
  Tessa ran one book against seventeen and reported the comparison still
  running. A later, narrower mention of a text now replaces the whole-work
  hit, and every capitalised name in the question is read before the limit
  applies.

### Help
- "How the system is built" says how the server reaches the two BullsAI
  parts: the gateway with a project key that carries a daily allowance, the
  compute with a service account that lets the server start GPU jobs on its
  own, since a person's sign-in expires after a few hours. Both boxes in the
  diagram carry an access line. No credential appears anywhere in the page
  or the code.

### Browse Corpus and Reader
- The button that opens a work's description now reads "About this text"
  in both places (it read "About", which said too little, especially in the
  Reader's header). The description itself is set at a reading width of
  about 65 characters with a looser line height, in a slightly larger type
  in Browse Corpus, where it had run the full width of the page as a slab
  of 300-character lines. The "Theme Search" badge on a covered work, a
  plain label until now, opens Theme Search with that language chosen, and
  the Theme Search page takes the language from such a link whether or not
  a query comes with it.

### Corpus
- Fixed 208,992 breathing and accent marks in 774 Greek files that were
  stored before the Greek vowel, or rho, they belong to (stored as
  ` ̔Ηροδότου`, should read `Ἡροδότου`), the result of a conversion
  convention that wrote the mark to the left of a letter. 207,362 of these
  sat before a capital, 1,630 before a lowercase word-initial vowel at a
  line start or after a space, the same fault (Strabo: marks before "ετι"
  for "ἔτι"). `scripts/corpus/fix_greek_capital_marks.py` moves each run of
  marks onto its letter and composes the precomposed form with NFC. A
  breathing or accent only ever belongs on a vowel, or a rough breathing on
  rho, so the fix is restricted to those letters: a mark before any other
  consonant, capital or lowercase, is left exactly as stored. Achilles
  Tatius 2.11.3 is the case that set this restriction: ` ̓μέθυστος` is a
  damaged ἀμέθυστος missing its alpha, and an earlier, wider version of
  this fix moved the smooth breathing onto the following mu, producing the
  nonsense `μ̓έθυστος`. The restriction leaves 97 capital-consonant and
  1,074 lowercase-consonant cases untouched, on top of about 130 further
  cases where an accent or breathing sits on a consonant mid-word, a space
  with no letter following, or a non-Greek character. All of these, 1,347
  cases in 133 files, are listed in
  `data/proposals/greek_stray_marks_2026-10-03.csv` for manual correction
  against an edition. This pull request does not change them. A sample of
  twenty affected lines, checked against the production tokenizer, showed
  the surface token wrong in all twenty cases (breaking exact-match and
  display) and the lemma wrong in one of twenty, where the word fell
  through the lookup table to the neural fallback. The Greek lemma caches,
  the Greek search index, and the stored passage wording for the changed
  files are rebuilt in a data operation after this merges (the maintainer
  runs it).

### Downloads
- The licence box states the current terms: open digital editions named
  on the Sources page, the Hebrew Bible text under CC BY-SA 4.0, translations
  public domain or non-commercial with attribution, and the derived tables'
  terms (BHSA CC BY-NC, Koine CC BY-NC-SA, GLAUx CC BY-SA, MQDQ CC BY-NC-ND).
  It had named PHI Latin Texts, which the corpus does not hold.

### Tessa
- When reading results she reports the engine's commonness figures as what
  the data says and no longer writes that a parallel "likely" reflects
  convention or allusion; anything beyond the figures goes in a sentence
  beginning "As background".
- Her health check of the campus model service allows eight seconds and
  keeps her available for three minutes after a good answer, so one slow
  reply under load no longer turns every question into "the assistant is
  not running just now" for the next twenty seconds.

### Data operations
- 2026-10-03 23:30 to 23:35 EDT: the passage descriptions behind Theme
  Search and Similar Passages replaced by the whole-corpus re-description
  (GLM 5.3 Flash; 510,584 of 510,839 windows), with their vectors and the
  word index, after retrieval measured level or slightly better (precision
  at ten 0.381 to 0.403). Record in docs/DATA_OPERATIONS.md.
- 2026-10-03 10:23 to 11:30 EDT: full Greek rebuild after #590 (lemma caches,
  index with `lemma_doc_freq`, bigram and frequency tables) and the stored
  wording of 21,395 passage windows refreshed for the 459 changed works.
  Scan afterwards: 0 misplaced marks remain in 1,268 files. Record in
  docs/DATA_OPERATIONS.md.

## 2026-10-02

### Tessa
- Every pair Tessa reads now carries corpus-wide figures on its shared
  words (in how many of the language's texts each occurs: rare, uncommon or
  common) and on how many works the pairing recurs in, so a verdict of convention or allusion rests
  on the data in front of her.
- When Tessa reads results she treats Latin u/v and i/j as one letter (arua
  and arva are the same word, never a spelling difference), and she may call
  a parallel convention or shared stock only when a fact in front of her
  shows it, in place of "appears to reflect" with nothing behind it.
- Tessa reports "running the comparison of X with Y" before she asks the
  search for it; for a small pair the comparison computes inside that call
  and the panel had shown "reading your question" for forty seconds.
- "Compare book 1 of each" scopes the comparison to the two books; the
  whole works had been compared, a run of many minutes. When a comparison
  outlasts her wait she now says it is still running and points at the
  results page, where the same run appears when it finishes, in place of
  the stock sentence that the corpus holds both texts.

### Data operations
- Septuagint retag (#578): lemma caches and index rows for 21 files,
  stored references in the passage index and the map caches rewritten
  (run 10:24 to 10:30 EDT). Backups `grc_index.db.bak-lxxrefs-20261002-1024`
  and `*.bak-lxxrefs-20261002-102838`. Record in docs/DATA_OPERATIONS.md.

### Texts
- The 21 Septuagint files that still carried CTS-URN line tags
  (`<septuaginta.tlg001 urn:cts:greekLit:tlg0527.tlg001.1st1K-grc1.1.1>`) are
  retagged to the plain form the other 34 use (`<septuaginta.genesis 1.1>`),
  13,729 lines; the stored references in the passage index and the
  connections-map caches follow through
  `scripts/corpus/retag_septuagint_refs.py`, and the search index rows and
  lemma caches are rebuilt for the 21 files (#564, data operation recorded
  in docs/DATA_OPERATIONS.md).
- The 55 Septuagint files show readers' book names, the Greek book's
  conventional English name with the Hebrew Bible's name in brackets where
  the two differ: "1 Kingdoms (1 Samuel)", "3 Kingdoms (1 Kings)", "Judges",
  "3 Maccabees", "Lamentations", "Daniel (Theodotion)"; the author shows as
  "Septuagint". They had shown transliterated file names (Basileion G,
  Kritai, Machabaeorum G) (#564, display overrides in
  `backend/text_metadata_overrides.json`).

### Corpus
- Per-text blurbs, second pass: 621 of the 894 works held back by the first
  check (#539) now have a blurb in `data/text_descriptions.json` (Greek 375,
  Latin 240, English 6), written by GLM 5.3 Flash from an 80-line opening
  and checked for contradictions by Qwen 3.8; 257 are still held back and 16
  returned no blurb. `scripts/corpus/describe_works.py` gained the
  second-pass mode (`--second-pass`, `BLURBS_JOB_DIR`, `BLURBS_OPENING_LINES`).

### Texts
- A part file that carries a label after its number is titled by the label:
  Livy "Books 21-30", Suetonius "Vespasian", Pliny "Preface", the
  Vulgate's "1 Chronicles", the English Bible's "Matthew" (#565, and the
  Vulgate and English Bible rows of #564). Eleven works and two Bibles, 219
  files, had shown "Book N" by file order. Files with a bare number are
  unchanged.

### Search
- Search result cards and Corpus search show `Author, Work title locus` for
  every text, built on the server the way Line Search has always built it,
  instead of the browser guessing author and work from the raw `.tess` tag.
  The guess broke on any text outside the browser's hand-kept abbreviation
  tables: doubled dots (`Ach..Tat..1.1.0`), raw file-id slugs
  (`bohairic.i_corinthians.1.1`), CTS URNs. A sweep of the first, middle and
  last tag of all 3,496 texts found 1,551 broken on search cards and 634 in
  Corpus search; the server-side citation builder now passes the same sweep
  (`scripts/review/check_result_citations.py`) at zero. The browser's old
  tag-parsing tables stay as a fallback for results cached before this
  shipped. (#577)

## 2026-10-01

### Tessa
- A request the campus gateway refuses (HTTP 429, or 502 and 503) is retried
  up to four times with a short pause before the assistant gives up. On the
  evening of 2026-10-01 the gateway refused about four requests in ten,
  intermittently, and half of Tessa's answers failed.

### Hebrew
- A Line Search word typed without vowel points matches every homograph
  reading of its consonants: a bare אל finds אל "to", אל² "not" and אל³
  "God", where it found only the commonest reading. A reading the stoplist
  drops gives way to the first content reading, so אל in a longer query
  still reaches "God". Pointed queries are unchanged.

### Help
- The Tessa page says what she does and where she runs (an open model on the
  university's AI platform, questions stay on campus). The paragraph that
  still placed her on the Tesserae server, and the sentences that described
  her by what she is not, are gone.

### Admin
- The Performance tab's concurrency controls keep following the server
  after the first load, and when running searches exceed a lowered cap the
  card says the system is draining and shows the count (#148).

### Greek
- A classical lemma table for the forms neither the treebank table nor the
  Koine table covers: `data/lemma_tables/greek_classical_lemmas.json`,
  365,997 forms built by `scripts/corpus/build_greek_classical_table.py`
  from the GLAUx treebank corpus, 936 treebank files of ancient Greek
  literature published by the Perseids Project under a Creative Commons
  Attribution-ShareAlike licence, attribution in
  `GREEK_CLASSICAL_LICENSE.txt`. It loads after the treebank table and the
  Koine table and fills only what both still lack, and the 6,136 forms
  where it disagrees with an existing table are kept in
  `greek_classical_conflicts.json` for review and not applied. The forms
  neither existing table covered were 14.4% of all Greek tokens on the
  production index, and the new table resolves 90% of them, the Iliad and
  Thucydides covered almost entirely. Greek lemma caches and index to be
  rebuilt.

### Corpus
- Septuagint text: 262 occurrences of a bare κα, on 244 lines of 11 books,
  corrected to καὶ, the same class of error as the κοὶ of #554 and found
  while measuring the Greek lemmatizer on the Septuagint. The list is
  `data/proposals/septuagint_ka_2026-10-01.csv`; no other word changed.
  Index rows and stored wording refreshed in the Greek rebuild that
  follows the tokenizer and Koine table changes.
### Greek
- A Koine lemma table for the forms the treebank table lacks:
  `data/lemma_tables/greek_koine_lemmas.json`, 31,069 forms built by
  `scripts/corpus/build_greek_koine_table.py` from the Rahlfs Septuagint
  morphology repository (Creative Commons Attribution-NonCommercial-ShareAlike
  4.0, a derivative of the CCAT analysis, attribution in
  `GREEK_KOINE_LICENSE.txt`). The treebank table wins wherever both have a
  form, and the 1,336 forms where the two disagree are kept in
  `greek_koine_conflicts.json` and not applied. On the production index 11%
  of Septuagint tokens carried a lemma that is no known lemma, and the table
  covers four fifths of them. Greek lemma caches and index to be rebuilt.

### Dictionaries
- Hebrew-Greek: 74 equivalents added from the second pass on the 1,787
  verse-alignment candidates of #519 (`backend/synonymy/v6_additions/hebrew_greek.csv`,
  comment line dated 2026-10-01). A model judged each pair with its BHSA
  glosses, 88 of its 216 yes rows were dropped because the Greek side was a
  lemmatizer artifact, and the remaining 128 were read by hand: 97 kept, 23
  of them already present. Among the additions: עד with αἰών, μάρτυς and
  μέχρι, אשרי with μακάριος, מאד with σφοδρός, שבע with ὄμνυμι and ἕβδομος.
- Hebrew-Latin: the bridged dictionary of 29,901 pairs is filtered to
  5,922. Pairs that share aligned Hebrew/Vulgate verses across 36 books
  (Psalms now included through Jerome's psalter from the Hebrew) stay when
  they co-occur well above chance and a model judge does not reject them,
  which removes frequent companions such as gold against argentum.
  Unattested pairs stay when two models independently judged them
  translation equivalents at high confidence and the Hebrew side is a
  dictionary form,
  and the rest are listed with reasons in
  `data/proposals/hebrew_latin_dropped_2026-10-01.csv` (HE.5). The medial-
  letter spellings the bridge inherited from CATSS are now matched as the
  lemmatizer writes them.
### Greek
- The Greek tokenizer treats the ano teleia, the middle dot, the Greek
  question mark and the spacing breathings and accents of the Extended
  block as word boundaries. They sit inside the Greek Unicode blocks and
  had ridden along on the word: the Septuagint text writes "αὐτοῦ·" and
  "᾿Ισραήλ", which the index held as the tokens "αυτου·" and "᾿ισραηλ",
  lemmatized as themselves. Greek lemma caches and index to be rebuilt.

### Data operations
- Full Greek rebuild for the classical lemma table (#571), 19:46 to 20:34
  EDT: lemma caches, index (221,708 distinct lemmas, from 464,732, as
  unresolved surface forms fold into dictionary forms), frequency table and
  bigram table. Backups `grc_index.db.bak-greek-20261001-1946` and
  `cache/lemmas/grc.bak-greek-20261001-1946/`. Record in docs/DATA_OPERATIONS.md.
- Full Greek rebuild for #558, #559 and #560: lemma caches, index, frequency
  and bigram tables, stored wording of the κα books (docs/DATA_OPERATIONS.md,
  2026-10-01).
- Hebrew index, lemma cache, frequency table and bigram table rebuilt for
  the homograph lemmas of #552 (docs/DATA_OPERATIONS.md, 2026-10-01).
- Greek index rows, lemma caches and stored passage wording refreshed for
  the 15 Septuagint books corrected in #554 (docs/DATA_OPERATIONS.md,
  2026-10-01).

### Scripts
- `scripts/corpus/rebuild_bigrams.py` registers the plugin languages before
  counting, and refuses to swap in a table with no bigrams. Without the
  registration a Hebrew or Coptic rebuild fell through to the Latin
  tokenizer and wrote an empty table over the live one.
### Corpus
- Septuagint text: 158 occurrences of κοὶ (and κοί) corrected to καὶ (καί)
  across 15 books (#523). The 157 in
  `data/proposals/septuagint_koi_2026-09-30.csv` plus one in the Psalms of
  Solomon that a paragraph mark had hidden from the search. No other word
  changed, and standalone κοὶ no longer occurs in the Septuagint files. The
  Greek index rows, lemma caches and passage-window text for the 15 books
  are refreshed in the matching data operation.

### Hebrew
- Homographs are told apart by their vowel points (#483). One consonantal
  spelling often covers several words (אל is "to", "not" and "God", עם is
  "with" and "people", מלך is "king" and "he reigned"), and the lemma table
  keyed by consonants gave 5.2% of BHSA's word occurrences the wrong lemma.
  The lemmatizer and tagger now look a word up by its pointed form first
  (`data/lemma_tables/hebrew_lemmas_pointed.json`, `hebrew_pos_pointed.json`,
  built with the consonantal tables by `scripts/corpus/build_hebrew_tables.py`)
  and by consonants when that misses. Homographs carry a superscript numeral
  in order of frequency (אל, אל², אל³), and `hebrew_homographs.json` lists
  every group with its gloss. The cross-language dictionaries, keyed by consonants,
  are reached through the numeral-stripped form. The stoplist stops the
  function readings only: it had stopped אף "nose" and נגד "report" for
  "even" and "opposite", and had left עם "with" and שם "there" off because
  their one lemma also meant "people" and "name". Wrong lemmas on BHSA fall
  from 21,687 occurrences to 4,804. On the held-out doublet 2 Samuel 22 =
  Psalm 18 (51 verse pairs) the default search finds 10, 35, 40 and 47 of
  them in the top 10, 50, 100 and 500, against 10, 36, 43 and 47 before.
  The one large mover is the pair whose extra shared word was עם "with",
  now stopped as the function word it is.
### Help and Tessa
- Tessa's dock reads "AI Assistant" under her name.
- The system schematic says which path is Theme Search's alone (the query
  encoder and the Reader) and which jobs go where: corpus jobs rebuild the
  data on disk, describing batches go to the gateway, GPU jobs run on the
  compute.

### Help
- The system schematic simplified: port numbers, the memory-cap note and
  the entries on paid models and preview sites are out, and the compute
  column names only what it does.

### Help
- A "How the system is built" topic under Reference & tools: a drawn
  schematic of every machine part (the server, its two helper services, the
  BullsAI gateway and compute), the data each reads, and the recurrent and
  one-off jobs.

### Infrastructure
- Stanza is pinned below 1.15. The 1.15.0 release of 2026-10-01 changed how
  the Hebrew model splits prefixed words, and an unpinned install made the
  test suite fail on every pull request opened after the release. Local and
  production installs run older versions and are unaffected.

### Search
- Formula filter: a parallel's shared words carry a formula_count, the
  number of corpus works where they recur together (a shared bigram of the
  two rarest shared lemmas, or one lemma's own count when only one is
  shared). A new search setting hides parallels above a chosen count or
  shows only those at or above it, so a set phrase like a Hebrew narrative
  formula can be hidden as clutter or isolated as the object of study. The
  "Formulas" control sits beside the stoplist settings, and a grey "in N
  works" tag marks each counted result. Measured on the cached Aeneid 1 vs.
  Lucan 1 fusion run: 36 of the top 100 parallels had no bigram-table entry,
  42 recurred in more than 5 works, 21 in more than 20.

### Corpus
- A text can now be licensed for indexing and search only: it sits on the
  server under `texts/<lang>/` like any other text and every search, the
  Reader and the passage windows treat it the same way, but it never reaches
  the public repository or a downloadable bundle. A registry
  (`data/restricted_texts.json`, empty by default) names which texts these
  are. `backend/restricted_texts.py` is the one place that answers whether a
  given text is one of them. Enforced at both exits a text could otherwise
  leave by: the per-language texts download and the passage-index release
  script withhold a restricted text and report how many were withheld.
  `scripts/corpus/restricted_texts_gitignore.py` turns a registry entry into
  a `.gitignore` rule so it is never committed. Wherever a passage is shown
  (search results, the Reader header, Similar Passages, Theme Comparison,
  and the Sources page) a small credit line now appears beneath it when the
  text is restricted. `scripts/corpus/remove_restricted_text.py` is the
  removal procedure for when a licence ends. It is a dry run by default,
  reporting what it would remove from the texts, the lemma cache, the
  inverted index and the passage index before anything is deleted.

## 2026-09-30

### Tests
- A graded set of forty questions checks the assistant's facts and refusals
  against the live site, `scripts/assistant_accuracy_check.py`.

### Corpus
- Seven Latin poetic texts (Prudentius five works, Dracontius Orestes and
  Satisfactio) re-sourced from Musisque Deoque to Perseus and Corpus
  Corporum. The converter keeps one line per verse in bare-verse TEI.
- Per-text blurbs written for 33 English, 355 Latin and 301 Greek works that
  had none, by GLM 5.3 Flash on the campus gateway from each work's opening
  lines and source record, checked by a second model (Qwen 3.8) for
  contradictions and implausible specifics against the same inputs rather
  than for unverified detail. 894 of 1,583 attempted were held back.
  `scripts/corpus/describe_works.py`.

### Search
- Hebrew-Greek dictionary: twenty-six equivalents for the commonest Hebrew
  words that the CATSS-derived list lacked (ποιέω for עשה, ἕως for עד, νῦν
  for עתה, πατάσσω for נכה and others), chosen from the pairs that co-occur
  far above chance across 20,240 aligned Hebrew and Septuagint verses
  (#519). The full list of candidates stays under data/proposals/. (#538)
- Hebrew-to-Greek search can route around the Septuagint pivot. A new
  setting answers the search through the Septuagint (default, unchanged),
  directly by dictionary, or both at once with each result labelled by the
  route that found it. Added to the Cross-Language form and the connector.
  (#536)
- Hebrew-Latin dictionary rebuilt from the main Greek-Latin dictionary and
  the curated pairs Greek-to-Latin search itself uses, not only the two
  small V6-additions CSVs. 20,631 to 29,907 lines. Vulgate Genesis token
  coverage 42.7 to 59.3 percent. (#536, closes #518)
- An exact-phrase Line Search of a single word returns its lines again. The
  two-lemma rule that belongs to co-occurrence searches no longer applies to
  exact searches, so a one-word Coptic query that returned nothing returns
  its 500 lines. (#509, closes #502)
- Hebrew cross-lingual dictionaries match lemmas written with final letters.
  The Hebrew-Greek and Hebrew-Latin tables write a word-final kaf, mem, nun,
  pe or tsade in medial form, so 1,125 and 552 keys could never match the
  lemmatizer's output. The loader now converts them. (#524, closes #517)
- Hebrew stoplist: ten entries that could never match a lemma removed, and
  the words for "with" and "there" taken off because as consonantal lemmas
  they cover "people" and "name" more often than the function words.
  Measured over the whole Hebrew Bible, decision recorded in
  docs/DECISIONS.md. (#507, part of #483)
- Cross-lingual dictionary matching: duplicate word matches for a lemma
  repeated in a line are collapsed, so they no longer inflate rarity scores.
  The Latin stoplist is folded to the u and i spelling the lemmas use. The
  vector-similarity recovery step is skipped for Hebrew and Coptic, whose
  embeddings live in a different space from the Latin and Greek ones. (#525,
  closes #520, #521, #522)
- Theme Comparison: two works or books read against each other by content,
  on the Theme Search page and in the connector as theme_compare (#535)
- Theme Comparison shows the shared wording inside each pair when the
  word-level comparison is cached, and word-level results carry the theme
  lift of their surrounding passages (#541)

### Assistant
- Asked to compare two texts, Tessa now runs the comparison and reads its
  first page, waiting up to a hundred seconds if the run has just started,
  instead of only handing over the control that opens it. The copy that
  called her search help now says search, read, interpret, and the results
  page invites the reader to ask her what the evidence shows. (#533)
- Two checks on the assistant's accuracy. Every exchange is kept on the
  server, without any identifier, for a weekly reading
  (`scripts/assistant_record_review.py`), and a second pass asks the model
  which specific claims in an answer (a date, an attribution, a title, a
  work's contents) the material it was shown does not support, and replaces
  or drops those sentences before the page keeps them. The Privacy page
  says so and no longer names a hosting company the site left. (#532)
- Tessa's prompts ask for judgement as well as report, now that a larger
  model answers: which parallels look like deliberate allusion and which
  like the stock of the genre, why a genuine one would matter, background
  marked as background. She sees ten passages instead of five, may write
  two paragraphs, is handed the corpus's holdings for any author a
  question names, and every citation, quotation and number guard still
  runs. The Help page says what she does. (#531)
- Tessa's model client can reach a keyed OpenAI-compatible gateway as well as
  the local model server, by configuration alone. It adds a bearer key, extra
  request fields (a model's thinking switch), a broader health check and a
  twenty-second availability cache. Unset, nothing changes. The Help page's
  sentence on where her model runs is updated. (#528)

### Data operations
- Afternoon: the assistant switched to the campus AI gateway and its local
  model server retired; the seven re-sourced Latin poems rebuilt into the
  Latin index, lemma caches, frequency cache, rare-bigram table and stored
  window text; the whole-corpus passage re-description with GLM 5.3 Flash
  begun (docs/DATA_OPERATIONS.md, 2026-09-30 afternoon entry).
- The four fixes above pulled onto production and the app reloaded, 07:25
  EDT, no bundle change. Reference searches passed. The Coptic single-word
  exact search returns 500 lines on the live site.

## 2026-09-29

### Data operations
- The nine works of #516 are live in every search path: Latin index 1,655
  texts, 697 passage windows described on UB's campus AI service and
  appended (510,839 windows), word index, density and map caches
  recomputed. `lxml` installed in the production environment. Details in
  docs/DATA_OPERATIONS.md, 2026-09-29.

### Corpus
- Nine Latin works added: three Pseudo-Caesar continuations of the civil-war
  commentaries (De Bello Africo, Alexandrino, Hispaniensi; Perseus/OGL
  canonical-latinLit, CC BY-SA 4.0), Vegetius' Epitoma Rei Militaris (4
  books, The Latin Library), and five short Latin Library texts (Grattius'
  Cynegetica, Germanicus' Aratea, Solinus' Collectanea Rerum Memorabilium,
  Censorinus' De Die Natali, Julius Obsequens' Liber de Prodigiis). Cicero's
  In Verrem and the Carmina Priapea were dropped from the candidate list
  after the duplicate check found both already in the corpus under other
  names. `scripts/corpus/latinlibrary_to_tess.py` gained handlers for all
  five Latin Library shapes. Metadata in `backend/text_sources.json` and
  `data/text_genres.csv`; per-text blurbs and the index/window rebuild are
  still owed.
- The text converter also reads the older TEI shape used by Corpus Corporum
  and MGH-derived files (numbered `div1` to `div7` nesting, no namespace or
  the TEI P4 one, sections marked by milestones, leaf text in paragraphs or
  verse lines), tried only when the modern shape yields nothing, so no
  existing file converts differently. 22 new tests on synthetic fixtures.

## 2026-09-28

### Housekeeping
- Comments, docstrings and test descriptions state the outcome or the rule
  and no longer name or quote anyone: 237 lines in 67 files rewritten, code
  unchanged. The automated pull-request review addresses the maintainer by
  role. The working list and the research notes are no longer in the
  repository (#510, #511).

### Data operations
- The passage index no longer holds a work twice. The whole-file windows of
  129 works stored both as one file and as book files were dropped
  (`scripts/corpus/drop_whole_file_windows.py`), 620,773 windows to
  510,142, the word index rebuilt and the density and connections-map
  caches recomputed. Eight works keep both copies until fifteen short book
  files have windows of their own. The Septuagint's Lamentations has fresh
  descriptions for its restored text, the first batch described by the
  free local model. docs/DATA_OPERATIONS.md, 2026-09-28.

## 2026-09-27

### Passage index
- A tool to drop a work's whole-file windows from the passage index once
  its book files carry their own (`scripts/corpus/drop_whole_file_windows.py`,
  dry run by default, refusing any work whose book files are not all
  indexed). 129 works are stored both ways with full book coverage, 110,631
  duplicate windows. Ends the double entry a passage could get in Similar
  Passages under two names. Decision in docs/DECISIONS.md. (#504)

### Search
- A third shared word now raises a parallel's score instead of lowering it.
  The score summed the rarity of the shared words and then divided by how
  many there were, which made it an average, so an extra shared word helped
  only when it was rarer than the ones already counted. That contradicted
  the method the code cites and its own description. Measured on Lucan 1
  against the whole Aeneid before the change, results sharing three words
  averaged 0.53 against 0.70 for two. After it, 1.60 against 1.41, and the
  commentator-attested parallels moved up, three more into the top half and
  seventy places in mean rank, while the fusion search held or improved at
  every depth. The scorer's description now matches the code, and the rules
  the scorer promises have tests for the first time (issue #465). The name
  of the scoring rule is now part of every results cache key, so a future
  change to the formula can no longer serve old scores from the cache.

### Coptic
- The seven Coptic-only letters (shei, fei, khei, hori, gangia, shima, dei)
  are stored as themselves. The normaliser had moved them from their only
  Unicode code points, U+03E2 to U+03EF, to U+2CB2 to U+2CBF, which Unicode
  assigns to seven different letters. Matching was unaffected, since both
  sides were moved alike, but every stored form carried the wrong letters:
  11,722 of the 29,323 lemmas in the Coptic index, 7,791 entries across the
  three Coptic dictionaries, and the stoplist, and two display work-arounds
  existed only to move them back for the reader. The normaliser now leaves
  them in place and strips U+2CB2 to U+2CBF, which in our texts occur only
  as editorial marks and were being read as letters, so that ':ⲻⲁⲗⲗⲁ' indexed
  as a word beginning with gangia. Dictionaries and stoplist are corrected
  in place, the interface's copy of the map and two dictionary-building
  scripts now use the one backend normaliser, the work-arounds are gone,
  and the Rare Words Explorer keeps traditional Coptic order through its
  sort key alone. The Coptic caches and index are rebuilt at deploy (issue
  #493).

### Corpus
- The Septuagint's Lamentations has its text back. Eighty-eight of its 150
  verses held nothing but the acrostic letter name, because the converter
  that brings texts in from Open Greek and Latin kept only the paragraphs of
  a verse and dropped its lines, and Swete's edition marks the letter as a
  paragraph and the verse as lines. The converter now keeps both in order,
  the file is regenerated from the same source with the same 150 references
  (664 words become 2,447), and a converter test holds the rule. The
  Septuagint's own introductory sentence before 1.1, which the converter
  has never carried for chapter-level prose, is still absent (issue #276).

## 2026-09-25

### Search
- The part-of-speech boost filed every proper noun among the pronouns,
  because it told tag schemes apart by prefix and `PROPN` begins with `PR`.
  A name therefore matched a pronoun and failed to match a noun (issue
  #487). Reading the stored tags showed more. Greek, and Latin where it is
  tagged, use the nine-position Perseus code, of which only the noun and
  verb positions were recognised, so adjectives, adverbs, pronouns,
  prepositions, conjunctions, articles and participles all collapsed into
  one class that matched itself. Untagged words, 82 percent of stored Latin
  tags, did the same. Each scheme is now matched exactly, and an untagged
  word is left out of the count. The boost is off by default and in
  production, so no live result changes. There was no test of this code
  before. There is one now.
- Hebrew: Jerusalem is read as one word. A combining grapheme joiner
  (U+034F) sits inside the name 562 times across 23 files, and the tokenizer
  split the word at it, so the index held the name under a truncated lemma
  481 times and under the correct one 118 times. A search for Jerusalem
  reached fewer than one occurrence in five. The joiner is now removed
  before tokenizing (#485). After the rebuild the correct lemma carries 625
  postings and the truncated one none. A live search returns 611 lines.
- Hebrew: a word outside the lookup table that goes to the Stanza fallback
  keeps its own lemma. The fallback was fed all the unknown words of a
  verse joined into one string and its output re-split, so a word Stanza
  chose to split or join shifted every lemma after it by one, and a rare
  name took the lemma of the word before it. Each word now goes through on
  its own, and parts of speech come from the lookup table's own tagging
  where it has the word (#491, replacing #486). In the live index, 519
  one-letter tokens carried a lemma of three letters or more before the
  rebuild. None do now.
- The Help page shows the Hebrew and Coptic stoplists beside the Latin,
  Greek and English ones, Hebrew reading right to left, and the Coptic
  letters shown as themselves rather than as the code points the matcher
  normalises them to (#488).
- Line Search: in the line list, a Hebrew or Coptic line's tag no longer runs
  into its text. Those tags carry the text's whole identifier with no
  spaces, so they could not wrap inside their column. The list now shows the
  locus alone, as the results below it already did, and Hebrew lines are
  right-aligned (#489).

- Hebrew: the optional Stanza fallback for words the lookup table lacks is
  off unless asked for, on the server and at build time alike. The
  production server never had Stanza while the index was built with it, so
  the two disagreed on a fraction of a percent of words (200 of 305,550).
  The index was rebuilt without it, and they now agree.

### Corpus
- A script renames a work inside the passage index without re-describing
  it. It rewrites the window ids, the description records and the four
  columns of the window text table, runs dry by default and leaves dated
  backups. It was used for Archimedes on 23 September (#476).

## 2026-09-23

### Reader
- Sixty-eight books that had no passages of their own now have them, so
  Similar Passages and Theme Search can reach them and their margin marks
  are their own. Statius' Achilleid book 1, all five books of Sedulius'
  Carmen paschale, twelve lives of Suetonius and nine books of Valerius
  Maximus were among them. Until now the margin showed whatever the whole
  work held, so opening Suetonius' life of Augustus drew the marks belonging
  to the life of Julius.
- A book with no passages of its own now shows an empty margin rather than
  another book's (#463).
- The Reader asked for a typeface nobody had loaded. It named Gentium Book
  Plus, the page fetched only Crimson Pro, Inter and Noto Sans, so every
  reader fell through to Georgia, which has no polytonic Greek and no Hebrew.
  Greek fell back glyph by glyph to whatever the machine held and Hebrew
  borrowed a system face that sits small at the same size. Two reported
  faults, one missing link. Gentium Book Plus, Noto Serif Hebrew and Noto
  Sans Coptic now load, and the reading pane tells the browser which
  language it is showing (#477).
- Switching the Reader to Greek lands on the Argonautica again. The retiring
  of duplicate texts on 10 September removed the copy the Reader's default
  pointed at, so the failed load fell back to the first Greek author in the
  list (#472).

### Corpus
- Archimedes is one author, not two. Eleven works imported under the French
  form of his name are filed with the twelfth under the Latin form, 826 line
  tags and the provenance entries with them, no text changed (#474). The
  passage index was renamed to match the same afternoon, see
  docs/DATA_OPERATIONS.md.

## 2026-09-22

### Search
- A parallel's score is no longer flattened at 1.0. On a single-channel
  search a sixth of the results computed above that and were all given the
  same number, so between 19 and 35 results per search arrived in no
  particular order. Twenty of the 47 parallels the commentators attest, out
  of the Lucan benchmark, were sitting in that undifferentiated block.
  Releasing the scores puts thirteen of those twenty in the top half of
  their block and lifts attested parallels in the top ten of a search from
  five to thirteen. The default fusion search was never affected, because it
  had already switched the ceiling off for itself, and that inconsistency
  between the two paths is what this removes. Results cached under the old
  ceiling are not reused.
- The scorer's own description of its formula said that more matching words
  raise the score. The code divides by the number of matching words, so they
  do not. The description now matches the code, and whether the code is
  right is an open question with the measurement attached (issue #465).
- A word counts as rare when it appears in at most 12% of the works in its
  own language's corpus, instead of a fixed 100 works in every language.
  100 was chosen for Latin, which holds 744 works. English holds 42, and its
  commonest word appears in all of them, so nothing could fail the test and
  every shared word counted as rare. Latin, Greek and Coptic barely move;
  English and Hebrew get a threshold that can exclude a word for the first
  time. This is also what caused an English comparison to produce 431,000
  matches and exhaust 12 GB of memory in September.

### Documentation
- The settings behind a search are now findable from the site. The Help
  page's fusion section links to the three documents that carry them: how
  the search works, how the channels are combined, and the dated decisions
  log with the measurement behind each choice.
- "How Tesserae Searches" gains a section on how rarity is measured, which
  had never been written down: a continuous scale that scores every result,
  a separate yes-or-no gate used by one channel, and the fact that the two
  count different things.

### Corpus
- Four Greek texts had English translators' notes and Latin apparatus
  pasted into the Greek itself, where the search treated them as part of
  the text. They are removed (#446). Five Greek capitals that a scanner had
  read as Latin lookalikes are corrected, so Miletus and Naxos now match
  those names elsewhere in the corpus. The Greek index has to be rebuilt
  before this reaches the live site.
- Arnobius book 1, Arnobius book 6 and the preface to Pliny's Natural
  History now appear in Similar Passages and in Theme Search. Those three
  books had text but no stored passages, so they were invisible to both.
  Nineteen passages were read and described locally and added to the index.
- Adding them changes the passage index, and the Reader's margin marks are
  cached against it, so every work's margin is being computed again. Until
  that finishes a work opened for the first time is slow.

## 2026-09-21

### Corpus
- The wording quoted by Similar Passages and Theme Search is refreshed for
  the works corrected last night. Across those works 2,526 stored passages
  quoted the superseded text and were rewritten. Four in five differ only
  in punctuation. The rest lose a printed page or line number that the
  scanned edition had dropped into the middle of a word, so a word such as
  the Greek for "he orders" is whole again instead of broken in two. No
  passage changed its sense, so they keep their existing descriptions
  rather than being sent through a language model again. An earlier
  version of this entry said 353 passages, which counted only the opening
  of each passage rather than all of it.

### Corpus
- Where a work is stored twice, as one file and as separate books, the books
  are now the authority and the single file is rebuilt from them, which is
  what a reader of one book sees. Six works were rebuilt: Apuleius,
  Arnobius, Prudentius, Ovid's Metamorphoses, Orosius and the Georgics. The
  differences were an OCR error reading "erg6" for "ergo", a running header
  glued into a line, lines split in two places, curly quotation marks, and
  spacing before punctuation.
- The Georgics went the other way first, because its book files held 42
  corrupted lines where the single file was sound, so those were repaired
  before the file was rebuilt from them.
- Pliny's preface and Arnobius book 6 had no book file at all and now do.
  Arnobius book 1 existed under a misspelled name and is renamed.
- The check that compares the two copies was only recognising books numbered
  with digits, so eleven files named for what they hold, a preface, the
  fragments, the Old Latin Psalms, looked missing when they were present.
  That is why an earlier count of works needing repair was far too high: of
  137 works stored both ways, 136 now agree.
- Arrian's Anabasis replaced with the canonical text of the same edition,
  Roos 1907, from the Perseus TEI rather than a scrape of a reading page.
  The old file was missing two sections, carried stray editorial numbers
  inside the Greek on 27 lines, and printed a percent sign where the edition
  has a dagger. The new one restores the two sections and the editor's own
  brackets.

### Corpus
- Prepared, not yet run: the two remaining works with genuinely missing
  book files get them (Arnobius' Against the Nations book 6, and the
  preface of Pliny's Natural History), and Arnobius book 1 is restored to
  the group under its correct filename, having been sitting under a
  misspelled name all along. Checking the corpus first found that ten of
  the twelve works on the 2026-09-21 missing-book-files list already have
  complete book files: their prefaces and fragment sections exist under
  names such as `.part.pr.` or `.part.preface.` that the comparison
  script's filename pattern does not recognize as a book file, so it
  reported them as missing when they were not. Also prepared: Ovid's
  Metamorphoses and Orosius' Histories Against the Pagans get their whole
  file regenerated from their book files, now the canonical copy, removing
  the curly-quote and em-dash spelling differences between the two copies
  of each work. Vergil's Georgics and Arrian's Anabasis were left alone:
  checking first found the Georgics' book files are mostly corrupted
  encoding, not the plain diaeresis difference expected, and Arrian's book
  files are a mixed improvement (two merged lines correctly split) and
  regression (two lines with a stray digit from the critical apparatus
  left in the text), so neither is a clean case for making the book files
  canonical.
- Switching language tabs quickly no longer shows the wrong corpus. Clicking
  Latin, then Greek, then English left three requests in the air, and
  whichever answered last won rather than whichever was asked for last, so
  the author and text pickers could list one language's works under another
  language's tab with nothing to say so.

### Internal
- Three small correctness fixes from the code review, none of which showed
  as a failure: the syntax database connection is now closed even when a row
  cannot be read, failed logins are written to the application log rather
  than to standard output where nobody sees them, and an exception clause
  that caught everything, including a request to shut the server down, now
  catches only errors.

### Internal
- The administrative panel has tests for the first time. It holds the powers
  with the most reach in the project, deleting a user, granting roles,
  resetting a password, and it had none. The 37 new tests cover who is
  allowed to act and the things that must never happen: an administrator
  cannot delete their own account, the last two senior accounts cannot be
  deleted, a session that has been revoked stops working at once, a failed
  deletion is rolled back rather than left half done, and repeated wrong
  passwords are locked out.
### Reader
- The coloured margin now answers for the book you are reading whichever way
  the text is named. Asked with the file name as it appears on disk, it fell
  back to the whole work, so a reader of Philippic 7 could have been shown
  marks belonging to Philippics 1 through 14. The Reader itself always asked
  the other way, so nobody saw it; anything else calling the same address
  did.

### Search
- How a multi-part work is collapsed to its own name is now decided in one
  place instead of fourteen. Three different rules were in use and one of
  them was wrong: it required the part number to end the name, so the 215
  files whose part carries a label, such as Pindar's Nemeans or the books
  of the Vulgate, were never recognised as belonging to their work. Their
  descriptions, translations and counts were looked up under a name nothing
  holds. Nothing errored, which is why it went unnoticed.
### Internal
- The reference search is checked by machine now, not by memory. It has said
  since August that a search for "arma virum" must return Ovid, Quintilian
  and Seneca, and nothing ran it. A script now asks a running site and fails
  loudly if an author disappears or the count collapses, and a test runs the
  same lookup machinery over a miniature index so every change is checked
  automatically.

### Reader
- The Reader says why it is waiting. Opening a text for the first time takes
  a few minutes to work out where the rest of the corpus connects to it,
  because every passage in the text is compared with the whole corpus. A
  note now appears after a few seconds, names the text, and says the wait
  happens once. Nothing appears for a text whose answer is already stored,
  which is the usual case and returns instantly.
### Search
- Latin u and v, i and j are now decided in one place instead of five. The
  rules had drifted apart, so the same two words could count as the same in
  one part of a search and different in another. Two real effects, both
  measured on the corpus: a function word spelled with a j, such as the
  1,691 occurrences of "jam" for "iam", was not recognised as a function
  word and was matched on as though it carried meaning, 1,705 occurrences in
  all; and a word at the start of a line, which editions capitalise, did not
  match its own lemma when the distance between matched words was measured,
  so pairs were measured from the wrong place. Searching the printed text
  keeps its own rule, including the old spelling of "divom" for "divum",
  which must not be applied to a dictionary lookup: the dictionary has both,
  and they are different words.

### Site
- The "Saved Searches" button on the search page opens its dialog again. It
  had done nothing at all when clicked: the dialog was rendered without the
  one property that tells it to draw itself, so it returned nothing and no
  error appeared anywhere.

### Repository
- New text files are visible to git again. `texts/` was ignored wholesale,
  which never untracked the 3,484 files already committed but silently hid
  every new one: an imported text did not show up in `git status`, was
  skipped by `git add texts/`, and was never committed, while the index
  build and the deploy after it behaved as though it had shipped. The
  languages that ship are now listed one by one; Persian, Urdu and Arabic
  stay ignored on purpose, as do scratch folders inside a language
  directory, the runtime caches and the pre-computed embeddings (those are
  recomputable, and a run writes gigabytes).
- The developer and contributor guides no longer tell you to build the
  front end with `cd client && npm run build`, which cannot work: there is
  no `package.json` under `client/`, and the build runs from the repository
  root.
### Internal
- About 970 lines of `backend/app.py` deleted: 24 web-address handlers that
  Flask could never reach, because the blueprint files registered the same
  addresses earlier in the same file. They had drifted from the live
  versions (the dead admin routes checked a weaker password path), so
  anyone debugging one of those addresses could have read, changed and
  tested the wrong function without noticing. Every remaining address was
  checked to answer with exactly the same function as before, in both
  deployment modes.

### Site
- Tessa, the assistant, was mounted twice on every page: two copies asked the
  assistant service for its status on each page load, shared one stored
  conversation, and drew the floating button on top of itself. One copy now.
- The popup used for Save Parallel, adding or editing an intertext in the
  Repository, and the rare-word definition viewer now announces itself as a
  dialog, and pressing Escape closes it. Opening it moves the keyboard focus
  inside, tabbing no longer escapes into the page behind it, and closing it
  returns focus to whatever button opened it. None of this changes how the
  popup looks or works with a mouse.
- The highlighted tab in the top navigation and the language row is no longer
  shown by color alone: it now also reads slightly bolder, and screen readers
  are told which one is selected. No layout change.

### Theme Search
- The Similarity Map on a phone: the column of work names took a fixed 190
  pixels, leaving about 200 for the map itself. On a narrow screen the names
  now take a third of the width and truncate to fit, and the slanted labels
  along the top truncate sooner, which also lowers the header strip. Desktop
  is unchanged.
### Corpus
- Eighty-seven damaged lines repaired in book files, found by comparing
  every work's whole file with its book files. Greek words inside Pliny's
  Natural History (77 lines) and three lines of Claudian were mojibake, the
  usual symptom of a file read in the wrong character encoding; Philippic 7
  was missing the opening bracket of its first line, so that line was not
  indexed from that file; three lines of Orosius carried the author's name
  twice in their reference; and Galen's first book was missing its first
  line. In every case the work's whole file already had the sound version,
  which is what the repair uses.
- A shared helper (`scripts/corpus/corpus_safety.py`) now gives any
  corpus-mutating script the three things the safety convention in
  `docs/DATA_OPERATIONS.md` asks for: a dry run by default, a dated backup
  that a rerun never overwrites, and a write-beside-and-rename swap that
  never leaves a half-written file. The audit of 2026-09-21 found that
  fewer than half the scripts under `scripts/corpus/` followed the
  convention, including `fix_hebrew_clitic_spacing.py`, which overwrote a
  `.tess` file in place with no backup at all. That script and
  `repair_lactantius_placidus.py` now use the helper; both were checked
  against the pre-change scripts on fixture data and produce byte-for-byte
  identical output when run with the new write flag.

### Language names
- Browse Corpus and the Rare Words Explorer showed the raw code "he" or "fa"
  in their headings instead of "Hebrew" or "Persian" whenever those
  languages reach those pages, and the admin Corpus Metadata table showed
  "English" for every Coptic or Hebrew work. A code review found the site
  had accumulated a dozen separate places that each spelled out their own
  list of language codes and names by hand, several missing the newer
  languages and one (an admin analytics export) calling Persian "Farsi"
  where the rest of the site says "Persian." All of them now read from the
  one shared list. Browse Corpus's era filter had also drifted from the
  site's own era list: English's "18th Century" option matched no work,
  since the site tags that period Neoclassical or Augustan, so it now reads
  from the same shared list too and offers the eras that are actually there.
### Corpus Browser and Rare Words Explorer
- Hebrew is now a tab on both pages, placed after English and before
  Coptic, matching the order already used in the Reader's language picker
  and Theme Search's language checkboxes. Both pages hardcoded their tabs
  to Latin, Greek, English and Coptic even though Hebrew has shipped
  elsewhere on the site since August, so it was unreachable from either
  page.
- The Rare Words Explorer can actually show Hebrew now. Its list is built
  by a step on the server that had a rule for Latin, Greek, English and
  Coptic and none for Hebrew, so it produced an empty list: the page would
  have shown a Hebrew tab with nothing in it. Hebrew words counted ten
  times or fewer in the corpus now qualify, leaving out single letters,
  transcription marks and the curated list of function words.
- Corpus Browser's era filter offers Biblical for Hebrew instead of
  falling back to the Latin era list, which is what happened before the
  filter had a Hebrew entry at all (the same gap already fixed for Coptic
  in a prior release). The live Hebrew corpus is 39 Hebrew Bible books, all
  one era, so Biblical plus Unknown is the whole list for now.
- Both pages now read language display names from the shared
  `languageNames.js` helper instead of a local, hand-rolled copy that did
  not know about Hebrew.
- The Rare Words Explorer's dictionary link sent every non-Latin,
  non-Greek, non-Coptic, non-English word to Logeion, a Greek and Latin
  lexicon; Hebrew words now link to Wiktionary instead, as English words
  already do.

## 2026-09-20

### Reader
- Works held in books open one book at a time: a whole-file work that also
  exists as book files (the Punica, the Aeneid, the Iliad and about 130
  others) opens on the book that holds the requested line, or on Book 1,
  so the books no longer run together and the previous/next links apply.
- A floating navigator at the bottom left of the window (to the top, to
  the end, previous and next book) that stays on screen wherever the
  reader is in the text.
- The gutter key now explains the numbered boxes: the count of other works
  that quote the line, click to see them.
- A passage opened from the Similarity Map says so and links back to the
  map; its link used to re-run "connections map: Vergil" as a Theme Search.
- The Read tab, clicked while the Reader is open, takes the Reader back to
  its starting page; it used to do nothing.
- Which book holds a line is now looked up by the server in the book files
  instead of read off the line number, which was wrong for Alcuin and
  Theodulf (a book file may hold several poems), the Verrines (part 3 is
  actio 2 book 2) and Hyperides (whole file and parts tag lines
  differently); book files with a suffix after their number count too.
- In Verbal Parallels a Latin word spelt with v or j is marked even when
  the match was reported in the other text's u or i spelling ("catervas"
  for "cateruas").
- The key above the text keeps "darker = more connections" with the two
  gutter colours it describes, and names both forms of quotation box:
  solid for a quotation, dashed for a possible echo (one rare shared
  phrase).

### Help and About
- The Reader help describes the quotation boxes (solid and dashed), the
  Reuse tab, reading a work book by book and the floating navigator; its
  gutter key text matches the key on the page (colours, not the old W and
  C letters). The Translation tab note says translators are named under
  each passage and that a few open non-commercial translations are used
  with attribution.
- The Sources page has a Translations block: the translation policy in
  plain words and, on request, the list of every translated work with its
  translator, per language, drawn from the same files the Reader credits.


### Theme Search
- The reader client's timeout grows with the rows sent (6 s for 100,
  12 s for 300). A fixed 6 s cut the 300-row call off just as it
  answered, so for nine minutes after the depth change every Theme Search
  ran without the reader; the depth was set back to 100 through the
  environment while this was fixed.
- The reader re-scores the whole composed list (about 300 rows), not its
  first hundred, so a work whose rows sat past the hundred can reach the
  page: the Odyssey's recognitions on "a wife or child recognizes someone
  long thought dead or lost" were at rows 146 to 148 and land at row 15.
  Precision neutral on the 16-query benchmark (0.444 against 0.453 with
  the lexical boost at 100 rows); about 9 s a query instead of 4 s.
- A word index over the passage descriptions (SQLite FTS5, BM25;
  `scripts/build_desc_fts.py`) adds a small lexical boost to the embedding
  similarity, so a description that shares words with the query rises a
  little. Measured on the real code path on the 16-query benchmark:
  first-ten precision 0.434 to 0.453, the four held-out topoi 0.325 to
  0.375 (docs/DECISIONS.md, 2026-09-20). The index is rebuilt after every passage-index change; the
  app refuses a stale one and runs without the boost, saying so in its log.
- Dates for the Nibelungenlied (c. 1200), the Chanson de Roland (c. 1100)
  and Dante (d. 1321), which had none because their languages were absent
  from the date table; and a work with an era but no year (the Hebrew
  Bible, "Biblical") shows the era instead of "undated".

- Sample searches re-measured on production: the recognition query (rated
  moderate, and it misses the Odyssey) is replaced by "funeral games with
  athletic contests held in honor of the dead" (the benchmark's best theme,
  first-ten precision 1.00) and "a storm at sea batters ships and terrifies
  the crew"; all five chips rated strong on 2026-09-20.

### Search
- Fusion channels no longer treat function words as matching features, and
  their candidate lists are bounded. The lemma, lemma_min1 and exact
  channels ran the matcher with an empty stopword set, so every pair of
  lines or two-line windows sharing "the", "and", "qui" or "sum" became a
  candidate held in memory (5.3 million window pairs for Paradise Lost
  against Hyperion; a web worker at 25.6 GB for 19 minutes on 2026-09-19).
  The curated function-word list now applies in those channels (a user's
  own "-1" in the classic search still means no stoplist at all),
  the matcher keeps only the top candidates by quick IDF (four times the
  channel's cap, the set the old pre-filter kept), and lemma, exact,
  dictionary and rare_word get the 50,000 result cap the other channels
  have (the dictionary channel alone blew a 12 GB cap on Seneca's Letters
  against the Aeneid; rare_word did the same on the whole of Paradise
  Lost). Whole Paradise Lost against Hyperion: 25.6 GB and 19 minutes
  before, 2.8 GB and 1.7 minutes after. Measurement and rationale in
  docs/DECISIONS.md (2026-09-20).

- English line search: the Latin u/v and i/j spelling fold applied to
  every language but Greek, so English queries for any word with a v or a
  j were looked up in Spenser's spelling ("love" as "loue", "voice" as
  "uoice") and returned only Spenser or nothing. The fold now applies to
  Latin only. The results page's "Across the corpus" panel, blank for
  such shared words, works for English again.

### Site
- Changing tabs no longer carries the previous page's query string along,
  so a Theme Search query no longer re-runs itself every time the Theme
  Search tab is reopened. Links opened at a page's own address keep their
  parameters as before.

### Corpus
- The English Bible is displayed as the King James Bible: the files named
  world_english_bible hold the Authorized Version of 1611 (a legacy label;
  the sources registry already credits it correctly). File identifiers
  unchanged; the rename of the files is a later corpus operation.
- Four works whose whole file and book files disagreed (found while
  verifying today's book-by-book Reader rule) are now consistent: Isocrates'
  Letters (parts 2 and 3 had every line tagged with a doubled bracket),
  Hyperides' Speeches (the whole file was missing the "speeches." segment
  its own part files use), Dionysius of Halicarnassus' Antiquitates
  Romanae (one line, 16.1.0, was missing from the part 12-20 file), and the
  Couplet et alii Confucius Sinarum Philosophus (part 1's lines carried a
  shortened "Couplet." tag instead of "Couplet et alii."). Text unchanged
  in every case except Dionysius, where the missing line was inserted. A
  new check script, `scripts/corpus/check_whole_vs_parts.py`, confirms the
  fix and, run against the whole corpus, found 137 works pairing a whole
  file with book files, of which 117 already agree and, beyond this
  batch's four, 20 more disagree pre-existing and out of this batch's
  scope (listed in the PR for a follow-up). The store-side ref rename these four needed
  (`scripts/corpus/apply_whole_vs_parts_refs.py`) is prepared but not yet
  run on production; see docs/DATA_OPERATIONS.md.
- Four files began with a byte-order mark that hid their first line from
  the indexes (Aretaeus, Confucius Sinarum Philosophus part 2, Macrobius'
  fragment, Ovid's Ibis); the mark is removed.

### Reader
- Kline's translation added for Punica 9-17 and the gaps of 1-8,
  non-commercial licence, attribution shown per passage.

## 2026-09-19

### Search
- English function-word list rebuilt from sources (275 words): the Snowball
  stopword list plus the same words in their Early Modern inflections after
  Barber, Early Modern English (1997). Seven content verbs the old list held
  (get, go, know, make, say, see, take) are gone, 27 Snowball function words
  it lacked are in, two duplicates removed. Rule recorded in
  docs/DECISIONS.md: stoplists are function words only; common content
  words are down-weighted, never removed. Help page and docs carry the
  sources; the list itself is visible on the Help page and at /api/stoplists.
- The batch lemma-cache builder's English path lemmatized every word as a
  noun, so past tenses ("stood", "went", "fled", "began") stayed as they
  were in the English caches while the index builder reduced them; in a
  Milton search Milton's own verbs then looked as rare as proper names and
  ranked high. The fast path now applies the main processor's noun-or-verb
  rule. English caches, index and Quotation table rebuilt (DATA_OPERATIONS).
- The quotation channel now carries weight 10 in the Latin and Greek fusion
  profile (it was 0). Measured on 32 prose quotations of Vergil (Gellius,
  Macrobius, Quintilian, Servius): first-ten recall 8 to 19, recall at 100
  14 to 28, for one Lucan pair lost at rank 100 on the poetry benchmarks and
  none in the top ten (evaluation/quotation_weight_test/REPORT.md). English
  keeps 0 until measured.
- The search page falls back to its default text pair whenever the
  remembered selection is not valid for the language; a stale remembered
  pair used to leave the English page with no texts chosen.

### Reader
- Quotation table builder: the "all shared n-grams commonplace" drop is now
  per language (`--drop-all-commonplace auto|on|off`, auto = English only).
  Measured on Latin it removed 1,863 strict pairs and gained none, among them
  genuine short scripture quotations made entirely of common words (John
  10.30 "ego et pater unum sumus" in Hilary); the English function-word junk
  it was written for does not occur in Latin or Greek at that scale.
- Quotation table builder: the commonplace rule is now "drop a pair only when
  every shared n-gram is commonplace-only". The earlier "count commonplace
  n-grams for nothing" removed Hamlet's function-word matches but, rebuilt on
  Latin, also lost 5,445 strict pairs, mostly the Fathers quoting the Vulgate
  in wording made of common words (Augustine, Conf. 7.13 and John 1.3). All
  shared n-grams count again for the totals and the shared count; the pair is
  refused only if none of them carries a content word.
- Quotation table builder: a word also counts as commonplace when it is in
  the language's stoplist (the cross-lingual function-word lists in
  backend/synonym_dict.py, accent-stripped and u/v folded). The data-driven
  threshold alone missed "shall" and "do" on the English corpus, so "what
  shall I do" still linked Hamlet to Bunyan after the previous fix.
- Quotation table builder: two rules tightened after the first English build
  marked Hamlet's "What shall I do?" as strictly quoted by eight Bible verses
  and paired the Faerie Queene's books with each other. An n-gram made only of
  commonplace words now counts toward no rule and no line total (before, the
  commonplace set only guarded the rare single-n-gram rule), and part files of
  one work count as the same work. The English table was taken off production
  until it is rebuilt under these rules; Latin and Greek are rebuilt too.
- Quotation table builder (`scripts/reuse/build_reuse_table.py`): a Greek
  lemma cache whose text_id holds a Greek file name as escaped bytes (eight
  such caches, written under an ASCII locale) crashed the Greek build with
  "surrogates not allowed"; the builder now decodes those ids back to UTF-8
  (the same round trip backend/lemma_cache.py already does) and reports how
  many it repaired.
- The connection gutter's density computation now scores a work's windows
  256 at a time instead of all at once. The old single block cost 2.5 MB per
  window (5 GB for the whole Punica, 11.6 GB for the Vulgate), which is what
  pushed a preview server past its memory caps and what a production worker
  paid on the first open of any large uncached work. Same answer, under
  0.7 GB. Also: the works-route unit test no longer writes the real coverage
  sidecar (it did, through a worktree symlink, on 2026-09-19).
- Navigation inside a text: a thin strip stays at the top of the text column
  with previous and next book, a Go to line box (a locus such as 6.851, or a
  bare line number within the open book) and Back to top, and the book links
  repeat at the end of the text. Until now the only way out of the bottom of a
  long book was a scroll back to the header.
- The side panel (Similar Passages, Verbal Parallels, Translation, Reuse) now
  stays on screen while the page scrolls. Its sticky rule had been cancelled
  by the outer card's overflow clipping since the Reader shipped, so deep in a
  text the panel sat above the fold and looked absent.

### Infrastructure
- The Python test workflow on main had failed since the Theme Search re-ranker
  merged: the security scan flagged the re-ranker client's URL open. The client
  now refuses a THEME_READER_URL without an http or https scheme and the scan
  line is marked as checked. No behaviour change for the configured service.

### Reader
- Similar Passages in the Reader showed the raw work id ("quintus_smyrnaeus.fall_of_troy")
  instead of a proper title. The passage index already sends author, title and
  display_name from `get_text_metadata` -- the same source Browse Corpus and
  Theme Search use -- but the Reader's card built its own rough label from the
  id instead of reading them. It now reads `display_name`, falling back to the
  old label only for a response that predates the field.
- Corpus-wide reuse table and "Reuse" tab: a small mark beside a line the
  corpus repeats verbatim elsewhere ("quoted in N works" on hover) opens a
  new Reuse tab beside Similar Passages, Verbal Parallels and Translation,
  listing the repeating lines grouped by work, newest-first by author date
  where known. Built from `scripts/reuse/build_reuse_table.py --language la`
  (ported from the `research/reuse_table/` prototype, containment-gated
  n-gram matching, see `research/reuse_table/REPORT_2026-09-18.md`), reading
  `texts/la/` as the live corpus so retired files are excluded automatically;
  writes `cache/reuse_pairs/la.db`. First run: 679 works, 516,458 lines,
  52,855 pairs kept in 419s under a 12G cap (98 live files skipped, Gellius
  among them, because the loader guessed the plain `<work>.json` cache
  filename instead of resolving the hashed name). Fixed to call
  `backend.lemma_cache.get_cached_units` and rebuilt: 777 works, 652,003
  lines, 62,265 pairs kept in ~30 minutes, 0 works skipped for missing
  cache; see docs/DATA_OPERATIONS.md and
  `research/reuse_table/REPORT_2026-09-18_production_build.md`. New endpoints
  `GET /api/reuse/line` and `GET /api/reuse/marks`
  (`backend/reuse_table.py`, `backend/blueprints/reuse.py`), registered
  site_only in `mcp_manifest.py`. Backend tests
  (`tests/test_reuse_routes.py`) and Vitest
  (`client/src/components/reader/ReuseTab.test.jsx`,
  `TextPane.reuse.test.jsx`). Help page: new Reuse paragraph under the
  Reader topic.

### Theme Search
- #388 The list of covered works is reachable, not just a checkbox in Browse
  Corpus: `/corpus?theme=1&language=la` opens Browse Corpus with the filter
  and language already set, with a heading, a Copy list button, and a
  Download list button for the works on screen. The Help page's Theme
  Search topic links to it, and the Theme Search page itself shows how much
  of the current language it reaches, with the same link (only when exactly
  one of the four Browse Corpus languages is selected). Verified against
  production: 765 of 782 Latin works covered, computed identically by both
  pages off one shared helper (`client/src/utils/passageCoverage.js`); a
  new App-level test confirms the `/corpus` deep link's query string
  survives the rewrite to the real route, `/browse`.
- The covered-works link (#388, above) only showed with exactly one of the
  four Browse Corpus languages selected, so the default "All languages"
  view had no link at all. The line under the language row now always
  shows: the per-language sentence stays for one covered language, a
  summed sentence ("Theme Search covers N works in 4 languages") for the
  default or several languages picked together, and a fixed sentence for
  a language Browse Corpus doesn't index (Hebrew, Persian, Urdu). The link
  always goes to the Latin list, `/corpus?theme=1&language=la`. Review
  follow-up: the single-covered-language sentence was still gated on
  `coverage.total > 0`, so a covered language with a zero or not-yet-loaded
  count rendered none of the three sentences; it now shows a loading
  sentence while unresolved and the fixed four-language sentence if the
  count resolves to zero. The summed fetch also used to run on every
  mount regardless of the picker; it now runs only the first time the
  summed or fixed sentence is actually needed, and `language`'s initial
  value is read synchronously from a shared link's `languages=` param
  (rather than set later in an effect) so that check is accurate on the
  very first render.

### Corpus
- Retire the Eugippius duplicate and resegment Ennodius Book 2 (batch 3):
  `eugippius.excerpta_ex_operibus_augustini` (correctly spelled, but drops
  the real Augustine wording for 183 of 390 excerpts in favor of one-line
  summaries) is retired; `eugippius.exerpta_ex_operibus_augustini`
  (misspelled filename, kept, has complete text for all 390) gets its
  displayed title corrected in code so the misspelling never surfaces.
  `magnus_felix_ennodius.carmina` (152 Book 2 poems stored one whole poem
  per line) is retired and replaced by `magnus_felix_ennodius.carmina_2`,
  rebuilt at proper one-verse-per-line granularity directly from the
  edition's own EpiDoc XML source, which also recovers a poem missing from
  the old file and drops a miscoded apparatus line. See
  docs/DATA_OPERATIONS.md for the excerpt-containment check, the
  verse-by-verse verification, and the registries edited. Archived:
  `~/tesserae-backups/retired_duplicates_2026-09-19b/`.
  Also checked whether the Sodoma and Iona poems, each transmitted under
  both a Cyprian and a Tertullian attribution, are duplicate copies:
  `tertullian_pseudo.de_sodoma`/`cyprian_pseudo.sodoma` and
  `tertullian_pseudo.de_iona_propheta`/`cyprian_pseudo.de_iona` both run
  around 53% word-chunk containment (well below the 90%+ seen for genuine
  same-edition duplicates elsewhere in this document, and the differences
  are word-choice-level, not OCR-level), so both pairs are kept as distinct
  recensions rather than deduplicated. Removed three orphaned
  `backend/text_sources.json` citation entries found while checking
  credits for this comparison.
  Also preserved the two Book 1 prose items flagged when the whole-poem
  file was retired: they turn out to be prose prefaces ("Dictio Ennodi
  diaconi quando de Roma rediit" and "Fausto Praefatio") attached to poems
  6 and 7, whose verse is already covered by `ennodius.carmina.tess`; the
  prefaces themselves are not duplicated anywhere, so they are kept in a
  new file, `magnus_felix_ennodius.carmina_1_praefationes.tess` (2 lines).

- Retire two more duplicate Latin files (batch 2):
  `juvencus_caius_vettius_aquilinus.evangeliorum_libri_quattuor` (whole
  books stored one per line; `juvencus.historia_evangelica` already
  carries the same poem at per-verse granularity) and
  `pseudo_cyprian.carmina` (a six-poem bundle; five of its six poems
  already exist as separate, per-verse `cyprian_pseudo.*` files, kept).
  Also dropped a stale `data/text_genres.csv` row and a stale
  `backend/text_sources.json` entry left over from the 2026-09-18 batch,
  for a file already gone. See docs/DATA_OPERATIONS.md for the containment
  checks and the registries edited. Archived:
  `~/tesserae-backups/retired_duplicates_2026-09-19/`.

- Retire 40 duplicate Latin files, rebuild Martial from the per-book files:
  `martial.epigrams` and its 14 `.part.N` files, missing dozens of epigrams
  per book, are rebuilt from the 14 `martialis.epigrammata_N` files that
  held the complete text (6,399 verse-lines to 9,375); those 14 per-book
  files and 26 other duplicate or stray files are retired (40 total; see
  docs/DATA_OPERATIONS.md for why the file count and the "33" the source
  report used disagree, a count the merge commit's own title (`de8863e`,
  "(#389)") carried forward unchanged). Archived, not deleted outright:
  `~/tesserae-backups/retired_duplicates_2026-09-18/`.

- #390 Fixed the coverage list going blank mid-deploy. Right after a deploy
  reload, each Apache worker loads the 2GB passage index on its first
  request (about 90 seconds), and `/api/passages/works` used to answer
  slow or empty during that window, which Browse Corpus and Theme Search
  both read as "0 of 782 works are covered" -- indistinguishable from a
  real gap. The route now reads a small `works_by_language.json` sidecar
  next to the index first, falling back to loading the full index only
  when that file is missing or stamped with a different index version;
  the sidecar is written by the index merge script
  (`scripts/merge_index.py`) and, as a backstop, by whichever worker loads
  the index first. On the client, both pages retry a failed or empty
  coverage fetch once at +3s and once more at +10s, and show "Theme
  Search coverage is loading" instead of asserting "0 of N" while that is
  still unresolved.
- Theme Similarity Map: a "Similarity Map" tab beside Theme Search showing how
  strongly authors, works, centuries or genres connect to one another,
  built from the same passage-index description embeddings Theme Search
  and Similar Passages already use (`backend/connections_map.py`,
  `scripts/build_connections_map.py`). Canvas heatmap, click a cell for
  the work pairs behind it, click a work pair for the strongest passage
  pairs, click a passage pair to open the Reader. Translation pairs (the
  same text in two languages) are flagged two ways -- a curated list
  (`data/translation_pairs.json`, 730 pairs) and a
  heuristic (window-order correlation) -- and hidden by default. New
  routes `/api/passages/map`, `/api/passages/map/cell`,
  `/api/passages/map/pair`, `/api/passages/map/work`, all site-only in
  `backend/blueprints/mcp_manifest.py` (read-only picture of an existing
  signal, not a new tool a connector caller needs). Help page: a
  paragraph under Theme Search.
- Similarity Map details settled on the preview (2026-09-19 to 20):
  authors in chronological order, log colour scale with a "relative to
  size" mode, hover highlights the row and column and boxes both names,
  frozen column headers, drill-down work by work, then book by book, then
  passages, with the browser's Back button unwinding each step; a "Map
  built <date>" footer with a "Refresh map" button instead of any notice
  that the stored map is older than the corpus (the API still reports it
  as `stale` for operators; `?refresh=1` clears the process caches). Help
  page section "The Similarity Map".

### Data operations
- Corpus connections map cache built for the first time
  (`cache/connections_map/<index_fingerprint>.db`, detail in
  docs/DATA_OPERATIONS.md, 2026-09-19).

## 2026-09-18

### Theme Search
- #382 The re-ranker: a small model trained once on 32,000 readings by a paid
  model reads the top hundred results against the query and re-orders
  them. Judged precision in the top ten on sixteen test themes rises from
  0.42 to 0.59 (the paid reader itself reaches 0.71); every scene query
  and every sealed Curtius topos improved. It runs as its own service
  (`services/reader_server.py`, port 8091, the pattern of the query
  encoder) so the web application never loads the model, adds about three
  seconds to a first-page search, and when it is down or slow the page
  comes back in index order with no error. `?reader=0` shows the old
  order. The reproducible citation names the re-ranker's version.
  Records: evaluation/theme_benchmark/distill_train/REPORT.md.

- Query expansion removed from Theme Search retrieval (`find_by_text`
  defaults to `expand=False`): measured no effect on 15 of 16 test queries
  and, on the one it touched, it pushed a right answer out of the top
  hundred before the reader ever saw it
  (evaluation/theme_benchmark/expansion_test/REPORT.md). Help page's
  reading-step figures corrected from 42/59 percent, measured on a
  different candidate set, to the live page's own 29/43 percent on the
  same sixteen test themes.
- #385 Help: names are precise and paraphrases broad in Theme Search, and
  what to type when a search finds little (from a user report).
- #383 Browse Corpus marks every work Theme Search covers with a "Theme
  Search" badge, shows how many of a language's works are covered, and can
  list only those; the Help page says what the index holds.

### Data operations
- Planned: `scripts/precompute_passage_density.py` warms the Reader gutter's
  passage-density cache (`cache/passage_density/`) and, with `--lexical`, the
  lexical-density cache (`cache/lexical_density/`) for every work in the
  passage index, so a first Reader open of a large work no longer pays the
  ~100s/1.4 GB the live `/api/passages/density` computation costs on an
  Apache worker. Not yet run against the production index (detail in
  docs/DATA_OPERATIONS.md).
- The re-ranker service installed and switched on (detail in
  docs/DATA_OPERATIONS.md, 2026-09-18).

## 2026-09-16

### Corpus
- #380 Milton, Paradise Lost: every book now runs from line 1. The file
  had begun each book at 2 with a duplicated number a few lines in, so
  the opening lines were cited one too high and Verity's notes missed
  them; a blank row in Book 4 is gone. `scripts/corpus/apply_paradise_lost_numbering.py`
  brought the stores into line (data operation below) and
  `rekey_verity_paradise_lost.py` re-keyed the commentary.
- #378 Wordsworth, The Prelude (1850): Books XIII and XIV get their own
  numbers. The file had run them together under Book XII, so a line of the
  Snowdon ascent read "Prelude 12.900". Part files 13 and 14 added, part 12
  cut to Book XII; `scripts/corpus/apply_prelude_books.py` brought the
  passage index and the English index into line (data operation below).

### Data operations
- Paradise Lost refs remapped in the passage index (69 windows, 138 line
  refs, 2 blank rows dropped), English lemma caches and index updated for
  the thirteen files.
- The Prelude's refs remapped in the passage index (197 whole-work windows,
  192 part windows moved to the new parts, ids kept in embedding order),
  English lemma caches rebuilt (139 had been missing), English index
  updated for the four files with document frequency rebuilt.

## 2026-09-13

### Help
- Help gains "How well does it work?": one dated, measured figure per
  search and language (Latin, Greek, Coptic, Hebrew, English, Cross-Language,
  Theme Search), with "not measured" where that is the truth, and a
  standing invitation under each language for specialists' feedback and
  help; articles with full details are noted as in preparation.

### Corpus
- Lucan, Bellum Civile: six misreadings in the whole-work file corrected
  from its book files ("vitum" to "victum", "Tentates" to "Teutates" and
  four more); whole and books now agree line for line.
- Lucretius, De Rerum Natura: the six book files, which came from a
  different (Latin Library) edition with transposed lines, are regenerated
  from the Perseus whole-work file (Leonard), and the whole file's tags
  take the site's usual form "lucr. 1.1". One edition, one citation form.
  `scripts/corpus/apply_lucretius_lucan_editions.py` brings the passage
  index, the translation map and cached results into line.

### Fixes
- #375 Lemma cache saves write beside the file and rename over it, and a
  failed save is logged and counted as an error; files owned by another
  account had made saves fail silently.

### Data operations
- Document frequency restored to the canonical one-document-per-work rule
  in the Latin and Greek indexes (book files collapse to their base work;
  Latin 782 works, Greek 853). The stale-entry drop of the day before had
  recomputed it per file. Scripts touching the table now all call
  `build_lemma_doc_freq`. Found on the way: the book files of Lucretius and
  of Lucan come from a different edition than their whole-work files.

## 2026-09-12

### Corpus
- #371 Repaired malformed line tags in 54 files (double space, doubled
  period: `<sal.  Cat..58.15>` is now `<sal. Cat. 58.15>`), 32,256 tags,
  text unchanged; `tests/test_tess_tags_clean.py` lints every corpus file.
- #372 `scripts/corpus/repair_ref_tags.py`: fixes from the production run
  (atomic writes, unique backup stamps, duplicate-heading handling).

### Data operations
- The same repair applied to every store that had copied the raw tags:
  lemma caches, Latin and Greek inverted indexes, passage index
  (descriptions and window texts), 41 translation maps, one cached result.
- Stale index entries dropped: 33 Greek (old Septuagint leftovers, retired
  duplicates, renamed Philo works) and 1 English.
  `scripts/corpus/drop_stale_index_entries.py`.
- Rare-bigram caches rebuilt from the corpus for Greek (610 to 900
  documents) and Latin (899 to 812; retired duplicates no longer counted).
  `scripts/corpus/rebuild_bigrams.py`.

### Decisions
- Poem-level book files (Catullus, Horace, Juvenal, Vergil and others; 178
  files) stay out of the inverted index: indexing them beside the whole
  works would inflate document frequencies (2026-09-12).

## 2026-09-11

### Ports from the preview branch (general improvements, no new language)
- #367 Fusion-route fixes (context confirmation once per search, compute at
  the storage cap, meter decided server-side); Tessa reads the top 25, 100
  or all loaded parallels and says so; Cite button with a reproducible
  reference, MLA and Chicago, and a corpus-version stamp on fusion and
  Theme Search responses; interface audit (contrast, one focus ring, phone
  tab-strip fade, link previews, page titles, Theme Search query in the
  address with Copy link, screen-reader labels); Theme Search offers any
  set of languages.
- #368 Reader on phones (bottom sheet, tap to select), long texts drawn in
  1,000-line stretches, selection fixes; #370 hotfix limits the Reader's
  index-lemma shortcut to Persian, Urdu and Arabic after it changed Latin
  results.
- #369 Scorer: a synonym pair scores in the dictionary channel again
  (benchmark 781 to 788 of 862).

### Connector
- #366 References are cleaned before the connector shows them, and
  passage lookups accept the cleaned form.

## 2026-09-10

### Corpus
- #360 Curtius batch: Greek Anthology (16 books), Tiberianus, Pentadius,
  Prudentius Cathemerinon, Matthew of Vendome, Geoffrey of Vinsauf,
  Eberhard the German, Peter Riga, complete Carmina Burana, Aelian re-cut
  by sentence; Greek lemma-cache normalisation fixed.
- #362 45 duplicate texts retired (weaker copy of each pair).
- #363 Paton's Greek Anthology translation aligned (76.5%); #365 Pope's
  Prudentius aligned (99.4%); #364 Aeschines Against Ctesiphon trimmed to
  the speech.

### Assistant and connector
- #355 to #359 Tessa prose and guards (plain verdict words, no arithmetic,
  no speculation about access, cleaner citations, caveat wording).
- #361 Connector parity with the site, with a parity test.

---

# Earlier (January to February 2026, as first written)

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

### Fusion Search (February 21–22, 2026)
- **9-channel fusion search** available as "Fusion — All Channels (best recall)" in match type dropdown
- Combines lemma, lemma_min1, exact, edit_distance, sound, semantic, dictionary, syntax, and rare_word channels
- Weighted score fusion with convergence bonus (Config D weights)
- Two-pass line/window architecture: line pass (all 9 channels) + window pass (4 channels: lemma, lemma_min1, rare_word, dictionary) for enjambed allusions
- Syntax channel restored using syntax_latin.db (542K pre-parsed lines, lemma-inverted-index pruning)
- SSE streaming with per-channel progress updates
- Channel badges on results showing which channels found each pair
- Fused score display and sorting
- Per-channel result capping (top 50K per channel before fusion)
- Internal parallelization of edit_distance and sound channels (8 worker processes)

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
