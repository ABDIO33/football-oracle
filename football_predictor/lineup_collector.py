"""
Bulk Lineup Collector — Fetch lineups from SofaScore API
Goal: Increase lineup coverage from 8.9% to 50%+

Endpoint: https://www.sofascore.com/api/v1/event/{event_id}/lineups
Uses curl_cffi with chrome124 impersonation (bypasses Cloudflare)
"""
import sys, os, json, time, sqlite3, numpy as np
sys.path.insert(0, os.path.dirname(__file__))

try:
    from curl_cffi import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'curl_cffi'])
    from curl_cffi import requests

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'models', 'lineup_collect_log.txt')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.sofascore.com/',
    'Origin': 'https://www.sofascore.com',
}

def log(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

def get_missing_event_ids(limit=50000):
    """Get event IDs that don't have lineup data yet"""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    cur.execute('''
        SELECT r.id, r.home_team, r.away_team, r.date 
        FROM sofa_historical_results r
        LEFT JOIN sofa_lineups l ON r.id = l.event_id
        WHERE l.event_id IS NULL
          AND r.date >= '2015-01-01'
          AND r.home_score IS NOT NULL
        ORDER BY r.start_timestamp DESC
        LIMIT ?
    ''', (limit,))
    
    results = cur.fetchall()
    conn.close()
    return results

def fetch_lineup(event_id):
    """Fetch lineup for a single event from SofaScore"""
    url = f'https://www.sofascore.com/api/v1/event/{event_id}/lineups'
    
    try:
        resp = requests.get(url, impersonate='chrome124', headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        
        # Parse lineups
        home_formation = None
        away_formation = None
        home_players = []
        away_players = []
        
        if 'home' in data:
            home = data['home']
            home_formation = home.get('formation', None)
            home_players = home.get('players', [])
        
        if 'away' in data:
            away = data['away']
            away_formation = away.get('formation', None)
            away_players = away.get('players', [])
        
        confirmed = 1  # SofaScore lineups are confirmed
        
        return {
            'home_formation': home_formation,
            'away_formation': away_formation,
            'home_players': home_players,
            'away_players': away_players,
            'confirmed': confirmed,
        }
    except Exception as e:
        return None

def store_lineup(event_id, lineup_data):
    """Store lineup in database"""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    home_players_json = json.dumps(lineup_data['home_players'], ensure_ascii=False)
    away_players_json = json.dumps(lineup_data['away_players'], ensure_ascii=False)
    
    cur.execute('''
        INSERT OR IGNORE INTO sofa_lineups 
        (event_id, home_formation, away_formation, home_players_json, away_players_json, confirmed)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        event_id,
        lineup_data['home_formation'],
        lineup_data['away_formation'],
        home_players_json,
        away_players_json,
        lineup_data['confirmed'],
    ))
    
    conn.commit()
    conn.close()

def store_formation_only(event_id, home_formation, away_formation):
    """Store just formations without full lineup (minimal mode)"""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    cur.execute('''
        INSERT OR IGNORE INTO sofa_lineups 
        (event_id, home_formation, away_formation, home_players_json, away_players_json, confirmed)
        VALUES (?, ?, ?, '[]', '[]', 1)
    ''', (event_id, str(home_formation), str(away_formation)))
    
    conn.commit()
    conn.close()

def main():
    log('=' * 60)
    log('LINEUP COLLECTOR v1.0')
    log('=' * 60)
    
    # Check current coverage
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM sofa_historical_results WHERE home_score IS NOT NULL')
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(DISTINCT event_id) FROM sofa_lineups')
    existing = cur.fetchone()[0]
    conn.close()
    
    log(f'Total matches: {total:,}')
    log(f'Existing lineups: {existing:,}')
    log(f'Coverage: {existing/total*100:.1f}%')
    log(f'Need to fetch: {total - existing:,}')
    
    # Get event IDs missing lineups
    matches = get_missing_event_ids(limit=100)  # Start small for testing
    log(f'Fetched {len(matches)} missing event IDs')
    
    if len(matches) == 0:
        log('No missing lineups!')
        return
    
    # Fetch lineups
    success = 0
    failed = 0
    
    for i, (event_id, hteam, ateam, date) in enumerate(matches):
        log(f'[{i+1}/{len(matches)}] {date} {hteam} vs {ateam} (ID: {event_id})')
        
        lineup = fetch_lineup(event_id)
        
        if lineup and lineup['home_formation']:
            store_lineup(event_id, lineup)
            success += 1
            log(f'  ✅ {lineup["home_formation"]} vs {lineup["away_formation"]}')
        elif lineup and not lineup['home_formation']:
            # Try to store minimal data
            store_formation_only(event_id, 'unknown', 'unknown')
            success += 1
            log(f'  ✅ Data available (no formation)')
        else:
            failed += 1
            log(f'  ❌ Failed')
        
        # Rate limiting
        if (i + 1) % 10 == 0:
            time.sleep(1)  # Avoid rate limiting
        else:
            time.sleep(0.2)
    
    log(f'\n=== RESULTS ===')
    log(f'Success: {success}')
    log(f'Failed: {failed}')
    
    # Final coverage
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(DISTINCT event_id) FROM sofa_lineups')
    total_lineups = cur.fetchone()[0]
    conn.close()
    
    log(f'Total lineups: {total_lineups:,}')
    log(f'Coverage: {total_lineups/total*100:.1f}%')

if __name__ == '__main__':
    main()
