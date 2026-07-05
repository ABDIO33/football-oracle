"""Debug season data structure"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

# Get raw seasons for PL
data = _get('/unique-tournament/17/seasons', cache_minutes=0)
if data:
    seasons = data.get('seasons', [])
    print(f'Total seasons: {len(seasons)}')
    for s in seasons[:10]:
        print(f'  Raw: {json.dumps(s)[:200]}')
    # Find latest season
    latest = seasons[-1] if seasons else None
    if latest:
        sid = latest.get('id')
        year = latest.get('year')
        name = latest.get('name')
        print(f'\nLatest season: id={sid} year={year} name={name}')
        
        # Try getting events for it
        data2 = _get(f'/unique-tournament/17/season/{sid}/events/last/0', cache_minutes=0)
        if data2:
            print(f'Events response keys: {list(data2.keys())}')
            if 'events' in data2:
                events = data2['events']
                print(f'Events count: {len(events)}')
                for e in events[:3]:
                    ht = e.get('homeTeam', {}).get('name', '?')
                    at = e.get('awayTeam', {}).get('name', '?')
                    status = e.get('status', {}).get('type', '?')
                    print(f'  {ht} vs {at} [{status}]')
            else:
                print(f'Response: {json.dumps(data2)[:500]}')
        else:
            print('No events data')

print('\nDone')
