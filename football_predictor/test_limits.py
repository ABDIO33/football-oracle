"""Test max events per season call"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

# PL 23/24 = T17 season 52186
tid, sid = 17, 52186

# Test different limits
limits = [30, 50, 100, 150, 200, 300, 500, 1000]
for n in limits:
    data = _get(f'/unique-tournament/{tid}/season/{sid}/events/last/{n}', cache_minutes=0)
    if data and 'events' in data:
        events = data['events']
        finished = len([e for e in events if e.get('status', {}).get('type') == 'finished'])
        print(f'limit={n:4d}: {len(events)} total, {finished} finished, hasNextPage={data.get("hasNextPage")}')
    time.sleep(0.35)

# Also test events/last with large number (200) for a team
print('\nTeam test (Barcelona, T17)...')
team_id = 2817  # Barcelona
for n in [30, 50, 100, 200]:
    data = _get(f'/team/{team_id}/events/last/{n}', cache_minutes=0)
    if data and 'events' in data:
        finished = len([e for e in data['events'] if e.get('status', {}).get('type') == 'finished'])
        print(f'  limit={n:4d}: {len(data["events"])} total, {finished} finished')
    time.sleep(0.35)

print('\nDone')
