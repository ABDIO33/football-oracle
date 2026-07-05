"""Check tournament response structure"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

# Get raw response for Premier League (tournament 17)
data = _get('/unique-tournament/17', cache_minutes=0)
if data:
    print('Keys in response:', list(data.keys()))
    print()
    
    # Check if seasons exists
    if 'seasons' in data:
        print(f'Seasons type: {type(data["seasons"])}')
        print(f'Seasons count: {len(data["seasons"])}')
        if data['seasons']:
            print(f'First season sample: {json.dumps(data["seasons"][0], indent=2)[:500]}')
    
    # Check uniqueTournament
    ut = data.get('uniqueTournament', {})
    print(f'\nuniqueTournament keys: {list(ut.keys())[:15]}')
    print(f'Name: {ut.get("name")}')
    print(f'Has category: {"category" in ut}')
    
    # Try getting seasons differently
    print(f'\nTrying category endpoint...')
    data2 = _get('/category/1', cache_minutes=0)
    if data2:
        print(f'Keys: {list(data2.keys())[:10]}')
        cats = data2.get('categories', [])
        print(f'Categories: {len(cats)}')
        if cats:
            print(f'Sample: {json.dumps(cats[0], indent=2)[:500]}')

print('\nDone')
