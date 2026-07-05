"""Quick survey: discover seasons for top tournaments"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

# Top tournament IDs from our data
top_tids = [17, 8, 23, 34, 35, 16, 7, 1, 24, 25, 18, 155, 242, 402, 54, 325, 390, 196, 53, 98, 491, 131]

print("Tournament Season Survey")
print("========================")
for tid in top_tids:
    data = _get(f'/unique-tournament/{tid}', cache_minutes=60)
    if data:
        t = data.get('uniqueTournament', {})
        name = t.get('name', '?')
        seasons = data.get('seasons', [])
        recent = [s for s in seasons if s.get('year', 0) >= 2010]
        print(f'T{tid:4d} {name:30s} | {len(seasons)} total seasons | {len(recent)} >= 2010')
        for s in recent[:3]:
            print(f'          year={s.get("year")} id={s.get("id")} name={s.get("name")}')
    time.sleep(0.35)

print("\nDone")
