import os, json, time, sqlite3
from datetime import datetime

try:
    import soccerdata as sd
except ImportError:
    sd = None

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
_CACHE = {}
_ELO = None

def _db():
    conn = sqlite3.connect(DB, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS elo_cache (team_name TEXT PRIMARY KEY, elo REAL, rank INTEGER, league TEXT, updated REAL)')
    return conn

def _get_ratings():
    global _ELO
    if _ELO is None and sd is not None:
        try:
            _ELO = sd.ClubElo()
        except:
            return None
    if _ELO is None:
        return None
    try:
        return _ELO.read_by_date(datetime.now().strftime('%Y-%m-%d'))
    except:
        try:
            return _ELO.read_by_date('2025-08-15')
        except:
            return None

def get_elo(team_name):
    cached = _CACHE.get(team_name)
    if cached and (time.time() - cached['_t']) < 3600:
        return cached
    conn = _db()
    row = conn.execute('SELECT elo, rank, league, updated FROM elo_cache WHERE team_name=? AND updated>?',
                       (team_name, time.time()-86400)).fetchone()
    conn.close()
    if row:
        return {'elo': row[0], 'rank': row[1], 'league': row[2]}
    ratings = _get_ratings()
    if ratings is None:
        return None
    team_lower = team_name.lower()
    matches = [t for t in ratings.index if team_lower in t.lower() or t.lower() in team_lower]
    if not matches:
        alt_map = {'manchester city': 'Man City', 'manchester united': 'Man United',
                   'nottingham forest': 'Forest', 'leicester': 'Leicester',
                   'tottenham hotspur': 'Tottenham', 'wolverhampton': 'Wolves',
                   'brighton and hove albion': 'Brighton',
                   'newcastle united': 'Newcastle', 'west ham united': 'West Ham'}
        alt = alt_map.get(team_lower)
        if alt:
            matches = [alt]
    if not matches:
        return None
    try:
        r = ratings.loc[matches[0]]
        elo_val = float(r['elo']) if hasattr(r, '__iter__') else float(r)
        rank_val = int(r['rank']) if hasattr(r, '__iter__') else 0
        league_val = str(r['league']) if hasattr(r, '__iter__') else ''
        result = {'elo': elo_val, 'rank': rank_val, 'league': league_val}
        conn = _db()
        conn.execute('REPLACE INTO elo_cache VALUES (?,?,?,?,?)',
                     (team_name, elo_val, rank_val, league_val, time.time()))
        conn.commit(); conn.close()
        _CACHE[team_name] = {**result, '_t': time.time()}
        return result
    except:
        return None

def get_live_team_data_full(team_name, league=None):
    elo_data = get_elo(team_name)
    if elo_data is None:
        return None
    avg_gs = 0.5 + (elo_data['elo'] - 1500) / 1000
    avg_gc = 0.5 + (2000 - elo_data['elo']) / 1000
    return {'info': {'name': team_name, 'source': 'clubelo'},
            'stats': {'avg_gs': max(0.3, min(3.0, avg_gs)),
                      'avg_gc': max(0.3, min(3.0, avg_gc)),
                      'matches_played': 10,
                      'elo': elo_data['elo'],
                      'rank': elo_data.get('rank', 0)},
            'events': []}

def warmup_all_teams(team_names):
    found = 0
    for name in team_names:
        if get_elo(name):
            found += 1
    return found
