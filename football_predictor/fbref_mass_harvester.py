#!/usr/bin/env python3
"""
FBref Wayback MASS HARVESTER — يستخرج كل المواسم (2015-2026) عبر Wayback Machine
"""
import sys, os, time, json, sqlite3, warnings
from datetime import datetime
warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')

import requests
from bs4 import BeautifulSoup

SESSION = requests.Session()
SESSION.headers.update({'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
SESSION.timeout = 45

def log(msg): print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def getdb():
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

# Init table
conn = getdb(); c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS source_fbref_killer (
    source_id TEXT PRIMARY KEY, raw_data TEXT,
    match_date TEXT, home_team TEXT, away_team TEXT,
    home_score INTEGER, away_score INTEGER,
    page_type TEXT, fetched_at TEXT DEFAULT (datetime('now'))
)''')
conn.commit(); conn.close()

def save(sid, raw, date='', home='', away='', hs=None, ac=None, ptype=''):
    try:
        conn = getdb(); c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO source_fbref_killer 
            (source_id, raw_data, match_date, home_team, away_team, home_score, away_score, page_type)
            VALUES (?,?,?,?,?,?,?,?)''',
            (str(sid)[:150], raw[:100000], date[:10], str(home)[:100], str(away)[:100], hs, ac, ptype))
        conn.commit(); conn.close()
        return True
    except: return False

def scrape_wb(url, date_str):
    wb_url = f'https://web.archive.org/web/{date_str}/{url}'
    try:
        r = SESSION.get(wb_url, timeout=45)
        if r.status_code == 200 and 'Playback' not in r.text[:200]:
            return r.text
    except: pass
    return None

# FBref comps + multi-season dates
COMPS = {
    9: 'Premier-League',
    12: 'La-Liga',
    20: 'Bundesliga',
    11: 'Serie-A',
    13: 'Ligue-1',
    10: 'Championship',
}

# Multiple dates to try for each season
DATES = [
    '20250601', '20250615',  # 2025-26
    '20250601', '20240601',  # 2024-25
    '20230601', '20220601',  # 2023-24, 2022-23
    '20210601', '20200601',  # 2021-22, 2020-21
    '20190601', '20180601',  # 2019-20, 2018-19
    '20170601', '20160601',  # 2017-18, 2016-17
]

def scrape_schedule(comp_id, league_name, date_str):
    """Get match results from FBref schedule via Wayback"""
    url = f'https://fbref.com/en/comps/{comp_id}/schedule/{league_name}-Scores-and-Fixtures'
    html = scrape_wb(url, date_str)
    if not html: return 0
    
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', class_='scores')
    if not table:
        tables = soup.find_all('table')
        table = tables[0] if tables else None
    if not table: return 0
    
    total = 0
    for row in table.find_all('tr'):
        cols = row.find_all(['td', 'th'])
        if len(cols) < 6: continue
        cells = [c.get_text(strip=True) for c in cols]
        date = cells[0]; home = cells[1]; score = cells[2]; away = cells[3]
        hs = ac = None
        if score and '-' in score:
            try:
                p = score.split('-')
                hs = int(p[0].strip()); ac = int(p[1].strip())
            except: pass
        if not home or not away: continue
        sid = f'fbref_{comp_id}_{date_str}_{date}_{home}_{away}'
        save(sid, json.dumps({'comp':comp_id,'league':league_name,'date':date,'home':home,'away':away,'score':score}), date, home, away, hs, ac, 'schedule')
        total += 1
    return total

def scrape_stats(comp_id, league_name, date_str):
    """Get team stats"""
    url = f'https://fbref.com/en/comps/{comp_id}/stats/{league_name}-Stats'
    html = scrape_wb(url, date_str)
    if not html: return 0
    soup = BeautifulSoup(html, 'html.parser')
    total = 0
    for table in soup.find_all('table', class_='stats_table'):
        for row in table.find_all('tr')[1:]:
            cols = row.find_all(['td','th'])
            cells = [c.get_text(strip=True) for c in cols]
            if len(cells) >= 3:
                sid = f'fbref_stats_{comp_id}_{league_name}_{date_str}_{cells[0]}'
                save(sid, json.dumps({'comp':comp_id,'league':league_name,'row':cells}), ptype='team_stats')
                total += 1
    return total

if __name__ == '__main__':
    log('🚀 FBREF WAYBACK MASS HARVESTER')
    log(f'Targeting {len(COMPS)} leagues × {len(DATES)} dates\n')
    
    total_matches = 0
    total_stats = 0
    successes = 0
    
    for date_str in DATES:
        log(f'\n{"="*60}')
        log(f'DATE: {date_str}')
        log(f'{"="*60}')
        
        for comp_id, league_name in COMPS.items():
            m = scrape_schedule(comp_id, league_name, date_str)
            s = scrape_stats(comp_id, league_name, date_str)
            if m > 0 or s > 0:
                successes += 1
            total_matches += m
            total_stats += s
            log(f'  {league_name:25s} → matches: {m:4d}, stats: {s:3d}')
            
            # Be gentle to Wayback
            time.sleep(1.5)
    
    # Results
    conn = getdb(); c = conn.cursor()
    total = c.execute('SELECT COUNT(*) FROM source_fbref_killer').fetchone()[0]
    log(f'\n{"="*60}')
    log(f'🏆 FINAL RESULTS')
    log(f'{"="*60}')
    log(f'Total matches extracted:  {total_matches}')
    log(f'Total stats rows:         {total_stats}')
    log(f'Total in DB:              {total}')
    log(f'Successful requests:      {successes}')
    
    by_type = c.execute('SELECT page_type, COUNT(*) FROM source_fbref_killer GROUP BY page_type').fetchall()
    for pt, ct in by_type:
        log(f'  {pt}: {ct}')
    conn.close()
