"""Store fetched lineups in sofa_lineups DB for model use"""
import sqlite3, os, json
from sofascore_scraper import get_match_lineups

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

# Match IDs for our betting matches
match_ids = {
    15186769: ('France', 'Iraq'),
    15186770: ('Norway', 'Senegal'),
    15186740: ('Jordan', 'Algeria'),
}

conn = sqlite3.connect(DB)

for mid, (ht, at) in match_ids.items():
    # Check if already in sofa_lineups
    existing = conn.execute(
        'SELECT confirmed FROM sofa_lineups WHERE event_id = ?', (mid,)
    ).fetchone()
    
    if existing:
        print(f'[SKIP] {ht} vs {at} (id={mid}) already in lineups, confirmed={existing[0]}')
        continue
    
    # Fetch lineups
    lu = get_match_lineups(mid)
    if not lu:
        print(f'[FAIL] {ht} vs {at} (id={mid}) no lineups')
        continue
    
    home = lu.get('home', {})
    away = lu.get('away', {})
    hf = home.get('formation', '')
    af = away.get('formation', '')
    hp = home.get('players', [])
    ap = away.get('players', [])
    confirmed = 1 if lu.get('confirmed') else 0
    
    conn.execute('''
        INSERT OR REPLACE INTO sofa_lineups 
        (event_id, home_formation, away_formation, 
         home_players_json, away_players_json, confirmed)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (mid, hf, af, json.dumps(hp), json.dumps(ap), confirmed))
    conn.commit()
    
    h_starters = len([p for p in hp if not p.get('substitute')])
    a_starters = len([p for p in ap if not p.get('substitute')])
    print(f'[OK]   {ht} vs {at} (id={mid}): {hf} vs {af}, {h_starters}/{a_starters} starters, confirmed={confirmed}')

# Also fetch lineups for ALL upcoming matches in next 3 days
print('\n--- Fetching more lineups for upcoming matches ---')
from sofascore_scraper import get_scheduled_events
from datetime import date, timedelta

for i in range(3):
    dt = date.today() + timedelta(days=i)
    ds = dt.strftime('%Y-%m-%d')
    events = get_scheduled_events(ds)
    if not events:
        continue
    
    for e in events:
        mid = e.get('id')
        if not mid:
            continue
        
        existing = conn.execute(
            'SELECT confirmed FROM sofa_lineups WHERE event_id = ?', (mid,)
        ).fetchone()
        if existing:
            continue
        
        ht = e.get('homeTeam', {}).get('name', '?')
        at = e.get('awayTeam', {}).get('name', '?')
        
        lu = get_match_lineups(mid)
        if not lu:
            continue
        
        home = lu.get('home', {})
        away = lu.get('away', {})
        hf = home.get('formation', '')
        af = away.get('formation', '')
        hp = home.get('players', [])
        ap = away.get('players', [])
        confirmed = 1 if lu.get('confirmed') else 0
        
        if not hf and not af:
            continue
        
        conn.execute('''
            INSERT OR REPLACE INTO sofa_lineups 
            (event_id, home_formation, away_formation, 
             home_players_json, away_players_json, confirmed)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (mid, hf, af, json.dumps(hp), json.dumps(ap), confirmed))
        conn.commit()
        
        print(f'  [ADD] {ds}: {ht} vs {at} ({hf} vs {af}, confirmed={confirmed})')

conn.close()
print('\nDone!')
