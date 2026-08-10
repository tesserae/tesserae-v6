# Tesserae MCP server

Exposes the Tesserae intertext-search API as tools for an MCP-capable AI client
(Claude Desktop, Claude Code, etc.). The API is open — no key required.

## Install & run
```bash
pip install "mcp[cli]" requests
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
| Tool | What it does |
|------|--------------|
| `get_languages` | List supported languages + cross-language pairs |
| `list_texts` | List texts (with ids) for a language; filter with `contains` |
| `line_search` | Corpus-wide search — the uniqueness check |
| `string_search` | Wildcard / boolean / exact text search |
| `rare_pairs` | Rare shared two-word collocations between two texts |
| `rare_words` | Rare shared individual words between two texts |
| `fusion_search` | Full weighted fusion comparison (can take minutes) |

`TESSERAE_API_BASE` overrides the API base (default the production site).

Unlike a ChatGPT Action, MCP tools have no short timeout, so `fusion_search`
(the flagship comparison) works here — it just may take a few minutes.
