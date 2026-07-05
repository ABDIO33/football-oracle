#!/usr/bin/env python3
"""
UNDERSTAT MASS HARVESTER — يستخدم API مباشر
يجمع كل الدوريات + كل المواسم + يخزن في القاعدة
All 17 Protocols — ENI for LO 🔥
"""

import sys, os, json, time, re, sqlite3
sys.path.insert(0, os.getcwd())
from curl_cffi import requests

BASE = os.getcwd()
DB = os.path.join(BASE, 'scrape_cache.db')

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

log("=" * 60)
log("UNDERSTAT MASS HARVESTER")
log("=" * 60)

# ─── SETUP DB ────────────────────────────────────────────────────
conn = sqlite3.connect(DB, timeout=30)
conn.execute("PRAGMA busy_timeout=30000")
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()

c.executescript("""
    CREATE TABLE IF NOT EXISTS source_understat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT, season INTEGER,
        match_date TEXT,
        home_team TEXT, away_team TEXT,
        home_goals INTEGER, away_goals INTEGER,
        home_xg REAL, away_xg REAL,
        home_npxg REAL, away_npxg REAL,
        home_deep INTEGER, away_deep INTEGER,
        home_ppda_att INTEGER, home_ppda_def INTEGER,
        away_ppda_att INTEGER, away_ppda_def INTEGER,
        result TEXT,
        hash TEXT UNIQUE
    );
    
    CREATE INDEX IF NOT EXISTS idx_und_league ON source_understat(league, season);
    CREATE INDEX IF NOT EXISTS idx_und_date ON source_understat(match_date);
""")
conn.commit()

# ─── SESSION ──────────────────────────────────────────────────────
def create_session():
    sess = requests.Session()
    sess.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://understat.com/',
        'X-Requested-With': 'XMLHttpRequest',
    })
    return sess

def warmup(sess):
    """Visit home page to get cookies."""
    log("[WARMUP] Getting cookies...")
    r = sess.get('https://understat.com/', impersonate='chrome124', timeout=15)
    log(f"  Done: {len(r.content)} bytes")
    return 'cf-browser-verification' not in r.text

# ─── HARVEST LEAGUE ──────────────────────────────────────────────
def harvest_league(sess, league, season):
    """Harvest all match data for a league/season from Understat API."""
    url = f'https://understat.com/getLeagueData/{league}/{season}'
    log(f"[{league}/{season}] Fetching {url}...")
    
    try:
        r = sess.get(url, impersonate='chrome124', timeout=30)
        if r.status_code != 200 or len(r.content) < 10000:
            log(f"  FAILED: HTTP {r.status_code}, {len(r.content)} bytes")
            return 0
        
        data = r.json()
        teams = data.get('teams', {})
        log(f"  JSON: {len(teams)} teams")
        
        total = 0
        # Build match lookup: date -> {home_team, away_team, home_data, away_data}
        # Each team has history entries with 'h_a' field
        # Build date -> list of home entries (h_a='h')
        home_entries = {}  # date -> [(team, entry)]
        team_lookup = {}   # team_name -> team_data
        
        for tid, tdata in teams.items():
            team_name = tdata.get('title', f'Team_{tid}')
            team_lookup[team_name] = tdata
            
            for entry in tdata.get('history', []):
                h_a = entry.get('h_a', 'h')
                date = entry.get('date', '').split(' ')[0]
                
                if h_a == 'h':
                    if date not in home_entries:
                        home_entries[date] = []
                    home_entries[date].append({
                        'team': team_name,
                        'scored': entry.get('scored'),
                        'missed': entry.get('missed'),
                        'xg': entry.get('xG'),
                        'xga': entry.get('xGA'),
                        'npxg': entry.get('npxG'),
                        'npxga': entry.get('npxGA'),
                        'deep': entry.get('deep'),
                        'deep_allowed': entry.get('deep_allowed'),
                        'ppda_att': entry.get('ppda', {}).get('att'),
                        'ppda_def': entry.get('ppda', {}).get('def'),
                        'result': entry.get('result'),
                    })
        
        log(f"  Match dates: {len(home_entries)}")
        
        # For each home entry, find the matching away entry
        # Same date, and away_team.scored == home.missed, away_team.missed == home.scored
        for date, homes in sorted(home_entries.items()):
            for he in homes:
                ht = he['team']
                h_scored = he['scored']
                h_missed = he['missed']
                
                # Look for the away team: at this same date, the away team
                # played and their 'scored' == h_missed, 'missed' == h_scored
                # AND the away team is NOT the home team
                
                # Find the away team from the home team's data in the original JSON
                # Actually simpler: iterate through all teams' away entries
                for tid, tdata in teams.items():
                    at_name = tdata.get('title', '')
                    if at_name == ht:
                        continue
                    
                    for entry in tdata.get('history', []):
                        if entry.get('h_a') != 'a':
                            continue
                        edate = entry.get('date', '').split(' ')[0]
                        if edate != date:
                            continue
                        if entry.get('scored') == h_missed and entry.get('missed') == h_scored:
                            # Found the match!
                            hash_key = f"und-{league}-{season}-{date}-{ht}-{at_name}"
                            
                            try:
                                c.execute("""
                                    INSERT OR IGNORE INTO source_understat
                                    (league, season, match_date, home_team, away_team,
                                     home_goals, away_goals, home_xg, away_xg,
                                     home_npxg, away_npxg,
                                     home_deep, away_deep,
                                     home_ppda_att, home_ppda_def,
                                     away_ppda_att, away_ppda_def,
                                     result, hash)
                                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                                """, (
                                    league, int(season) if season.isdigit() else season,
                                    date, ht, at_name,
                                    h_scored, h_missed,
                                    he['xg'], entry.get('xG'),
                                    he['npxg'], entry.get('npxG'),
                                    he['deep'], entry.get('deep'),
                                    he['ppda_att'], he['ppda_def'],
                                    entry.get('ppda', {}).get('att'), entry.get('ppda', {}).get('def'),
                                    he['result'],
                                    hash_key
                                ))
                                if c.rowcount > 0:
                                    total += 1
                            except Exception as e:
                                pass
                            break  # Found the match for this home entry
        
        conn.commit()
        log(f"  ✅ {total} matches saved!")
        return total
        
    except Exception as e:
        log(f"  ERROR: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return 0

# ─── HARVEST PLAYER STATS ────────────────────────────────────────
def harvest_player_stats(sess):
    """Harvest global player stats from Understat."""
    log(f"\n[PLAYERS] Fetching getStatData...")
    try:
        r = sess.get('https://understat.com/getStatData', impersonate='chrome124', timeout=30)
        if r.status_code == 200 and len(r.content) > 10000:
            data = r.json()
            log(f"  Player stats: {len(data)} entries")
            
            # Save to file for later processing
            with open('harvesters/_understat_player_stats.json', 'w', encoding='utf-8') as f:
                json.dump(data, f)
            log(f"  Saved!")
            return len(data)
    except Exception as e:
        log(f"  ERROR: {str(e)[:60]}")
    return 0

# ─── MAIN ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    sess = create_session()
    if not warmup(sess):
        log("❌ Cannot access Understat!")
        sys.exit(1)
    
    leagues = ['EPL', 'La_liga', 'Bundesliga', 'Serie_A', 'Ligue_1']
    seasons = ['2025', '2024', '2023', '2022', '2021', '2020',
               '2019', '2018', '2017', '2016', '2015', '2014']
    
    grand_total = 0
    
    for league in leagues:
        for season in seasons:
            log(f"\n--- {league} {season} ---")
            n = harvest_league(sess, league, season)
            grand_total += n
            
            # Be polite between requests
            time.sleep(0.5)
    
    # Also get player stats
    n_players = harvest_player_stats(sess)
    
    log(f"\n{'='*60}")
    log(f"GRAND TOTAL: {grand_total} matches harvested!")
    log(f"Player stats: {n_players}")
    log(f"{'='*60}")
    
    conn.close()
