# fetchdown

Free web search + clean-markdown extraction for LLM agents. A self-hosted,
no-API-key replacement for paid search/read services (Jina, etc.).

- **Search** the web via DuckDuckGo (`ddgs`)
- **Read** any URL — HTML (via `trafilatura`) or PDF (via `pymupdf`)
- **Clean** the output: nav, ads, citations, TOC dumps, and duplicate boilerplate stripped
- Fetches all results **in parallel** with a connection-pooled, browser-impersonating HTTP client (`curl_cffi`)

Three ways to use it: as an **MCP server** (for tool-calling agents), as a **Python
library** (for code-executing agents), or as an **HTTP service**.

## Install

```bash
uv sync                 # core (library + MCP server)
uv sync --extra http    # also installs Flask for the HTTP server
```

## 1. MCP server (recommended for agents)

Exposes two tools — `web_search` and `read_url` — over stdio.

```bash
uv run fetchdown-mcp
```

Register it with an MCP client. For **Claude Desktop** / **Claude Code**, add to
your MCP config:

```json
{
  "mcpServers": {
    "fetchdown": {
      "command": "uv",
      "args": ["--directory", "/Users/arshchawla21/Projects/Business/fetchdown", "run", "fetchdown-mcp"]
    }
  }
}
```

The agent then calls:
- `web_search(query, n=5, fetch_content=True)` — search + read top results in one call
- `read_url(url)` — read a single page you already have a link to

## 2. Python library

```python
from fetchdown import search, fetch

# Search + fetch + clean, in parallel:
results = search("python asyncio tutorial", n=5)
for r in results:
    print(r["title"], r["url"], r["chars"], r["error"])
    print(r["markdown"])

# Just the hits, no content (fast):
hits = search("python asyncio", n=5, fetch_content=False)

# Read one page:
page = fetch("https://example.com/article")
print(page["markdown"])
```

Every result is a dict: `{url, title, markdown, chars, elapsed, error}`
(or `{url, title, snippet}` when `fetch_content=False`). Failures never raise —
`markdown` is `None` and `error` holds the reason.

## 3. HTTP service

```bash
uv run fetchdown-http          # dev server on :5000
```

- `GET /search?q=<query>&n=5&fetch=1`
- `GET /read?url=<url>`
- `GET /health`
