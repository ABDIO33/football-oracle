"""Test max events per team"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get
import time

# Test team events with different limits
team_id = 2817  # Barcelona
for n in [30, 50, 100, 200, 300, 500]:
    data = _get(f'/team/{team_id}/events/last/{n}', cache_minutes=0)
    if data and 'events' in data:
        finished = len([e for e in data['events'] if e.get('status', {}).get('type') == 'finished'])
        print(f'  limit={n:4d}: {len(data["events"])} total, {finished} finished')
    time.sleep(0.35)
