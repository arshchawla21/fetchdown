"""Backwards-compatible entry point.

The engine now lives in the `fetchdown` package:
    from fetchdown import search, fetch        # library
    python -m fetchdown.server                 # MCP server (stdio)
    python -m fetchdown.app                    # Flask HTTP server

Running this file directly still starts the Flask dev server.
"""
from fetchdown.app import app, main

if __name__ == '__main__':
    main()
