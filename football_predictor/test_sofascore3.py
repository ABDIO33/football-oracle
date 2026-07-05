"""Test full SofaScore pipeline with curl_cffi chrome124"""
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

def test(ep, desc=""):
    url = f'{BASE}{ep}'
    try:
        resp = requests.get(url, headers=headers, impersonate="chrome124", timeout=15)
        ok = resp.status_code == 200
        print(f'[{"OK" if ok else "XX"}] {resp.status_code} | {desc or ep}')
        if ok:
            data = resp.json()
            return data
        else:
            print(f'  Body: {resp.text[:200]}')
    except Exception as e:
        print(f'[ERR] {desc}: {e}')
    return None

# 1. Get info for team 2817 (Barcelona)
print("\n--- Team Info ---")
data = test('/team/2817', 'Team info')
if data:
    team = data.get('team', {})
    print(f'  Name: {team.get("name")}')
    print(f'  Country: {team.get("country", {}).get("name")}')
    print(f'  Sport: {team.get("sport", {}).get("name")}')

# 2. Get recent events for Barcelona
print("\n--- Team Events ---")
data = test('/team/2817/events/last/5', 'Last 5 matches')
if data:
    for e in data.get('events', []):
        ht = e.get('homeTeam', {}).get('name', '?')
        at = e.get('awayTeam', {}).get('name', '?')
        hs = e.get('homeScore', {}).get('display', '?')
        as_ = e.get('awayScore', {}).get('display', '?')
        status = e.get('status', {}).get('type', '?')
        print(f'  {ht} {hs}-{as_} {at} ({status})')

# 3. Get upcoming events
print("\n--- Upcoming Events ---")
data = test('/team/2817/events/next/5', 'Next 5 matches')
if data:
    for e in data.get('events', []):
        ht = e.get('homeTeam', {}).get('name', '?')
        at = e.get('awayTeam', {}).get('name', '?')
        print(f'  {ht} vs {at}')
        start = e.get('startTimestamp')
        if start:
            from datetime import datetime
            print(f'    Date: {datetime.fromtimestamp(start)}')

# 4. Get match statistics for a sample match
print("\n--- Match Statistics ---")
if data and data.get('events'):
    match_id = data['events'][0].get('id')
    if match_id:
        data2 = test(f'/event/{match_id}/statistics', f'Stats for match {match_id}')
        if data2:
            stats = data2.get('statistics', [])
            print(f'  Groups: {len(stats)}')

# 5. Get lineups
print("\n--- Lineups ---")
if match_id:
    data2 = test(f'/event/{match_id}/lineups', f'Lineups for match {match_id}')
    if data2:
        home = data2.get('home', {})
        away = data2.get('away', {})
        print(f'  Home formation: {home.get("formation")}')
        print(f'  Away formation: {away.get("formation")}')
        print(f'  Home players: {len(home.get("players", []))}')
        print(f'  Away players: {len(away.get("players", []))}')

# 6. Search for WC 2026 matches
print("\n--- World Cup Search ---")
data = test('/search/teams?q=Iraq', 'Search Iraq')
if data:
    for r in data.get('results', [])[:3]:
        e = r.get('entity', {})
        print(f'  {e.get("name")} (id={e.get("id")})')

print("\nDone!")
