"""Wikipedia-based football data scraper — unlimited, no API key"""
import requests, re, time, os, sqlite3, json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

WIKI_BASE = 'https://en.wikipedia.org'
CACHE_DB = os.path.join(os.path.dirname(__file__), 'wikipedia.db')
_cache = {}
_last_req = 0

LEAGUE_PAGES = {
    'Premier League': '/wiki/2025%E2%80%9326_Premier_League',
    'La Liga': '/wiki/2025%E2%80%9326_La_Liga',
    'Bundesliga': '/wiki/2025%E2%80%9326_Bundesliga',
    'Serie A': '/wiki/2025%E2%80%9326_Serie_A',
    'Ligue 1': '/wiki/2025%E2%80%9326_Ligue_1',
    'Eredivisie': '/wiki/2025%E2%80%9326_Eredivisie',
    'World Cup 2026': '/wiki/2026_FIFA_World_Cup',
}

MONTH_MAP = {
    'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
    'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12,
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
}

def _get(url, cache_minutes=1440):
    global _last_req
    if url in _cache:
        if time.time() - _cache[url]['time'] < cache_minutes * 60:
            return _cache[url]['data']
    now = time.time()
    if now - _last_req < 0.5:
        time.sleep(0.5 - (now - _last_req))
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        _last_req = time.time()
        if r.status_code == 200:
            _cache[url] = {'data': r.text, 'time': time.time()}
            return r.text
    except Exception:
        pass
    return None

def _parse_score(cell):
    text = cell.get_text(strip=True)
    m = re.search(r'(\d+)\s*[–\-—]\s*(\d+)', text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None

def _parse_date(text):
    text = re.sub(r'\[\d+\]', '', text).strip()
    parts = text.split()
    if len(parts) >= 3 and parts[0].isdigit() and parts[1] in MONTH_MAP and parts[2].isdigit():
        return f'{parts[2]}-{MONTH_MAP[parts[1]]:02d}-{int(parts[0]):02d}'
    return text

def get_league_matches(league_name, limit=100):
    path = LEAGUE_PAGES.get(league_name)
    if not path:
        return []
    html = _get(WIKI_BASE + path)
    if not html:
        return []
    soup = BeautifulSoup(html, 'lxml')
    matches = []
    # Find match result tables
    tables = soup.find_all('table', class_='wikitable')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:
                home = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                score_cell = cells[2] if len(cells) > 2 else None
                away = cells[3].get_text(strip=True) if len(cells) > 3 else ''
                date_cell = cells[0] if len(cells) > 0 else None
                if score_cell:
                    h, a = _parse_score(score_cell)
                    if h is not None:
                        date_str = date_cell.get_text(strip=True) if date_cell else ''
                        matches.append({
                            'home': home.replace('\n', ' ').strip(),
                            'away': away.replace('\n', ' ').strip(),
                            'home_score': h,
                            'away_score': a,
                            'date': _parse_date(date_str),
                        })
        if len(matches) >= limit:
            break
    # Also check for schedule tables (different format)
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 5 and not matches:
                continue
            if len(cells) >= 5:
                text = row.get_text(strip=True)
                score_match = re.search(r'(\d+)\s*[–\-—]\s*(\d+)', text)
                if score_match:
                    all_text = [c.get_text(strip=True) for c in cells]
                    combined = ' '.join(all_text)
                    teams = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', combined)
                    if len(teams) >= 2:
                        h = int(score_match.group(1))
                        a = int(score_match.group(2))
                        if h != a or h > 0 or a > 0:
                            matches.append({
                                'home': teams[0],
                                'away': teams[-1],
                                'home_score': h,
                                'away_score': a,
                                'date': '',
                            })
        if len(matches) >= limit:
            break
    return matches[:limit]

def get_league_standings(league_name):
    path = LEAGUE_PAGES.get(league_name)
    if not path:
        return []
    html = _get(WIKI_BASE + path)
    if not html:
        return []
    soup = BeautifulSoup(html, 'lxml')
    standings = []
    tables = soup.find_all('table', class_='wikitable')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 10:
                pos = cells[0].get_text(strip=True)
                team = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                pts = cells[-1].get_text(strip=True) if len(cells) > 0 else ''
                if pos.isdigit() and team and pts.isdigit():
                    standings.append({
                        'position': int(pos),
                        'team': team.replace('\n', ' ').strip(),
                        'played': cells[2].get_text(strip=True) if len(cells) > 2 else '0',
                        'won': cells[3].get_text(strip=True) if len(cells) > 3 else '0',
                        'drawn': cells[4].get_text(strip=True) if len(cells) > 4 else '0',
                        'lost': cells[5].get_text(strip=True) if len(cells) > 5 else '0',
                        'gf': cells[6].get_text(strip=True) if len(cells) > 6 else '0',
                        'ga': cells[7].get_text(strip=True) if len(cells) > 7 else '0',
                        'gd': cells[8].get_text(strip=True) if len(cells) > 8 else '0',
                        'points': int(pts),
                    })
        if standings:
            break
    return standings

def get_team_matches(team_name, league_name=None):
    """Get match results for a team from Wikipedia"""
    leagues = [league_name] if league_name else list(LEAGUE_PAGES.keys())
    all_matches = []
    for lg in leagues:
        matches = get_league_matches(lg)
        for m in matches:
            if team_name.lower() in m['home'].lower() or team_name.lower() in m['away'].lower():
                all_matches.append(m)
    return all_matches

def get_h2h(team1, team2, league_name=None):
    matches = get_team_matches(team1, league_name)
    h2h = []
    for m in matches:
        if team2.lower() in m['home'].lower() or team2.lower() in m['away'].lower():
            if team1.lower() in m['home'].lower() or team1.lower() in m['away'].lower():
                h2h.append(m)
    return h2h

def get_wc2026_group_matches():
    """Extract World Cup 2026 group stage matches from Wikipedia"""
    html = _get(WIKI_BASE + '/wiki/2026_FIFA_World_Cup')
    if not html:
        return []
    soup = BeautifulSoup(html, 'lxml')
    matches = []
    # Group stage tables: each group has a wikitable with match rows
    tables = soup.find_all('table', class_='wikitable')
    current_group = None
    for table in tables:
        caption = table.find('caption')
        if caption:
            cap_text = caption.get_text(strip=True)
            gm = re.search(r'Group\s+([A-Z])', cap_text)
            if gm:
                current_group = gm.group(1)
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 4:
                # Try different formats
                row_text = row.get_text(strip=True)
                score_match = re.search(r'(\d+)\s*[–\-—]\s*(\d+)', row_text)
                if score_match:
                    texts = [c.get_text(strip=True) for c in cells]
                    # Find team names (non-numeric, non-date text)
                    teams_found = []
                    for t in texts:
                        if t and not t.isdigit() and not re.match(r'^\d+$', t):
                            is_date = bool(re.match(r'^\d+\s+\w+', t))
                            if not is_date and not t.startswith('v') and t not in ('H', 'A', 'N'):
                                teams_found.append(t)
                    if len(teams_found) >= 2:
                        h = int(score_match.group(1))
                        a = int(score_match.group(2))
                        matches.append({
                            'home': teams_found[0],
                            'away': teams_found[-1],
                            'home_score': h,
                            'away_score': a,
                            'group': current_group,
                        })
    return matches
