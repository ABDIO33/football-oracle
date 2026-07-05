"""Compare tournament structures"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

# Compare PL (17) vs WC (16)
for tid, label in [(17, 'Premier League'), (16, 'FIFA World Cup'), (7, 'UCL')]:
    data = _get(f'/unique-tournament/{tid}', cache_minutes=0)
    if data:
        ut = data.get('uniqueTournament', {})
        print(f'\n{label} (T{tid}):')
        print(f'  Keys: {list(data.keys())}')
        print(f'  Has rounds: {ut.get("hasRounds")}')
        print(f'  Has groups: {ut.get("hasGroups")}')
        print(f'  Category: {ut.get("category", {}).get("name")}')
        
        # The seasons might be accessed differently
        # Try category/uniqueTournament endpoint
        data2 = _get(f'/category/{ut.get("category", {}).get("id")}/unique-tournament/{tid}', cache_minutes=0)
        if data2:
            print(f'  Cat endpoint keys: {list(data2.keys())}')
        
        # Try standings endpoint to find seasons
        # seasons might be at /unique-tournament/{id}/seasons
        data3 = _get(f'/unique-tournament/{tid}/seasons', cache_minutes=0)
        if data3:
            print(f'  Seasons endpoint keys: {list(data3.keys())[:10]}')
            seasons = data3.get('seasons', [])
            print(f'  Seasons count: {len(seasons)}')
            if seasons:
                recent = [s for s in seasons if s.get('year', 0) >= 2010]
                print(f'  Recent seasons: {len(recent)}')
                for s in recent[:3]:
                    print(f'    year={s.get("year")} id={s.get("id")} name={s.get("name")}')

print('\nDone')
