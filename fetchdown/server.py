"""MCP server exposing fetchdown as agent tools.

Run over stdio (for Claude Desktop / Claude Code / any MCP client):

    fetchdown-mcp
    # or
    uv run python -m fetchdown.server

Exposes two tools:
    web_search(query, n=5, fetch_content=True)
    read_url(url)
"""
from mcp.server.fastmcp import FastMCP

from ._core import search as _search, fetch as _fetch

mcp = FastMCP("fetchdown")


def _format_result(r: dict) -> str:
    title = r.get("title") or "(no title)"
    url = r.get("url") or ""
    if r.get("error"):
        return f"## {title}\n{url}\n\n_Could not fetch: {r['error']}_"
    body = r.get("markdown") or r.get("snippet") or ""
    return f"## {title}\n{url}\n\n{body}"


@mcp.tool()
def web_search(query: str, n: int = 5, fetch_content: bool = True) -> str:
    """Search the web (DuckDuckGo) and return the top results as clean markdown.

    A free replacement for paid search/read APIs. By default it fetches and
    extracts the readable content of each result page (boilerplate, nav, ads,
    and citations stripped), so a single call gives you ready-to-read text.

    Args:
        query: what to search for.
        n: number of results to return (1-10, default 5).
        fetch_content: when True (default), fetch + extract each page's content.
            Set False for a fast list of titles/URLs/snippets only.
    """
    results = _search(query, n=n, fetch_content=fetch_content)
    if not results:
        return f"No results for: {query}"
    header = f"# Search results for: {query}\n"
    return header + "\n\n---\n\n".join(_format_result(r) for r in results)


@mcp.tool()
def read_url(url: str) -> str:
    """Fetch a single URL and return its main content as clean markdown.

    Handles HTML (via trafilatura) and PDFs. Strips navigation, ads, and
    boilerplate. Use this to read a specific page the user or you already have a
    link to.
    """
    r = _fetch(url)
    if r.get("error"):
        return f"Could not read {url}: {r['error']}"
    return _format_result(r)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
