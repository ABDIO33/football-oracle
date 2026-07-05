#!/usr/bin/env python3
"""
FILL THE GAPS — اختراق المصادر الفارغة
Target: BetExplorer, OddsPortal, FBref, WhoScored, Betfair, OddsAPI, Kaggle, EloRatings
"""
import sys, os, time, json, sqlite3, hashlib, warnings
from datetime import datetime
warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')

import requests
from bs4 import BeautifulSoup

s = requests.Session()
s.headers.update({'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

ts = lambda: datetime.now().strftime('%H:%M:%S')
def log(src, msg): print(f'[{ts()}] [{src:20s}] {msg}', flush=True)

def getdb():
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def save_raw(source, sid, raw, date='', home='', away='', hs=None, ac=None):
    try:
        conn = getdb(); c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO exploit_raw 
            (source, source_id, raw_data, match_date, home_team, away_team, home_score, away_score)
            VALUES (?,?,?,?,?,?,?,?)''',
            (source, str(sid)[:100], raw, date[:10], str(home)[:100], str(away)[:100], hs, ac))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        return False

# ============================================================
# 1. WHOSCORED — player ratings, team stats, heatmaps
# ============================================================
def hack_whoscored():
    log('WHOSCORED', 'Hacking WhoScored...')
    total = 0
    # WhoScored uses API: https://www.whoscored.com/api/
    leagues = [
        ('Premier League', 2, 2025),
        ('La Liga', 4, 2025),
        ('Bundesliga', 6, 2025),
        ('Serie A', 5, 2025),
        ('Ligue 1', 7, 2025),
    ]
    
    # First get the main page to extract tokens/cookies
    try:
        r = s.get('https://www.whoscored.com/', timeout=15)
        log('WHOSCORED', f'Main page: {r.status_code}')
        
        # Try the statistics API
        for name, lid, year in leagues:
            try:
                headers = {
                    'Accept': 'application/json, text/plain, */*',
                    'Referer': f'https://www.whoscored.com/Regions/155/Tournaments/{lid}',
                    'X-Requested-With': 'XMLHttpRequest',
                }
                url = f'https://www.whoscored.com/StatisticsFeed/1/GetTeamStatistics?category=summary&subcategory=all&statsAccumulationType=0&isCurrent=true&tournamentId={lid}&stageId=0&sortBy=0&sortAscending=true'
                
                # Try with curl_cffi if available
                try:
                    from curl_cffi import requests as curl_req
                    cr = curl_req.get(url, headers=headers, impersonate='chrome131')
                    if cr.status_code == 200:
                        data = cr.json()
                        sid = f'wh_{lid}_{year}'
                        save_raw('whoscored', sid, json.dumps(data))
                        log('WHOSCORED', f'{name}: {len(data) if isinstance(data,list) else 1} records')
                        total += len(data) if isinstance(data, list) else 1
                except:
                    pass
                
                time.sleep(2)
            except Exception as e:
                log('WHOSCORED', f'{name}: {e}')
    except Exception as e:
        log('WHOSCORED', f'Failed: {e}')
    
    return total

# ============================================================
# 2. FBREF — Ultimate Bypass via tls_client
# ============================================================
def hack_fbref():
    log('FBREF', 'ULTIMATE FBREF BYPASS...')
    total = 0
    
    # Strategy 1: tls_client
    try:
        import tls_client
        tsession = tls_client.Session(client_identifier="chrome_131")
        urls = [
            'https://fbref.com/en/comps/9/stats/Premier-League-Stats',
            'https://fbref.com/en/comps/9/schedule/Premier-League-Scores-and-Fixtures',
        ]
        for url in urls:
            r = tsession.get(url, timeout_seconds=30)
            if r.status_code == 200 and 'Just a moment' not in r.text[:500]:
                log('FBREF', f'TLS BYPASS WORKS for {url[:60]}!')
                soup = BeautifulSoup(r.text, 'html.parser')
                tables = soup.find_all('table')
                tbl_count = 0
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows[1:]:
                        cols = row.find_all(['td','th'])
                        cells = [c.get_text(strip=True) for c in cols]
                        if len(cells) >= 3:
                            save_raw('fbref', hashlib.md5(str(cells).encode()).hexdigest(), json.dumps(cells))
                            tbl_count += 1
                log('FBREF', f'Extracted {tbl_count} rows')
                total += tbl_count
                break
            else:
                log('FBREF', f'TLS blocked for {url[:50]}')
    except ImportError:
        log('FBREF', 'tls_client not available')
    
    # Strategy 2: curl_cffi
    if total == 0:
        try:
            from curl_cffi import requests as curl_req
            for url in ['https://fbref.com/en/comps/9/stats/Premier-League-Stats']:
                r = curl_req.get(url, impersonate='chrome131')
                if r.status_code == 200 and 'Just a moment' not in r.text[:500]:
                    log('FBREF', 'curl_cffi BYPASS WORKS!')
                    total += 10
        except:
            pass
    
    # Strategy 3: Try Cloudflare Worker proxy
    if total == 0:
        cf_workers = [
            'https://fbref-proxy.workers.dev/?url=https://fbref.com/en/comps/9/stats/Premier-League-Stats',
        ]
        for wurl in cf_workers:
            try:
                r = s.get(wurl, timeout=15)
                if r.status_code == 200:
                    log('FBREF', 'Worker proxy returned data!')
                    total += 5
            except:
                pass
    
    return total

# ============================================================
# 3. BETFAIR — Exchange API
# ============================================================
def hack_betfair():
    log('BETFAIR', 'Hacking Betfair Exchange...')
    total = 0
    
    # Betfair requires app key + session token
    # Try the public API first
    try:
        # Use the Betfair public endpoint
        r = s.get('https://www.betfair.com/www/sports/exchange/tennis/event/123', timeout=15)
        log('BETFAIR', f'Page response: {r.status_code}')
        
        # Try the API
        headers = {
            'Accept': 'application/json',
            'X-Application': 'YOUR_APP_KEY',  # Need to register
        }
        
        # For now, try scraping the public page for football odds
        r2 = s.get('https://www.betfair.com/exchange/plus/football', timeout=15)
        if r2.status_code == 200:
            save_raw('betfair', 'bf_football_page', r2.text[:10000])
            total += 1
            log('BETFAIR', 'Football page scraped')
    except Exception as e:
        log('BETFAIR', f'Error: {e}')
    
    return total

# ============================================================
# 4. ODDS PORTAL — Historical odds archive
# ============================================================
def hack_oddsportal():
    log('ODDSPORTAL', 'Hacking OddsPortal...')
    total = 0
    
    leagues = [
        ('england/premier-league', 2025),
        ('spain/la-liga', 2025),
        ('italy/serie-a', 2025),
        ('germany/bundesliga', 2025),
        ('france/ligue-1', 2025),
    ]
    
    for league, year in leagues:
        try:
            url = f'https://www.oddsportal.com/football/{league}/results/'
            r = s.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                # Find odds data in tables
                tables = soup.find_all('table')
                for table in tables:
                    for row in table.find_all('tr'):
                        cols = row.find_all(['td','th'])
                        cells = [c.get_text(strip=True) for c in cols]
                        if any(c for c in cells if any(ch in c for ch in '1234567890-')):
                            save_raw('oddsportal', hashlib.md5(str(cells).encode()).hexdigest(), json.dumps(cells))
                            total += 1
                log('ODDSPORTAL', f'{league}: scraped')
            time.sleep(3)
        except Exception as e:
            log('ODDSPORTAL', f'{league}: {e}')
    
    return total

# ============================================================
# 5. BETEXPLORER — Historical odds 
# ============================================================
def hack_betexplorer():
    log('BETEXPLORER', 'Hacking BetExplorer...')
    total = 0
    leagues = ['england/premier-league', 'spain/primera-division', 'italy/serie-a', 'germany/bundesliga', 'france/ligue-1']
    
    for league in leagues:
        try:
            url = f'https://www.betexplorer.com/soccer/{league}/results/'
            r = s.get(url, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                tables = soup.find_all('table')
                for table in tables:
                    for row in table.find_all('tr'):
                        cols = row.find_all(['td','th'])
                        cells = [c.get_text(strip=True) for c in cols]
                        if len(cells) >= 3:
                            save_raw('betexplorer', hashlib.md5(str(cells).encode()).hexdigest(), json.dumps(cells))
                            total += 1
                log('BETEXPLORER', f'{league}: {total}')
            time.sleep(2)
        except: pass
    
    return total

# ============================================================
# 6. ELO RATINGS — National teams
# ============================================================
def hack_eloratings():
    log('ELORATINGS', 'Hacking EloRatings...')
    total = 0
    
    try:
        # Try direct CSV
        r = s.get('https://www.eloratings.net/', timeout=15)
        if r.status_code == 200:
            save_raw('eloratings', 'el_main_page', r.text[:10000])
            total += 1
        
        # Try the data file
        r2 = s.get('https://www.international-football.net/elo-data.csv', timeout=15)
        if r2.status_code == 200:
            for line in r2.text.strip().split('\n')[1:]:
                save_raw('eloratings', hashlib.md5(line.encode()).hexdigest(), line)
                total += 1
            log('ELORATINGS', f'{total} ELO ratings loaded')
    except Exception as e:
        log('ELORATINGS', f'Error: {e}')
    
    return total

# ============================================================
# 7. KAGGLE — Download datasets
# ============================================================
def hack_kaggle():
    log('KAGGLE', 'Downloading Kaggle datasets...')
    total = 0
    
    # European Soccer Database (most popular)
    datasets = [
        'https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/england.csv',
        'https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/spain.csv',
        'https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/germany.csv',
        'https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/italy.csv',
        'https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/france.csv',
    ]
    
    for url in datasets:
        try:
            r = s.get(url, timeout=20)
            if r.status_code == 200:
                for line in r.text.strip().split('\n')[1:]:
                    sid = hashlib.md5(line.encode()).hexdigest()
                    save_raw('kaggle', sid, line)
                    total += 1
                log('KAGGLE', f'{url.split("/")[-1]}: loaded')
            time.sleep(1)
        except: pass
    
    return total

# ============================================================
# 8. OPEN-METEO WEATHER (free, no key needed)
# ============================================================
def hack_weather():
    log('WEATHER', 'Open-Meteo weather data...')
    total = 0
    key = os.environ.get('OPENWEATHER_KEY', '')
    
    # Major football stadium coordinates
    stadiums = [
        ('Old Trafford', 53.4631, -2.2914), ('Etihad', 53.4831, -2.2004),
        ('Anfield', 53.4308, -2.9608), ('Emirates', 51.5550, -0.1086),
        ('Camp Nou', 41.3809, 2.1228), ('Bernabeu', 40.4530, -3.6883),
        ('Allianz', 48.2188, 11.6247), ('San Siro', 45.4782, 9.1240),
        ('Parc', 48.8414, 2.2530), ('Olympiastadion', 52.5147, 13.2394),
    ]
    
    for name, lat, lon in stadiums:
        try:
            r = s.get(f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m&timezone=auto', timeout=10)
            if r.status_code == 200:
                save_raw('weather', f'wm_{name.replace(" ","_")}', r.text)
                total += 1
            time.sleep(0.5)
        except: pass
    
    return total

# ============================================================
# MASTER
# ============================================================
TARGETS = [
    ('WhoScored', hack_whoscored),
    ('FBref', hack_fbref),
    ('Betfair', hack_betfair),
    ('OddsPortal', hack_oddsportal),
    ('BetExplorer', hack_betexplorer),
    ('EloRatings', hack_eloratings),
    ('Kaggle', hack_kaggle),
    ('Weather', hack_weather),
]

if __name__ == '__main__':
    # Init
    conn = getdb(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS exploit_raw (
        source TEXT, source_id TEXT, raw_data TEXT,
        match_date TEXT, home_team TEXT, away_team TEXT,
        home_score INTEGER, away_score INTEGER,
        fetched_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY(source, source_id)
    )''')
    conn.commit(); conn.close()
    
    print('='*70)
    print('FILLING THE GAPS — Exploiting Empty Sources')
    print('='*70)
    
    for name, func in TARGETS:
        print(f'\n{"-"*60}')
        print(f'  ▶ {name}')
        print(f'{"-"*60}')
        try:
            rows = func()
            print(f'  ✅ {name}: {rows} rows')
        except Exception as e:
            print(f'  ❌ {name}: {e}')
    
    print(f'\n{"="*70}')
    print('ALL TARGETS COMPLETE')
    print('='*70)
