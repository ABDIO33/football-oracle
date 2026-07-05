"""Debug odds structure"""
import sqlite3, json

conn = sqlite3.connect('scrape_cache.db')

targets = ['France', 'Iraq', 'Norway', 'Senegal', 'Jordan', 'Algeria']

cur = conn.execute('SELECT home_team, away_team, odds_json, league FROM odds_upcoming')
for r in cur.fetchall():
    ht, at, ojson, league = r
    if any(t in ht or t in at for t in targets):
        odds = json.loads(ojson)
        print(f'{ht} vs {at} ({league}):')
        print(f'  Sources: {[o.get("key") for o in odds]}')
        for o in odds:
            key = o.get('key')
            outcomes = o.get('outcomes', [])
            if key == 'pinnacle':
                for oc in outcomes:
                    print(f'    {oc.get("name","?")}: {oc.get("price","?")}')
        print()

conn.close()
