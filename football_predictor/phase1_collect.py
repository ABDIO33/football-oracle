"""
Phase 1-B: Bulk SofaScore collector — fetch ALL tournament seasons
Target: 500K-1M matches total
Strategy: For each known tournament, get all seasons, fetch ALL matches per season
"""
import sys, os, json, time, sqlite3
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
MIN_YEAR = 2010

def get_tournament_seasons(tid):
    """Get all seasons for a tournament"""
    data = _get(f'/unique-tournament/{tid}', cache_minutes=60)
    if not data:
        return []
    t = data.get('uniqueTournament', {})
    if t.get('sport', {}).get('slug') not in (None, 'football'):
        return []
    seasons = []
    for s in data.get('seasons', []):
        year = s.get('year', 0)
        if year >= MIN_YEAR:
            seasons.append({'year': year, 'id': s.get('id'), 'name': s.get('name', str(year))})
    return seasons

def fetch_season_events(tid, sid, year):
    """Fetch ALL events for a tournament season"""
    all_events = []
    offset = 0
    while True:
        data = _get(f'/unique-tournament/{tid}/season/{sid}/events/last/{offset}', cache_minutes=60)
        if not data or 'events' not in data:
            break
        events = data['events']
        if not events:
            break
        all_events.extend(events)
        if len(events) < 100:
            break
        offset += 100
        time.sleep(0.35)
    return all_events

def main():
    conn = sqlite3.connect(DB)
    
    # Get existing tournament IDs that have data
    cur = conn.execute('SELECT DISTINCT unique_tournament_id FROM sofa_historical_results WHERE unique_tournament_id IS NOT NULL')
    existing_tids = set(r[0] for r in cur.fetchall())
    print(f'Existing tournaments in DB: {len(existing_tids)}')
    
    # Also scan known football tournament ranges
    print('Scanning for additional tournaments (1-300)...')
    for tid in range(1, 301):
        if tid in existing_tids:
            continue
        data = _get(f'/unique-tournament/{tid}', cache_minutes=1440)
        if data:
            t = data.get('uniqueTournament', {})
            sport_slug = (t.get('sport') or {}).get('slug')
            if sport_slug in (None, 'football'):
                has_recent = any(s.get('year', 0) >= MIN_YEAR for s in data.get('seasons', []))
                if has_recent:
                    existing_tids.add(tid)
                    print(f'  Found new tournament [{tid}]: {t.get("name")}')
        if tid % 100 == 0:
            print(f'  Scanned {tid}/300...')
    
    print(f'\nTotal football tournaments: {len(existing_tids)}')
    
    # For each tournament, get seasons and fetch events
    total_new = 0
    total_existing = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
    print(f'Starting matches: {total_existing}')
    
    for tid in sorted(existing_tids):
        seasons = get_tournament_seasons(tid)
        if not seasons:
            continue
        
        for s in seasons:
            year = s['year']
            sid = s['id']
            
            # Check if we already have this tournament+season
            existing_season = conn.execute('''
                SELECT COUNT(*) FROM sofa_historical_results 
                WHERE unique_tournament_id = ? AND season_id = ?
            ''', (tid, sid)).fetchone()[0]
            
            if existing_season > 0:
                continue  # Skip if we already have it
            
            # Fetch events
            events = fetch_season_events(tid, sid, year)
            if not events:
                continue
            
            # Store in DB
            batch = []
            for e in events:
                status = e.get('status', {}).get('type', '')
                if status != 'finished':
                    continue
                    
                home_team = e.get('homeTeam', {}).get('name', '')
                away_team = e.get('awayTeam', {}).get('name', '')
                if not home_team or not away_team:
                    continue
                
                home_score = e.get('homeScore', {}).get('display', 0)
                away_score = e.get('awayScore', {}).get('display', 0)
                start_ts = e.get('startTimestamp', 0)
                date_str = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d') if start_ts else ''
                tournament_name = e.get('tournament', {}).get('name', '')
                
                eid = e.get('id')
                
                batch.append((eid, home_team, away_team, home_score, away_score, 
                             date_str, tournament_name, tid, sid))
                
                if len(batch) >= 200:
                    conn.executemany('''
                        INSERT OR IGNORE INTO sofa_historical_results
                        (id, home_team, away_team, home_score, away_score,
                         date, tournament, unique_tournament_id, season_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', batch)
                    conn.commit()
                    batch = []
            
            if batch:
                conn.executemany('''
                    INSERT OR IGNORE INTO sofa_historical_results
                    (id, home_team, away_team, home_score, away_score,
                     date, tournament, unique_tournament_id, season_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch)
                conn.commit()
            
            total_new += len(events)
            print(f'  [T{tid}] Season {year}: {len(events)} matches (total new: {total_new})')
            
            time.sleep(0.35)  # Rate limit
    
    final_count = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
    print(f'\n=== COLLECTION COMPLETE ===')
    print(f'Before: {total_existing}')
    print(f'Added: {total_new}')
    print(f'Total: {final_count}')
    
    conn.close()

if __name__ == '__main__':
    main()
