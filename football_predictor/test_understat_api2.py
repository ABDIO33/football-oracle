"""Try different Understat API variations"""
import requests

base = 'https://understat.com'
headers = {'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}

tests = [
    '/getLeagueData/EPL/2025',
    '/getLeagueData/La+liga/2025',
    '/getLeagueData/Bundesliga/2025',
    '/api/getLeagueData/EPL/2025',
    '/getLeagueData?league=EPL&season=2025',
    '/league/EPL/2025',
    '/main/getLeagueData/EPL/2025',
]

for path in tests:
    url = base + path
    r = requests.get(url, headers=headers, timeout=15)
    ct = r.headers.get('Content-Type', '')
    is_json = 'json' in ct
    print(f'{path}: {r.status_code} ({len(r.text)} bytes) json={is_json}', end='')
    if is_json:
        d = r.json()
        print(f' keys={list(d.keys())[:5]}', end='')
    print()
