"""FotMob scraper — parity with sofascore_scraper.py (no Selenium, no API keys)"""
import json, re, sqlite3, os, time, urllib.parse
from datetime import datetime, timezone
import urllib.request, urllib.error

DB_PATH = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
BASE = 'https://www.fotmob.com'
HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

LEAGUES = {47: 'EPL', 53: 'LaLiga', 54: 'Bundesliga', 55: 'SerieA', 74: 'Ligue1'}
L_REV = {v: k for k, v in LEAGUES.items()}


# ── DB ──────────────────────────────────────────────────────────────────
def _db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.execute('''CREATE TABLE IF NOT EXISTS fotmob_team_map (
        team_name TEXT, team_id INTEGER, league_id INTEGER,
        PRIMARY KEY (team_name, league_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS fotmob_match_cache (
        id INTEGER PRIMARY KEY, slug TEXT, home_name TEXT, away_name TEXT,
        home_id INTEGER, away_id INTEGER, home_score INTEGER, away_score INTEGER,
        data TEXT, scraped_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS fotmob_league_cache (
        league_id INTEGER, season TEXT, data TEXT, scraped_at TEXT,
        PRIMARY KEY (league_id, season))''')
    c.commit()
    return c


# ── HTTP helpers ────────────────────────────────────────────────────────
def _fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=15) as r:
        return r.read().decode('utf-8')


def _nd(html):
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    return json.loads(m.group(1)) if m else None


def _delay():
    time.sleep(0.35)


# ── League ──────────────────────────────────────────────────────────────
def get_league_data(league_id, season=None):
    c = _db()
    s = season or (datetime.now(timezone.utc).strftime('%Y') + '/' +
                   str(int(datetime.now(timezone.utc).strftime('%Y')) + 1))
    row = c.execute('SELECT data FROM fotmob_league_cache WHERE league_id=? AND season=?',
                    (league_id, s)).fetchone()
    if row:
        c.close()
        return json.loads(row[0])
    html = _fetch(f'{BASE}/leagues/{league_id}')
    d = _nd(html)
    if not d:
        c.close()
        return None
    data = d.get('props', {}).get('pageProps', {})
    c.execute('INSERT OR REPLACE INTO fotmob_league_cache VALUES (?,?,?,?)',
              (league_id, s, json.dumps(data), datetime.now(timezone.utc).isoformat()))
    c.commit()
    c.close()
    return data


def get_league_matches(league_id, season=None):
    data = get_league_data(league_id, season)
    if not data:
        return []
    return data.get('overview', {}).get('leagueOverviewMatches', [])


def get_standings(league_id, season=None):
    data = get_league_data(league_id, season)
    if not data:
        return []
    return data.get('table', [])


# ── Team ────────────────────────────────────────────────────────────────
def search_team(query):
    c = _db()
    rows = c.execute(
        'SELECT team_name, team_id, league_id FROM fotmob_team_map WHERE team_name LIKE ?',
        (f'%{query}%',)).fetchall()
    c.close()
    if rows:
        return [{'name': r[0], 'id': r[1], 'leagueId': r[2]} for r in rows]
    return None


def resolve_team_id(team_name, league=None):
    c = _db()
    lid = L_REV.get(league) if league else None
    if lid:
        row = c.execute('SELECT team_id FROM fotmob_team_map WHERE team_name=? AND league_id=?',
                        (team_name, lid)).fetchone()
        if row:
            c.close()
            return row[0]
    row = c.execute('SELECT team_id FROM fotmob_team_map WHERE team_name=?', (team_name,)).fetchone()
    c.close()
    return row[0] if row else None


def get_team_info(team_id):
    html = _fetch(f'{BASE}/teams/{team_id}')
    nd = _nd(html)
    if not nd:
        return None
    fb = nd.get('props', {}).get('pageProps', {}).get('fallback', {})
    data = fb.get(f'team-{team_id}', {})
    details = data.get('details', {})
    overview = data.get('overview', {})
    return {
        'id': team_id,
        'name': details.get('name', ''),
        'short_name': details.get('shortName', ''),
        'country': details.get('country', ''),
        'venue': overview.get('venue', {}),
        'team_form': overview.get('teamForm', []),
        'last_match': overview.get('lastMatch'),
        'next_match': overview.get('nextMatch'),
    }


def get_team_events(team_id, limit=30, status='finished'):
    html = _fetch(f'{BASE}/teams/{team_id}')
    nd = _nd(html)
    if not nd:
        return []
    fb = nd.get('props', {}).get('pageProps', {}).get('fallback', {})
    data = fb.get(f'team-{team_id}', {})
    overview = data.get('overview', {})
    fixtures = overview.get('overviewFixtures', [])
    if not fixtures:
        matches = overview.get('matches', [])
        if isinstance(matches, list):
            fixtures = matches
        else:
            ov = overview.get('overviewFixtures', {})
            fixtures = ov.get('matches', ov.get('allMatches', []))
    if status == 'finished':
        return [m for m in fixtures if m.get('status', {}).get('finished', False)][:limit]
    else:
        return [m for m in fixtures if not m.get('status', {}).get('finished', False)][:limit]


def get_team_upcoming(team_id, limit=5):
    return get_team_events(team_id, limit=limit, status='upcoming')


def extract_team_stats(events, team_id):
    form_str = ''
    total_gs = total_gc = 0
    n = 0
    for m in events:
        home_id = m.get('home', {}).get('id', m.get('home', {}).get('teamId'))
        away_id = m.get('away', {}).get('id', m.get('away', {}).get('teamId'))
        hs = m.get('home', {}).get('score')
        aws = m.get('away', {}).get('score')
        if hs is None:
            continue
        try:
            hs, aws = int(hs), int(aws)
        except (ValueError, TypeError):
            continue
        is_home = (home_id == team_id)
        if is_home:
            total_gs += hs; total_gc += aws
            form_str += 'W' if hs > aws else ('D' if hs == aws else 'L')
        else:
            total_gs += aws; total_gc += hs
            form_str += 'W' if aws > hs else ('D' if aws == hs else 'L')
        n += 1
    return {
        'form': form_str[-10:] if form_str else '',
        'avg_gs': round(total_gs / n, 2) if n else 0,
        'avg_gc': round(total_gc / n, 2) if n else 0,
        'matches_played': n,
    }


# ── Match ───────────────────────────────────────────────────────────────
def _score_from_events(content):
    events = content.get('matchFacts', {}).get('events', {}).get('events', [])
    if not events:
        return None, None
    hg = sum(1 for e in events if e.get('type') == 'Goal' and e.get('isHome'))
    ag = sum(1 for e in events if e.get('type') == 'Goal' and not e.get('isHome'))
    if hg or ag:
        return hg, ag
    for e in reversed(events):
        ns = e.get('newScore')
        if ns and len(ns) == 2:
            return ns[0], ns[1]
    return None, None


def _extract(content, home_id, away_id):
    stats = {}
    for pn, pd in content.get('stats', {}).get('Periods', {}).items():
        for sg in pd.get('stats', []):
            for s in sg.get('stats', []):
                ss = s.get('stats', [])
                if len(ss) == 2:
                    k = s.get('key', '')
                    if k and k != 'None':
                        stats[f'{pn}_{k}'] = (ss[0], ss[1])
    xg = {}
    for pn, pd in content.get('stats', {}).get('Periods', {}).items():
        for sg in pd.get('stats', []):
            for s in sg.get('stats', []):
                k = s.get('key', '')
                if 'expected_goals' in k or 'xG' in k:
                    ss = s.get('stats', [])
                    if len(ss) == 2:
                        try:
                            xg[f'{pn}_{k}'] = (float(ss[0]) if ss[0] else 0, float(ss[1]) if ss[1] else 0)
                        except:
                            pass
    shots = content.get('shotmap', {}).get('shots', [])
    hxg = hyg = hsh = ash = 0
    for so in shots:
        g = so.get('expectedGoals', 0)
        if so.get('teamId') == home_id:
            hxg += g; hsh += 1
        else:
            hyg += g; ash += 1
    h2h_d = content.get('h2h', {})
    hm = h2h_d.get('matches', [])
    hs_ = h2h_d.get('summary', [])
    if isinstance(hs_, list) and len(hs_) == 3:
        hw, dr, aw = hs_
    else:
        hw = sum(1 for x in hm if x.get('home', {}).get('score', 0) > x.get('away', {}).get('score', 0))
        dr = sum(1 for x in hm if x.get('home', {}).get('score', 0) == x.get('away', {}).get('score', 0))
        aw = len(hm) - hw - dr
    form = []
    for te in content.get('matchFacts', {}).get('teamForm', []):
        form.append([{
            'r': e.get('result'), 'rs': e.get('resultString', ''),
            's': e.get('score', ''), 'd': e.get('date', {}).get('utcTime', ''),
            'ht': e.get('tooltipText', {}).get('homeTeam', ''),
            'at': e.get('tooltipText', {}).get('awayTeam', ''),
            'hs': e.get('tooltipText', {}).get('homeScore', ''),
            'aws': e.get('tooltipText', {}).get('awayScore', ''),
        } for e in te if te])
    lineup = content.get('lineup', {})
    return stats, xg, {'home_xg': hxg, 'away_xg': hyg, 'home_shots': hsh, 'away_shots': ash}, {
        'total': hw + dr + aw, 'home_wins': hw, 'draws': dr, 'away_wins': aw,
        'recent': [{'home': x.get('home', {}).get('name', ''),
                    'away': x.get('away', {}).get('name', ''),
                    'home_score': x.get('home', {}).get('score', ''),
                    'away_score': x.get('away', {}).get('score', ''),
                    'date': x.get('matchDateUTC', ''),
                    'league': x.get('leagueName', x.get('tournament', {}).get('name', ''))}
                   for x in hm[:20]],
    }, form, lineup


def get_match_detail(match_id):
    """Get match detail by numeric ID. Returns None if ID doesn't match."""
    c = _db()
    row = c.execute('SELECT data FROM fotmob_match_cache WHERE id=?', (match_id,)).fetchone()
    if row:
        c.close()
        return json.loads(row[0])
    html = _fetch(f'{BASE}/match/{match_id}')
    nd = _nd(html)
    if not nd:
        c.close()
        return None
    pp = nd.get('props', {}).get('pageProps', {})
    g = pp.get('general', {})
    mid = int(g.get('matchId', 0))
    if mid != match_id:
        c.close()
        return None
    return _save_match(mid, '', pp, c)


def get_match_by_slug(slug):
    c = _db()
    row = c.execute('SELECT data FROM fotmob_match_cache WHERE slug=?', (slug,)).fetchone()
    if row:
        c.close()
        return json.loads(row[0])
    html = _fetch(f'{BASE}{slug}')
    nd = _nd(html)
    if not nd:
        c.close()
        return None
    pp = nd.get('props', {}).get('pageProps', {})
    mid = int(pp.get('general', {}).get('matchId', 0))
    return _save_match(mid, slug, pp, c)


def _save_match(mid, slug, pp, c):
    g = pp.get('general', {})
    content = pp.get('content', {})
    ht = g.get('homeTeam', {}); at = g.get('awayTeam', {})
    home_id = ht.get('id', 0); away_id = at.get('id', 0)
    hs, aws = _score_from_events(content)
    stats, xg, xg_shots, h2h, form, lineup = _extract(content, home_id, away_id)
    md = {
        'id': mid, 'slug': slug,
        'home_team': ht.get('name', ''), 'away_team': at.get('name', ''),
        'home_id': home_id, 'away_id': away_id,
        'home_score': hs, 'away_score': aws,
        'round': g.get('matchRound', ''),
        'league_id': g.get('leagueId', g.get('league', {}).get('id')),
        'league_name': g.get('leagueName', g.get('league', {}).get('name', '')),
        'match_date_utc': g.get('matchTimeUTC', ''),
        'started': g.get('started', False), 'finished': g.get('finished', False),
        'stats': stats, 'xg': xg, 'xg_shots': xg_shots,
        'h2h': h2h, 'form': form, 'lineup': lineup,
    }
    c.execute('INSERT OR REPLACE INTO fotmob_match_cache VALUES (?,?,?,?,?,?,?,?,?,?)',
              (mid, slug, ht.get('name', ''), at.get('name', ''),
               home_id, away_id, hs, aws,
               json.dumps(md), datetime.now(timezone.utc).isoformat()))
    c.commit()
    return md


def get_match_statistics(match_id):
    md = get_match_detail(match_id)
    return md.get('stats') if md else None


def get_match_lineups(match_id):
    md = get_match_detail(match_id)
    return md.get('lineup') if md else None


def get_match_h2h(match_id):
    md = get_match_detail(match_id)
    return md.get('h2h') if md else None


# ── Combo ───────────────────────────────────────────────────────────────
def get_live_team_data_full(team_name, league=None):
    tid = resolve_team_id(team_name, league)
    if not tid and league:
        return None
    if not tid:
        c = _db()
        row = c.execute('SELECT team_id FROM fotmob_team_map WHERE team_name=?', (team_name,)).fetchone()
        tid = row[0] if row else None
        c.close()
    if not tid:
        return None
    info = get_team_info(tid)
    events = get_team_events(tid, limit=30)
    stats = extract_team_stats(events, tid)
    return {'info': info, 'events': events, 'stats': stats}


def get_h2h_data_full(team1_name, team2_name, limit=20):
    t1 = resolve_team_id(team1_name)
    t2 = resolve_team_id(team2_name)
    if not t1 or not t2:
        return None
    c = _db()
    rows = c.execute(
        'SELECT data FROM fotmob_match_cache WHERE (home_id=? AND away_id=?) OR (home_id=? AND away_id=?)',
        (int(t1), int(t2), int(t2), int(t1))).fetchall()
    c.close()
    matches = [json.loads(r[0]) for r in rows]
    if len(matches) >= limit:
        return matches[:limit]
    s1, s2 = str(t1), str(t2)
    league_matches = []
    for lid in LEAGUES:
        for m in get_league_matches(lid):
            hid = str(m.get('home', {}).get('id', ''))
            aid = str(m.get('away', {}).get('id', ''))
            if (hid == s1 and aid == s2) or (hid == s2 and aid == s1):
                league_matches.append({
                    'home': team1_name if hid == s1 else team2_name,
                    'away': team2_name if hid == s1 else team1_name,
                    'home_score': m.get('home', {}).get('score'),
                    'away_score': m.get('away', {}).get('score'),
                    'date': m.get('status', {}).get('utcTime', ''),
                })
    return matches + league_matches


# ── Warmup ──────────────────────────────────────────────────────────────
def warmup_all_teams(team_names, league=None):
    c = _db()
    lid = L_REV.get(league) if league else None
    if lid:
        data = get_league_data(lid)
        if data:
            tbls = data.get('table', [])
            if isinstance(tbls, list):
                for tbl in tbls:
                    all_rows = tbl.get('data', {}).get('table', {}).get('all', [])
                    for row in all_rows:
                        tn = row.get('name', '')
                        ti = row.get('id')
                        if tn and ti:
                            c.execute('INSERT OR IGNORE INTO fotmob_team_map VALUES (?,?,?)',
                                      (tn, ti, lid))
        _delay()
    found = 0
    for name in team_names:
        rows = c.execute('SELECT team_id, league_id FROM fotmob_team_map WHERE team_name=?',
                         (name,)).fetchall()
        if rows:
            found += 1
    c.commit()
    c.close()
    return found


def warmup_cache(league_ids=None):
    for lid in (league_ids or list(LEAGUES.keys())):
        name = LEAGUES.get(lid, '?')
        print(f'  caching league {lid} ({name})…')
        matches = get_league_matches(lid)
        print(f'    {len(matches)} matches')
        _delay()


# ── Test ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('=== FotMob scraper test ===')
    warmup_cache()
    lid = 47
    data = get_league_data(lid)
    tbl = data.get('table', [])
    if isinstance(tbl, list) and tbl:
        all_rows = tbl[0].get('data', {}).get('table', {}).get('all', [])
        c = _db()
        for r in all_rows:
            c.execute('INSERT OR IGNORE INTO fotmob_team_map VALUES (?,?,?)',
                      (r.get('name', ''), r.get('id', ''), lid))
        c.commit()
        c.close()
    print('Team map built')
    match = get_league_matches(47)[0]
    slug = match.get('pageUrl', '').split('#')[0]
    md = get_match_by_slug(slug)
    if md:
        print(f'\nMatch: {md["home_team"]} {md["home_score"]}-{md["away_score"]} {md["away_team"]}')
        print(f'  xG: {md["xg"]}')
        print(f'  xG shots: {md["xg_shots"]}')
        print(f'  H2H: {md["h2h"]["total"]} ({md["h2h"]["home_wins"]}H/{md["h2h"]["draws"]}D/{md["h2h"]["away_wins"]}A)')
        print(f'  Form entries: {len(md["form"])}')
        print(f'  Lineups keys: {list(md["lineup"].keys()) if md["lineup"] else "none"}')
    team = search_team('Liverpool')
    print(f'\nSearch Liverpool: {team}')
    info = get_team_info(8650) if not team else get_team_info(team[0]['id'])
    if info:
        print(f'Team info: {info["name"]} ({info["country"]})')
    events = get_team_events(8650, limit=5)
    print(f'Team events: {len(events)}')
    h2h_full = get_h2h_data_full('Liverpool', 'Manchester City', limit=3)
    print(f'H2H Liverpool vs Man City: {len(h2h_full) if h2h_full else "failed"} matches')
