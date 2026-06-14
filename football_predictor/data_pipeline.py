import sqlite3, os, json, time, requests, threading
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__) or '.', 'football.db')
API_SPORT_KEY = os.environ.get('API_SPORT_KEY', '')
FOOTBALL_DATA_KEY = os.environ.get('FOOTBALL_DATA_API_KEY', '')
API_FOOTBALL_BASE = 'https://v3.football.api-sports.io'
FOOTBALL_DATA_BASE = 'https://api.football-data.org/v4'
headers_api = lambda: {'x-apisports-key': os.environ.get('API_SPORT_KEY', '')}
headers_fd = lambda: {'X-Auth-Token': os.environ.get('FOOTBALL_DATA_API_KEY', '')}

TOP_LEAGUES = [
    (39, 'Premier League'), (140, 'La Liga'), (78, 'Bundesliga'),
    (135, 'Serie A'), (61, 'Ligue 1'), (2, 'UEFA Champions League'),
    (1, 'World Cup'), (88, 'Eredivisie'), (94, 'Primeira Liga'),
    (203, 'Turkish Super Lig')
]
FD_COMPETITIONS = [
    ('PL', 'Premier League'), ('PD', 'La Liga'), ('BL1', 'Bundesliga'),
    ('SA', 'Serie A'), ('FL1', 'Ligue 1'), ('CL', 'Champions League'),
    ('WC', 'World Cup'), ('DED', 'Eredivisie'), ('PPL', 'Primeira Liga'),
    ('TSL', 'Turkish Super Lig')
]
FD_MAP = {name: code for code, name in FD_COMPETITIONS}

def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _get_conn()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS pipeline_log (id INTEGER PRIMARY KEY AUTOINCREMENT, run_time TEXT, status TEXT, matches_count INTEGER, teams_refreshed INTEGER, message TEXT);
        CREATE TABLE IF NOT EXISTS elo_ratings (team_name TEXT PRIMARY KEY, elo INTEGER, last_updated TEXT);
        CREATE TABLE IF NOT EXISTS standings (team_name TEXT, league TEXT, position INTEGER, points INTEGER, form TEXT, updated TEXT, PRIMARY KEY (team_name, league));
        CREATE TABLE IF NOT EXISTS match_results (id TEXT PRIMARY KEY, date TEXT, home_team TEXT, away_team TEXT, home_score INTEGER, away_score INTEGER, league TEXT, season TEXT);
    ''')
    conn.commit(); conn.close()

def save_match_result(match_id, date, home_team, away_team, home_score, away_score, league, season):
    conn = _get_conn()
    try:
        conn.execute('INSERT OR IGNORE INTO match_results VALUES (?,?,?,?,?,?,?,?)',
                     (match_id, date, home_team, away_team, home_score, away_score, league, season))
        conn.commit()
    finally:
        conn.close()

def update_elo(team_name, new_elo):
    conn = _get_conn()
    try:
        conn.execute('INSERT OR REPLACE INTO elo_ratings VALUES (?,?,?)',
                     (team_name, new_elo, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
    finally:
        conn.close()

def save_standings(team_name, league, position, points, form):
    conn = _get_conn()
    try:
        conn.execute('INSERT OR REPLACE INTO standings VALUES (?,?,?,?,?,?)',
                     (team_name, league, position, points, form, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
    finally:
        conn.close()

def log_pipeline_run(status, matches_count, teams_refreshed, message=''):
    conn = _get_conn()
    try:
        conn.execute('INSERT INTO pipeline_log (run_time, status, matches_count, teams_refreshed, message) VALUES (?,?,?,?,?)',
                     (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), status, matches_count, teams_refreshed, message))
        conn.commit()
    finally:
        conn.close()

def _elo_expected(h_elo, a_elo):
    return 1.0 / (1.0 + 10.0 ** ((a_elo - h_elo) / 400.0))

def _update_elo_from_result(home_team, away_team, home_score, away_score):
    K = 32
    conn = _get_conn()
    try:
        hr = conn.execute('SELECT elo FROM elo_ratings WHERE team_name=?', (home_team,)).fetchone()
        ar = conn.execute('SELECT elo FROM elo_ratings WHERE team_name=?', (away_team,)).fetchone()
        h_elo = hr[0] if hr else 1500
        a_elo = ar[0] if ar else 1500
        e_h = _elo_expected(h_elo, a_elo)
        e_a = 1.0 - e_h
        if home_score > away_score: s_h, s_a = 1.0, 0.0
        elif home_score < away_score: s_h, s_a = 0.0, 1.0
        else: s_h, s_a = 0.5, 0.5
        update_elo(home_team, int(h_elo + K * (s_h - e_h)))
        update_elo(away_team, int(a_elo + K * (s_a - e_a)))
    finally:
        conn.close()

def fetch_fixtures_api_sports(league_id, league_name, date):
    m_cnt, t_cnt = 0, 0
    try:
        resp = requests.get(f'{API_FOOTBALL_BASE}/fixtures?league={league_id}&season=2025&date={date}',
                            headers=headers_api(), timeout=15)
        if resp.status_code != 200: return 0, 0
        data = resp.json()
        if not data.get('response'): return 0, 0
        seen = set()
        for item in data['response']:
            fx = item.get('fixture', {})
            mid = str(fx.get('id', ''))
            st = fx.get('status', {}).get('short', '')
            seas = str(item.get('league', {}).get('season', ''))
            home = item.get('teams', {}).get('home', {}).get('name', '')
            away = item.get('teams', {}).get('away', {}).get('name', '')
            g = item.get('goals', {})
            hs, aws = g.get('home'), g.get('away')
            if mid and st == 'FT' and hs is not None and aws is not None:
                save_match_result(mid, date, home, away, hs, aws, league_name, seas)
                _update_elo_from_result(home, away, hs, aws)
                seen.update([home, away]); m_cnt += 1
        t_cnt = len(seen)
        time.sleep(1.5)
    except requests.exceptions.Timeout:
        print(f'[api-football] Timeout {league_name} {date}')
    except Exception as e:
        print(f'[api-football] Error {league_name} {date}: {e}')
    return m_cnt, t_cnt

def fetch_fixtures_football_data(code, league_name, date):
    m_cnt, t_cnt = 0, 0
    try:
        resp = requests.get(f'{FOOTBALL_DATA_BASE}/competitions/{code}/matches?dateFrom={date}&dateTo={date}',
                            headers=headers_fd(), timeout=15)
        if resp.status_code != 200: return 0, 0
        matches = resp.json().get('matches', [])
        if not matches: return 0, 0
        seen = set()
        for m in matches:
            if m.get('status') != 'FINISHED': continue
            mid = str(m.get('id', ''))
            md = m.get('utcDate', date)[:10]
            home = m.get('homeTeam', {}).get('name', '')
            away = m.get('awayTeam', {}).get('name', '')
            ft = m.get('score', {}).get('fullTime', {})
            hs, aws = ft.get('home'), ft.get('away')
            if mid and hs is not None and aws is not None:
                save_match_result(mid, md, home, away, hs, aws, league_name, '2025')
                seen.update([home, away]); m_cnt += 1
        t_cnt = len(seen)
        time.sleep(0.6)
    except requests.exceptions.Timeout:
        print(f'[football-data] Timeout {league_name} {date}')
    except Exception as e:
        print(f'[football-data] Error {league_name} {date}: {e}')
    return m_cnt, t_cnt

def _fetch_standings_api_sports():
    t = 0
    for lid, lname in TOP_LEAGUES:
        try:
            resp = requests.get(f'{API_FOOTBALL_BASE}/standings?league={lid}&season=2025', headers=headers_api(), timeout=15)
            if resp.status_code != 200: continue
            resp_data = resp.json().get('response', [])
            if not resp_data: continue
            for rg in resp_data[0].get('league', {}).get('standings', []):
                for e in rg:
                    tn = e.get('team', {}).get('name', '')
                    if tn:
                        save_standings(tn, lname, e.get('rank', 0), e.get('points', 0), e.get('form', ''))
                        t += 1
            time.sleep(1.5)
        except requests.exceptions.Timeout:
            print(f'[api-football] Standings timeout {lname}')
        except Exception as ex:
            print(f'[api-football] Standings error {lname}: {ex}')
    return t

def _fetch_standings_football_data():
    t = 0
    for code, lname in FD_COMPETITIONS:
        try:
            resp = requests.get(f'{FOOTBALL_DATA_BASE}/competitions/{code}/standings', headers=headers_fd(), timeout=15)
            if resp.status_code != 200: continue
            for grp in resp.json().get('standings', []):
                for e in grp.get('table', []):
                    tn = e.get('team', {}).get('name', '')
                    if tn:
                        save_standings(tn, lname, e.get('position', 0), e.get('points', 0), e.get('form', ''))
                        t += 1
            time.sleep(0.6)
        except requests.exceptions.Timeout:
            print(f'[football-data] Standings timeout {lname}')
        except Exception as ex:
            print(f'[football-data] Standings error {lname}: {ex}')
    return t

def _process_league(league_id, league_name, dates):
    total_m, total_t = 0, 0
    for d in dates:
        m, t = fetch_fixtures_api_sports(league_id, league_name, d)
        total_m += m; total_t += t
    if total_m == 0 and total_t == 0:
        code = FD_MAP.get(league_name)
        if code:
            for d in dates:
                m, t = fetch_fixtures_football_data(code, league_name, d)
                total_m += m; total_t += t
    return total_m, total_t

def run_pipeline():
    init_db()
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    tomorrow = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    dates = (yesterday, today, tomorrow)
    total_m = total_t = 0
    for lid, lname in TOP_LEAGUES:
        m, t = _process_league(lid, lname, dates)
        total_m += m; total_t += t
    st = _fetch_standings_api_sports()
    if st == 0:
        st = _fetch_standings_football_data()
    total_t = max(total_t, st)
    msg = f'Pipeline updated: {total_m} matches, {total_t} teams refreshed'
    print(f'[Pipeline] {msg}')
    log_pipeline_run('success', total_m, total_t, msg)
    return {'status': 'success', 'matches_count': total_m, 'teams_refreshed': total_t, 'message': msg, 'run_time': today}

def start_pipeline(interval_hours=6):
    t = threading.Thread(target=_pipeline_loop, args=(interval_hours,), daemon=True)
    t.start(); return t

def _pipeline_loop(interval_hours):
    while True:
        try:
            r = run_pipeline()
            print(f"[Pipeline] {r.get('message', 'OK')}")
        except Exception as e:
            print(f"[Pipeline] Error: {e}")
        time.sleep(interval_hours * 3600)

def get_pipeline_status():
    conn = _get_conn()
    try:
        row = conn.execute('SELECT run_time, status, matches_count, teams_refreshed, message FROM pipeline_log ORDER BY id DESC LIMIT 1').fetchone()
        if row:
            return {k: row[k] for k in ('last_run','status','matches_count','teams_refreshed','message')}
        return {'last_run': None, 'status': 'never_run', 'matches_count': 0, 'teams_refreshed': 0, 'message': 'Pipeline has not run yet.'}
    finally:
        conn.close()

if __name__ == '__main__':
    print('[Pipeline] Running once...')
    print(json.dumps(run_pipeline(), indent=2))
