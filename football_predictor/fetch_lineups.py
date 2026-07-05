"""Fetch lineups for upcoming matches from SofaScore API"""
import sys, os, json, time
from datetime import date, datetime, timedelta
from sofascore_scraper import search_team, get_scheduled_events, get_match_lineups, get_match_details
from smart_team_mapper import resolve_team_name

NORM_CACHE = {}

def norm(t):
    """Normalize team name for matching"""
    t = t.strip().lower()
    t = t.replace('-', ' ').replace("'", '').replace('.', '')
    for w in ['fc', 'cf', 'ac', 'afc', 'sc', 'as', 'rc', 'cd', 'deportivo',
              'real', 'club', 'atletico', 'athletic', 'sporting', 'sport',
              'fk', 'sk', 'nk', 'hns', 'ks', 'ksv', 'sv', 'vfl', 'tsv',
              '1.', '2.']:
        t = t.replace(f' {w} ', ' ').replace(f' {w}', '').replace(f'{w} ', '')
    return t.strip()

def find_sofascore_id(home_team, away_team, events):
    """Find SofaScore match ID by matching team names"""
    hn = norm(home_team)
    an = norm(away_team)
    
    for e in events:
        ht = e.get('homeTeam', {}).get('name', '')
        at = e.get('awayTeam', {}).get('name', '')
        htn = norm(ht)
        atn = norm(at)
        
        if (hn in htn or htn in hn) and (an in atn or atn in an):
            return e.get('id')
        # Try swap
        if (hn in atn or atn in hn) and (an in htn or htn in an):
            return e.get('id')
    return None

def get_formation_type(formation_str):
    """Convert formation string like 4-2-3-1 to defender count"""
    if not formation_str:
        return 4.0
    try:
        first = int(formation_str.split('-')[0])
        if first in (3, 4, 5):
            return float(first)
    except:
        pass
    return 4.0

def main():
    import sqlite3
    
    db = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
    conn = sqlite3.connect(db)
    
    # Get dates for next 7 days
    today = date.today()
    dates = [today + timedelta(days=i) for i in range(7)]
    
    total_found = 0
    total_with_lineups = 0
    
    for dt in dates:
        ds = dt.strftime('%Y-%m-%d')
        events = get_scheduled_events(ds)
        if not events:
            continue
        
        # For each match in odds_upcoming on this date
        from datetime import datetime as dt2
        day_start = int(dt2(dt.year, dt.month, dt.day).timestamp())
        day_end = day_start + 86400
        
        cur = conn.execute('''
            SELECT event_id, home_team, away_team, commence_time 
            FROM odds_upcoming 
            WHERE commence_time BETWEEN ? AND ?
        ''', (day_start, day_end))
        
        for row in cur.fetchall():
            odds_id, ht, at, ct = row
            ht = resolve_team_name(ht) or ht
            at = resolve_team_name(at) or at
            
            mid = find_sofascore_id(ht, at, events)
            if not mid:
                continue
            
            total_found += 1
            
            # Check if we already have lineups
            existing = conn.execute(
                'SELECT confirmed FROM sofa_lineups WHERE event_id = ?', (mid,)
            ).fetchone()
            
            if existing and existing[0]:
                total_with_lineups += 1
                continue
            
            # Fetch lineups
            lu = get_match_lineups(mid)
            if not lu:
                continue
            
            home = lu.get('home', {})
            away = lu.get('away', {})
            confirmed = 1 if lu.get('confirmed') else 0
            
            home_formation = home.get('formation', '')
            away_formation = away.get('formation', '')
            home_players = home.get('players', [])
            away_players = away.get('players', [])
            
            if not home_formation and not away_formation:
                continue
            
            # Store in sofa_lineups table
            conn.execute('''
                INSERT OR REPLACE INTO sofa_lineups 
                (event_id, home_formation, away_formation, 
                 home_players_json, away_players_json, confirmed)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                mid, home_formation, away_formation,
                json.dumps(home_players), json.dumps(away_players), confirmed
            ))
            conn.commit()
            total_with_lineups += 1
            
            dt_str = datetime.fromtimestamp(ct).strftime('%H:%M')
            print(f'  [{ds} {dt_str}] {ht} vs {at} (id={mid})')
            print(f'    Formations: {home_formation} vs {away_formation}')
            hp = len([p for p in home_players if not p.get('substitute')])
            ap = len([p for p in away_players if not p.get('substitute')])
            print(f'    Starters: {hp} vs {ap} (confirmed={confirmed})')
            
            time.sleep(0.5)  # Rate limit
    
    conn.close()
    print(f'\nSummary: {total_found} matches with SofaScore IDs, '
          f'{total_with_lineups} with lineup data')

if __name__ == '__main__':
    main()
