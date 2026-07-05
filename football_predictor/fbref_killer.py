#!/usr/bin/env python3
"""
FBREF KILLER — يتجاوز Cloudflare عبر Wayback Machine + Google Cache
يستخرج كل مباريات + إحصائيات FBref بدون حظر
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
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

def log(msg): print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def getdb():
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def save_fbref(sid, raw, date='', home='', away='', hs=None, ac=None, page_type=''):
    try:
        conn = getdb(); c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO source_fbref 
            (source_id, raw_data, match_date, home_team, away_team, home_score, away_score, page_type)
            VALUES (?,?,?,?,?,?,?,?)''',
            (str(sid)[:100], raw, date[:10], str(home)[:100], str(away)[:100], hs, ac, page_type))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        return False

# Make sure source_fbref table exists
conn = getdb(); c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS source_fbref (
    source_id TEXT PRIMARY KEY, raw_data TEXT,
    match_date TEXT, home_team TEXT, away_team TEXT,
    home_score INTEGER, away_score INTEGER,
    page_type TEXT, fetched_at TEXT DEFAULT (datetime('now'))
)''')
conn.commit(); conn.close()

# ============================================================================
# FBref Targets
# ============================================================================
COMPS = {
    9: 'Premier-League', 12: 'La-Liga', 20: 'Bundesliga',
    11: 'Serie-A', 13: 'Ligue-1', 10: 'Championship',
    22: 'Champions-League', 19: 'Europa-League',
    21: 'Europa-Conference-League',
}

def scrape_via_wayback(url, date='20250601'):
    """Fetch via Wayback Machine"""
    wb_url = f'https://web.archive.org/web/{date}/{url}'
    r = s.get(wb_url, timeout=30)
    if r.status_code == 200 and 'Playback' not in r.text[:200]:
        return r.text
    return None

def scrape_via_google_cache(url):
    """Fetch via Google Cache"""
    gc = f'https://webcache.googleusercontent.com/search?q=cache:{url}'
    r = s.get(gc, timeout=15)
    if r.status_code == 200:
        return r.text
    return None

def scrape_schedule(comp_id, league_name, year=2026):
    """Get all match results from FBref schedule page"""
    log(f'[FBref] Schedule: {league_name} {year}')
    url = f'https://fbref.com/en/comps/{comp_id}/schedule/{league_name}-Scores-and-Fixtures'
    
    html = scrape_via_wayback(url)
    if not html:
        html = scrape_via_google_cache(url)
    if not html:
        log(f'[FBref] ❌ Cannot access {league_name}')
        return 0
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the scores table
    scores_table = soup.find('table', class_='scores')
    if not scores_table:
        # Try to find any table with match data
        tables = soup.find_all('table')
        scores_table = tables[0] if tables else None
    
    if not scores_table:
        log(f'[FBref] ❌ No table found for {league_name}')
        return 0
    
    total = 0
    rows = scores_table.find_all('tr')
    
    for row in rows:
        cols = row.find_all(['td', 'th'])
        if len(cols) < 6:
            continue
        
        cells = [c.get_text(strip=True) for c in cols]
        
        # Try to extract: date, home, score, away
        date = cells[0] if len(cells) > 0 else ''
        home = cells[1] if len(cells) > 1 else ''
        score = cells[2] if len(cells) > 2 else ''
        away = cells[3] if len(cells) > 3 else ''
        
        # Parse score
        hs = None; ac = None
        if score and '-' in score:
            try:
                parts = score.split('-')
                hs = int(parts[0].strip())
                ac = int(parts[1].strip())
            except: pass
        
        if not home or not away:
            continue
        
        # Save
        sid = f'fbref_{comp_id}_{year}_{date}_{home}_{away}'
        raw = json.dumps({'comp': comp_id, 'league': league_name, 'year': year,
                         'date': date, 'home': home, 'away': away,
                         'score': score, 'url': url, 'html': html[:5000]})
        
        # Also try to get the match page for detailed stats
        match_link = cols[1].find('a') if len(cols) > 1 else None
        match_url = ''
        if match_link and match_link.get('href'):
            match_url = 'https://fbref.com' + match_link['href']
            # Get detailed match stats
            try:
                mhtml = scrape_via_wayback(match_url)
                if mhtml:
                    msoup = BeautifulSoup(mhtml, 'html.parser')
                    mtables = msoup.find_all('table')
                    raw_detailed = json.dumps({
                        'match_stats': str(mtables[:10]),
                        'match_url': match_url,
                    })
                    sid_detail = f'fbref_detail_{comp_id}_{date}_{home}_{away}'
                    save_fbref(sid_detail, raw_detailed, date, home, away, hs, ac, 'match_detail')
                    total += 1
                    log(f'[FBref] ✅ Match detail: {home} vs {away} - {score}')
            except: pass
        
        save_fbref(sid, raw, date, home, away, hs, ac, 'schedule')
        total += 1
    
    log(f'[FBref] ✅ {league_name}: {total} matches')
    return total

def scrape_team_stats(comp_id, league_name):
    """Get team stats from FBref"""
    log(f'[FBref] Stats: {league_name}')
    url = f'https://fbref.com/en/comps/{comp_id}/stats/{league_name}-Stats'
    
    html = scrape_via_wayback(url)
    if not html:
        return 0
    
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    
    total = 0
    for table in tables:
        rows = table.find_all('tr')
        for row in rows[1:]:
            cols = row.find_all(['td', 'th'])
            cells = [c.get_text(strip=True) for c in cols]
            if len(cells) >= 3:
                team = cells[0] if len(cells) > 0 else ''
                sid = f'fbref_stats_{comp_id}_{team}'
                save_fbref(sid, json.dumps({'comp': comp_id, 'league': league_name, 'row': cells, 'header': str(table.find('caption'))}), page_type='team_stats')
                total += 1
    
    log(f'[FBref] ✅ {league_name} stats: {total} rows')
    return total

# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    log('🚀 FBREF KILLER starting...')
    
    for comp_id, league_name in COMPS.items():
        log('='*60)
        log(f'  Attacking: {league_name} (comp {comp_id})')
        log('='*60)
        
        # 1. Schedule/Results
        m = scrape_schedule(comp_id, league_name)
        log(f'  Matches: {m}')
        
        # 2. Team Stats
        stats_rows = scrape_team_stats(comp_id, league_name)
        log(f'  Stats rows: {stats_rows}')
        
        time.sleep(2)
    
    # Check results
    conn = getdb(); c = conn.cursor()
    cnt = c.execute('SELECT COUNT(*) FROM source_fbref').fetchone()[0]
    types = c.execute('SELECT page_type, COUNT(*) FROM source_fbref GROUP BY page_type').fetchall()
    log('='*60)
    log(f'✅ TOTAL FBref rows: {cnt}')
    for pt, ct in types:
        log(f'   {pt}: {ct}')
    conn.close()
