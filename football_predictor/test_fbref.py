"""Test FBref bypass with curl_cffi"""
from curl_cffi import requests

TESTS = [
    # Team page with xG tables
    ('https://fbref.com/en/squads/206d90db/FC-Barcelona-Stats', 'Barcelona squad'),
    # Match results with xG
    ('https://fbref.com/en/comps/12/La-Liga-Stats', 'La Liga'),
    # Player stats
    ('https://fbref.com/en/players/dea698d9/Lamine-Yamal-Stats', 'Yamal'),
    # All competitions
    ('https://fbref.com/en/comps/', 'Competitions'),
]

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.6099.230 Mobile Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

for url, desc in TESTS:
    print(f'\n=== {desc} ===')
    # Test 1: curl_cffi with impersonate only
    try:
        r = requests.get(url, headers=HEADERS, impersonate='chrome120', timeout=20)
        print(f'  impersonate:  {r.status_code}', end='')
        if r.status_code == 200:
            print(f'  ({len(r.text)} bytes)', end='')
            if 'stats_table' in r.text:
                print('  ✅ HAS xG TABLE')
            elif 'Page Not Found' in r.text or len(r.text) < 500:
                print('  ❌ NO CONTENT')
            else:
                print('  ⚠️  PAGE LOADED (no stats_table marker)')
        else:
            print()
    except Exception as e:
        print(f'  impersonate:  ERROR {e}')

    # Test 2: with x-requested-with header (Sofascore trick)
    try:
        h2 = HEADERS.copy()
        h2['x-requested-with'] = '721637'
        r = requests.get(url, headers=h2, impersonate='chrome120', timeout=20)
        print(f'  +721637:       {r.status_code}', end='')
        if r.status_code == 200:
            print(f'  ({len(r.text)} bytes)', end='')
            if 'stats_table' in r.text:
                print('  ✅ HAS xG TABLE')
            elif len(r.text) < 500:
                print('  ❌ NO CONTENT')
            else:
                print('  ⚠️  LOADED')
        else:
            print()
    except Exception as e:
        print(f'  +721637:       ERROR {e}')
