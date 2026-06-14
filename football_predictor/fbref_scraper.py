"""FBref scraper — fetches team xG/xGA via seleniumbase uc=True.
Works on GHA (Chrome pre-installed on Ubuntu). Falls back gracefully."""

import os, json, time, sqlite3, atexit

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
_CHROME_OK = None
_CACHE = {}
_DRIVER = None
atexit.register(lambda: _close())

def _ensure_db():
    conn = sqlite3.connect(DB, timeout=5)
    conn.execute('''CREATE TABLE IF NOT EXISTS fbref_cache (
        team TEXT, season TEXT, stat TEXT, value REAL, updated REAL,
        PRIMARY KEY(team, season, stat)
    )''')
    return conn

def _chrome_available():
    global _CHROME_OK
    if _CHROME_OK is not None:
        return _CHROME_OK
    import shutil
    for name in ['google-chrome', 'google-chrome-stable', 'chromium-browser', 'chromium',
                  'chrome.exe', 'GoogleChrome.exe']:
        if shutil.which(name):
            _CHROME_OK = True
            return True
    for path in ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
                 '/usr/bin/chromium-browser', '/usr/bin/chromium',
                 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
                 os.path.expandvars('%LOCALAPPDATA%\\Google\\Chrome\\Application\\chrome.exe')]:
        if os.path.exists(path):
            _CHROME_OK = True
            return True
    _CHROME_OK = False
    return False

def _get_soup(url):
    """Fetch FBref page with seleniumbase uc=True and return BeautifulSoup."""
    global _DRIVER
    if not _chrome_available():
        return None
    try:
        if _DRIVER is None:
            from seleniumbase import Driver
            _DRIVER = Driver(uc=True, headless=True)
        _DRIVER.get(url)
        from bs4 import BeautifulSoup
        return BeautifulSoup(_DRIVER.page_source, 'html.parser')
    except Exception as e:
        print(f"[FBref] _get_soup error: {e}")
        return None

def _close():
    global _DRIVER
    if _DRIVER:
        try: _DRIVER.quit()
        except: pass
        _DRIVER = None

def get_team_xg(team_name, season='2025'):
    """Fetch per-game xG/xGA for a team via FBref."""
    key = f'{team_name}_{season}'
    if key in _CACHE:
        return _CACHE[key]
    
    conn = _ensure_db()
    row = conn.execute(
        'SELECT stat, value FROM fbref_cache WHERE team=? AND season=?',
        (team_name, season)
    ).fetchall()
    if row:
        result = {r[0]: r[1] for r in row}
        _CACHE[key] = result
        conn.close()
        return result
    conn.close()
    
    # Map team name to FBref URL slug
    slug = team_name.lower().replace(' ', '-').replace('&', 'and')
    slug = slug.replace('--', '-').replace("'", '')
    url = f'https://fbref.com/en/comps/9/{season}/stats/{season}-Premier-League-Stats'
    soup = _get_soup(url)
    if soup is None:
        return None
    
    try:
        # Find the standard stats table
        table = soup.find('table', id=lambda x: x and 'stats_standard' in x)
        if not table:
            return None
        
        rows = table.find_all('tr')
        for row in rows:
            th = row.find('th', {'data-stat': 'player'})
            if not th: continue
            player_link = th.find('a')
            if not player_link: continue
            # We need team-level stats, not player stats
            pass
        
        # FBref has per-team summary at the bottom of the table
        # Simpler: just try soccerdata.FBref as fallback
        return _get_team_xg_soccerdata(team_name, season)
    except Exception as e:
        print(f"[FBref] parse error: {e}")
        return _get_team_xg_soccerdata(team_name, season)

def _get_team_xg_soccerdata(team_name, season='2025'):
    """Fallback: use soccerdata.FBref which uses seleniumbase internally."""
    try:
        from soccerdata import FBref
        fb = FBref(leagues="ENG-Premier League", seasons=season if season == '2025' else int(season))
        stats = fb.read_team_season_stats(stat_type='standard')
        if stats is None or stats.empty: return None
        team_data = stats[stats['team'].str.contains(team_name, case=False, na=False)]
        if team_data.empty: return None
        result = {
            'xg_per_game': float(team_data['xg_per_game'].mean()) if 'xg_per_game' in team_data.columns else None,
            'xga_per_game': float(team_data['xga_per_game'].mean()) if 'xga_per_game' in team_data.columns else None,
            'matches': int(team_data['matches'].sum()) if 'matches' in team_data.columns else 0,
        }
        conn = _ensure_db()
        for k, v in result.items():
            if v is not None:
                conn.execute('REPLACE INTO fbref_cache VALUES (?,?,?,?,?)',
                             (team_name, season, k, v, time.time()))
        conn.commit(); conn.close()
        _CACHE[f'{team_name}_{season}'] = result
        return result
    except Exception as e:
        print(f"[FBref] soccerdata error: {e}")
        return None

def get_match_xg(home_team, away_team, season='2025'):
    """Get match-level xG data."""
    try:
        from soccerdata import FBref
        fb = FBref(leagues="ENG-Premier League", seasons=season if season == '2025' else int(season))
        matches = fb.read_schedule()
        if matches is None or matches.empty:
            return None
        
        mask = (
            matches['home_team'].str.contains(home_team, case=False, na=False) &
            matches['away_team'].str.contains(away_team, case=False, na=False)
        )
        match = matches[mask]
        if match.empty:
            return None
        
        match = match.iloc[0]
        return {
            'home_xg': float(match.get('home_xg', 0)) if 'home_xg' in match.index else None,
            'away_xg': float(match.get('away_xg', 0)) if 'away_xg' in match.index else None,
            'date': str(match.get('date', '')),
            'score': f"{match.get('home_score','?')}-{match.get('away_score','?')}",
        }
    except Exception as e:
        print(f"[FBref] get_match_xg error: {e}")
        return None

def get_live_team_data_full(team_name):
    """Interface for prediction_engine."""
    stats = get_team_xg(team_name)
    if not stats or stats.get('xg_per_game') is None:
        return None
    return {
        'info': {'name': team_name, 'source': 'fbref'},
        'stats': {
            'avg_gs': stats['xg_per_game'],
            'avg_gc': stats['xga_per_game'] if stats.get('xga_per_game') else stats['xg_per_game'] * 0.8,
            'matches_played': stats.get('matches', 0),
        },
        'events': []
    }

if __name__ == '__main__':
    d = get_team_xg('Liverpool')
    if d: print(json.dumps(d, indent=2))
    else: print('FBref not available (Chrome needed)')
