"""Sofascore API client — unlimited, no API key, replaces api-football"""
import requests, json, time, os, re, sqlite3
from datetime import datetime, timedelta
import edge_scraper

BASE = 'https://api.sofascore.com/api/v1'
SOFA_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.6099.230 Mobile Safari/537.36'
    ),
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://www.sofascore.com',
    'Referer': 'https://www.sofascore.com/',
}
SOFA_DB = os.path.join(os.path.dirname(__file__), 'sofascore.db')
_cache = {}
_last_req = 0

def _db():
    conn = sqlite3.connect(SOFA_DB)
    conn.execute('CREATE TABLE IF NOT EXISTS team_map (name TEXT PRIMARY KEY, sofa_id INTEGER, slug TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS team_cache (sofa_id INTEGER PRIMARY KEY, data TEXT, updated REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS match_cache (match_id INTEGER PRIMARY KEY, data TEXT, updated REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS edge_cache (path TEXT PRIMARY KEY, data TEXT, updated REAL)')
    conn.commit()
    return conn

def _get(path, params=None, cache_minutes=1440, allow_edge=True):
    global _last_req
    url = f'{BASE}{path}'
    if params:
        qs = '&'.join(f'{k}={v}' for k,v in params.items())
        url = f'{url}?{qs}'
    if url in _cache:
        entry = _cache[url]
        if time.time() - entry['time'] < cache_minutes * 60:
            return entry['data']
    now = time.time()
    if now - _last_req < 0.3:
        time.sleep(0.3 - (now - _last_req))
    try:
        r = requests.get(url, headers=SOFA_HEADERS, timeout=15)
        _last_req = time.time()
        if r.status_code == 200:
            data = r.json()
            _cache[url] = {'data': data, 'time': time.time()}
            return data
    except Exception:
        pass
    # Fallback via Edge WebDriver when direct fails (bypasses Cloudflare)
    if allow_edge:
        try:
            html = _edge_page(path)
            if html:
                data = json.loads(html)
                _cache[url] = {'data': data, 'time': time.time()}
                return data
        except:
            pass
    return None

def _edge_page(path):
    """Fetch Sofascore API endpoint via Edge WebDriver bypassing Cloudflare"""
    api_url = f'{BASE}{path}'
    safe_path = path.replace('/', '_').replace('?', '_')
    try:
        conn = sqlite3.connect(SOFA_DB)
        cur = conn.execute('SELECT data FROM edge_cache WHERE path = ? AND updated > ?', (safe_path, time.time() - 3600))
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except:
        pass
    driver = edge_scraper._driver_get()
    try:
        # Navigate to the Sofascore website page that loads this API data
        if '/team/' in path and '/events/' in path:
            parts = path.split('/')
            team_id = parts[2]
            driver.get(f'https://www.sofascore.com/team/{team_id}')
        else:
            driver.get(f'https://www.sofascore.com/')
        time.sleep(5)
        # Extract JSON from page source (Sofascore embeds data in <script> tags)
        import re
        html = driver.page_source
        scripts = re.findall(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if scripts:
            import json
            data = json.loads(scripts[0])
            # Try to extract API response from the embedded data
            result = _extract_from_next_data(data, path)
            if result:
                try:
                    conn = sqlite3.connect(SOFA_DB)
                    conn.execute('INSERT OR REPLACE INTO edge_cache VALUES (?, ?, ?)', (safe_path, json.dumps(result, default=str), time.time()))
                    conn.commit(); conn.close()
                except: pass
                return json.dumps(result)
        # If __NEXT_DATA__ not found, try __INITIAL_STATE__
        state = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
        if state:
            return state.group(1)
    except:
        pass
    return None

def _extract_from_next_data(data, path):
    try:
        if 'props' in data and 'pageProps' in data['props']:
            pp = data['props']['pageProps']
            if '/team/' in path:
                return pp.get('team', pp)
            if '/match/' in path:
                return pp.get('match', pp)
            return pp
    except:
        pass
    return None

def search_team(query):
    """Search for a team by name, return list of {id, name, slug, country}"""
    data = _get(f'/search/teams?q={query.replace(" ", "%20")}', cache_minutes=60)
    if not data or 'results' not in data:
        return []
    teams = []
    for r in data['results']:
        if r.get('type') == 'team' and 'entity' in r:
            e = r['entity']
            teams.append({
                'id': e.get('id'),
                'name': e.get('name'),
                'shortName': e.get('shortName'),
                'slug': e.get('slug'),
                'country': e.get('country', {}).get('name') if e.get('country') else None,
            })
    return teams

def resolve_team_id(team_name):
    conn = _db()
    cur = conn.execute('SELECT sofa_id FROM team_map WHERE name = ?', (team_name.lower(),))
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0]
    results = search_team(team_name)
    if results:
        team = results[0]
        conn.execute('INSERT OR REPLACE INTO team_map VALUES (?, ?, ?)',
                     (team_name.lower(), team['id'], team.get('slug', '')))
        conn.commit()
        conn.close()
        return team['id']
    conn.close()
    return None

def get_team_info(team_id):
    data = _get(f'/team/{team_id}', cache_minutes=1440)
    return data.get('team') if data else None

def get_team_events(team_id, limit=30, status='finished'):
    """Get finished matches for a team"""
    data = _get(f'/team/{team_id}/events/last/{limit}', cache_minutes=30)
    if not data or 'events' not in data:
        return []
    events = data['events']
    if status == 'finished':
        events = [e for e in events if e.get('status', {}).get('type') == 'finished']
    return events

def get_team_upcoming(team_id, limit=5):
    data = _get(f'/team/{team_id}/events/next/{limit}', cache_minutes=60)
    if not data or 'events' not in data:
        return []
    return data['events']

def get_match_detail(match_id):
    data = _get(f'/match/{match_id}', cache_minutes=30)
    return data

def get_match_statistics(match_id):
    data = _get(f'/match/{match_id}/statistics', cache_minutes=1440)
    return data

def get_match_lineups(match_id):
    data = _get(f'/match/{match_id}/lineups', cache_minutes=1440)
    return data

def get_match_h2h(match_id):
    data = _get(f'/match/{match_id}/h2h', cache_minutes=1440)
    return data

def get_standings(tournament_id, season_id):
    data = _get(f'/unique-tournament/{tournament_id}/season/{season_id}/standings/total', cache_minutes=60)
    return data

def extract_team_stats(events, team_id):
    """Extract form, goals scored, goals conceded from match events"""
    form = []
    total_gs = total_gc = 0
    match_count = 0
    for e in events:
        home_id = e.get('homeTeam', {}).get('id')
        away_id = e.get('awayTeam', {}).get('id')
        home_score = e.get('homeScore', {}).get('display', 0)
        away_score = e.get('awayScore', {}).get('display', 0)
        if team_id == home_id:
            gs, gc = home_score, away_score
            won = home_score > away_score
            drew = home_score == away_score
        elif team_id == away_id:
            gs, gc = away_score, home_score
            won = away_score > home_score
            drew = away_score == home_score
        else:
            continue
        total_gs += gs
        total_gc += gc
        match_count += 1
        if won:
            form.append('W')
        elif drew:
            form.append('D')
        else:
            form.append('L')
    return {
        'form': ''.join(form[:10]) if form else '',
        'form_rating': (form.count('W') * 3 + form.count('D')) / max(len(form) * 3, 1) * 100,
        'avg_gs': total_gs / max(match_count, 1),
        'avg_gc': total_gc / max(match_count, 1),
        'matches_played': match_count,
        'total_gs': total_gs,
        'total_gc': total_gc,
    }

def get_live_team_data_full(team_name):
    """Complete replacement for get_live_team_data() — Sofascore only"""
    team_id = resolve_team_id(team_name)
    if not team_id:
        return None
    info = get_team_info(team_id)
    events = get_team_events(team_id, limit=30)
    stats = extract_team_stats(events, team_id)
    return {
        'team_id': team_id,
        'name': info.get('name', team_name) if info else team_name,
        'country': info.get('country', {}).get('name') if info and info.get('country') else None,
        'form': stats['form'],
        'form_rating': stats['form_rating'],
        'avg_goals_scored': stats['avg_gs'],
        'avg_goals_conceded': stats['avg_gc'],
        'total_goals_scored': stats['total_gs'],
        'total_goals_conceded': stats['total_gc'],
        'matches_played': stats['matches_played'],
        'events': events,
        'source': 'sofascore',
    }

def get_h2h_data_full(team1_name, team2_name, limit=20):
    """Get H2H via resolving match IDs for both teams"""
    id1 = resolve_team_id(team1_name)
    id2 = resolve_team_id(team2_name)
    if not id1 or not id2:
        return None
    events1 = get_team_events(id1, limit=50)
    events2 = get_team_events(id2, limit=50)
    id2_set = {e.get('id') for e in events2}
    common = [e for e in events1 if e.get('id') in id2_set]
    common = sorted(common, key=lambda e: e.get('startTimestamp', 0), reverse=True)[:limit]
    h2h_data = []
    for e in common:
        home_id = e.get('homeTeam', {}).get('id')
        home_score = e.get('homeScore', {}).get('display', 0)
        away_score = e.get('awayScore', {}).get('display', 0)
        if home_id == id1:
            h2h_data.append({'home': team1_name, 'away': team2_name,
                             'home_score': home_score, 'away_score': away_score,
                             'date': e.get('startTimestamp', 0),
                             'winner': 'home' if home_score > away_score else ('away' if away_score > home_score else 'draw')})
        else:
            h2h_data.append({'home': team2_name, 'away': team1_name,
                             'home_score': away_score, 'away_score': home_score,
                             'date': e.get('startTimestamp', 0),
                             'winner': 'away' if home_score > away_score else ('home' if away_score > home_score else 'draw')})
    return h2h_data

def warmup_all_teams(team_names):
    """Pre-resolve all team names to Sofascore IDs (run once at startup)"""
    conn = _db()
    found = 0
    for name in team_names:
        cur = conn.execute('SELECT sofa_id FROM team_map WHERE name = ?', (name.lower(),))
        if cur.fetchone():
            found += 1
            continue
        results = search_team(name)
        if results:
            team = results[0]
            conn.execute('INSERT OR REPLACE INTO team_map VALUES (?, ?, ?)',
                         (name.lower(), team['id'], team.get('slug', '')))
            found += 1
        time.sleep(0.35)
    conn.commit()
    conn.close()
    return found
