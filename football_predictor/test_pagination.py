"""Test pagination of season events"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

# Premier League 23/24 season = id 52186
sid = 52186
tid = 17

# Test different limits
for offset in [0, 30, 60, 90]:
    data = _get(f'/unique-tournament/{tid}/season/{sid}/events/last/{offset}', cache_minutes=0)
    if data and 'events' in data:
        events = data['events']
        has_next = data.get('hasNextPage', False)
        finished = len([e for e in events if e.get('status', {}).get('type') == 'finished'])
        print(f'  offset={offset:3d}: {len(events)} events ({finished} finished), hasNextPage={has_next}')
        if events:
            first = events[0]
            last = events[-1]
            print(f'    First: {first.get("homeTeam",{}).get("name")} vs {first.get("awayTeam",{}).get("name")}')
            print(f'    Last:  {last.get("homeTeam",{}).get("name")} vs {last.get("awayTeam",{}).get("name")}')

# Test with limit=50 (try different format)
print('\nTrying different endpoint formats...')
# Try /events with limit parameter
for path in [
    f'/unique-tournament/{tid}/season/{sid}/events?limit=100',
    f'/unique-tournament/{tid}/season/{sid}/events?page=0&size=100',
    f'/unique-tournament/{tid}/season/{sid}/events/0',
]:
    data = _get(path, cache_minutes=0)
    if data:
        print(f'  {path[:60]}: keys={list(data.keys())[:5]}')
        print(f'  events={len(data.get("events", []))}')

# Check if hasNextPage works
print('\nVerifying pagination loop...')
all_events = []
offset = 0
while True:
    data = _get(f'/unique-tournament/{tid}/season/{sid}/events/last/{offset}', cache_minutes=0)
    if not data or 'events' not in data:
        break
    events = data['events']
    if not events:
        break
    all_events.extend(events)
    print(f'  offset={offset}: got {len(events)}, total={len(all_events)}, hasNextPage={data.get("hasNextPage")}')
    if not data.get('hasNextPage'):
        break
    offset += 30

print(f'\nTotal events fetched: {len(all_events)}')

print('\nDone')
