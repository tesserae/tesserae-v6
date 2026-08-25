# MCP connector: use your own AI with Tesserae

**Live since 2026-08-14.** Lets an outside assistant run Tesserae searches
directly.

Connector URL: `https://tesserae.caset.buffalo.edu/api/mcp`

## Two routes for a reader

1. **Free, any AI, including sandboxed ones.** Run the search on the site, click
   Export CSV, paste it into any assistant with the prompt from the Help page.
   The CSV carries each parallel loci, both lines, the score, the shared words
   and which detection methods agreed. Works with free tiers and with apps like
   standard Gemini that cannot reach an API.
2. **The AI runs the searches.** Requires a paid subscription (Claude Pro
   minimum for connectors, added on desktop or web rather than mobile). Then a
   reader can simply ask.

An advanced local option runs the connector on the reader's own machine with
`tesserae_mcp.py`, needing no account.

## Tools exposed

`list_texts`, `line_search`, `string_search`, `fusion_search`, `compare_texts`,
`rare_words`, `rare_pairs`, `cross_language`, `get_languages`,
`submit_feature_request`, and the passage-index tools (theme search, similar
passages).

## Notes

- The connector inherits backend bugs. The single-word exact search fault
  affected it while its own tool description promised that a single-word query
  lists every line containing the word.
- Interactively-authenticated MCP servers may be absent in headless or scheduled
  runs.
- Tessa is a *different* thing: she runs on this server for readers who do not
  have their own AI. See [assistant_tessa.md](assistant_tessa.md).
