"""fetchdown — free web search + clean-markdown extraction for LLM agents.

    from fetchdown import search, fetch

    results = search("python asyncio tutorial", n=5)
    page = fetch("https://example.com/article")
"""
from ._core import search, fetch

__all__ = ["search", "fetch"]
__version__ = "0.1.0"
