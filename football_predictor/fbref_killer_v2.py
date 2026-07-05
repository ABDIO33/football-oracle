#!/usr/bin/env python3
"""
FBREF KILLER V2 — يتجاوز Cloudflare عبر Wayback Machine
"""
import sys, os, time, json, sqlite3, hashlib, warnings
from datetime import datetime
warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')

import requests
from bs4 import BeautifulSoup

SESSION = requests.Session()
SESSION.headers.update({'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

def log(msg): print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def getdb():
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

# Init new table
conn = getdb(); c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS source_fbref_killer (
    source_id TEXT PRIMARY KEY, raw_data TEXT,
    match_date TEXT, home_team TEXT, away_team TEXT,
    home_score INTEGER, away_score INTEGER,
    page_type TEXT, fetched_at TEXT DEFAULT (datetime('now'))
)''')
conn.commit(); conn.close()

def save_fbref(sid, raw, date='', home='', away='', hs=None, ac=None, ptype=''):
    try:
        conn = getdb(); c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO source_fbref_killer 
            (source_id, raw_data, match_date, home_team, away_team, home_score, away_score, page_type)
            VALUES (?,?,?,?,?,?,?,?)''',
            (str(sid)[:150], raw[:100000], date[:10], str(home)[:100], str(away)[:100], hs, ac, ptype))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        log(f'  SAVE ERROR: {e}')
        return False

def via_wayback(url, date='20250601'):
    wb_url = f'https://web.archive.org/web/{date}/{url}'
    try:
        r = SESSION.get(wb_url, timeout=30)
        if r.status_code == 200 and 'Playback' not in r.text[:200]:
            return r.text
    except: pass
    return None

COMPS = {
    9: 'Premier-League', 12: 'La-Liga', 20: 'Bundesliga',
    11: 'Serie-A', 13: 'Ligue-1', 10: 'Championship',
    22: 'Champions-League', 19: 'Europa-League',
}

def scrape_schedule(comp_id, league_name):
    log(f'  Schedule: {league_name}')
    url = f'https://fbref.com/en/comps/{comp_id}/schedule/{league_name}-Scores-and-Fixtures'
    html = via_wayback(url)
    if not html:
        log(f'  ❌ Cannot access {league_name}')
        return 0
    
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', class_='scores')
    if not table:
        tables = soup.find_all('table')
        table = tables[0] if tables else None
    if not table:
        log(f'  ❌ No table')
        return 0
    
    total = 0
    for row in table.find_all('tr'):
        cols = row.find_all(['td', 'th'])
        if len(cols) < 6: continue
        cells = [c.get_text(strip=True) for c in cols]
        date = cells[0] if len(cells) > 0 else ''
        home = cells[1] if len(cells) > 1 else ''
        score = cells[2] if len(cells) > 2 else ''
        away = cells[3] if len(cells) > 3 else ''
        hs = ac = None
        if score and '-' in score:
            try:
                p = score.split('-')
                hs = int(p[0].strip()); ac = int(p[1].strip())
            except: pass
        if not home or not away: continue
        sid = f'fbref_{comp_id}_{date}_{home}_{away}'
        save_fbref(sid, json.dumps({'comp':comp_id,'league':league_name,'date':date,'home':home,'away':away,'score':score}), date, home, away, hs, ac, 'schedule')
        total += 1
    log(f'  ✅ {league_name}: {total} matches')
    return total

def scrape_team_stats(comp_id, league_name):
    log(f'  Stats: {league_name}')
    url = f'https://fbref.com/en/comps/{comp_id}/stats/{league_name}-Stats'
    html = via_wayback(url)
    if not html: return 0
    soup = BeautifulSoup(html, 'html.parser')
    total = 0
    for table in soup.find_all('table', class_='stats_table'):
        for row in table.find_all('tr')[1:]:
            cols = row.find_all(['td','th'])
            cells = [c.get_text(strip=True) for c in cols]
            if len(cells) >= 3:
                sid = f'fbref_stats_{comp_id}_{league_name}_{cells[0]}'
                save_fbref(sid, json.dumps({'comp':comp_id,'league':league_name,'row':cells}), ptype='team_stats')
                total += 1
    log(f'  ✅ Stats: {total} rows')
    return total

if __name__ == '__main__':
    log('🚀 FBREF KILLER V2')
    for comp_id, league_name in COMPS.items():
        log('='*50)
        log(f'  {league_name} (comp {comp_id})')
        scrape_schedule(comp_id, league_name)
        scrape_team_stats(comp_id, league_name)
        time.sleep(1)
    
    conn = getdb(); c = conn.cursor()
    cnt = c.execute('SELECT COUNT(*) FROM source_fbref_killer').fetchone()[0]
    by_type = c.execute('SELECT page_type, COUNT(*) FROM source_fbref_killer GROUP BY page_type').fetchall()
    log('='*50)
    log(f'✅ TOTAL: {cnt} rows')
    for pt, ct in by_type:
        log(f'   {pt}: {ct}')
    conn.close()
