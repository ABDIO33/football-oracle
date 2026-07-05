"""Properly test SofaScore API with curl_cffi - 404 is success!"""
from curl_cffi import requests
import json

headers = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/124.0.0.0 Safari/537.36'),
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.sofascore.com/',
    'Origin': 'https://www.sofascore.com',
    'x-requested-with': 'XMLHttpRequest'
}

endpoints = [
    # Team search (Barcelona)
    '/api/v1/search/teams?q=Barcelona',
    # Unique tournaments
    '/api/v1/unique-tournament/1',
    # Live matches
    '/api/v1/sport/football/events/live',
    # Config
    '/api/v1/config/device-info/android',
    # Featured events
    '/api/v1/sport/football/featured-events',
]

for ep in endpoints:
    url = f'https://www.sofascore.com{ep}'
    try:
        resp = requests.get(url, headers=headers, impersonate="chrome124", timeout=15)
        print(f'{resp.status_code:3d} | {ep}')
        if resp.status_code == 200:
            data = resp.json()
            if 'results' in data:
                print(f'       -> {len(data["results"])} results')
                if data['results']:
                    r = data['results'][0]
                    e = r.get('entity', {})
                    print(f'       -> First: {e.get("name")} (id={e.get("id")})')
            elif 'team' in data:
                print(f'       -> Team: {data["team"].get("name")}')
            elif 'events' in data:
                print(f'       -> {len(data["events"])} events')
        elif resp.status_code == 404:
            print(f'       -> Body: {resp.text[:200]}')
        else:
            print(f'       -> {resp.text[:200]}')
    except Exception as e:
        print(f'ERR | {ep}: {e}')
