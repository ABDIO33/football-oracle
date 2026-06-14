"""Playwright-based Sofascore scraper - replaces Selenium/Edge WebDriver"""
import os, json, re, time, sqlite3
from datetime import datetime, timedelta

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

BASE_WEB = 'https://www.sofascore.com'
SCRAPE_DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

_playwright = None
_browser = None
_last_use = 0

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'

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

def _init_db():
    conn = sqlite3.connect(SCRAPE_DB, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS cache (url TEXT PRIMARY KEY, data TEXT, updated REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS team_map (name TEXT PRIMARY KEY, team_id TEXT, slug TEXT)')
    conn.commit()
    conn.close()

_init_db()

def _get_browser():
    global _playwright, _browser, _last_use
    now = time.time()
    if _browser is None or (now - _last_use) > 120:
        close()
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
    _last_use = now
    return _browser

def _new_page():
    browser = _get_browser()
    page = browser.new_page(user_agent=UA, viewport={'width': 1920, 'height': 1080})
    return page

def _cache_get(url, max_age=3600):
    try:
        conn = sqlite3.connect(SCRAPE_DB, timeout=3)
        cur = conn.execute('SELECT data, updated FROM cache WHERE url = ?', (url,))
        row = cur.fetchone()
        conn.close()
        if row and (time.time() - row[1]) < max_age:
            return json.loads(row[0])
    except:
        pass
    return None

def _cache_set(url, data):
    try:
        conn = sqlite3.connect(SCRAPE_DB, timeout=3)
        conn.execute('INSERT OR REPLACE INTO cache VALUES (?, ?, ?)',
                     (url, json.dumps(data, default=str), time.time()))
        conn.commit()
        conn.close()
    except:
        pass

def _extract_next(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    m2 = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
    if m2:
        return json.loads(m2.group(1))
    return None

def fetch_page(url, cache_min=60):
    cache_url = f'playwright:{url}'
    cached = _cache_get(cache_url, cache_min * 60)
    if cached:
        return cached
    page = _new_page()
    try:
        page.goto(url, wait_until='load', timeout=30000)
        page.wait_for_timeout(3000)
        html = page.content()
        page.close()
        _cache_set(cache_url, html)
        return html
    except Exception as e:
        try:
            page.close()
        except:
            pass
        return None

def search_team(team_name):
    """Search for a team on Sofascore and return team info."""
    slug = team_name.lower().replace(' ', '-')
    url = f'{BASE_WEB}/search?q={team_name.replace(" ", "%20")}'
    page = _new_page()
    try:
        page.goto(url, wait_until='load', timeout=30000)
        page.wait_for_timeout(5000)
        html = page.content()
        data = _extract_next(html)
        page.close()
        if data:
            props = data.get('props', {}).get('pageProps', {})
            teams = props.get('teams') or props.get('searchResults') or []
            if isinstance(teams, list):
                for t in teams:
                    if isinstance(t, dict):
                        name = t.get('name', '')
                        if team_name.lower() in name.lower():
                            return {
                                'id': t.get('id'),
                                'name': name,
                                'slug': t.get('slug', slug),
                            }
        # Fallback: try from URL pattern
        return resolve_team_slug(team_name)
    except:
        try: page.close()
        except: pass
        return resolve_team_slug(team_name)

def resolve_team_slug(team_name):
    """Get team slug from name using mapping or direct page."""
    slug = team_name.lower().replace(' ', '-')
    url = f'{BASE_WEB}/football/team/{slug}'
    page = _new_page()
    try:
        page.goto(url, wait_until='load', timeout=30000)
        page.wait_for_timeout(3000)
        html = page.content()
        data = _extract_next(html)
        page.close()
        if data:
            props = data.get('props', {}).get('pageProps', {})
            td = props.get('teamDetails', {})
            if td.get('name'):
                return {
                    'id': td.get('id'),
                    'name': td.get('name'),
                    'slug': td.get('slug', slug),
                }
    except:
        try: page.close()
        except: pass
    return None

def get_team_form(team_name):
    """Get team form data from Sofascore via Playwright."""
    # Try resolve team
    team = resolve_team_slug(team_name)
    if not team:
        team = search_team(team_name)
    if not team:
        return None

    team_id = team.get('id')
    if not team_id:
        return None

    url = f'{BASE_WEB}/football/team/{team["slug"]}/{team_id}'
    html = fetch_page(url, cache_min=30)
    if not html:
        return None

    data = _extract_next(html)
    if not data:
        return None

    props = data.get('props', {}).get('pageProps', {})
    td = props.get('teamDetails', {})
    if not td:
        return None

    # Try to get events from the page
    events = props.get('events') or props.get('teamEvents') or []
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
        'source': 'sofascore_playwright'
    }

def close():
    global _playwright, _browser
    try:
        if _browser:
            _browser.close()
    except:
        pass
    try:
        if _playwright:
            _playwright.stop()
    except:
        pass
    _browser = None
    _playwright = None

if __name__ == '__main__':
    import sys
    team = sys.argv[1] if len(sys.argv) > 1 else 'Spain'
    print(f"Testing team: {team}")
    info = resolve_team_slug(team)
    print(f"Resolved: {info}")
    if info:
        form = get_team_form(team)
        print(f"Form: {form}")
    close()
