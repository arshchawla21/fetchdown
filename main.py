from flask import Flask, jsonify, request
from ddgs import DDGS
from curl_cffi import requests as cffi_requests
import trafilatura
import pymupdf
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re
import time

app = Flask(__name__)

FETCH_TIMEOUT = 10

# Wiki citation/edit markers
WIKI_NOISE_RE = re.compile(r'\[\d+\]|\[edit\]|\[\s*citation needed\s*\]', re.IGNORECASE)

# Orphan page-range refs left after stripping wiki citations: ": 111-148"
PAGE_REF_PREFIX_RE = re.compile(r'^:\s*\d+(?:[–\-]\d+)?\s*', re.MULTILINE)

# Bullets with leading whitespace from stripped citation prefixes
LIST_INDENT_RE = re.compile(r'^[ \t]+(?=- )', re.MULTILINE)

# Adjacent duplicate phrases (2-7 tokens, each 2+ chars). Catches doubled bylines:
# "Reviewed by Erika Rasure Reviewed by Erika Rasure" -> "Reviewed by Erika Rasure"
ADJACENT_DUP_RE = re.compile(r'\b((?:\S{2,}\s+){1,6}\S{2,})\s+\1\b')

# Investopedia-style TOC + author cards. Strip from "Table of Contents..." up to first prose lead.
TOC_DUMP_RE = re.compile(
    r'Table of Contents Expand Table of Contents.{30,2500}?'
    r'(?=\b(?:Definition|Key Takeaways|Important|Introduction|Overview|Abstract|Summary)\b)',
    re.DOTALL,
)

# Inline CTA / nav phrases
CTA_RE = re.compile(
    r'Get personalized, AI-powered answers[^.]*?ASK\s*'
    r'|Learn about our (?:editorial policies|Financial Review Board)\s*'
    r'|Subscribe to our newsletter[^.]*?\.\s*'
    r'|Sign up for[^.]*?newsletter[^.]*?\.\s*',
    re.IGNORECASE,
)

# Tail markers — truncate from the first match onward (refs, source lists, etc.)
TAIL_TRUNCATE_RE = re.compile(
    r'\n#{1,6}\s*(?:references?|external links?|see also|notes?|bibliography|further reading|sources|citations?|related articles?)\s*\n'
    r'|\bArticle Sources\b'
    r'|\nRead more\s+\w',
    re.IGNORECASE,
)

EXTRA_BLANKLINES_RE = re.compile(r'\n{3,}')


def _is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith('.pdf')


def _fetch(url: str):
    try:
        resp = cffi_requests.get(url, impersonate='chrome', timeout=FETCH_TIMEOUT, allow_redirects=True)
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


def _clean_markdown(md: str) -> str:
    md = WIKI_NOISE_RE.sub('', md)
    md = PAGE_REF_PREFIX_RE.sub('', md)
    md = LIST_INDENT_RE.sub('', md)
    # Two passes: catches "A B A B C D C D" patterns
    md = ADJACENT_DUP_RE.sub(r'\1', md)
    md = ADJACENT_DUP_RE.sub(r'\1', md)
    md = TOC_DUMP_RE.sub('', md)
    md = CTA_RE.sub('', md)
    m = TAIL_TRUNCATE_RE.search(md)
    if m:
        md = md[:m.start()]
    md = EXTRA_BLANKLINES_RE.sub('\n\n', md)
    return md.strip()


def fetch_and_extract(result):
    url = result['href']
    title = result.get('title', '')
    start = time.time()

    def _err(msg):
        return {'url': url, 'title': title, 'markdown': None, 'error': msg, 'elapsed': round(time.time() - start, 2)}

    resp = _fetch(url)
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

    markdown = _clean_markdown(markdown)

    if len(markdown) > 20000:
        markdown = markdown[:20000]

    return {
        'url': url,
        'title': title,
        'markdown': markdown,
        'chars': len(markdown),
        'elapsed': round(time.time() - start, 2),
        'error': None,
    }


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'missing ?q= parameter'}), 400

    num_results = min(int(request.args.get('n', 5)), 10)

    total_start = time.time()

    try:
        ddgs_results = list(DDGS().text(query, max_results=num_results))
    except Exception as e:
        return jsonify({'error': f'search failed: {str(e)}'}), 500

    # Deduplicate by domain+path-prefix before fetching
    seen_domains = set()
    deduped = []
    for r in ddgs_results:
        domain = urlparse(r['href']).netloc + urlparse(r['href']).path[:20]
        if domain not in seen_domains:
            seen_domains.add(domain)
            deduped.append(r)

    # Phase B: URLs -> markdown (parallel)
    results = []
    with ThreadPoolExecutor(max_workers=len(deduped) or 1) as executor:
        futures = {executor.submit(fetch_and_extract, r): r for r in deduped}
        for future in as_completed(futures):
            original = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                results.append({
                    'url': original['href'],
                    'title': original.get('title', ''),
                    'markdown': None,
                    'error': str(e),
                    'elapsed': None,
                })

    url_order = {r['href']: i for i, r in enumerate(deduped)}
    results.sort(key=lambda x: url_order.get(x.get('url', ''), 999))

    return jsonify({
        'query': query,
        'total_elapsed': round(time.time() - total_start, 2),
        'count': len(results),
        'results': results,
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
