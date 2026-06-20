"""FlashScore scraper — free REST API via local-ruua.flashscore.ninja"""
import os, sqlite3, json, time, re
from datetime import datetime, timedelta
from curl_cffi import requests

BASE = "https://local-ruua.flashscore.ninja"
XFSIGN = "SW9D1eZo"
NOT_CHR = "\u00ac"
DIV_CHR = "\u00f7"

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

_HEADERS = {
    'x-fsign': XFSIGN,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.flashscore.com/',
    'Accept': '*/*',
}

STAT_IDS = {
    '12': 'possession',
    '34': 'total_shots',
    '13': 'shots_on_target',
    '16': 'corners',
    '23': 'yellow_cards',
    '22': 'red_cards',
    '24': 'fouls',
    '25': 'offsides',
    '26': 'free_kicks',
    '27': 'throwins',
    '28': 'goal_kicks',
    '29': 'saves',
    '30': 'crosses',
    '33': 'shots_off_target',
    '41': 'blocked_shots',
    '46': 'big_chances',
}

def _fetch(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, impersonate="chrome120", headers=_HEADERS, timeout=30)
            if r.status_code == 200 and len(r.content) > 10:
                return r.content
        except Exception as e:
            if i == retries - 1:
                pass
            time.sleep(1.5)
    return None

def _parse_feed(data):
    text = data.decode('utf-8', errors='replace')
    records = text.split('~')
    result = []
    for rec in records:
        if not rec.strip():
            continue
        fields = rec.split(NOT_CHR)
        parsed = {}
        for f in fields:
            if DIV_CHR in f:
                k, v = f.split(DIV_CHR, 1)
                parsed[k.strip()] = v.strip()
            elif f.strip():
                parsed.setdefault('_type', f.strip())
        if parsed:
            result.append(parsed)
    return result

def get_matches(offset=1):
    """Fetch matches. offset=1=today, 2=yesterday, 3=day_before, etc."""
    url = f"{BASE}/1/x/feed/f_1_0_3_en_{offset}"
    data = _fetch(url)
    if not data:
        return []
    records = _parse_feed(data)
    matches = []
    seen = set()
    for rec in records:
        mid = rec.get('AA') or rec.get('AD')
        if mid and mid not in seen and len(mid) > 3:
            seen.add(mid)
            home = rec.get('CX', '')
            away = rec.get('AE') or rec.get('AF', '')
            ts = rec.get('AD', '')
            home_score = rec.get('CR') or rec.get('AX', '')
            away_score = rec.get('CR') or rec.get('BW', '')
            comp = rec.get('ZA', '')
            matches.append({
                'id': mid,
                'home': home,
                'away': away,
                'timestamp': ts,
                'home_score': home_score,
                'away_score': away_score,
                'competition': comp,
            })
    return matches

def parse_stats(records):
    stats = {}
    for rec in records:
        sid = rec.get('SD', '')
        if sid in STAT_IDS:
            sh = rec.get('SH', '0').rstrip('%')
            si = rec.get('SI', '0').rstrip('%')
            try:
                stats[STAT_IDS[sid]] = {'home': float(sh), 'away': float(si)}
            except ValueError:
                pass
    return stats

def get_match_detail(match_id):
    result = {'info': [], 'stats': [], 'lineups': [], 'events': []}
    endpoints = [
        ('info', f"df_sui_1_{match_id}"),
        ('stats', f"df_st_1_{match_id}"),
        ('lineups', f"df_scr_1_{match_id}"),
        ('events', f"df_lc_1_{match_id}"),
    ]
    for key, ep in endpoints:
        data = _fetch(f"{BASE}/1/x/feed/{ep}")
        if data:
            result[key] = parse_stats(_parse_feed(data)) if key == 'stats' else _parse_feed(data)
        time.sleep(0.3)
    return result

def store_yesterday():
    """Fetch yesterday's matches with stats and store in DB."""
    conn = sqlite3.connect(DB, timeout=5)
    conn.execute('''CREATE TABLE IF NOT EXISTS flashscore_matches (
        match_id TEXT PRIMARY KEY,
        home_team TEXT, away_team TEXT,
        home_score TEXT, away_score TEXT,
        competition TEXT, ts TEXT,
        stats_json TEXT, fetched_at TEXT
    )''')
    conn.commit()

    matches = get_matches(offset=2)
    count = 0
    for m in matches:
        detail = get_match_detail(m['id'])
        stats = detail.get('stats', {})
        if not stats:
            continue
        conn.execute('''INSERT OR REPLACE INTO flashscore_matches
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (m['id'], m['home'], m['away'],
              m.get('home_score', ''), m.get('away_score', ''),
              m.get('competition', ''), m.get('timestamp', ''),
              json.dumps(stats, default=str),
              datetime.now().isoformat()))
        count += 1
        if count % 20 == 0:
            conn.commit()
    conn.commit()
    conn.close()
    return count

def get_team_recent_stats(team_name, days=7):
    """Get recent FlashScore stats for a team (last N days)."""
    conn = sqlite3.connect(DB, timeout=5)
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute('''
        SELECT stats_json, home_team, away_team, home_score, away_score, ts
        FROM flashscore_matches
        WHERE (LOWER(home_team) LIKE ? OR LOWER(away_team) LIKE ?)
        AND fetched_at >= ?
        ORDER BY ts DESC LIMIT 10
    ''', (f'%{team_name.lower()}%', f'%{team_name.lower()}%', cutoff)).fetchall()
    conn.close()
    result = []
    for stats_json, home, away, hs, aw, ts in rows:
        stats = json.loads(stats_json) if stats_json else {}
        is_home = team_name.lower() in home.lower()
        result.append({
            'team': team_name,
            'opponent': away if is_home else home,
            'is_home': is_home,
            'goals_for': int(hs) if hs and is_home else (int(aw) if aw else 0),
            'goals_against': int(aw) if aw and is_home else (int(hs) if hs else 0),
            'stats': stats,
            'timestamp': ts,
        })
    return result

if __name__ == '__main__':
    print("[Flash] Storing yesterday's matches...")
    c = store_yesterday()
    print(f"[Flash] Stored {c} matches with stats")
    if c > 0:
        print(f"[Flash] Sample: {get_team_recent_stats('Costa Brava', days=7)[:1]}")
