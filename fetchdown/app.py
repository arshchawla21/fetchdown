"""Optional HTTP adapter over the fetchdown core.

    uv run python -m fetchdown.app      # dev server on :5000
    # GET /search?q=...&n=5
    # GET /read?url=...
    # GET /health
"""
import time

from flask import Flask, jsonify, request

from ._core import search as _search, fetch as _fetch

app = Flask(__name__)


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'missing ?q= parameter'}), 400
    n = min(int(request.args.get('n', 5)), 10)
    fetch_content = request.args.get('fetch', '1') not in ('0', 'false', 'no')

    start = time.time()
    try:
        results = _search(query, n=n, fetch_content=fetch_content)
    except Exception as e:
        return jsonify({'error': f'search failed: {str(e)}'}), 500

    return jsonify({
        'query': query,
        'total_elapsed': round(time.time() - start, 2),
        'count': len(results),
        'results': results,
    })


@app.route('/read', methods=['GET'])
def read():
    url = request.args.get('url', '').strip()
    if not url:
        return jsonify({'error': 'missing ?url= parameter'}), 400
    return jsonify(_fetch(url))


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


def main():
    app.run(debug=True, port=5000)


if __name__ == '__main__':
    main()
