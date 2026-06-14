"""Test FotMob web API endpoints"""
import requests, json

BASE = 'https://www.fotmob.com/api'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
    'Accept': 'application/json',
}

tests = [
    # Todays matches
    ('GET', f'{BASE}/matches', {'date': '20260613'}, 'Today matches'),
    # Standings - Premier League
    ('GET', f'{BASE}/standings', {'leagueId': 47}, 'Premier League standings'),
    # Team - Barcelona
    ('GET', f'{BASE}/team', {'teamId': 9851}, 'Barcelona team'),
    # Player - Messi
    ('GET', f'{BASE}/player', {'id': 664500}, 'Player'),
    # League matches
    ('GET', f'{BASE}/league', {'id': 47, 'season': '2025/2026'}, 'League matches'),
]

for method, url, params, desc in tests:
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        ct = r.headers.get('Content-Type', '')
        is_json = 'json' in ct
        size = len(r.text)
        print(f'{desc:30s} {r.status_code} ({size:>8,} bytes) json={is_json}', end='')
        if r.status_code == 200 and is_json:
            data = r.json()
            if 'matches' in desc.lower():
                leagues = data.get('leagues', [])
                print(f'  leagues={len(leagues)}')
                for l in leagues[:2]:
                    print(f'    {l.get("leagueName", "?"):25s} matches={len(l.get("matches",[]))}')
            elif 'standings' in desc.lower():
                tables = data.get('standings', [])
                print(f'  tables={len(tables)}')
                if tables:
                    table = tables[0].get('table', [])
                    print(f'    Top: {table[0]["name"] if table else "?"}')
            elif 'team' in desc.lower():
                print(f'  name={data.get("name","?")}')
            elif 'league' in desc.lower():
                fixtures = data.get('fixtures', {})
                dates = list(fixtures.keys())[:3]
                print(f'  dates={len(fixtures)}')
        else:
            print()
    except Exception as e:
        print(f'{desc:30s} ERROR {e}')
