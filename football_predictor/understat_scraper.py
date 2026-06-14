import os, json, time, sqlite3, re
from datetime import datetime

try:
    from tls_requests import get as tls_get
except ImportError:
    tls_get = None

import urllib.request, urllib.error

BASE = 'https://understat.com'
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
_CACHE = {}
LEAGUES = {
    'EPL': 'EPL', 'La_Liga': 'La_Liga', 'Bundesliga': 'Bundesliga',
    'Serie_A': 'Serie_A', 'Ligue_1': 'Ligue_1'
}

def _db():
    conn = sqlite3.connect(DB, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS understat_cache (key TEXT PRIMARY KEY, data TEXT, updated REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS understat_ppda (team_name TEXT, season TEXT, ppda_avg REAL, opp_ppda_avg REAL, xg_avg REAL, xga_avg REAL, matches INTEGER, updated REAL, PRIMARY KEY(team_name,season))')
    return conn

def _fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Encoding': 'gzip'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                import gzip
                try:
                    return gzip.decompress(raw).decode('utf-8')
                except:
                    return raw.decode('utf-8')
        except Exception as e:
            if i < retries - 1:
                time.sleep(1)
    return None

def get_league_data(league='EPL', season='2025'):
    key = f'ul_{league}_{season}'
    cached = _CACHE.get(key)
    if cached: return cached
    conn = _db()
    row = conn.execute('SELECT data FROM understat_cache WHERE key=? AND updated>?', (key, time.time()-3600)).fetchone()
    conn.close()
    if row:
        _CACHE[key] = json.loads(row[0])
        return _CACHE[key]
    url = f'{BASE}/getLeagueData/{league}/{season}'
    html = _fetch(url)
    if not html: return None
    try:
        data = json.loads(html)
    except:
        return None
    _CACHE[key] = data
    conn = _db()
    conn.execute('REPLACE INTO understat_cache VALUES (?,?,?)', (key, json.dumps(data), time.time()))
    conn.commit(); conn.close()
    return data

def get_team_ppda(team_name, league='EPL', season='2025'):
    """Get PPDA, xG, xGA averages for a team from Understat."""
    result_key = f'{team_name}_{league}_{season}'
    cached = _CACHE.get(f'ppda_{result_key}')
    if cached: return cached
    conn = _db()
    row = conn.execute('SELECT ppda_avg, opp_ppda_avg, xg_avg, xga_avg, matches FROM understat_ppda WHERE team_name=? AND season=?',
                       (team_name, season)).fetchone()
    conn.close()
    if row:
        result = {'ppda': row[0], 'opp_ppda': row[1], 'xg_avg': row[2], 'xga_avg': row[3], 'matches': row[4]}
        _CACHE[f'ppda_{result_key}'] = result
        return result
    data = get_league_data(league, season)
    if not data: return None
    team_lower = team_name.lower()
    team_data = None
    for tid, td in data.get('teams', {}).items():
        if team_lower in td.get('title', '').lower():
            team_data = td
            break
    if not team_data:
        for tid, td in data.get('teams', {}).items():
            title = td.get('title', '')
            if title.lower() in team_lower or team_lower in title.lower():
                team_data = td
                break
    if not team_data:
        return None
    history = team_data.get('history', [])
    if not history:
        return None
    total_ppda_att = total_ppda_def = total_opp_att = total_opp_def = 0
    total_xg = total_xga = 0
    n = 0
    for m in history:
        ppda = m.get('ppda', {})
        pa = ppda.get('att', 0) if isinstance(ppda, dict) else 0
        pd = ppda.get('def', 0) if isinstance(ppda, dict) else 0
        ppda_allowed = m.get('ppda_allowed', {})
        oa = ppda_allowed.get('att', 0) if isinstance(ppda_allowed, dict) else 0
        od = ppda_allowed.get('def', 0) if isinstance(ppda_allowed, dict) else 0
        xg = float(m.get('xG', 0) or 0)
        xga = float(m.get('xGA', 0) or 0)
        if pd > 0:
            total_ppda_att += pa; total_ppda_def += pd; total_xg += xg; total_xga += xga
            if od > 0:
                total_opp_att += oa; total_opp_def += od
            n += 1
    if n == 0:
        return None
    ppda = round(total_ppda_att / total_ppda_def, 2) if total_ppda_def else 0
    opp_ppda = round(total_opp_att / total_opp_def, 2) if total_opp_def else 0
    xg_avg = round(total_xg / n, 3)
    xga_avg = round(total_xga / n, 3)
    result = {'ppda': ppda, 'opp_ppda': opp_ppda, 'xg_avg': xg_avg, 'xga_avg': xga_avg, 'matches': n}
    _CACHE[f'ppda_{result_key}'] = result
    conn = _db()
    conn.execute('REPLACE INTO understat_ppda VALUES (?,?,?,?,?,?,?,?)',
                 (team_name, season, ppda, opp_ppda, xg_avg, xga_avg, n, time.time()))
    conn.commit(); conn.close()
    return result

def get_live_team_data_full(team_name, league=None):
    """Match prediction_engine interface."""
    lg = league if league and league in LEAGUES else 'EPL'
    stats = get_team_ppda(team_name, lg)
    if stats is None:
        for l in LEAGUES:
            stats = get_team_ppda(team_name, l)
            if stats: break
    if stats is None:
        return None
    return {'info': {'name': team_name, 'source': 'understat'},
            'stats': {'avg_gs': stats.get('xg_avg', 0) * 0.8 + 0.2,
                      'avg_gc': stats.get('xga_avg', 0) * 0.8 + 0.2,
                      'matches_played': stats.get('matches', 0),
                      'ppda': stats.get('ppda', 0),
                      'opp_ppda': stats.get('opp_ppda', 0)},
            'events': []}

def warmup_all_teams(team_names, league='EPL', season='2025'):
    found = 0
    for name in team_names:
        if get_team_ppda(name, league, season):
            found += 1
    return found
