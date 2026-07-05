"""Find World Cup tournament ID and fetch lineups"""
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

BASE = 'https://www.sofascore.com/api/v1'

def get(ep):
    url = f'{BASE}{ep}'
    try:
        resp = requests.get(url, headers=headers, impersonate="chrome124", timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

# 1. Search for unique tournaments
print("=== Searching for World Cup tournament ===")
# Try the categories endpoint
data = get('/category/1')  # football category
if data:
    cats = data.get('categories', [])
    print(f'Categories: {len(cats)}')
    for c in cats[:5]:
        name = c.get('name', c.get('slug', '?'))
        print(f'  {name}')

# Try all popular football tournaments
tournament_ids = {
    1: 'EURO', 3: 'UCL', 7: 'UCL (alt)', 16: 'FIFA Club WC',
    17: 'WC', 34: 'WC Qual', 35: 'WC (alt)',
    72: 'FIFA WC', 132: 'World Cup'
}

for tid, name in sorted(tournament_ids.items()):
    data = get(f'/unique-tournament/{tid}')
    if data:
        t = data.get('uniqueTournament', {})
        print(f'  [{tid}] {t.get("name")} (slug={t.get("slug")})')
        seasons = data.get('seasons', [])
        if seasons:
            for s in sorted(seasons, key=lambda x: x.get('year', 0), reverse=True)[:3]:
                print(f'    Season: {s.get("year")} (id={s.get("id")})')
    else:
        print(f'  [{tid}] Not found')

# 2. Check Iraq vs France match from scheduled events
print("\n=== Iraq vs France Match ===")
data = get('/sport/football/scheduled-events/2026-06-23')
if data and data.get('events'):
    for e in data['events']:
        ht = e.get('homeTeam', {}).get('name', '')
        at = e.get('awayTeam', {}).get('name', '')
        if 'Iraq' in ht or 'France' in ht or 'Iraq' in at or 'France' in at:
            mid = e.get('id')
            print(f'  Match ID: {mid}')
            print(f'  {ht} vs {at}')
            print(f'  Tournament: {e.get("tournament", {}).get("name")}')
            print(f'  Season: {e.get("season", {}).get("name")}')
            # Get lineups
            if mid:
                lu = get(f'/event/{mid}/lineups')
                if lu:
                    home = lu.get('home', {})
                    away = lu.get('away', {})
                    print(f'  Home formation: {home.get("formation")}')
                    print(f'  Away formation: {away.get("formation")}')
                stats = get(f'/event/{mid}/statistics')
                if stats:
                    groups = stats.get('statistics', [])
                    print(f'  Stat groups: {len(groups)}')

print("\nDone!")
