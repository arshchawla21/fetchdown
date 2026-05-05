from flask import Flask, jsonify, request
from ddgs import DDGS
import trafilatura
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

app = Flask(__name__)


def fetch_and_extract(result):
    url = result['href']
    title = result.get('title', '')
    start = time.time()

    html = trafilatura.fetch_url(url)
    if not html:
        from scrapling.fetchers import StealthyFetcher
        page = StealthyFetcher.fetch(url)
        html = page.html

    if not html:
        return {'url': url, 'title': title, 'markdown': None, 'error': 'fetch failed', 'elapsed': round(time.time() - start, 2)}

    markdown = trafilatura.extract(html, output_format='markdown', include_links=False)

    if not markdown:
        return {'url': url, 'title': title, 'markdown': None, 'error': 'extraction failed', 'elapsed': round(time.time() - start, 2)}
    
    if len(markdown) > 20000:
        markdown = markdown[:20000]  # truncate, don't drop

    return {
        'url': url,
        'title': title,
        'markdown': markdown,
        'chars': len(markdown),
        'elapsed': round(time.time() - start, 2),
        'error': None
    }


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'missing ?q= parameter'}), 400

    num_results = min(int(request.args.get('n', 5)), 10)  # cap at 10

    total_start = time.time()

    # Phase A: keyword -> URLs
    try:
        ddgs_results = list(DDGS().text(query, max_results=num_results))
    except Exception as e:
        return jsonify({'error': f'search failed: {str(e)}'}), 500
    

    # Deduplicate by domain before fetching
    from urllib.parse import urlparse

    seen_domains = set()
    deduped = []
    for r in ddgs_results:
        domain = urlparse(r['href']).netloc + urlparse(r['href']).path[:20]
        if domain not in seen_domains:
            seen_domains.add(domain)
            deduped.append(r)

    futures = {executor.submit(fetch_and_extract, r): r for r in ddgs_results}  # deduped

    # Phase B: URLs -> markdown (parallel)
    results = []
    with ThreadPoolExecutor(max_workers=num_results) as executor:
        futures = {executor.submit(fetch_and_extract, r): r for r in ddgs_results}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({'error': str(e)})

    # Sort back by original order
    url_order = {r['href']: i for i, r in enumerate(ddgs_results)}
    results.sort(key=lambda x: url_order.get(x.get('url', ''), 999))

    return jsonify({
        'query': query,
        'total_elapsed': round(time.time() - total_start, 2),
        'count': len(results),
        'results': results
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True, port=5000)