"""Core web search + content extraction engine.

Pure functions with no web-framework dependency. Two public entry points:

    fetch(url)            -> dict   single URL -> cleaned markdown
    search(query, n=...)  -> list   DDGS results, each fetched + cleaned in parallel
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import time

from ddgs import DDGS
from curl_cffi import requests as cffi_requests
import trafilatura
import pymupdf

from ._clean import clean_markdown

FETCH_TIMEOUT = 10
MAX_CHARS = 20000

# Module-level HTTP session: reuses TLS connections + pool across requests.
_HTTP_SESSION = cffi_requests.Session(impersonate='chrome')


def _is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith('.pdf')


def _http_get(url: str):
    try:
        resp = _HTTP_SESSION.get(url, timeout=FETCH_TIMEOUT, allow_redirects=True)
        if resp.status_code == 200:
            return resp
    except Exception:
        return None
    return None


def _extract_pdf(pdf_bytes: bytes) -> str:
    doc = pymupdf.open(stream=pdf_bytes, filetype='pdf')
    try:
        return '\n\n'.join(page.get_text() for page in doc).strip()
    finally:
        doc.close()


def fetch(url: str, title: str = '', max_chars: int = MAX_CHARS) -> dict:
    """Fetch a single URL and return cleaned markdown.

    Returns a dict: {url, title, markdown, chars, elapsed, error}.
    On any failure, markdown is None and error holds the reason.
    """
    start = time.time()

    def _err(msg):
        return {'url': url, 'title': title, 'markdown': None,
                'chars': 0, 'elapsed': round(time.time() - start, 2), 'error': msg}

    resp = _http_get(url)
    if resp is None:
        return _err('fetch failed')

    content = resp.content
    if _is_pdf_url(url) or content[:5] == b'%PDF-':
        try:
            markdown = _extract_pdf(content)
        except Exception as e:
            return _err(f'pdf: {e}')
    else:
        markdown = trafilatura.extract(
            resp.text,
            output_format='markdown',
            include_links=False,
            include_tables=False,
            include_comments=False,
        )

    if not markdown:
        return _err('extraction failed')

    markdown = clean_markdown(markdown)
    if max_chars and len(markdown) > max_chars:
        markdown = markdown[:max_chars]

    return {
        'url': url,
        'title': title,
        'markdown': markdown,
        'chars': len(markdown),
        'elapsed': round(time.time() - start, 2),
        'error': None,
    }


def search(query: str, n: int = 5, fetch_content: bool = True,
           max_chars: int = MAX_CHARS) -> list[dict]:
    """Search the web via DuckDuckGo and (optionally) fetch each result's content.

    Args:
        query: search string.
        n: max results (1-10).
        fetch_content: if True, fetch + extract markdown for each hit in parallel.
            If False, returns just the search hits (url/title/snippet) — much faster.
        max_chars: truncate each page's markdown to this length.

    Returns a list of result dicts in DDGS rank order. When fetch_content is True
    each dict carries {url, title, markdown, chars, elapsed, error}; otherwise
    {url, title, snippet}.
    """
    n = max(1, min(int(n), 10))
    seen_domains = set()
    hits = []  # deduped search hits in rank order

    for r in DDGS().text(query, max_results=n):
        href = r.get('href') or ''
        if not href:
            continue
        parsed = urlparse(href)
        domain = parsed.netloc + parsed.path[:20]
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        hits.append(r)

    if not fetch_content:
        return [{'url': h.get('href', ''), 'title': h.get('title', ''),
                 'snippet': h.get('body', '')} for h in hits]

    order = {h.get('href', ''): i for i, h in enumerate(hits)}
    results = []
    with ThreadPoolExecutor(max_workers=max(1, len(hits))) as executor:
        futures = {
            executor.submit(fetch, h.get('href', ''), h.get('title', ''), max_chars): h
            for h in hits
        }
        for future in as_completed(futures):
            h = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                results.append({'url': h.get('href', ''), 'title': h.get('title', ''),
                                'markdown': None, 'chars': 0, 'elapsed': None, 'error': str(e)})

    results.sort(key=lambda x: order.get(x.get('url', ''), 999))
    return results
