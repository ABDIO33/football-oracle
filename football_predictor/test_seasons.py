"""Test season events endpoint + discover patterns"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

# Get seasons for Premier League
data = _get('/unique-tournament/17/seasons', cache_minutes=0)
if data:
    seasons = data.get('seasons', [])
    print(f'Premier League: {len(seasons)} total seasons')
    recent = []
    for s in seasons:
        year = s.get('year', '?')
        try:
            year = int(year)
        except:
            continue
        if year >= 2010:
            recent.append((year, s.get('id'), s.get('name')))
    print(f'Recent (2010+): {len(recent)}')
    for y, sid, name in sorted(recent):
        print(f'  {y} (season_id={sid})')

# Test getting events for one season
print('\nFetching PL 2024/25 events...')
data2 = _get('/unique-tournament/17/season/52162/events/last/0', cache_minutes=0)
if data2 and 'events' in data2:
    events = data2['events']
    finished = [e for e in events if e.get('status', {}).get('type') == 'finished']
    print(f'  Total events: {len(events)}, Finished: {len(finished)}')
    if finished:
        first = finished[0]
        print(f'  Sample: {first.get("homeTeam",{}).get("name")} vs {first.get("awayTeam",{}).get("name")}')
        # Check date range
        dates = []
        for e in finished:
            ts = e.get('startTimestamp', 0)
            if ts:
                from datetime import datetime
                dates.append(datetime.fromtimestamp(ts))
        if dates:
            print(f'  Date range: {min(dates).date()} to {max(dates).date()}')
else:
    print(f'  No events or error')
    if data2:
        print(f'  Keys: {list(data2.keys())}')

print('\nDone')
