#!/usr/bin/env python3
"""
SIMPLE SCRAPERS — Soccerway + 11v11 + Livescore + Pinnacle
تصيب بيانات من مواقع تشتغل مع HTTP بسيط
All Protocols Active — ENI for LO 🔥
"""

import urllib.request, urllib.error
import sqlite3, json, time, re, os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, 'scrape_cache.db')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def fetch(url):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=20)
            return resp.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5)
                continue
            return None
        except Exception as e:
            if i < 2:
                time.sleep(2)
                continue
            return None
    return None

def ensure_tables():
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS source_soccerway (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league TEXT, match_date TEXT, home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER, hash TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS source_livescore (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league TEXT, match_date TEXT, home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER, status TEXT, hash TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS source_pinnacle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league TEXT, match_date TEXT, home_team TEXT, away_team TEXT,
            odds_h REAL, odds_a REAL, hash TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS source_11v11 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team TEXT, away_team TEXT, match_date TEXT, competition TEXT,
            home_score INTEGER, away_score INTEGER, hash TEXT UNIQUE
        );
    """)
    conn.commit()
    conn.close()

def parse_soccerway():
    """Parse Premier League results from Soccerway"""
    log("Soccerway: Fetching EPL results...")
    html = fetch('https://us.soccerway.com/national/england/premier-league/20242025/regular-season/r81310/')
    if not html:
        log("Soccerway: FAILED to fetch")
        return 0
    
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    total = 0
    
    # Find match blocks - Soccerway uses <tr class="match">
    matches = re.findall(
        r'<tr[^>]*class="[^"]*match[^"]*"[^>]*>.*?</tr>',
        html, re.DOTALL
    )
    log(f"Soccerway: Found {len(matches)} match rows")
    
    for m in matches[:380]:
        try:
            # Extract team names and scores
            teams = re.findall(r'<td[^>]*class="[^"]*team[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>', m, re.DOTALL)
            scores = re.findall(r'<td[^>]*class="[^"]*score[^"]*"[^>]*>\s*(\d+)\s*', m)
            
            if len(teams) >= 2 and len(scores) >= 2:
                home = teams[0].strip()
                away = teams[1].strip()
                hs = int(scores[0])
                as_ = int(scores[1])
                
                # Get date
                date_match = re.search(r'<td[^>]*class="[^"]*date[^"]*"[^>]*>\s*(\d{2}/\d{2}/\d{2,4})', m)
                match_date = date_match.group(1) if date_match else ''
                
                hash_key = f"sw-{home}-{away}-{match_date}"
                
                c.execute('''INSERT OR IGNORE INTO source_soccerway 
                    (league, match_date, home_team, away_team, home_score, away_score, hash)
                    VALUES (?,?,?,?,?,?,?)''',
                    ('England-Premier-League', match_date, home, away, hs, as_, hash_key))
                total += 1
        except:
            pass
    
    conn.commit()
    conn.close()
    log(f"Soccerway: {total} matches saved")
    return total

def parse_livescore():
    """Parse live/scheduled matches from Livescore"""
    log("Livescore: Fetching...")
    html = fetch('https://www.livescore.com/en/')
    if not html:
        log("Livescore: FAILED")
        return 0
    
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    total = 0
    
    # Livescore loads data via JavaScript - look for embedded JSON
    # Try to find match data patterns
    matches = re.findall(
        r'["\']home["\']\s*:\s*["\']([^"\']+)["\'].*?'
        r'["\']away["\']\s*:\s*["\']([^"\']+)["\']',
        html, re.DOTALL
    )
    
    for m in matches[:100]:
        try:
            home, away = m
            hash_key = f"ls-{home}-{away}"
            c.execute('''INSERT OR IGNORE INTO source_livescore
                (league, home_team, away_team, status, hash) VALUES (?,?,?,?,?)''',
                ('Unknown', home.strip(), away.strip(), 'scheduled', hash_key))
            total += 1
        except:
            pass
    
    conn.commit()
    conn.close()
    log(f"Livescore: {total} matches found")
    return total

def parse_pinnacle():
    """Parse odds from Pinnacle"""
    log("Pinnacle: Fetching EPL odds...")
    html = fetch('https://www.pinnacle.com/en/soccer/england-premier-league/matchups/')
    if not html:
        log("Pinnacle: FAILED")
        return 0
    
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    total = 0
    
    # Pinnacle embeds match data in script tags
    # Look for JSON-like structures
    scripts = re.findall(r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*({.*?});</script>', html, re.DOTALL)
    
    if scripts:
        try:
            data = json.loads(scripts[0])
            # Navigate to find matches
            log("Pinnacle: Found initial state JSON")
        except:
            log("Pinnacle: JSON parse failed")
    
    # Also try to find match listings in HTML
    matchups = re.findall(
        r'class="[^"]*style_title[^"]*"[^>]*>([^<]+)</span>.*?'
        r'class="[^"]*style_odds[^"]*"[^>]*>([^<]+)</span>',
        html, re.DOTALL
    )
    
    for m in matchups[:50]:
        try:
            team_name, odds = m
            hash_key = f"pin-{team_name.strip()}"
            c.execute('''INSERT OR IGNORE INTO source_pinnacle
                (league, home_team, odds_h, hash) VALUES (?,?,?,?)''',
                ('England-Premier-League', team_name.strip(), odds.strip(), hash_key))
            total += 1
        except:
            pass
    
    conn.commit()
    conn.close()
    log(f"Pinnacle: {total} odds entries")
    return total

def parse_11v11():
    """Parse head-to-head data from 11v11"""
    log("11v11: Fetching...")
    html = fetch('https://www.11v11.com/competitions/premier-league/2025/')
    if not html:
        log("11v11: FAILED")
        return 0
    
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    total = 0
    
    # 11v11 has a simple table structure
    rows = re.findall(
        r'<tr[^>]*>.*?<td[^>]*class="[^"]*date[^"]*"[^>]*>\s*([^<]+)\s*</td>.*?'
        r'<td[^>]*class="[^"]*home[^"]*"[^>]*>\s*([^<]+)\s*</td>.*?'
        r'<td[^>]*class="[^"]*score[^"]*"[^>]*>\s*([^<]+)\s*</td>.*?'
        r'<td[^>]*class="[^"]*away[^"]*"[^>]*>\s*([^<]+)\s*</td>',
        html, re.DOTALL
    )
    
    for row in rows[:380]:
        try:
            date_str, home, score, away = row
            score = score.strip()
            if '-' in score:
                parts = score.split('-')
                hs = int(parts[0].strip())
                as_ = int(parts[1].strip())
            else:
                continue
            
            hash_key = f"11-{home.strip()}-{away.strip()}-{date_str.strip()}"
            c.execute('''INSERT OR IGNORE INTO source_11v11
                (home_team, away_team, match_date, competition, home_score, away_score, hash)
                VALUES (?,?,?,?,?,?,?)''',
                (home.strip(), away.strip(), date_str.strip(), 'Premier League', hs, as_, hash_key))
            total += 1
        except:
            pass
    
    conn.commit()
    conn.close()
    log(f"11v11: {total} matches")
    return total

if __name__ == '__main__':
    log("="*50)
    log("SIMPLE SCRAPERS — STARTING")
    log("="*50)
    
    ensure_tables()
    
    results = {}
    for name, func in [('Soccerway', parse_soccerway), ('11v11', parse_11v11),
                        ('Livescore', parse_livescore), ('Pinnacle', parse_pinnacle)]:
        try:
            n = func()
            results[name] = n
        except Exception as e:
            log(f"{name}: ERROR - {str(e)[:80]}")
            results[name] = 0
    
    log("\n" + "="*50)
    log("RESULTS")
    log("="*50)
    for name, n in results.items():
        log(f"  {name:15s}: {n} entries")
    log("="*50)
    
    # Final DB count
    conn = sqlite3.connect(DB)
    for table in ['source_soccerway', 'source_11v11', 'source_livescore', 'source_pinnacle']:
        try:
            n = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            log(f"  DB {table}: {n} rows")
        except:
            log(f"  DB {table}: ERROR")
    conn.close()
