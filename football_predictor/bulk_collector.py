"""
Phase 1-C: FULL BULK COLLECTOR — fetch all tournament seasons from SofaScore
Paginates through all events for every season of every football tournament
Target: 500K-1M total matches
"""
import sys, os, json, time, sqlite3
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
MIN_YEAR = 2010

def get_all_tournament_ids():
    """Get all tournament IDs from existing data + scan for more"""
    conn = sqlite3.connect(DB)
    cur = conn.execute('SELECT DISTINCT unique_tournament_id FROM sofa_historical_results WHERE unique_tournament_id IS NOT NULL')
    tids = set(r[0] for r in cur.fetchall())
    conn.close()
    print(f'Existing tournaments in DB: {len(tids)}')
    return tids

def get_seasons(tid):
    """Get all seasons for a tournament"""
    data = _get(f'/unique-tournament/{tid}/seasons', cache_minutes=1440)
    if not data:
        return []
    seasons = data.get('seasons', [])
    result = []
    for s in seasons:
        raw = s.get('year', '')
        name = s.get('name', '')
        sid = s.get('id')
        # Parse year from format like "23/24" or "2024" or "24/25"
        year_num = 0
        if '/' in str(raw):
            try:
                # Take first part: "23/24" -> 23 -> 2023
                yr = int(str(raw).split('/')[0])
                year_num = 2000 + yr if yr < 100 else yr
            except:
                continue
        elif isinstance(raw, (int, float)):
            year_num = int(raw)
        else:
            try:
                year_num = int(str(raw)[:4])
            except:
                continue
        
        if year_num >= MIN_YEAR:
            result.append({'year': year_num, 'id': sid, 'name': name})
    
    return result

def fetch_season_events(tid, sid, year):
    """Fetch ALL events for a tournament season using pagination"""
    all_events = []
    offset = 0
    empty_count = 0
    
    while True:
        data = _get(f'/unique-tournament/{tid}/season/{sid}/events/last/{offset}', cache_minutes=60)
        if not data:
            empty_count += 1
            if empty_count >= 2:
                break
            time.sleep(1)
            continue
        
        events = data.get('events', [])
        if not events:
            break
        
        # Filter only finished matches
        for e in events:
            if e.get('status', {}).get('type') == 'finished':
                all_events.append(e)
        
        if not data.get('hasNextPage'):
            break
        
        offset += 30
        empty_count = 0
        time.sleep(0.35)
    
    return all_events

def store_events(conn, events, tid, sid, year):
    """Store events in DB"""
    stored = 0
    batch = []
    
    for e in events:
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
        
        if len(batch) >= 500:
            try:
                conn.executemany('''
                    INSERT OR IGNORE INTO sofa_historical_results
                    (id, home_team, away_team, home_score, away_score,
                     date, tournament, unique_tournament_id, season_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch)
                conn.commit()
                stored += len(batch)
            except Exception as ex:
                conn.rollback()
                print(f'      DB error: {ex}')
            batch = []
    
    if batch:
        try:
            conn.executemany('''
                INSERT OR IGNORE INTO sofa_historical_results
                (id, home_team, away_team, home_score, away_score,
                 date, tournament, unique_tournament_id, season_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch)
            conn.commit()
            stored += len(batch)
        except Exception as ex:
            conn.rollback()
            print(f'      DB error: {ex}')
    
    return stored

def main():
    conn = sqlite3.connect(DB)
    tids = get_all_tournament_ids()
    
    start_count = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
    print(f'Starting matches: {start_count}')
    
    total_new = 0
    total_skipped = 0
    
    for tid in sorted(tids):
        # Get seasons
        seasons = get_seasons(tid)
        if not seasons:
            total_skipped += 1
            continue
        
        tournament_name = '?'
        data = _get(f'/unique-tournament/{tid}', cache_minutes=1440)
        if data:
            tournament_name = data.get('uniqueTournament', {}).get('name', '?')
        
        print(f'\n[T{tid}] {tournament_name}: {len(seasons)} seasons')
        
        for s in seasons:
            sid = s['id']
            year = s['year']
            
            # Check if we already have this season
            existing = conn.execute('''
                SELECT COUNT(*) FROM sofa_historical_results 
                WHERE unique_tournament_id = ? AND season_id = ?
            ''', (tid, sid)).fetchone()[0]
            
            if existing > 50:  # Skip if we already have substantial data
                print(f'  Season {year}: SKIP (already {existing} matches)')
                continue
            
            # Fetch events
            events = fetch_season_events(tid, sid, year)
            if not events:
                print(f'  Season {year}: 0 finished matches')
                continue
            
            # Store
            stored = store_events(conn, events, tid, sid, year)
            total_new += stored
            
            if stored > 0:
                print(f'  Season {year}: {len(events)} fetched, {stored} new (total new: {total_new})')
            
            time.sleep(0.35)
    
    final_count = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
    print(f'\n{"="*60}')
    print(f'BULK COLLECTION COMPLETE')
    print(f'  Before: {start_count}')
    print(f'  New:    {total_new}')
    print(f'  Total:  {final_count}')
    print(f'  Target: 500K-1M')
    print(f'  Progress: {final_count/1000000:.1%} of 1M')
    print(f'{"="*60}')
    
    conn.close()

if __name__ == '__main__':
    main()
