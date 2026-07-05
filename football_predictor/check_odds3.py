"""Get actual odds data"""
import sqlite3, json

conn = sqlite3.connect('scrape_cache.db')

cur = conn.execute("SELECT home_team, away_team, odds_json FROM odds_upcoming WHERE home_team='France' AND away_team='Iraq'")
r = cur.fetchone()
if r:
    ht, at, ojson = r
    odds = json.loads(ojson)
    for o in odds:
        key = o.get('key')
        outcomes = o.get('outcomes', [])
        print(f'{key}:')
        for oc in outcomes:
            print(f'  {oc.get("name","?")}: {oc.get("price","?")}')

conn.close()
