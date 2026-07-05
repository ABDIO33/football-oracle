"""Extract actual Pinnacle odds from proper JSON path"""
import sqlite3, json

conn = sqlite3.connect('scrape_cache.db')

targets = [
    ('France', 'Iraq'), ('Norway', 'Senegal'),
    ('Jordan', 'Algeria')
]

cur = conn.execute('SELECT home_team, away_team, odds_json FROM odds_upcoming')
for r in cur.fetchall():
    ht, at, ojson = r
    for t_h, t_a in targets:
        if ht.lower() == t_h.lower() and at.lower() == t_a.lower():
            odds = json.loads(ojson)
            # Find pinnacle
            pinnacle = None
            for o in odds:
                if 'pinnacle' in o.get('key', '').lower():
                    pinnacle = o
                    break
            if pinnacle:
                markets = pinnacle.get('markets', [])
                if markets:
                    outcomes = markets[0].get('outcomes', [])
                    odds_h = odds_d = odds_a = None
                    for oc in outcomes:
                        name = oc.get('name', '')
                        price = oc.get('price', 0)
                        if name == ht or name == 'Home':
                            odds_h = price
                        elif name == at or name == 'Away':
                            odds_a = price
                        elif name == 'Draw':
                            odds_d = price
                    print(f'{ht} vs {at} [Pinnacle]:')
                    print(f'  {ht}: {odds_h}')
                    print(f'  Draw: {odds_d}')
                    print(f'  {at}: {odds_a}')
                    
                    # Compare with model
                    from direct_predictor import predict_match
                    pred = predict_match(ht, at, '2026-06-22')
                    if pred:
                        probs = pred.get('probs_1x2', {})
                        print(f'  Model 1X2: {probs.get("home",0):.1%} / {probs.get("draw",0):.1%} / {probs.get("away",0):.1%}')
                        if odds_h and probs.get('home'):
                            ev_h = (probs['home'] * odds_h - 1) * 100
                            print(f'  EV Home: {ev_h:.1f}%')
                        if odds_d and probs.get('draw'):
                            ev_d = (probs['draw'] * odds_d - 1) * 100
                            print(f'  EV Draw: {ev_d:.1f}%')
                        if odds_a and probs.get('away'):
                            ev_a = (probs['away'] * odds_a - 1) * 100
                            print(f'  EV Away: {ev_a:.1f}%')
                    print()
            break

conn.close()
