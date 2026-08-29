# The Reader

**Live.** Read a text with two things beside it: a gutter of marks showing where
the rest of the corpus connects to each line, and a panel of those connections
for whatever is selected.

`/read?work=<work>.tess&lang=<lang>` — optionally `&ref=`, `&refEnd=`, `&tab=`,
`&q=`.

## The gutter

Two nine-pixel columns down the left of the text, with a key above it:

| Mark | Colour | Meaning |
|---|---|---|
| **W** | red `#b91c1c` | shared wording: another passage uses some of the same words |
| **C** | purple `#7c6bb0` | similar content, whether or not any words are shared |

Darker means more connections. The two columns fill **independently** as each
answer arrives, so one may be marked while the other is still working: hollow
pulsing marks read as "not known yet" rather than "nothing here".

The key was missing until 2026-08-25. The only explanation was a `title`
tooltip, which does not exist on a phone, so a reader saw two columns of coloured
squares with no way to learn what they were. The legend chip was also the wrong
colour, amber against a purple mark.

## The panel

- **Similar passages** — passages elsewhere whose content resembles the
  selection, across every indexed language.
- **Translation** — the aligned public-domain English where one exists. Coverage
  is partial: roughly a fifth of the Greek corpus and a tenth of the Latin, and
  the panel says so rather than leaving a reader to discover it.

Summaries in the panel mark any participant not found in the passage: "(not
found here: Aeneas)".

## Arriving from Theme Search

The link carries both ends of the matched window plus the query:

```
/read?work=...&lang=...&ref=<ref_start>&refEnd=<ref_end>&tab=translation&q=<query>
```

The Reader selects the **whole matched span**, scrolls it to the middle, opens
the translation, and shows the originating search above the text with a link
back to results.

Passing only `ref_start` selected a single line, so the translation panel fetched
the English for one line and a reader saw a whole original beside a fragment.
Both ends matter.

Refs match exactly between the passage index and the text API — both use
`"valerius flaccus 1.1"` — so no normalisation is needed.

## Performance

Gutter: 5.4s on first visit, instant thereafter. Density is cached to disk and
keyed by an index fingerprint, so it invalidates when the index changes.

## Open

- Original and translation sit in two columns, not interleaved line by line.
  Interleaving is a larger piece of work and worth doing deliberately.
- The verbal-parallel tab is not wired to the search engines yet.

## Verbal Parallels on a passage (2026-08-29)

A multi-line selection is searched on its most distinctive words: above 12
content lemmas, line_search keeps the rarest by corpus document frequency
and names them in the response (`query_reduced`); the panel shows the
reader which words were matched on. Details and measurements in
rare_words.md. Documented on the site's Help page (Reader section, "The
panel" list) and shown inline in the panel itself.
