"""Local air-quality explorer. Run: python app.py"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import Flask, render_template, request
from unified_map import build_map

load_dotenv(Path(__file__).with_name('.env'))
app = Flask(__name__)
BASE_URL = 'https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69'


class FetchError(Exception):
    pass


def _fetch_records(state, city):
    key = os.environ.get('DATA_GOV_API_KEY', '').strip()
    if not key:
        raise FetchError('Set DATA_GOV_API_KEY in your .env file, then restart the app.')
    if not shutil.which('curl'):
        raise FetchError('curl is required. Install it on the computer running Flask.')
    params = {'api-key': key, 'format': 'json', 'limit': 100, 'offset': 0,
              'filters[state]': state}
    if city:
        params['filters[city]'] = city
    records, seen_pages = [], set()
    for _ in range(200):
        # Pass URL via stdin configuration so the key is not a process argument.
        config = 'url = ' + json.dumps(BASE_URL + '?' + urlencode(params)) + '\n'
        try:
            result = subprocess.run(
                ['curl', '--config', '-', '--silent', '--show-error', '--fail',
                 '--connect-timeout', '15', '--max-time', '120',
                 '-H', 'accept: application/json'],
                input=config, capture_output=True, text=True, timeout=125)
        except (OSError, subprocess.TimeoutExpired):
            raise FetchError('The API connection failed or timed out. Please try again.') from None
        if result.returncode:
            raise FetchError('The API request failed (possibly a timeout or HTTP 502). Please try again.')
        try:
            data = json.loads(result.stdout)
            if not isinstance(data, dict) or not isinstance(data.get('records'), list):
                raise ValueError
            batch = data['records']
            if any(not isinstance(row, dict) for row in batch):
                raise ValueError
            total = int(data['total']) if data.get('total') is not None else None
            if total is not None and total < 0:
                raise ValueError
        except (ValueError, TypeError):
            raise FetchError('The API returned an unexpected response. Please try again.') from None
        if not batch:
            if total is not None and len(records) < total:
                raise FetchError('The API stopped before returning all records. Please try again.')
            return records
        signature = json.dumps(batch, sort_keys=True)
        if signature in seen_pages:
            raise FetchError('The API repeated a page. Fetch stopped to avoid duplicate data.')
        seen_pages.add(signature)
        records.extend(batch)
        params['offset'] += len(batch)
        if total is not None and len(records) >= total:
            return records
    raise FetchError('The query exceeded 200 pages. Please narrow it to a city.')



def fetch_records(state, city):
    """Use exact filters first, then tolerate user-entered capitalisation."""
    state = ' '.join(state.split())
    city = ' '.join(city.split())
    records = _fetch_records(state, city)
    if records:
        return records
    canonical_state = state.title()
    if canonical_state != state:
        records = _fetch_records(canonical_state, city)
        if records:
            return records
    if city:
        # Resolve city spelling/case against returned data, never substitute another city.
        state_records = _fetch_records(canonical_state, '')
        wanted = city.casefold()
        return [r for r in state_records
                if ' '.join(str(r.get('city', '')).split()).casefold() == wanted]
    return []


@app.route('/', methods=['GET', 'POST'])
def index():
    state, city = '', ''
    error = None
    map_html = None
    count = station_count = skipped = 0
    loaded = False
    if request.method == 'GET':
        map_html, _, _ = build_map([])
    if request.method == 'POST':
        state = request.form.get('state', '').strip()
        city = request.form.get('city', '').strip()
        try:
            if not state or len(state) > 100 or len(city) > 100:
                raise FetchError('Enter a state, and keep each filter under 100 characters.')
            records = fetch_records(state, city)
            count = len(records)
            loaded = True
            map_html, station_count, skipped = build_map(records)
        except FetchError as exc:
            error = str(exc)
    return render_template('index.html', state=state, city=city, error=error,
                           map_html=map_html, count=count, station_count=station_count,
                           skipped=skipped, loaded=loaded)


@app.route('/connectivity', methods=['GET', 'POST'])
def connectivity():
    import math
    from transport import search_transport, transport_map, CATEGORIES, DATA_DIR
    lat, lon, radius, limit = '', '', 5.0, 5
    error, map_html, results = None, None, None
    try:
        if request.method == 'POST':
            lat = float(request.form.get('latitude', ''))
            lon = float(request.form.get('longitude', ''))
            radius = float(request.form.get('radius', ''))
            limit = int(request.form.get('limit', ''))
            if not (math.isfinite(lat) and math.isfinite(lon) and
                    -90 <= lat <= 90 and -180 <= lon <= 180 and
                    math.isfinite(radius) and 0.1 <= radius <= 100 and 1 <= limit <= 20):
                raise ValueError
            results = search_transport(lat, lon, radius, limit)
            map_html = transport_map(lat, lon, results, radius)
    except (ValueError, OverflowError):
        error = 'Enter valid coordinates, a radius from 0.1 to 100 km, and 1–20 results per category.'
        lat, lon, radius, limit = '', '', 5.0, 5
    except OSError:
        error = 'Local transport data is missing. Restore the connectivity folder from the download.'
    return render_template('connectivity.html', lat=lat, lon=lon, radius=radius,
                           limit=limit, error=error, results=results, map_html=map_html,
                           categories=CATEGORIES)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
