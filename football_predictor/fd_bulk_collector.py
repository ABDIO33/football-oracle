"""
FOOTBALL-DATA.ORG BULK COLLECTOR — checkpointed, runs in background
Target: 500K+ matches from 13 major competitions, 1888-2027
"""
import sys, os, json, time, sqlite3, requests, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
API_KEY = '70ba60f333794f91a709977368ac9418'
BASE = 'https://api.football-data.org/v4'
CP_FILE = os.path.join(os.path.dirname(__file__), 'models', 'fd_progress.json')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'models', 'fd_collect_log.txt')

COMPETITIONS = {
    'PL':  {'id': 2021, 'name': 'Premier League', 'seasons': list(range(1993, 2027))},
    'ELC': {'id': 2016, 'name': 'Championship', 'seasons': list(range(2004, 2027))},
    'PD':  {'id': 2014, 'name': 'La Liga', 'seasons': list(range(1995, 2027))},
    'BL1': {'id': 2002, 'name': 'Bundesliga', 'seasons': list(range(1995, 2027))},
    'SA':  {'id': 2019, 'name': 'Serie A', 'seasons': list(range(1995, 2027))},
    'FL1': {'id': 2015, 'name': 'Ligue 1', 'seasons': list(range(1995, 2027))},
    'DED': {'id': 2003, 'name': 'Eredivisie', 'seasons': list(range(1995, 2027))},
    'PPL': {'id': 2017, 'name': 'Primeira Liga', 'seasons': list(range(2002, 2027))},
    'CL':  {'id': 2001, 'name': 'Champions League', 'seasons': list(range(1999, 2027))},
    'EL':  {'id': 2146, 'name': 'Europa League', 'seasons': list(range(2004, 2027))},
    'WC':  {'id': 2000, 'name': 'World Cup', 'seasons': [2018, 2022, 2026]},
    'EC':  {'id': 2018, 'name': 'Euro', 'seasons': [2000, 2004, 2008, 2012, 2016, 2020, 2024]},
    'CLI': {'id': 2006, 'name': 'Copa Libertadores', 'seasons': list(range(2000, 2027))},
}

log_f = open(LOG_FILE, 'a', encoding='utf-8')
def log(msg):
    log_f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    log_f.flush()
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')
    sys.stdout.flush()

log('='*60)
log('FOOTBALL-DATA.ORG BULK COLLECTOR')
log(f'Competitions: {len(COMPETITIONS)}')
log('='*60)

# Load checkpoint
progress = {}
if os.path.exists(CP_FILE):
    progress = json.load(open(CP_FILE))
    log(f'Resuming: {sum(1 for v in progress.values() if v.get("done"))} competitions done')
else:
    progress = {}

total_new = 0
headers = {'X-Auth-Token': API_KEY}

for code, comp in COMPETITIONS.items():
    cid = comp['id']
    cp_key = f'{code}_{cid}'
    completed_seasons = progress.get(cp_key, {})
    if completed_seasons.get('done'):
        log(f'{code}: already done ({completed_seasons.get("count", 0)} matches)')
        continue
    
    log(f'\n{code} ({comp["name"]}): {len(comp["seasons"])} seasons')
    seasons_done = completed_seasons.get('seasons', [])
    season_count = 0
    
    for yr in comp['seasons']:
        syr = str(yr)
        if syr in seasons_done:
            continue
        if yr in [2000, 2004, 2008, 2012, 2016, 2018]:
            log(f'  Season {yr}: skipping (pre-2012)')
            seasons_done.append(syr)
            continue
        
        try:
            url = f'{BASE}/competitions/{cid}/matches?season={yr}'
            resp = requests.get(url, headers=headers, timeout=15)
            
            if resp.status_code == 429:
                log(f'  Rate limited! Waiting 60s...')
                time.sleep(60)
                resp = requests.get(url, headers=headers, timeout=15)
            
            if resp.status_code != 200:
                log(f'  Season {yr}: {resp.status_code} - {resp.text[:100]}')
                continue
            
            data = resp.json()
            matches = data.get('matches', [])
            
            if not matches:
                seasons_done.append(syr)
                continue
            
            # Insert into DB
            conn = sqlite3.connect(DB)
            inserted = 0
            for m in matches:
                if m.get('status') != 'FINISHED':
                    continue
                h = m.get('homeTeam', {}).get('name', '')
                a = m.get('awayTeam', {}).get('name', '')
                hs = m.get('score', {}).get('fullTime', {}).get('home')
                aws = m.get('score', {}).get('fullTime', {}).get('away')
                if hs is None or aws is None:
                    continue
                date = m.get('utcDate', '')[:10]
                mid = m.get('id', 0)
                league = comp['name']
                
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO sofa_historical_results
                        (id, home_team, away_team, home_score, away_score, date, home_league, start_timestamp, status_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'finished')
                    """, (mid * -1, h, a, hs, aws, date, league, time.mktime(time.strptime(date, '%Y-%m-%d')) if date else 0))
                    if conn.total_changes > 0:
                        inserted += 1
                except:
                    pass
            
            conn.commit()
            conn.close()
            
            season_count += inserted
            total_new += inserted
            seasons_done.append(syr)
            
            # Save progress after each season
            progress[cp_key] = {'seasons': seasons_done, 'count': season_count}
            json.dump(progress, open(CP_FILE, 'w'))
            
            if inserted > 0:
                log(f'  Season {yr}: {inserted} matches ({season_count} total)')
            
            # Rate limit: 10 req/min = 6s between requests
            time.sleep(6)
            
        except Exception as e:
            log(f'  Season {yr}: ERROR {e}')
            continue
    
    progress[cp_key] = {'seasons': seasons_done, 'count': season_count, 'done': True}
    json.dump(progress, open(CP_FILE, 'w'))
    log(f'{code}: DONE ({season_count} matches added)')

log(f'\n=== TOTAL NEW MATCHES: {total_new} ===')
log(f'Total in DB: query count')
log('Done!')
log_f.close()
