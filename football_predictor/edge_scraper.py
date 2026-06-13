"""Edge WebDriver scraper for Flashscore — unlimited team + match data"""
import time, re, os, json, sqlite3, threading
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from bs4 import BeautifulSoup

EDGE_PATH = r'C:\Program Files (x86)\Microsoft\EdgeCore\149.0.4022.62\msedge.exe'
SCRAPE_DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

_driver = None
_last_use = 0
_driver_lock = threading.Lock()

FLASH_ID = {
    'England': 'j9N9ZNFA', 'Spain': 'bLyo6mco', 'Brazil': 'I9l9aqLq',
    'Argentina': 'f9OppQjp', 'Mexico': 'o6ihcnkd', 'South Africa': 'w2ijyvlr',
    'South Korea': 'K6Gs7P6G', 'Czech Republic': '6LHwBDGU',
    'Morocco': 'IDKYO3R8', 'Portugal': '7E4s4E4s', 'France': '5TR5TR5T',
    'Germany': 'ptQide1O', 'Italy': '8R8R8R8R', 'Netherlands': 'WYintcWb',
    'Belgium': 'GbB957na', 'Croatia': '9S9S9S9S', 'Japan': 'ULXPdOUj',
    'Saudi Arabia': 'biSY8ox4', 'Iran': 'xrRx85iA', 'Australia': 'xSrf6qMM',
    'USA': 'fuitL4CF', 'Canada': 'x4toKORL', 'Nigeria': 'QqZVYk95',
    'Senegal': 'rHJ2vy1B', 'Ghana': 'bejDn7NN', 'Egypt': 'QqZVYk95',
    'Paraguay': 'YaNlqp6j', 'Switzerland': 'rHJ2vy1B', 'Sweden': 'OQyqbHWB',
    'Tunisia': 'QqZVYk95', 'Ecuador': '8tbm8Tri', 'Uruguay': 'xMk44orG',
    'Qatar': 'zqzHL77i', 'Cape Verde': 'MocyWdm7', 'Bosnia': 'fqe7WYTr',
    'Haiti': 'nk4v10Z1', 'Scotland': 'fZRU25WH', 'Curacao': 'bLLGpOkQ',
    'Turkey': 'QeijuHo5', 'Ivory Coast': 'G2FRjBgn', 'New Zealand': 'rLctHkpU',
}

def _init_db():
    conn = sqlite3.connect(SCRAPE_DB, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS cache (url TEXT PRIMARY KEY, data TEXT, updated REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS team_map (name TEXT PRIMARY KEY, team_id TEXT)')
    conn.commit()
    conn.close()

_init_db()

def _driver_get():
    global _driver, _last_use
    with _driver_lock:
        now = time.time()
        if _driver is None or (now - _last_use) > 120:
            if _driver:
                try: _driver.quit()
                except: pass
            opts = Options()
            opts.binary_location = EDGE_PATH
            opts.add_argument('--headless=new')
            opts.add_argument('--no-sandbox')
            opts.add_argument('--disable-gpu')
            opts.add_argument('--window-size=1920,1080')
            opts.add_argument('--disable-blink-features=AutomationControlled')
            opts.add_experimental_option('excludeSwitches', ['enable-automation'])
            opts.add_experimental_option('useAutomationExtension', False)
            _driver = webdriver.Edge(options=opts)
        _last_use = now
        return _driver

def _cache_get(url, max_age=3600):
    try:
        conn = sqlite3.connect(SCRAPE_DB, timeout=3)
        cur = conn.execute('SELECT data, updated FROM cache WHERE url = ?', (url,))
        row = cur.fetchone()
        conn.close()
        if row and (time.time() - row[1]) < max_age:
            return json.loads(row[0])
    except: pass
    return None

def _cache_set(url, data):
    try:
        conn = sqlite3.connect(SCRAPE_DB, timeout=3)
        conn.execute('INSERT OR REPLACE INTO cache VALUES (?, ?, ?)',
                     (url, json.dumps(data, default=str), time.time()))
        conn.commit()
        conn.close()
    except: pass

def _page(url, cache_min=60):
    c = _cache_get(url, cache_min * 60)
    if c: return c
    try:
        d = _driver_get()
        d.get(url)
        time.sleep(4)
        h = d.page_source
        _cache_set(url, h)
        return h
    except: return None

SOFASCORE_SLUGS = {
    'England': 'england', 'Spain': 'spain', 'Brazil': 'brazil', 'Argentina': 'argentina',
    'Mexico': 'mexico', 'South Korea': 'south-korea', 'Portugal': 'portugal',
    'France': 'france', 'Germany': 'germany', 'Italy': 'italy', 'Netherlands': 'netherlands',
    'Belgium': 'belgium', 'Croatia': 'croatia', 'Switzerland': 'switzerland',
    'Sweden': 'sweden', 'Denmark': 'denmark', 'Poland': 'poland', 'Austria': 'austria',
    'Serbia': 'serbia', 'Ukraine': 'ukraine', 'Japan': 'japan', 'Saudi Arabia': 'saudi-arabia',
    'Iran': 'iran', 'Australia': 'australia', 'USA': 'usa', 'Canada': 'canada',
    'Nigeria': 'nigeria', 'Senegal': 'senegal', 'Ghana': 'ghana', 'Egypt': 'egypt',
    'Paraguay': 'paraguay', 'Ecuador': 'ecuador', 'Uruguay': 'uruguay', 'Colombia': 'colombia',
    'Chile': 'chile', 'Morocco': 'morocco', 'Algeria': 'algeria', 'Tunisia': 'tunisia',
    'Ivory Coast': 'cote-d-ivoire', 'Cameroon': 'cameroon', 'Burkina Faso': 'burkina-faso',
    'South Africa': 'south-africa', 'New Zealand': 'new-zealand', 'Scotland': 'scotland',
    'Turkey': 'turkiye', 'Czech Republic': 'czech-republic', 'Qatar': 'qatar',
    'Jamaica': 'jamaica', 'Costa Rica': 'costa-rica', 'Honduras': 'honduras',
}
SOFASCORE_COUNTRY_ID = {
    'England': 44, 'Spain': 49, 'Brazil': 28, 'Argentina': 26, 'Mexico': 129,
    'Portugal': 43, 'France': 47, 'Germany': 41, 'Italy': 42,
    'Netherlands': 45, 'Belgium': 46, 'Croatia': 38, 'Switzerland': 48,
    'Japan': 93, 'South Korea': 112, 'Australia': 23,
    'USA': 237, 'Canada': 31, 'Nigeria': 138, 'Senegal': 176,
    'Egypt': 56, 'Morocco': 133, 'Algeria': 22,
}

SOFASCORE_API_BASE = 'https://api.sofascore.com/api/v1'

def _sofascore_via_edge(path):
    """Fetch Sofascore API data via __NEXT_DATA__ extraction (bypasses Cloudflare)"""
    try:
        conn = sqlite3.connect(SCRAPE_DB, timeout=3)
        cur = conn.execute('SELECT data, updated FROM cache WHERE url = ?', (f'sofa_edge:{path}',))
        row = cur.fetchone()
        conn.close()
        if row and (time.time() - row[1]) < 3600:
            return json.loads(row[0])
    except: pass
    d = _driver_get()
    try:
        # Extract API path from the full path
        api_path = path
        # Build a direct page URL based on path type
        page_url = 'https://www.sofascore.com/'
        if '/team/' in path and '/events/' in path:
            parts = path.split('/')
            team_id = parts[2]
            page_url = f'https://www.sofascore.com/team/football/{team_id}'
        elif '/team/' in path:
            parts = path.split('/')
            team_id = parts[2]
            page_url = f'https://www.sofascore.com/team/football/{team_id}'
        elif '/match/' in path:
            parts = path.split('/')
            match_id = parts[2]
            page_url = f'https://www.sofascore.com/match/{match_id}'
        elif '/search/' in path:
            q = path.split('q=')[-1] if 'q=' in path else ''
            page_url = f'https://www.sofascore.com/search?q={q}'
        d.get(page_url)
        time.sleep(5)
        html = d.page_source
        # Extract __NEXT_DATA__ (Next.js embedded JSON)
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            import json
            data = json.loads(match.group(1))
            props = data.get('props', {}).get('pageProps', {})
            result = props
            _cache_set(f'sofa_edge:{path}', result)
            return result
        # Fallback: try __INITIAL_STATE__
        state = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
        if state:
            import json
            result = json.loads(state.group(1))
            _cache_set(f'sofa_edge:{path}', result)
            return result
    except: pass
    return None

def get_sofascore_team_form(team_name):
    """Get team form from Sofascore via __NEXT_DATA__ extraction (no API calls, no 403)"""
    try:
        # Try to find team via search page
        search = _sofascore_via_edge(f'/search/teams?q={team_name.replace(" ", "%20")}')
        team_id = None
        if search:
            # Try to extract from pageProps
            teams_data = search.get('teams', search.get('searchResults', search))
            if isinstance(teams_data, list):
                for r in teams_data:
                    if isinstance(r, dict):
                        name = r.get('name', r.get('teamName', '')).lower()
                        if team_name.lower() in name:
                            team_id = r.get('id')
                            break
        # If we couldn't find team_id from search, try direct team page by slug
        if not team_id:
            slug = team_name.lower().replace(' ', '-')
            team_page = _sofascore_via_edge(f'/team/{slug}')
            if team_page:
                team_data = team_page.get('team', team_page)
                if isinstance(team_data, dict):
                    team_id = team_data.get('id')
        if not team_id:
            return None
        # Get events from team page
        events_data = _sofascore_via_edge(f'/team/{team_id}/events/last/30')
        if not events_data:
            return None
        # Try to extract events from pageProps
        events = events_data.get('events', events_data.get('teamEvents', []))
        if not isinstance(events, list):
            return None
        matches = []
        for e in events:
            if not isinstance(e, dict):
                continue
            status = e.get('status', {})
            if isinstance(status, dict) and status.get('type') != 'finished':
                continue
            home_team = (e.get('homeTeam') or {}).get('name', '')
            away_team = (e.get('awayTeam') or {}).get('name', '')
            home_score = (e.get('homeScore') or {}).get('display', 0)
            away_score = (e.get('awayScore') or {}).get('display', 0)
            if home_team and away_team:
                matches.append({'home': home_team, 'away': away_team, 'hs': home_score, 'as': away_score})
        if not matches:
            return None
        matches = matches[-15:]
        wins = draws = losses = gf = ga = 0
        tl = team_name.lower()
        for m in matches:
            if tl in m['home'].lower():
                if m['hs'] > m['as']: wins += 1
                elif m['hs'] == m['as']: draws += 1
                else: losses += 1
                gf += m['hs']; ga += m['as']
            elif tl in m['away'].lower():
                if m['as'] > m['hs']: wins += 1
                elif m['as'] == m['hs']: draws += 1
                else: losses += 1
                gf += m['as']; ga += m['hs']
        n = max(len(matches), 1)
        return {
            'wins': wins, 'draws': draws, 'losses': losses,
            'gf': gf, 'ga': ga, 'matches': len(matches),
            'form_rating': round((wins * 3 + draws) / (n * 3) * 100),
            'avg_gs': round(gf / n, 2), 'avg_gc': round(ga / n, 2),
            'source': 'sofascore_edge'
        }
    except:
        return None

def close():
    global _driver
    with _driver_lock:
        if _driver:
            try: _driver.quit()
            except: pass
            _driver = None

def _id(team):
    """Get Flashscore team ID"""
    try:
        conn = sqlite3.connect(SCRAPE_DB, timeout=3)
        cur = conn.execute('SELECT team_id FROM team_map WHERE name = ?', (team.lower(),))
        row = cur.fetchone()
        conn.close()
        if row: return row[0]
    except: pass
    return FLASH_ID.get(team)

def _save_id(team, tid):
    try:
        conn = sqlite3.connect(SCRAPE_DB, timeout=3)
        conn.execute('INSERT OR REPLACE INTO team_map VALUES (?, ?)', (team.lower(), tid))
        conn.commit()
        conn.close()
    except: pass

def get_team_form(team_name):
    """Extract team form from Flashscore team page via score spans"""
    tid = _id(team_name)
    if not tid:
        return None
    slug = team_name.lower().replace(' ', '-')
    html = _page(f'https://www.flashscore.com/team/{slug}/{tid}/', 30)
    if not html:
        return None
    soup = BeautifulSoup(html, 'lxml')
    score_spans_home = [s for s in soup.find_all('span') if any('event__score--home' in c for c in s.get('class', []))]
    score_spans_away = [s for s in soup.find_all('span') if any('event__score--away' in c for c in s.get('class', []))]
    # Pair up score spans with team names by walking up to shared parent
    matches = []
    used = set()
    for sh, sa in zip(score_spans_home, score_spans_away):
        sh_text = sh.get_text(strip=True)
        sa_text = sa.get_text(strip=True)
        if not (sh_text.isdigit() and sa_text.isdigit()):
            continue
        # Find nearest team name divs above these spans
        parent = sh.parent
        for _ in range(10):
            home_found = parent.find('div', class_=re.compile(r'homeParticipant'))
            away_found = parent.find('div', class_=re.compile(r'awayParticipant'))
            if home_found and away_found:
                ht = home_found.get_text(strip=True)
                at = away_found.get_text(strip=True)
                key = (ht, at, sh_text, sa_text)
                if key not in used:
                    used.add(key)
                    matches.append({'home': ht, 'away': at, 'hs': int(sh_text), 'as': int(sa_text)})
                break
            parent = parent.parent if parent.parent != parent else None
            if parent is None:
                break
    if not matches:
        return None
    # Remove duplicate matches by (home, away, hs, as)
    unique = []
    seen = set()
    for m in matches:
        key = (m['home'], m['away'], m['hs'], m['as'])
        if key not in seen:
            seen.add(key)
            unique.append(m)
    matches = unique[-15:]
    wins = draws = losses = gf = ga = 0
    for m in matches:
        if team_name.lower() in m['home'].lower():
            if m['hs'] > m['as']: wins += 1
            elif m['hs'] == m['as']: draws += 1
            else: losses += 1
            gf += m['hs']; ga += m['as']
        elif team_name.lower() in m['away'].lower():
            if m['as'] > m['hs']: wins += 1
            elif m['as'] == m['hs']: draws += 1
            else: losses += 1
            gf += m['as']; ga += m['hs']
    n = max(len(matches), 1)
    return {
        'wins': wins, 'draws': draws, 'losses': losses,
        'gf': gf, 'ga': ga, 'matches': len(matches),
        'form_rating': round((wins * 3 + draws) / (n * 3) * 100),
        'avg_gs': round(gf / n, 2), 'avg_gc': round(ga / n, 2),
        'source': 'flashscore'
    }

def get_live_matches():
    """Get all live/upcoming matches from Flashscore"""
    html = _page('https://www.flashscore.com/football/', 15)
    if not html: return []
    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text(separator='\n')
    lines = text.split('\n')
    matches = []
    i = 0
    while i < len(lines) - 2:
        l = lines[i].strip()
        if re.match(r'^\d+$', l) and i+1 < len(lines) and re.match(r'^\d+$', lines[i+1].strip()):
            t1 = lines[i-1].strip() if i-1 >= 0 else ''
            t2 = lines[i+2].strip() if i+2 < len(lines) else ''
            if t1 and t2 and not re.match(r'^\d+$', t1) and not re.match(r'^\d+$', t2):
                matches.append({'home': t1, 'away': t2, 'hs': int(l), 'as': int(lines[i+1].strip())})
                i += 3; continue
        i += 1
    return matches

def search_team_id(team_name):
    """Search for team ID on Flashscore from football page"""
    html = _page('https://www.flashscore.com/football/', 60)
    if not html: return None
    links = re.findall(r'/team/([^/]+)/([a-zA-Z0-9]+)/', html)
    for slug, tid in links:
        if team_name.lower().replace(' ', '-') == slug.lower():
            _save_id(team_name, tid)
            return tid
    # Fuzzy match
    for slug, tid in links:
        if team_name.lower()[:3] in slug.lower() or slug.lower() in team_name.lower():
            _save_id(team_name, tid)
            return tid
    return None
