"""Discover SofaScore endpoints for upcoming fixtures"""
from curl_cffi import requests
import json
from datetime import datetime

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

def get(ep, desc=""):
    url = f'{BASE}{ep}'
    try:
        resp = requests.get(url, headers=headers, impersonate="chrome124", timeout=15)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f'  [{resp.status_code}] {desc}')
            return None
    except Exception as e:
        print(f'  [ERR] {desc}: {e}')
        return None

# 1. Find tournament IDs
print("=== Finding World Cup ===")
# Try searching for World Cup
data = get('/search/teams?q=World%20Cup', 'Search World Cup')
if data:
    for r in data.get('results', []):
        e = r.get('entity', {})
        print(f'  {e.get("name")} (id={e.get("id")}, type={r.get("type")})')

# 2. List unique tournaments (football)
print("\n=== Popular Tournaments ===")
data = get('/unique-tournament/1', 'La Liga info')
if data:
    t = data.get('uniqueTournament', {})
    print(f'  {t.get("name")} (id={t.get("id")})')

data = get('/unique-tournament/3', 'Premier League info')
if data:
    t = data.get('uniqueTournament', {})
    print(f'  {t.get("name")} (id={t.get("id")})')

data = get('/unique-tournament/7', 'World Cup info')
if data:
    t = data.get('uniqueTournament', {})
    print(f'  {t.get("name")} (id={t.get("id")})')
    # Get seasons for World Cup
    seasons = data.get('seasons', [])
    print(f'  Seasons: {len(seasons)}')
    for s in sorted(seasons, key=lambda x: x.get('year', 0), reverse=True)[:5]:
        print(f'    {s.get("year")} (id={s.get("id")}, name={s.get("name")})')

# 3. Get World Cup 2026 season matches
print("\n=== World Cup 2026 Matches ===")
# First, find season ID for 2026 WC
data = get('/unique-tournament/7', 'WC seasons')
if data:
    for s in data.get('seasons', []):
        if s.get('year') == 2026:
            sid = s.get('id')
            print(f'WC 2026 season id: {sid}')
            # Get events for this season
            data2 = get(f'/unique-tournament/7/season/{sid}/events/last/0', 'WC 2026 events')
            if data2:
                for e in data2.get('events', []):
                    ht = e.get('homeTeam', {}).get('name', '?')
                    at = e.get('awayTeam', {}).get('name', '?')
                    status = e.get('status', {}).get('type', '?')
                    start = e.get('startTimestamp', 0)
                    dt = datetime.fromtimestamp(start) if start else '?'
                    print(f'  {ht} vs {at} [{status}] @ {dt}')
                    if status == 'notstarted':
                        hs = e.get('homeScore', {}).get('display', 0)
                        as_ = e.get('awayScore', {}).get('display', 0)
                        print(f'    Score: {hs}-{as_}')
            break

# 4. Get upcoming matches for a specific date
print("\n=== Matches by Date ===")
from datetime import date, timedelta
today = date.today()
for i in range(7):
    d = today + timedelta(days=i)
    ds = d.strftime('%Y-%m-%d')
    data = get(f'/sport/football/scheduled-events/{ds}', f'Scheduled {ds}')
    if data and data.get('events'):
        print(f'  {ds}: {len(data["events"])} matches')
        for e in data['events'][:3]:
            ht = e.get('homeTeam', {}).get('name', '?')
            at = e.get('awayTeam', {}).get('name', '?')
            print(f'    {ht} vs {at}')

# 5. Test getting H2H
print("\n=== H2H Test ===")
data = get('/team/2817/events/last/5', 'Barca last 5')
if data and data.get('events'):
    eid = data['events'][0].get('id')
    if eid:
        data2 = get(f'/event/{eid}/h2h', f'H2H for {eid}')
        if data2:
            h2h = data2.get('h2h', {})
            print(f'  Home wins: {h2h.get("homeWins")}')
            print(f'  Away wins: {h2h.get("awayWins")}')
            print(f'  Draws: {h2h.get("draws")}')

print("\nDone!")
