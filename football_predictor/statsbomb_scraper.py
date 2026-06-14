try:
    from statsbombpy import sb
except ImportError:
    sb = None

import os, json, sqlite3, time
from datetime import datetime

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
_CACHE = {}

COMPETITIONS = [
    (9, 281, 'Bundesliga', '2023/2024'),
    (11, 90, 'La Liga', '2020/2021'),
    (11, 4, 'La Liga', '2019/2020'),
    (7, 41, 'Ligue 1', '2022/2023'),
    (7, 42, 'Ligue 1', '2021/2022'),
    (2, 27, 'Premier League', '2015/2016'),
    (12, 28, 'Serie A', '2015/2016'),
]

def _db():
    conn = sqlite3.connect(DB, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS statsbomb_cache (key TEXT PRIMARY KEY, data TEXT, updated REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS statsbomb_team_stats (team_name TEXT, comp_name TEXT, season TEXT, xg_avg REAL, xga_avg REAL, ppda REAL, matches INTEGER, updated REAL, PRIMARY KEY(team_name,comp_name,season))')
    return conn

def _cached(key, ttl=86400):
    if key in _CACHE:
        return _CACHE[key]
    conn = _db()
    row = conn.execute('SELECT data FROM statsbomb_cache WHERE key=? AND updated>?', (key, time.time()-ttl)).fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def _set_cache(key, data):
    conn = _db()
    conn.execute('REPLACE INTO statsbomb_cache VALUES (?,?,?)', (key, json.dumps(data), time.time()))
    conn.commit(); conn.close()
    _CACHE[key] = data

def list_competitions():
    if sb is None: return []
    return COMPETITIONS

def get_matches(comp_id, season_id):
    key = f'matches_{comp_id}_{season_id}'
    cached = _cached(key, ttl=86400*7)
    if cached: return cached
    if sb is None: return []
    try:
        matches = sb.matches(competition_id=comp_id, season_id=season_id)
        out = matches.to_dict('records')
        _set_cache(key, out)
        return out
    except Exception as e:
        return []

def get_team_season_stats(team_name, comp_id=None, season_id=None):
    """Get xG/xGA/PPDA season averages for a team from StatsBomb data."""
    key = f'team_stats_{team_name}_{comp_id}_{season_id}'
    cached = _cached(key, ttl=86400*7)
    if cached: return cached
    if sb is None: return None

    xg_total = xga_total = ppda_total = n = 0
    comps = [(comp_id, season_id)] if (comp_id is not None and season_id is not None) else COMPETITIONS
    for cid, sid, cname, sname in comps:
        matches = get_matches(cid, sid)
        for m in matches:
            home = m.get('home_team', '')
            away = m.get('away_team', '')
            if team_name.lower() not in (home.lower(), away.lower()):
                continue
            mid = m['match_id']
            events = get_events(mid)
            if events is None:
                continue
            team_id = m.get('home_team_id') if home.lower() == team_name.lower() else m.get('away_team_id')
            is_home = (home.lower() == team_name.lower())
            team_xg = team_xga = ppda_count = opp_passes = 0
            for ev in events:
                if ev.get('type') == 'Shot' and ev.get('team_id') == team_id:
                    team_xg += ev.get('shot_statsbomb_xg', 0) or 0
                if ev.get('type') == 'Shot' and ev.get('team_id') != team_id:
                    team_xga += ev.get('shot_statsbomb_xg', 0) or 0
                if ev.get('type') == 'Pass' and ev.get('team_id') == team_id:
                    opp_passes += 1
                if ev.get('type') in ('Pressure', 'Duel') and ev.get('team_id') == team_id:
                    ppda_count += 1
            if team_xg > 0 or team_xga > 0:
                xg_total += team_xg; xga_total += team_xga
                if opp_passes > 0:
                    ppda_total += opp_passes / max(ppda_count, 1)
                n += 1
    if n == 0:
        return None
    result = {'xg_avg': round(xg_total/n, 3), 'xga_avg': round(xga_total/n, 3),
              'ppda': round(ppda_total/n, 1) if ppda_total else 0, 'matches': n}
    _set_cache(key, result)
    conn = _db()
    conn.execute('REPLACE INTO statsbomb_team_stats VALUES (?,?,?,?,?,?,?,?)',
                 (team_name, str(comp_id) if comp_id else 'all', str(season_id) if season_id else 'all',
                  result['xg_avg'], result['xga_avg'], result['ppda'], n, time.time()))
    conn.commit(); conn.close()
    return result

def get_events(match_id):
    key = f'events_{match_id}'
    cached = _cached(key, ttl=86400*30)
    if cached:
        return cached
    if sb is None:
        return None
    try:
        evs = sb.events(match_id=match_id)
        out = evs.to_dict('records')
        _set_cache(key, out)
        return out
    except Exception as e:
        return None

def get_live_team_data_full(team_name, league=None):
    """Match prediction_engine interface - return StatsBomb stats."""
    if sb is None:
        return None
    result = get_team_season_stats(team_name)
    if result is None:
        return None
    return {'info': {'name': team_name, 'source': 'statsbomb'},
            'stats': {'avg_gs': result['xg_avg'] * 0.85 + 0.3,
                      'avg_gc': result['xga_avg'] * 0.85 + 0.3,
                      'matches_played': result['matches'],
                      'form': '', 'ppda': result['ppda']},
            'events': []}

def warmup_all_teams(team_names):
    """Pre-cache StatsBomb data for a list of teams."""
    if sb is None:
        return 0
    found = 0
    for name in team_names:
        res = get_team_season_stats(name)
        if res:
            found += 1
    return found
