"""Check odds format for a future match"""
import sqlite3, json
from datetime import datetime

conn = sqlite3.connect('scrape_cache.db')

# Find a future match with odds
cur = conn.execute("""
    SELECT home_team, away_team, odds_json, commence_time FROM odds_upcoming 
    WHERE commence_time > 1782500000 LIMIT 3
""")
for r in cur.fetchall():
    ht, at, ojson, ct = r
    dt = datetime.fromtimestamp(ct)
    odds = json.loads(ojson)
    print(f'{ht} vs {at} ({dt}):')
    for o in odds[:3]:
        key = o.get('key')
        outcomes = o.get('outcomes', [])
        print(f'  {key}:')
        for oc in outcomes:
            print(f'    {oc.get("name","?")}: {oc.get("price","?")}')
    print()

conn.close()
