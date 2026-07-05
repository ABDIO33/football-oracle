"""
Bulk Lineup Collector Runner
Fetches lineups from SofaScore in batches
"""
import sys, os, time, json, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
from curl_cffi import requests

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'lineup_bulk_log.txt')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://www.sofascore.com',
    'Referer': 'https://www.sofascore.com/',
    'x-requested-with': 'XMLHttpRequest',
}

def log(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(msg)

def get_missing_events(limit=1000, min_year=2024):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(f'''
        SELECT r.id, r.home_team, r.away_team, r.date FROM sofa_historical_results r
        LEFT JOIN sofa_lineups l ON r.id = l.event_id
        WHERE l.event_id IS NULL AND r.date >= "{min_year}-01-01"
        AND r.home_score IS NOT NULL
        ORDER BY r.start_timestamp DESC
        LIMIT {limit}
    ''')
    results = cur.fetchall()
    conn.close()
    return results

def fetch_lineup(event_id):
    url = f'https://www.sofascore.com/api/v1/event/{event_id}/lineups'
    try:
        r = requests.get(url, headers=HEADERS, impersonate='chrome124', timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        home = data.get('home', {})
        away = data.get('away', {})
        return {
            'home_formation': home.get('formation'),
            'away_formation': away.get('formation'),
            'home_players': json.dumps(home.get('players', [])),
            'away_players': json.dumps(away.get('players', [])),
            'confirmed': 1,
        }
    except Exception as e:
        return None

def store_lineup(event_id, lineup):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('''INSERT OR IGNORE INTO sofa_lineups 
        (event_id, home_formation, away_formation, home_players_json, away_players_json, confirmed)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (event_id, lineup['home_formation'], lineup['away_formation'],
         lineup['home_players'], lineup['away_players'], lineup['confirmed']))
    conn.commit()
    conn.close()

log('=== LINEUP BULK COLLECTOR ===')

# Get missing events
events = get_missing_events(limit=500, min_year=2024)
log(f'Missing events (2024+): {len(events)}')

if len(events) == 0:
    # Try older years
    events = get_missing_events(limit=500, min_year=2020)
    log(f'Missing events (2020+): {len(events)}')

success = 0
failed = 0
no_formation = 0

for i, (event_id, ht, at, dt) in enumerate(events):
    if i >= 100:  # Process 100 per run
        break
    
    lineup = fetch_lineup(event_id)
    
    if lineup and lineup['home_formation']:
        store_lineup(event_id, lineup)
        success += 1
        if (i+1) % 10 == 0:
            print(f'  [{i+1}] OK: {dt} {ht} vs {at} -> {lineup["home_formation"]} vs {lineup["away_formation"]}')
    elif lineup and not lineup['home_formation']:
        # Store anyway
        store_lineup(event_id, lineup)
        no_formation += 1
        print(f'  [{i+1}] NF: {dt} {ht} vs {at} (no formation)')
    else:
        failed += 1
        print(f'  [{i+1}] FAIL: {dt} {ht} vs {at}')
    
    time.sleep(0.5)  # Rate limit

# Summary
total_tried = success + failed + no_formation
log(f'\n=== COLLECTION RESULTS ===')
log(f'Tried: {total_tried}')
log(f'Success: {success}')
log(f'No formation: {no_formation}')
log(f'Failed: {failed}')
log(f'Success rate: {success/total_tried*100:.0f}%')

# Update coverage
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM sofa_historical_results WHERE home_score IS NOT NULL')
total_m = cur.fetchone()[0]
cur.execute('SELECT COUNT(DISTINCT event_id) FROM sofa_lineups')
total_l = cur.fetchone()[0]
conn.close()
log(f'Total coverage: {total_l}/{total_m} = {total_l/total_m*100:.1f}%')
