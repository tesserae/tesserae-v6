# Tesserae MCP server

Exposes the Tesserae intertext-search API as tools for an MCP-capable AI client
(Claude Desktop, Claude Code, etc.). The API is open — no key required.

## Install & run
```bash
pip install fastmcp requests
python tesserae_mcp.py     # stdio transport
```

## Configure

**Claude Desktop** — add to `claude_desktop_config.json` (Settings → Developer →
Edit Config):
```json
{
  "mcpServers": {
    "tesserae": {
      "command": "python",
      "args": ["/full/path/to/tesserae_mcp.py"]
    }
  }
}
```

**Claude Code** — `claude mcp add tesserae -- python /full/path/to/tesserae_mcp.py`

Then restart the client and ask, e.g., *"Use Tesserae to compare Aeneid 1 with
Lucan's Civil War 1 and show the strongest parallels."*

## Tools

**Discovery**
| Tool | What it does |
|------|--------------|
| `get_languages` | List supported languages + cross-language pairs |
| `list_texts` | List texts (with ids) for a language; filter with `contains` |
| `describe_text` | Description, source citation, author dates, and genre/meter for one text |

**Word-level comparison**
| Tool | What it does |
|------|--------------|
| `compare_texts` | All-in-one: runs rare_words + rare_pairs + fusion_search and cross-references the results — start here |
| `rare_pairs` | Rare shared two-word collocations between two texts |
| `rare_words` | Rare shared individual words between two texts |
| `fusion_search` | Full 9-channel weighted fusion comparison (can take minutes on first run) |
| `cross_language` | Cross-language parallels (e.g. a Greek source behind a Latin poem) |

**Content / thematic search**
| Tool | What it does |
|------|--------------|
| `theme_search` | Find passages about a described subject, across all languages |
| `theme_compare` | Two whole works compared by content — closest scene pairs, no shared vocabulary needed |
| `similar_passages` | Content neighbours of a known passage |
| `theme_pair_lift` | Content-similarity context for word-level match pairs from fusion_search |

**Corpus search & passage fetch**
| Tool | What it does |
|------|--------------|
| `line_search` | Corpus-wide word/phrase search — the uniqueness check |
| `string_search` | Wildcard / boolean / exact text search |
| `get_passage` | Fetch the actual lines at a locus (always call before quoting a theme_search gist) |

**Utility**
| Tool | What it does |
|------|--------------|
| `submit_feature_request` | Report a missing text, incorrect attribution, or API suggestion |

`TESSERAE_API_BASE` overrides the API base (default the production site).

Unlike a ChatGPT Action, MCP tools have no short timeout, so `fusion_search`
(the flagship comparison) works here — it just may take a few minutes.
