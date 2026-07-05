"""Check Pinnacle odds for our betting matches"""
import sqlite3, json

conn = sqlite3.connect('scrape_cache.db')

targets = [
    ('France', 'Iraq'), ('Norway', 'Senegal'),
    ('Jordan', 'Algeria'), ('Senegal', 'Norway'),
    ('Algeria', 'Jordan'), ('Iraq', 'France')
]

cur = conn.execute('SELECT home_team, away_team, odds_json, commence_time FROM odds_upcoming')
for r in cur.fetchall():
    ht, at, ojson, ct = r
    for t_h, t_a in targets:
        if (ht.lower() == t_h.lower() and at.lower() == t_a.lower()) or \
           (ht.lower() == t_a.lower() and at.lower() == t_h.lower()):
            odds = json.loads(ojson)
            pinnacle = [o for o in odds if 'pinnacle' in o.get('key', '').lower()]
            if pinnacle:
                p = pinnacle[0]
                outcomes = p.get('outcomes', [])
                print(f'{ht} vs {at} [Pinnacle]:')
                for o in outcomes:
                    print(f'  {o.get("name","?")}: {o.get("price","?")}')
            else:
                print(f'{ht} vs {at}: NO PINNACLE ODDS')
                for o in odds[:2]:
                    print(f'  {o.get("key")}: {[x.get("price") for x in o.get("outcomes",[])]}')
            print()
            break

conn.close()
